"""토큰 API 스키마."""

from pydantic import BaseModel


class TokenBalanceResponse(BaseModel):
    balance: int
    plan: str
    monthly_tokens: int


class AttendanceResponse(BaseModel):
    success: bool
    message: str
    tokens_earned: int
    new_balance: int
