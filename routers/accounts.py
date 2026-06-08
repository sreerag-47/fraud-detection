from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from database import get_db

from dependencies import get_current_user

from models.user import User
from models.account import Account


router = APIRouter(
    prefix="/accounts",
    tags=["Accounts"]
)


class DepositPayload(BaseModel):
    amount: float


@router.get("/me")
async def get_my_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):

    query = select(Account).where(
        Account.user_id == current_user.id
    )

    result = await db.execute(query)

    accounts = result.scalars().all()

    return accounts


@router.post("/{account_id}/deposit")
async def deposit_funds(
    account_id: int,
    payload: DepositPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.is_admin:
        query = select(Account).where(Account.id == account_id)
    else:
        query = select(Account).where(
            Account.id == account_id,
            Account.user_id == current_user.id
        )

    result = await db.execute(query)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=403,
            detail="You do not own this account"
        )

    if payload.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Deposit amount must be greater than zero"
        )

    account.balance += payload.amount
    await db.commit()
    await db.refresh(account)

    return {
        "message": "Deposit successful",
        "account_id": account.id,
        "new_balance": account.balance
    }