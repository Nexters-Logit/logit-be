from fastapi import status

SEND_CHAT_SWAGGER = {
    "summary": "메시지 전송",
    "description": """
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
    "responses": {
        status.HTTP_200_OK: {
            "description": "메시지 전송 성공",
            "content": {
                "application/json": {
                    "examples": {
                        "초안 생성": {
                            "summary": "자기소개서 초안 생성해줘",
                            "value": {
                                "chat_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
                                "is_draft": True,
                            },
                        },
                        "일반 대화": {
                            "summary": "일반 대화 (수정 요청 등)",
                            "value": {
                                "chat_id": "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed",
                                "is_draft": False,
                            },
                        },
                    }
                }
            },
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "채팅방을 찾을 수 없음",
            "content": {
                "application/json": {
                    "example": {"detail": "Chat not found"}
                }
            },
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "검증 오류",
        },
    },
}
