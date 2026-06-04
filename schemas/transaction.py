from pydantic import BaseModel
from typing import List
from datetime import datetime


class TransactionCreate(BaseModel):
    account_id: int
    amount: float
    merchant_name: str
    merchant_category: str
    city: str
    country: str
    ip_address: str
    device_id: str


class TransactionResponse(BaseModel):
    id: int
    account_id: int
    amount: float
    merchant_name: str
    merchant_category: str
    city: str
    country: str
    risk_score: float
    decision: str
    fraud_flags: List[str]
    timestamp: datetime

    class Config:
        from_attributes = True