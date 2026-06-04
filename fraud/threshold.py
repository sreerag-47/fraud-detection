from fraud.schemas import TransactionContext


async def check_threshold(ctx: TransactionContext, db):

    triggered_rules = []

    details = {}

    if ctx.amount > 50000:

        triggered_rules.append("THR-01")

        details["THR-01"] = (
            "Transaction amount exceeded ₹50,000 threshold"
        )

    return triggered_rules, details