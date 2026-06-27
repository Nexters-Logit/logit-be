"""요금제 응답 스키마."""

from pydantic import BaseModel


class PlanResponse(BaseModel):
    id: str
    subscription_type: str
    plan_key: str
    name: str
    original_price: int
    price: int
    description: str | None
    badge: str | None
    features: list[str] | None
    is_recommended: bool
    is_free: bool
    display_order: int

    @classmethod
    def from_model(cls, plan: object) -> "PlanResponse":
        return cls(
            id=plan.id,
            subscription_type=plan.subscription_type,
            plan_key=plan.plan_key,
            name=plan.name,
            original_price=plan.original_price,
            price=plan.price,
            description=plan.description,
            badge=plan.badge,
            features=plan.features,
            is_recommended=plan.is_recommended,
            is_free=plan.is_free,
            display_order=plan.display_order,
        )
