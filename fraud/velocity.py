from datetime import datetime, timedelta

from sqlalchemy import select, func

from fraud.schemas import TransactionContext
from models.transaction import Transaction


async def check_velocity(ctx: TransactionContext, db):

    triggered_rules = []
    details = {}

    one_hour_ago = datetime.utcnow() - timedelta(hours=1)

    query = select(func.count(Transaction.id)).where(
        Transaction.account_id == ctx.account_id,
        Transaction.timestamp >= one_hour_ago
    )

    result = await db.execute(query)

    transaction_count = result.scalar()

    if transaction_count >= 5:
        triggered_rules.append("VEL-01")

        details["VEL-01"] = (
            f"{transaction_count} transactions detected within last hour"
        )

    if ctx.amount > 10000:
        triggered_rules.append("VEL-TEST-01")

        details["VEL-TEST-01"] = (
            "High transaction amount velocity test triggered"
        )

    return triggered_rules, details