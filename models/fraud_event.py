from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func

from database import Base


class FraudEvent(Base):
    __tablename__ = "fraud_events"

    id = Column(Integer, primary_key=True, index=True)

    transaction_id = Column(Integer, ForeignKey("transactions.id"))

    rule_triggered = Column(String, nullable=False)

    severity = Column(String, nullable=False)

    details = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())