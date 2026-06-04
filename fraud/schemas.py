from dataclasses import dataclass
from typing import List
from datetime import datetime


@dataclass
class TransactionContext:
    account_id: int
    amount: float
    merchant_name: str
    merchant_category: str
    city: str
    country: str
    ip_address: str
    device_id: str
    timestamp: datetime


@dataclass
class FraudResult:
    risk_score: float
    decision: str
    triggered_rules: List[str]
    details: dict