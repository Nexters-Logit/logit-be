from fastapi import status

GET_CHAT_HISTORY_SWAGGER = {
    "summary": "채팅 히스토리 조회",
    "description": """
특정 문항(Question)에 대한 채팅 히스토리를 조회합니다.

**반환 정보:**
- 프로젝트명 (회사_채용유형)
- 생성일
- 문항 내용
- 채팅 메시지 목록 (시간순 정렬)

**각 메시지 정보:**
- role: "user" 또는 "ai"
- content: 메시지 내용
- is_draft: 자기소개서 초안 여부

**추가 반환 정보:**
- experience_ids: 최근 선택된 경험 ID 목록 (응답 최상위)
""",
    "responses": {
        status.HTTP_200_OK: {
            "description": "채팅 히스토리 조회 성공",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "문항을 찾을 수 없음",
            "content": {
                "application/json": {
                    "example": {"detail": "Question not found"}
                }
            },
        },
    },
}

UPDATE_ANSWER_SWAGGER = {
    "summary": "자기소개서 답변 업데이트",
    "description": """
AI가 생성한 초안(is_draft=true)을 자기소개서 답변으로 저장합니다.

**프로세스:**
1. 해당 chat_id의 AI 메시지 조회
2. 해당 메시지의 content를 Question의 answer에 저장

**사용 시점:**
- 채팅 화면에서 AI 초안의 "자기소개서 업데이트" 버튼 클릭 시
""",
    "responses": {
        status.HTTP_200_OK: {
            "description": "답변 업데이트 성공",
            "content": {
                "application/json": {
                    "example": {
                        "question_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                        "answer": "Cardify 프로젝트에서..."
                    }
                }
            },
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "채팅 메시지를 찾을 수 없음",
            "content": {
                "application/json": {
                    "example": {"detail": "Chat not found"}
                }
            },
        },
    },
}

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
