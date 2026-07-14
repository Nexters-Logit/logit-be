"""요금제 라우터."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_db

from .models import Plan
from .schemas import PlanResponse

router = APIRouter()


@router.get("/", response_model=list[PlanResponse])
async def list_plans(
    session: AsyncSession = Depends(get_async_db),
) -> list[PlanResponse]:
    """활성화된 요금제 목록을 반환한다. 인증 불필요."""
    result = await session.execute(
        select(Plan)
        .where(Plan.is_active == True)  # noqa: E712
        .order_by(Plan.display_order)
    )
    plans = result.scalars().all()
    return [PlanResponse.from_model(p) for p in plans]
