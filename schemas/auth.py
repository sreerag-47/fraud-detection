from pydantic import BaseModel, EmailStr
from typing import Optional


class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str
    home_city: Optional[str] = "Kozhikode"
    home_country: Optional[str] = "India"
    account_type: Optional[str] = "savings"
    balance: Optional[float] = 10000.0


class UserLogin(BaseModel):
    email: EmailStr
    password: str