from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func
import httpx

from database import get_db
from models.transaction import Transaction
from models.account import Account
from schemas.transaction import TransactionCreate

from models.fraud_event import FraudEvent
from dependencies import get_current_user
from models.user import User
from models.fraud_rule import FraudRule
from models.device_log import DeviceLog
from config import runtime_settings

router = APIRouter(
    prefix="/transactions",
    tags=["Transactions"]
)


async def send_webhook(webhook_url: str, payload: dict):
    if not webhook_url:
        return
    try:
        if "http://test/" in webhook_url:
            from main import app
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(webhook_url, json=payload, timeout=5.0)
                print(f"Webhook sent to {webhook_url} (ASGI Test mode), status: {response.status_code}")
        else:
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=payload, timeout=5.0)
                print(f"Webhook sent to {webhook_url}, status code: {response.status_code}")
    except Exception as e:
        print(f"Failed to send webhook to {webhook_url}: {e}")


@router.post("/")
async def create_transaction(
    transaction: TransactionCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):

    if current_user.is_admin:
        query = select(Account).where(Account.id == transaction.account_id)
    else:
        query = select(Account).where(
            Account.id == transaction.account_id,
            Account.user_id == current_user.id
        )

    result = await db.execute(query)

    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=403,
            detail="You do not own this account"
        )

    # 0. Check for sufficient funds
    if account.balance < transaction.amount:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient funds. Required: INR {transaction.amount:.2f}, Available: INR {account.balance:.2f}"
        )

    # 1. Fetch active fraud rules
    rules_query = select(FraudRule).where(FraudRule.is_active == True)
    rules_result = await db.execute(rules_query)
    active_rules = rules_result.scalars().all()

    triggered_rules = []
    risk_score = 0.0
    details = {}

    # Bind parameters to use for executing SQL expressions
    bindings = {
        "account_id": transaction.account_id,
        "amount": transaction.amount,
        "merchant_name": transaction.merchant_name,
        "merchant_category": transaction.merchant_category,
        "city": transaction.city,
        "country": transaction.country,
        "ip_address": transaction.ip_address,
        "device_id": transaction.device_id
    }

    # 2. Evaluate rules dynamically
    for rule in active_rules:
        try:
            stmt = text(rule.sql_expression)
            eval_res = await db.execute(stmt, bindings)
            val = eval_res.scalar()
            
            is_triggered = False
            if isinstance(val, bool):
                is_triggered = val
            elif isinstance(val, (int, float)):
                is_triggered = val > 0
            elif val is not None:
                is_triggered = bool(val)

            if is_triggered:
                triggered_rules.append(rule.code)
                risk_score += rule.weight

                # Generate dynamic details message for known rules
                if rule.code == "VEL-01":
                    hour_query = text("SELECT COUNT(*) FROM transactions WHERE account_id = :account_id AND timestamp >= NOW() - INTERVAL '1 hour'")
                    hour_res = await db.execute(hour_query, {"account_id": transaction.account_id})
                    count = hour_res.scalar() or 0
                    # Add 1 to count because the new transaction is not in DB yet but will be
                    details[rule.code] = f"{count + 1} transactions detected within last hour"
                elif rule.code == "VEL-TEST-01":
                    details[rule.code] = "High transaction amount velocity test triggered"
                elif rule.code == "LOC-01":
                    details[rule.code] = f"Transaction country '{transaction.country}' does not match home country '{account.home_country or ''}'"
                elif rule.code == "THR-01":
                    details[rule.code] = "Transaction amount exceeded INR 50,000 threshold"
                elif rule.code == "BEH-01":
                    details[rule.code] = f"Unusual merchant category: {transaction.merchant_category}"
                elif rule.code == "DEV-01":
                    details[rule.code] = "New device detected for account"
                elif rule.code == "VEL-HIGH-FREQ":
                    freq_query = text("SELECT COUNT(*) FROM transactions WHERE account_id = :account_id AND timestamp >= NOW() - INTERVAL '2 minutes'")
                    freq_res = await db.execute(freq_query, {"account_id": transaction.account_id})
                    count = freq_res.scalar() or 0
                    # Add 1 to count because the new transaction is not in DB yet but will be
                    details[rule.code] = f"{count + 1} high frequency transactions detected in last 2 minutes"
                elif rule.code == "THR-NORM-EXCEED":
                    avg_query = text("SELECT AVG(amount) FROM transactions WHERE account_id = :account_id")
                    avg_res = await db.execute(avg_query, {"account_id": transaction.account_id})
                    avg_amount = avg_res.scalar() or 0.0
                    details[rule.code] = f"Transaction amount INR {transaction.amount} exceeds account average of INR {round(avg_amount, 2)} by over 3x"
                elif rule.code == "BEH-MICRO-TEST":
                    details[rule.code] = "High-value transaction immediately following small micro-test transactions"
                elif rule.code == "LOC-NEW-COUNTRY":
                    details[rule.code] = f"Transaction from a country user has never accessed from: {transaction.country}"
                elif rule.code == "DEV-MULTI-ACCOUNT":
                    details[rule.code] = "Device linked to multiple distinct platform accounts"
                elif rule.code == "REP-AMT":
                    details[rule.code] = f"Repeated transaction of amount INR {transaction.amount} detected in the last 5 minutes"
                else:
                    details[rule.code] = f"Rule '{rule.name}' triggered"
        except Exception as e:
            # Prevent crashing the API if there is a syntax error in a custom rule
            print(f"Error executing rule {rule.code}: {e}")

    # Clamp risk score
    risk_score = min(risk_score, 1.0)

    # Decision mapping: BLOCK if risk_score >= 0.80, REVIEW if risk_score >= 0.55, else ALLOW
    decision = "ALLOW"
    if risk_score >= 0.80:
        decision = "BLOCK"
    elif risk_score >= 0.55:
        decision = "REVIEW"

    # If transaction is NOT blocked, deduct the amount from the account balance
    if decision != "BLOCK":
        account.balance -= transaction.amount

    # Create new transaction
    new_transaction = Transaction(
        account_id=transaction.account_id,
        amount=transaction.amount,
        merchant_name=transaction.merchant_name,
        merchant_category=transaction.merchant_category,
        city=transaction.city,
        country=transaction.country,
        ip_address=transaction.ip_address,
        device_id=transaction.device_id,
        risk_score=risk_score,
        decision=decision,
        fraud_flags=triggered_rules
    )

    db.add(new_transaction)
    await db.flush()  # Populate new_transaction.id

    # Create fraud event records
    for rule_code, detail_msg in details.items():
        event = FraudEvent(
            transaction_id=new_transaction.id,
            rule_triggered=rule_code,
            severity="MEDIUM",
            details=detail_msg
        )
        db.add(event)

    # Upsert Device Log
    device_query = select(DeviceLog).where(
        DeviceLog.account_id == new_transaction.account_id,
        DeviceLog.device_id == new_transaction.device_id
    )
    device_result = await db.execute(device_query)
    device_log = device_result.scalar_one_or_none()

    if device_log:
        device_log.last_seen = func.now()
        device_log.ip_address = new_transaction.ip_address
    else:
        new_device_log = DeviceLog(
            account_id=new_transaction.account_id,
            device_id=new_transaction.device_id,
            ip_address=new_transaction.ip_address,
            last_seen=func.now()
        )
        db.add(new_device_log)
    await db.commit()
    await db.refresh(new_transaction)

    # 3. Trigger Webhook in Background if configured
    webhook_url = runtime_settings.get("WEBHOOK_URL", "")
    if webhook_url:
        webhook_payload = {
            "event": f"transaction.{new_transaction.decision.lower()}",
            "timestamp": new_transaction.timestamp.isoformat() if hasattr(new_transaction.timestamp, "isoformat") else str(new_transaction.timestamp),
            "data": {
                "transaction_id": new_transaction.id,
                "account_id": new_transaction.account_id,
                "amount": new_transaction.amount,
                "merchant_name": new_transaction.merchant_name,
                "merchant_category": new_transaction.merchant_category,
                "city": new_transaction.city,
                "country": new_transaction.country,
                "ip_address": new_transaction.ip_address,
                "device_id": new_transaction.device_id,
                "risk_score": new_transaction.risk_score,
                "decision": new_transaction.decision,
                "triggered_rules": new_transaction.fraud_flags,
                "details": details
            }
        }
        background_tasks.add_task(send_webhook, webhook_url, webhook_payload)

    return {
        "message": "Transaction processed",
        "transaction_id": new_transaction.id,
        "risk_score": new_transaction.risk_score,
        "decision": new_transaction.decision,
        "triggered_rules": new_transaction.fraud_flags,
        "details": details
    }


@router.get("/")
async def get_my_transactions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Fetch accounts owned by current user
    accounts_query = select(Account.id).where(Account.user_id == current_user.id)
    accounts_result = await db.execute(accounts_query)
    account_ids = accounts_result.scalars().all()

    if not account_ids:
        return []

    # Fetch transactions for those accounts
    query = select(Transaction).where(Transaction.account_id.in_(account_ids)).order_by(Transaction.timestamp.desc())
    result = await db.execute(query)
    transactions = result.scalars().all()

    return transactions