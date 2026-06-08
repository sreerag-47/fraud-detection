from pydantic import BaseModel
from typing import Optional

class FraudRuleCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    sql_expression: str
    weight: float = 0.0

class FraudRuleResponse(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str]
    sql_expression: str
    weight: float
    is_active: bool

    class Config:
        from_attributes = True
