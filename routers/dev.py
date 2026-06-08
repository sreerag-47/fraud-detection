from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func, inspect
from datetime import datetime, date
from typing import Dict, Any, List
from pydantic import BaseModel

from database import get_db
from models.user import User
from models.account import Account
from models.transaction import Transaction
from models.fraud_event import FraudEvent
from models.fraud_rule import FraudRule
from models.device_log import DeviceLog


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


# --- Database Playground API Endpoints ---

MODEL_MAP = {
    "users": User,
    "accounts": Account,
    "transactions": Transaction,
    "fraud_rules": FraudRule,
    "fraud_events": FraudEvent,
    "device_logs": DeviceLog
}


def model_to_dict(instance):
    if not instance:
        return None
    data = {}
    for col in inspect(instance.__class__).columns:
        val = getattr(instance, col.name)
        if isinstance(val, (datetime, date)):
            val = val.isoformat()
        data[col.name] = val
    return data


@router.get("/db/tables")
async def list_tables_and_counts(db: AsyncSession = Depends(get_db)):
    counts = {}
    for name, model in MODEL_MAP.items():
        try:
            stmt = select(func.count()).select_from(model)
            res = await db.execute(stmt)
            counts[name] = res.scalar() or 0
        except Exception as e:
            counts[name] = f"Error: {str(e)}"
    return counts


@router.get("/db/tables/{table_name}")
async def list_table_rows(
    table_name: str,
    db: AsyncSession = Depends(get_db)
):
    if table_name not in MODEL_MAP:
        raise HTTPException(status_code=404, detail=f"Table {table_name} not found")
    
    model = MODEL_MAP[table_name]
    try:
        # Order by id if the model has an id column
        if hasattr(model, "id"):
            stmt = select(model).order_by(model.id.asc())
        else:
            stmt = select(model)
            
        res = await db.execute(stmt)
        rows = res.scalars().all()
        return [model_to_dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RowCreate(BaseModel):
    data: Dict[str, Any]


@router.post("/db/tables/{table_name}")
async def create_table_row(
    table_name: str,
    payload: RowCreate,
    db: AsyncSession = Depends(get_db)
):
    if table_name not in MODEL_MAP:
        raise HTTPException(status_code=404, detail=f"Table {table_name} not found")
    
    model = MODEL_MAP[table_name]
    try:
        valid_cols = {col.name for col in inspect(model).columns}
        init_data = {k: v for k, v in payload.data.items() if k in valid_cols and k != 'id'}
        
        if table_name == "users" and "password" in payload.data:
            from utils import hash_password
            init_data["password_hash"] = hash_password(payload.data["password"])
            
        instance = model(**init_data)
        db.add(instance)
        await db.commit()
        await db.refresh(instance)
        return model_to_dict(instance)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


class RowUpdate(BaseModel):
    data: Dict[str, Any]


@router.put("/db/tables/{table_name}/{row_id}")
async def update_table_row(
    table_name: str,
    row_id: int,
    payload: RowUpdate,
    db: AsyncSession = Depends(get_db)
):
    if table_name not in MODEL_MAP:
        raise HTTPException(status_code=404, detail=f"Table {table_name} not found")
    
    model = MODEL_MAP[table_name]
    try:
        stmt = select(model).where(model.id == row_id)
        res = await db.execute(stmt)
        instance = res.scalar_one_or_none()
        if not instance:
            raise HTTPException(status_code=404, detail=f"Row with id {row_id} not found")
            
        valid_cols = {col.name for col in inspect(model).columns}
        for key, value in payload.data.items():
            if key in valid_cols and key != 'id':
                setattr(instance, key, value)
                
        await db.commit()
        await db.refresh(instance)
        return model_to_dict(instance)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/db/tables/{table_name}/{row_id}")
async def delete_table_row(
    table_name: str,
    row_id: int,
    db: AsyncSession = Depends(get_db)
):
    if table_name not in MODEL_MAP:
        raise HTTPException(status_code=404, detail=f"Table {table_name} not found")
    
    model = MODEL_MAP[table_name]
    try:
        stmt = select(model).where(model.id == row_id)
        res = await db.execute(stmt)
        instance = res.scalar_one_or_none()
        if not instance:
            raise HTTPException(status_code=404, detail=f"Row with id {row_id} not found")
            
        await db.delete(instance)
        await db.commit()
        return {"message": f"Row {row_id} deleted successfully from {table_name}"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


class SQLQuery(BaseModel):
    query: str


@router.post("/db/query")
async def run_raw_sql_query(
    payload: SQLQuery,
    db: AsyncSession = Depends(get_db)
):
    try:
        stmt = text(payload.query)
        result = await db.execute(stmt)
        
        if result.returns_rows:
            rows = result.all()
            columns = list(result.keys())
            
            formatted_rows = []
            for row in rows:
                row_data = {}
                for idx, col in enumerate(columns):
                    val = row[idx]
                    if isinstance(val, (datetime, date)):
                        val = val.isoformat()
                    row_data[col] = val
                formatted_rows.append(row_data)
                
            return {
                "type": "select",
                "columns": columns,
                "rows": formatted_rows,
                "row_count": len(formatted_rows)
            }
        else:
            await db.commit()
            return {
                "type": "command",
                "row_count": result.rowcount
            }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


# --- Mock Webhook Receiver for Testing ---
received_webhooks = []

@router.post("/webhook-receiver")
async def webhook_receiver(payload: dict):
    from datetime import datetime
    received_webhooks.append({
        "received_at": datetime.now().isoformat(),
        "payload": payload
    })
    if len(received_webhooks) > 50:
        received_webhooks.pop(0)
    print(f"Webhook received! Event: {payload.get('event')}, Decision: {payload.get('data', {}).get('decision')}")
    return {"status": "success", "message": "Webhook received successfully"}

@router.get("/webhook-received")
async def get_received_webhooks():
    return received_webhooks

@router.delete("/webhook-received")
async def clear_received_webhooks():
    received_webhooks.clear()
    return {"message": "Webhook logs cleared"}