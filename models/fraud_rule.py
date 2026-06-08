from sqlalchemy import Column, Integer, String, Float, Boolean, Text
from database import Base

class FraudRule(Base):
    __tablename__ = "fraud_rules"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    sql_expression = Column(Text, nullable=False)
    weight = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
