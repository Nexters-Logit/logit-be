from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import MessageRequest, MessageResponse
from .service import (
    create_user_message,
    create_assistant_message,
    get_chat_by_id
)
from src.database import get_async_db

router = APIRouter()


@router.post(
        "/message", 
        response_model=MessageResponse,
        status_code=status.HTTP_200_OK,
        summary="메시지 전송",
        description="""
        채팅방에 메시지를 전송하고 AI 응답을 받습니다.
        
        **프로세스:**
        1. 사용자 메시지 저장 (experience_ids 포함)
        2. 사용자 메시지 분석 (초안 생성 의도 감지)
        3. AI 응답 생성 (현재는 테스트 응답, 추후 RAG 적용)
        4. AI 응답 저장 및 반환
        
        **초안 판단 기준:**
        - "써줘", "생성", "초안", "작성해줘", "만들어줘" 등의 키워드 포함 시 is_draft=true
        - 일반 대화는 is_draft=false
        """,
        responses={
        200: {
            "description": "메시지 전송 성공",
            "content": {
                "application/json": {
                    "examples": {
                        "초안 생성": {
                            "summary": "자기소개서 초안 생성해줘",
                            "value": {
                                "chat_message_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
                                "is_draft": True
                            }
                        },
                        "일반 대화": {
                            "summary": "일반 대화 (수정 요청 등)",
                            "value": {
                                "chat_message_id": "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed",
                                "is_draft": False
                            }
                        }
                    }
                }
            }
        },
        404: {
            "description": "채팅방을 찾을 수 없음",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Chat not found"
                    }
                }
            }
        },
        422: {
            "description": "검증 오류",
            "content": {
                "application/json": {
                    "examples": {
                        "경험 개수 초과": {
                            "summary": "경험 4개 이상 선택",
                            "value": {
                                "detail": [
                                    {
                                        "loc": ["body", "experience_ids"],
                                        "msg": "최대 3개의 경험만 선택할 수 있습니다",
                                        "type": "value_error"
                                    }
                                ]
                            }
                        },
                        "경험 중복": {
                            "summary": "중복된 경험 선택",
                            "value": {
                                "detail": [
                                    {
                                        "loc": ["body", "experience_ids"],
                                        "msg": "중복된 경험을 선택할 수 없습니다",
                                        "type": "value_error"
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        }
    }
)
async def send_message(
    data: MessageRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """메시지 전송 API"""
    
    # 1. Chat 조회
    chat = await get_chat_by_id(db, data.chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # 2. 사용자 메시지 생성
    user_msg = await create_user_message(
        db=db,
        chat_id=data.chat_id,
        content=data.content,
        experience_ids=data.experience_ids
    )
    
    # 3. AI 응답 생성 (임시)
    ai_response = "테스트 응답입니다. RAG는 이후 구현"
    
    # 4. AI 메시지 생성
    ai_msg = await create_assistant_message(
        db=db,
        chat_id=data.chat_id,
        content=ai_response,
        experience_ids=data.experience_ids,
        user_content=data.content
    )
    
    return MessageResponse(
        chat_message_id=ai_msg.id,
        is_draft=ai_msg.is_draft
    )