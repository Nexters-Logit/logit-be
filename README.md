# Logit Server

자기소개서 작성을 도와주는 AI 서비스 **Logit**의 Backend API

## 프로젝트 소개

Logit은 사용자의 경험을 기반으로 자기소개서 작성을 돕는 AI 서비스입니다.
- **경험 관리**: 사용자의 경험을 등록하고 벡터 DB에 저장
- **프로젝트 기반 작성**: 지원할 회사/직무별 프로젝트 생성
- **AI 기반 문항 답변**: RAG를 활용하여 경험 기반 자기소개서 초안 생성
- **대화형 편집**: 채팅을 통한 답변 수정 및 개선

## 기술 스택

- **FastAPI** + SQLModel + asyncpg
- **PostgreSQL** + **Redis** + **Qdrant** (벡터 DB)
- **OAuth 2.0** (Google, Apple)
- **uv** (패키지 매니저)
- **LangChain** + OpenAI

## 빠른 시작

```bash
# 환경변수 설정
cp .env.example .env

# 빌드 및 실행
make quick-start

# 개발 모드
make dev
```

## 주요 명령어

```bash
make up              # 서비스 시작
make down            # 서비스 중지
make logs            # 로그 보기
make test            # 테스트 실행
make migrate-create MSG="메시지"  # 마이그레이션 생성
```

## API 문서

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 서비스 포트

| 서비스 | 포트 |
|--------|------|
| FastAPI | 8000 |
| PostgreSQL | 5432 |
| Redis | 6379 |
| Qdrant | 6333 |
