"""토큰 시스템 상수."""

# 채팅/초안 토큰 소모량
CHAT_TOKEN_COST = 5
DRAFT_TOKEN_COST = 10

# 플랜별 월 지급 토큰
PLAN_MONTHLY_TOKENS: dict[str, int] = {
    "free": 50,    # 구독 없음 또는 비활성
    "lite": 400,
    "pro": 2000,
}

# 이벤트 토큰
SIGNUP_BONUS_TOKENS = 50        # 신규 가입 1회성 보너스
ATTENDANCE_TOKENS = 3           # 출석 시 지급
REFERRAL_TOKENS = 10            # 초대 성공 시 양쪽 각각

# 출석 이벤트 총 풀 (이 값 소진 시 출석 이벤트 종료)
ATTENDANCE_EVENT_TOTAL_POOL = 30_000
