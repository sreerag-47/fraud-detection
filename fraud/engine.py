from fraud.schemas import FraudResult

from fraud.velocity import check_velocity
from fraud.location import check_location
from fraud.threshold import check_threshold
from fraud.behaviour import check_behaviour
from fraud.device import check_device


RULE_WEIGHTS = {
    "VEL-01": 0.15,
    "VEL-TEST-01": 0.30,

    "LOC-01": 0.40,

    "THR-01": 0.20,

    "BEH-01": 0.10,

    "DEV-01": 0.15
}


async def run_fraud_check(ctx, db):

    triggered_rules = []

    details = {}

    modules = [
        check_velocity,
        check_location,
        check_threshold,
        check_behaviour,
        check_device
    ]

    for module in modules:

        rules, module_details = await module(ctx, db)

        triggered_rules.extend(rules)

        details.update(module_details)

    risk_score = min(
        sum(RULE_WEIGHTS.get(rule, 0) for rule in triggered_rules),
        1.0
    )

    if risk_score >= 0.85:
        decision = "BLOCK"

    elif risk_score >= 0.55:
        decision = "REVIEW"

    else:
        decision = "ALLOW"

    return FraudResult(
        risk_score=risk_score,
        decision=decision,
        triggered_rules=triggered_rules,
        details=details
    )