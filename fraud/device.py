from sqlalchemy import select

from fraud.schemas import TransactionContext
from models.device_log import DeviceLog


async def check_device(ctx: TransactionContext, db):

    triggered_rules = []

    details = {}

    query = select(DeviceLog).where(
        DeviceLog.account_id == ctx.account_id,
        DeviceLog.device_id == ctx.device_id
    )

    result = await db.execute(query)

    existing_device = result.scalar_one_or_none()

    if not existing_device:

        triggered_rules.append("DEV-01")

        details["DEV-01"] = (
            "New device detected for account"
        )

    return triggered_rules, details