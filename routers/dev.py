from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User
from models.account import Account


router = APIRouter(
    prefix="/dev",
    tags=["Development"]
)


@router.post("/seed")
async def seed_database(db: AsyncSession = Depends(get_db)):
    user = User(
        name="Test User",
        email="test@example.com",
        password_hash="hashed_password"
    )

    db.add(user)

    await db.commit()

    await db.refresh(user)

    account = Account(
        user_id=user.id,
        account_number="BG001",
        balance=50000,
        account_type="savings",
        home_city="Kozhikode",
        home_country="India"
    )

    db.add(account)

    await db.commit()

    await db.refresh(account)

    return {
        "message": "Seed data created",
        "user_id": user.id,
        "account_id": account.id
    }