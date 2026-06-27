"""배너 라우터."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_db

from .models import Banner
from .schemas import BannerResponse

router = APIRouter()


@router.get("/", response_model=list[BannerResponse])
async def list_banners(
    session: AsyncSession = Depends(get_async_db),
) -> list[BannerResponse]:
    """노출 중인 배너 목록을 순서대로 반환한다. 인증 불필요."""
    result = await session.execute(
        select(Banner)
        .where(Banner.is_visible == True)  # noqa: E712
        .order_by(Banner.display_order, Banner.created_at)
    )
    banners = result.scalars().all()
    return [BannerResponse.from_model(b) for b in banners]
