from fraud.schemas import TransactionContext


async def check_behaviour(ctx: TransactionContext, db):

    triggered_rules = []

    details = {}

    unusual_categories = [
        "jewellery",
        "crypto",
        "luxury"
    ]

    if ctx.merchant_category.lower() in unusual_categories:

        triggered_rules.append("BEH-01")

        details["BEH-01"] = (
            f"Unusual merchant category: {ctx.merchant_category}"
        )

    return triggered_rules, details