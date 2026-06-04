from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db

from models.user import User
from models.account import Account

from schemas.auth import UserRegister

from utils import (
    hash_password,
    verify_password,
    create_access_token
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.post("/register")
async def register(
    user: UserRegister,
    db: AsyncSession = Depends(get_db)
):

    query = select(User).where(
        User.email == user.email
    )

    result = await db.execute(query)

    existing_user = result.scalar_one_or_none()

    if existing_user:

        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    new_user = User(
        name=user.name,
        email=user.email,
        password_hash=hash_password(user.password)
    )

    db.add(new_user)

    await db.commit()

    await db.refresh(new_user)

    account = Account(
        user_id=new_user.id,
        account_number=f"BG{1000 + new_user.id}",
        balance=10000,
        account_type="savings",
        home_city="Kozhikode",
        home_country="India"
    )

    db.add(account)

    await db.commit()

    await db.refresh(account)

    return {
        "message": "User registered successfully",
        "user_id": new_user.id,
        "account_id": account.id,
        "account_number": account.account_number
    }


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):

    query = select(User).where(
        User.email == form_data.username
    )

    result = await db.execute(query)

    db_user = result.scalar_one_or_none()

    if not db_user:

        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    if not verify_password(
        form_data.password,
        db_user.password_hash
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    access_token = create_access_token({
        "sub": str(db_user.id)
    })

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }