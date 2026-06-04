from sqlalchemy import select

from fraud.schemas import TransactionContext
from models.account import Account


async def check_location(ctx: TransactionContext, db):

    triggered_rules = []

    details = {}

    query = select(Account).where(
        Account.id == ctx.account_id
    )

    result = await db.execute(query)

    account = result.scalar_one_or_none()

    if not account:
        return triggered_rules, details

    if account.home_country != ctx.country:

        triggered_rules.append("LOC-01")

        details["LOC-01"] = (
            f"Transaction country '{ctx.country}' "
            f"does not match home country "
            f"'{account.home_country}'"
        )

    return triggered_rules, details