"""토큰 API 스키마."""

from pydantic import BaseModel


class TokenBalanceResponse(BaseModel):
    balance: int
    plan: str
    monthly_tokens: int
    monthly_grant_received: bool = False
    monthly_grant_amount: int = 0
    signup_bonus_received: bool = False
    signup_bonus_amount: int = 0
    attendance_received: bool = False
    attendance_amount: int = 0
    referral_reward_received: bool = False
    referral_reward_amount: int = 0
    referral_reward_count: int = 0
