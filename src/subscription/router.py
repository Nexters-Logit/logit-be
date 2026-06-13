"""구독 API 엔드포인트."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.common.responses import (
    ERROR_403_FORBIDDEN,
    RESPONSES_CRUD_WITH_AUTH,
    create_responses,
)
from src.users.dependencies import ActiveUser, SessionDep

from .models import Subscription, SubscriptionType
from .service import (
    get_all_subscriptions,
    get_or_create_mcp_token,
    get_subscription_by_type,
)


class McpTokenResponse(BaseModel):
    token: str


router = APIRouter()


@router.get(
    "/me",
    response_model=list[Subscription],
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="내 구독 상태 조회",
)
async def get_my_subscriptions(
    session: SessionDep,
    current_user: ActiveUser,
):
    """
    현재 유저의 전체 구독 목록을 반환합니다.

    - 만료된 구독은 자동으로 is_active=False 처리 후 반환합니다.
    """
    return await get_all_subscriptions(session, current_user.id)


@router.get(
    "/me/mcp-token",
    response_model=McpTokenResponse,
    responses=create_responses(
        RESPONSES_CRUD_WITH_AUTH,
        {403: ERROR_403_FORBIDDEN},
    ),
    summary="MCP 서버 토큰 발급",
)
async def get_mcp_token(
    session: SessionDep,
    current_user: ActiveUser,
):
    """
    활성 MCP 구독이 있는 유저에게 MCP 서버 접속용 JWT 토큰을 발급합니다.

    - 구독이 없거나 만료된 경우 403을 반환합니다.
    - 만료 여부는 호출 시점에 실시간으로 확인합니다.
    """
    token, is_expired = await get_or_create_mcp_token(session, current_user.id)

    if is_expired:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MCP 구독이 만료되었습니다. 결제 후 이용해주세요.",
        )

    return McpTokenResponse(token=token)


@router.get(
    "/me/{type}",
    response_model=Subscription | None,
    responses=RESPONSES_CRUD_WITH_AUTH,
    summary="특정 타입 구독 상태 조회",
)
async def get_my_subscription_by_type(
    session: SessionDep,
    current_user: ActiveUser,
    type: SubscriptionType,
):
    """
    현재 유저의 특정 타입(mcp | logit) 구독을 반환합니다.

    - 만료 상태라면 is_active=False 로 업데이트 후 반환합니다.
    - 구독이 없으면 null을 반환합니다.
    """
    return await get_subscription_by_type(session, current_user.id, type)
