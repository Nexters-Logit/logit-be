# Logit Server

써줘 AI의 Logit Backend API

**Domain-Driven Architecture** with **2025 Best Practices** (fastapi-best-practices 기반)

## 🏗️ Architecture

### Domain-Driven Design (Netflix Dispatch Style)

```
app/
├── auth/                   # 인증 도메인
│   ├── router.py          # OAuth & JWT 엔드포인트
│   ├── schemas.py         # Token, OAuthUserCreate
│   ├── service.py         # OAuth 비즈니스 로직
│   └── constants.py       # OAuth URLs, scopes
├── users/                  # 사용자 도메인
│   ├── router.py          # User 관리 엔드포인트
│   ├── schemas.py         # UserCreate, UserPublic
│   ├── models.py          # User DB 모델
│   ├── service.py         # User CRUD 로직
│   └── dependencies.py    # 인증 의존성 주입
├── shared/                 # 공통 모듈
│   └── exceptions.py      # 커스텀 예외
├── core/                   # 핵심 설정
│   ├── config.py          # 환경 설정
│   ├── db.py              # DB 초기화
│   └── security.py        # JWT & 암호화
└── main.py                # FastAPI 앱
```

## ⚡ 최신 기술 스택

### Performance-First Stack

| 카테고리        | 기술                   | 이유                             |
| --------------- | ---------------------- | -------------------------------- |
| ORM             | **SQLModel + asyncpg** | psycopg3보다 **5배 빠름**        |
| Vector DB       | **Qdrant**             | ChromaDB보다 빠르고 비용효율적   |
| Cache           | **Redis**              | 업계 표준                        |
| Package Manager | **uv**                 | pip/poetry보다 **10-100배 빠름** |
| Auth            | **OAuth 2.0 + JWT**    | Google, Apple 소셜 로그인        |

### 벤치마크 데이터

**asyncpg vs psycopg3**: 5x faster
**Qdrant vs ChromaDB**:

- Qdrant: 20-50ms latency, production-grade
- ChromaDB: 20ms, 프로토타입용
  **uv vs poetry**: 10-100x faster install

## 주요 기능

- 🔐 **OAuth 인증**: Google, Apple OAuth 2.0
- 🎫 **JWT 토큰**: Access (8일) + Refresh (30일)
- 💉 **의존성 주입**: FastAPI Depends() 패턴
- 🚀 **비동기**: asyncpg로 DB 성능 최적화
- 🗄️ **PostgreSQL**: SQLModel ORM
- 💾 **Redis**: 캐싱
- 🧠 **Qdrant**: 프로덕션급 벡터 DB
- 📦 **uv**: 초고속 패키지 관리

## 빠른 시작

### Prerequisites

- Docker Desktop
- uv (optional, for local dev)

### 🚀 Quick Start (Makefile 사용)

```bash
# 도움말 보기
make help

# 빌드 및 실행 (원스텝!)
make quick-start

# 또는 개발 모드 (코드 변경 시 자동 리로드)
make dev
```

**✨ 자동 마이그레이션**: `entrypoint.sh`가 컨테이너 시작 시 자동으로:

1. ⏳ PostgreSQL 준비 대기
2. 🔄 `alembic upgrade head` 실행
3. 🎉 FastAPI 앱 시작

### 1. Docker로 실행

```bash
# 환경변수 설정
cp .env.example .env
# .env 파일에서 OAuth credentials 설정

# 빌드 및 실행
make build
make up

# 로그 확인
make logs

# 서비스 중지
make down
```

### 2. Makefile 주요 명령어

| 명령어                             | 설명                     |
| ---------------------------------- | ------------------------ |
| `make help`                        | 사용 가능한 명령어 보기  |
| `make quick-start`                 | 빌드 + 실행 (원스텝)     |
| `make dev`                         | Watch 모드 (자동 리로드) |
| `make up`                          | 서비스 시작              |
| `make down`                        | 서비스 중지              |
| `make logs`                        | 전체 로그 보기           |
| `make logs-app`                    | 앱 로그만 보기           |
| `make test`                        | 테스트 실행              |
| `make test-cov`                    | 커버리지 포함 테스트     |
| `make migrate-create MSG="메시지"` | 마이그레이션 생성        |
| `make migrate-history`             | 마이그레이션 히스토리    |
| `make db-shell`                    | PostgreSQL 쉘 열기       |
| `make clean`                       | 컨테이너/볼륨 삭제       |
| `make format`                      | 코드 포맷팅 (ruff)       |
| `make lint`                        | 린트 검사 (ruff)         |

### 3. 데이터베이스 마이그레이션

모델 변경 후 마이그레이션 생성:

```bash
make migrate-create MSG="Add bio field"

# 컨테이너 재시작 시 자동 적용됨
make restart
```

## API 문서

서버 실행 후 접속:

- **Root**: http://localhost:8000/
- **Health Check**: http://localhost:8000/health
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Services

| 서비스     | 포트       | 설명      |
| ---------- | ---------- | --------- |
| FastAPI    | 8000       | API 서버  |
| PostgreSQL | 5432       | 관계형 DB |
| Redis      | 6379       | 캐시      |
| Qdrant     | 6333, 6334 | 벡터 DB   |

## 개발 가이드

### 새 도메인 추가하기

```bash
# 1. 도메인 디렉토리 생성
mkdir -p app/posts

# 2. 필수 파일 생성
touch app/posts/{__init__,router,schemas,models,service,dependencies}.py

# 3. main.py에 라우터 등록
# app.include_router(posts_router.router, prefix="/api/v1/posts", tags=["Posts"])
```

### 도메인 구조 (fastapi-best-practices)

각 도메인은 다음 파일들을 포함:

- `router.py` - API 엔드포인트 정의
- `schemas.py` - Pydantic 모델 (검증)
- `models.py` - SQLModel (DB)
- `service.py` - 비즈니스 로직
- `dependencies.py` - 의존성 주입
- `constants.py` - 상수
- `exceptions.py` - 예외

### Alembic 마이그레이션

```bash
make migrate-create MSG="Add posts table"
make migrate-history
make migrate-down  # 롤백
```

### 테스트

```bash
make test          # 기본 테스트
make test-cov      # 커버리지 포함
make test-local    # 로컬 실행 (uv)
```

## 참고 자료

- [FastAPI Best Practices (14,000+ ⭐)](https://github.com/zhanymkanov/fastapi-best-practices)
- [FastAPI Official Docs](https://fastapi.tiangolo.com/)
- [SQLModel Docs](https://sqlmodel.tiangolo.com/)
- [Qdrant Docs](https://qdrant.tech/documentation/)
- [uv Package Manager](https://docs.astral.sh/uv/)
