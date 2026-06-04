from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)

    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)

    amount = Column(Float, nullable=False)

    merchant_name = Column(String, nullable=False)

    merchant_category = Column(String, nullable=False)

    city = Column(String, nullable=False)

    country = Column(String, nullable=False)

    ip_address = Column(String, nullable=False)

    device_id = Column(String, nullable=False)

    risk_score = Column(Float, default=0.0)

    decision = Column(String, default="ALLOW")

    fraud_flags = Column(JSON, default=[])

    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    account = relationship("Account")