from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from typing import List

from database import get_db
from dependencies import get_current_admin
from models.user import User
from models.account import Account
from models.transaction import Transaction
from models.fraud_event import FraudEvent
from models.fraud_rule import FraudRule
from schemas.fraud_rule import FraudRuleCreate, FraudRuleResponse

router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)


@router.get("/transactions")
async def list_all_transactions(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    query = (
        select(Transaction)
        .options(joinedload(Transaction.account).joinedload(Account.user))
        .order_by(Transaction.timestamp.desc())
    )
    result = await db.execute(query)
    transactions = result.scalars().all()

    formatted = []
    for tx in transactions:
        formatted.append({
            "id": tx.id,
            "account_id": tx.account_id,
            "account_number": tx.account.account_number if tx.account else None,
            "user_name": tx.account.user.name if tx.account and tx.account.user else None,
            "user_email": tx.account.user.email if tx.account and tx.account.user else None,
            "amount": tx.amount,
            "merchant_name": tx.merchant_name,
            "merchant_category": tx.merchant_category,
            "city": tx.city,
            "country": tx.country,
            "ip_address": tx.ip_address,
            "device_id": tx.device_id,
            "risk_score": tx.risk_score,
            "decision": tx.decision,
            "fraud_flags": tx.fraud_flags,
            "timestamp": tx.timestamp
        })
    return formatted


@router.get("/fraud-events")
async def list_all_fraud_events(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    query = select(FraudEvent).order_by(FraudEvent.created_at.desc())
    result = await db.execute(query)
    events = result.scalars().all()
    return events


@router.get("/rules", response_model=List[FraudRuleResponse])
async def list_all_rules(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    query = select(FraudRule).order_by(FraudRule.id.asc())
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/rules", response_model=FraudRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    rule_in: FraudRuleCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    # Check if code already exists
    stmt = select(FraudRule).where(FraudRule.code == rule_in.code)
    existing = await db.execute(stmt)
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rule with code '{rule_in.code}' already exists"
        )
    
    new_rule = FraudRule(
        code=rule_in.code,
        name=rule_in.name,
        description=rule_in.description,
        sql_expression=rule_in.sql_expression,
        weight=rule_in.weight,
        is_active=True
    )
    db.add(new_rule)
    await db.commit()
    await db.refresh(new_rule)
    return new_rule


@router.put("/rules/{code}/toggle", response_model=FraudRuleResponse)
async def toggle_rule(
    code: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    stmt = select(FraudRule).where(FraudRule.code == code)
    res = await db.execute(stmt)
    rule = res.scalar_one_or_none()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule with code '{code}' not found"
        )
    rule.is_active = not rule.is_active
    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/rules/{code}")
async def delete_rule(
    code: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    DEFAULT_RULES = {
        'VEL-01', 'VEL-TEST-01', 'LOC-01', 'THR-01', 'BEH-01', 'DEV-01',
        'VEL-HIGH-FREQ', 'THR-NORM-EXCEED', 'BEH-MICRO-TEST', 'LOC-NEW-COUNTRY',
        'DEV-MULTI-ACCOUNT', 'REP-AMT'
    }
    if code in DEFAULT_RULES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete default system rules"
        )
        
    stmt = select(FraudRule).where(FraudRule.code == code)
    res = await db.execute(stmt)
    rule = res.scalar_one_or_none()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule with code '{code}' not found"
        )
    await db.delete(rule)
    await db.commit()
    return {"message": f"Rule with code '{code}' deleted successfully"}


from pydantic import BaseModel
from config import runtime_settings

class WebhookSettingsUpdate(BaseModel):
    webhook_url: str

@router.post("/webhook-settings")
async def update_webhook_settings(
    payload: WebhookSettingsUpdate,
    admin: User = Depends(get_current_admin)
):
    runtime_settings["WEBHOOK_URL"] = payload.webhook_url
    return {"message": "Webhook URL updated successfully", "webhook_url": runtime_settings["WEBHOOK_URL"]}

@router.get("/webhook-settings")
async def get_webhook_settings(
    admin: User = Depends(get_current_admin)
):
    return {"webhook_url": runtime_settings.get("WEBHOOK_URL", "")}
