from fastapi import status

GET_CHAT_HISTORY_SWAGGER = {
    "summary": "채팅 히스토리 조회",
    "description": """
특정 문항(Question)에 대한 채팅 히스토리를 조회합니다.

## 페이지네이션

Cursor 기반 페이지네이션을 지원합니다.

**쿼리 파라미터:**
- `cursor`: 다음 페이지 조회용 (이전 응답의 `next_cursor` 값)
- `size`: 한 페이지에 가져올 메시지 수 (기본값: 20, 최대: 100)

**응답 페이지네이션 필드:**
- `next_cursor`: 다음 페이지 조회용 cursor (없으면 마지막 페이지)
- `has_more`: 더 많은 데이터가 있는지 여부

**사용 예시:**
```
# 첫 페이지
GET /projects/chats/{question_id}?size=20

# 다음 페이지 (이전 응답의 next_cursor 사용)
GET /projects/chats/{question_id}?cursor=1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed&size=20
```

---

**반환 정보:**
- 프로젝트명 (회사_채용유형)
- 생성일
- 문항 내용
- 현재 저장된 자기소개서 답변 (answer)
- 채팅 메시지 목록 (시간순 정렬)

**각 메시지 정보:**
- role: "user" 또는 "assistant"
- content: 메시지 내용
- is_draft: 자기소개서 초안 여부

**추가 반환 정보:**
- experience_ids: 최근 선택된 경험 ID 목록 (응답 최상위)
- remaining_chats: 남은 채팅 횟수
""",
    "responses": {
        status.HTTP_200_OK: {
            "description": "채팅 히스토리 조회 성공",
            "content": {
                "application/json": {
                    "examples": {
                        "with_more_pages": {
                            "summary": "더 많은 페이지가 있는 경우",
                            "value": {
                                "project_name": "네이버_백엔드개발자",
                                "project_created_at": "2026-01-20T10:00:00Z",
                                "question_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "question": "지원동기 및 향후 목표",
                                "answer": "Cardify 프로젝트에서...",
                                "chats": [
                                    {
                                        "id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
                                        "role": "user",
                                        "content": "협업 경험 써줘",
                                        "is_draft": False,
                                        "created_at": "2026-01-20T10:00:00Z"
                                    },
                                    {
                                        "id": "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed",
                                        "role": "assistant",
                                        "content": "Cardify 프로젝트에서...",
                                        "is_draft": True,
                                        "created_at": "2026-01-20T10:00:05Z"
                                    }
                                ],
                                "experience_ids": ["7c9e6679-7425-40de-944b-e07fc1f90ae7"],
                                "next_cursor": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
                                "has_more": True,
                                "remaining_chats": 8
                            }
                        },
                        "last_page": {
                            "summary": "마지막 페이지",
                            "value": {
                                "project_name": "네이버_백엔드개발자",
                                "project_created_at": "2026-01-20T10:00:00Z",
                                "question_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "question": "지원동기 및 향후 목표",
                                "answer": None,
                                "chats": [
                                    {
                                        "id": "abc12345-1234-5678-9abc-def012345678",
                                        "role": "user",
                                        "content": "첫 번째 메시지",
                                        "is_draft": False,
                                        "created_at": "2026-01-20T09:00:00Z"
                                    }
                                ],
                                "experience_ids": [],
                                "next_cursor": None,
                                "has_more": False,
                                "remaining_chats": 10
                            }
                        }
                    }
                }
            },
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

SEND_CHAT_SWAGGER = {
    "summary": "메시지 전송 (SSE 스트리밍)",
    "description": """
채팅방에 메시지를 전송하고 AI 응답을 SSE 스트리밍으로 받습니다.

**응답 형식:** Server-Sent Events (text/event-stream)

**프로세스:**
1. 사용자 메시지 저장 (experience_ids 포함)
2. 선택된 경험 정보를 Qdrant에서 조회
3. Langchain + GPT-4o-mini로 AI 응답 스트리밍 생성
4. AI 응답 저장 및 완료 이벤트 전송

**AI 참고 정보:**
- 회사명, 채용공고 (Project)
- 문항, 글자수 제한 (Question)
- 선택한 경험 정보 (Qdrant)
- 이전 채팅 히스토리

---

## SSE 이벤트 형식

각 이벤트는 `data: {JSON}\\n\\n` 형식으로 전송됩니다.

### 1. content 이벤트 (스트리밍 중)
```json
{"type": "content", "content": "텍스트 조각"}
```

### 2. done 이벤트 (완료)
```json
{"type": "done", "chat_id": "uuid", "is_draft": true}
```
- `chat_id`: 저장된 AI 메시지 ID
- `is_draft`: 자기소개서 초안 여부

### 3. error 이벤트 (에러)
```json
{"type": "error", "message": "에러 메시지"}
```

---

## 클라이언트 구현 예시

### Web (JavaScript - fetch + ReadableStream)

### iOS (Swift - URLSession)

### Android (Kotlin - OkHttp)
---

**초안 판단 기준:**
- "써줘", "생성", "초안", "작성해줘", "만들어줘" 등의 키워드 포함 시 `is_draft=true`
- 일반 대화는 `is_draft=false`
""",
    "responses": {
        status.HTTP_200_OK: {
            "description": "SSE 스트리밍 응답",
            "content": {
                "text/event-stream": {
                    "examples": {
                        "streaming": {
                            "summary": "스트리밍 응답 예시",
                            "value": 'data: {"type": "content", "content": "Cardify"}\n\ndata: {"type": "content", "content": " 프로젝트에서"}\n\ndata: {"type": "content", "content": " 협업을 통해..."}\n\ndata: {"type": "done", "chat_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d", "is_draft": true, "remaining_chats": 9}\n\n'
                        },
                        "error": {
                            "summary": "에러 응답 예시",
                            "value": 'data: {"type": "error", "message": "Question not found"}\n\n'
                        }
                    }
                }
            },
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "요청 검증 오류",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_field": {
                            "summary": "필수 필드 누락",
                            "value": {
                                "detail": [
                                    {
                                        "type": "missing",
                                        "loc": ["body", "question_id"],
                                        "msg": "Field required",
                                        "input": {}
                                    }
                                ]
                            }
                        },
                        "content_too_long": {
                            "summary": "content 글자수 초과 (최대 5000자)",
                            "value": {
                                "detail": [
                                    {
                                        "type": "string_too_long",
                                        "loc": ["body", "content"],
                                        "msg": "String should have at most 5000 characters",
                                        "input": "..."
                                    }
                                ]
                            }
                        },
                        "too_many_experiences": {
                            "summary": "경험 ID 초과 (최대 3개)",
                            "value": {
                                "detail": [
                                    {
                                        "type": "value_error",
                                        "loc": ["body", "experience_ids"],
                                        "msg": "Value error, 최대 3개의 경험만 선택할 수 있습니다",
                                        "input": ["id1", "id2", "id3", "id4"]
                                    }
                                ]
                            }
                        }
                    }
                }
            },
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "description": "일일 채팅 제한 초과",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "message": "일일 채팅 제한을 초과했습니다.",
                            "remaining": 0
                        }
                    }
                }
            },
        },
    },
}