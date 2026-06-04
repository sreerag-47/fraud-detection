from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db

from dependencies import get_current_user

from models.user import User
from models.account import Account


router = APIRouter(
    prefix="/accounts",
    tags=["Accounts"]
)


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