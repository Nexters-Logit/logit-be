"""결제 플랜 정의."""

from dataclasses import dataclass

from src.subscription.models import SubscriptionPlan, SubscriptionType


@dataclass(frozen=True)
class PlanInfo:
    subscription_type: SubscriptionType
    plan: SubscriptionPlan
    price: int       # KRW
    good_name: str   # PayApp 상품명


PLANS: dict[str, PlanInfo] = {
    "mcp:basic": PlanInfo(
        subscription_type=SubscriptionType.MCP,
        plan=SubscriptionPlan.BASIC,
        price=1000,
        good_name="Logit MCP 구독",
    ),
    "logit:lite": PlanInfo(
        subscription_type=SubscriptionType.LOGIT,
        plan=SubscriptionPlan.LITE,
        price=6900,
        good_name="Logit Lite 구독",
    ),
    "logit:pro": PlanInfo(
        subscription_type=SubscriptionType.LOGIT,
        plan=SubscriptionPlan.PRO,
        price=14900,
        good_name="Logit Pro 구독",
    ),
}


def get_plan(subscription_type: SubscriptionType, plan: SubscriptionPlan) -> PlanInfo | None:
    key = f"{subscription_type.value}:{plan.value}"
    return PLANS.get(key)


def plan_key(subscription_type: SubscriptionType, plan: SubscriptionPlan) -> str:
    return f"{subscription_type.value}:{plan.value}"
