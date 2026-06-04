from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.transaction import Transaction
from models.account import Account
from schemas.transaction import TransactionCreate

from fraud.schemas import TransactionContext
from fraud.engine import run_fraud_check

from models.fraud_event import FraudEvent
from models.device_log import DeviceLog
from dependencies import get_current_user
from models.user import User

router = APIRouter(
    prefix="/transactions",
    tags=["Transactions"]
)


@router.post("/")
async def create_transaction(
    transaction: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):

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

    ctx = TransactionContext(
        account_id=transaction.account_id,
        amount=transaction.amount,
        merchant_name=transaction.merchant_name,
        merchant_category=transaction.merchant_category,
        city=transaction.city,
        country=transaction.country,
        ip_address=transaction.ip_address,
        device_id=transaction.device_id,
        timestamp=datetime.utcnow()
    )

    fraud_result = await run_fraud_check(ctx, db)

    new_transaction = Transaction(
        account_id=transaction.account_id,
        amount=transaction.amount,
        merchant_name=transaction.merchant_name,
        merchant_category=transaction.merchant_category,
        city=transaction.city,
        country=transaction.country,
        ip_address=transaction.ip_address,
        device_id=transaction.device_id,
        risk_score=fraud_result.risk_score,
        decision=fraud_result.decision,
        fraud_flags=fraud_result.triggered_rules
    )

    db.add(new_transaction)

    await db.commit()

    device_query = select(DeviceLog).where(
        DeviceLog.account_id == transaction.account_id,
        DeviceLog.device_id == transaction.device_id
    )

    device_result = await db.execute(device_query)

    existing_device = device_result.scalar_one_or_none()

    if existing_device:

        existing_device.last_seen = ctx.timestamp

    else:

        new_device = DeviceLog(
            account_id=transaction.account_id,
            device_id=transaction.device_id,
            ip_address=transaction.ip_address
        )

        db.add(new_device)

    await db.commit()

    await db.refresh(new_transaction)

    for rule in fraud_result.triggered_rules:

        fraud_event = FraudEvent(
            transaction_id=new_transaction.id,
            rule_triggered=rule,
            severity="MEDIUM",
            details=fraud_result.details.get(rule, "")
        )

        db.add(fraud_event)

    await db.commit()

    return {
        "message": "Transaction processed",
        "transaction_id": new_transaction.id,
        "risk_score": fraud_result.risk_score,
        "decision": fraud_result.decision,
        "triggered_rules": fraud_result.triggered_rules,
        "details": fraud_result.details
    }