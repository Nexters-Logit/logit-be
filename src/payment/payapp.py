"""PayApp REST API 클라이언트."""

import urllib.parse
from datetime import date, timedelta

import httpx

PAYAPP_API_URL = "https://api.payapp.kr/oapi/apiLoad.html"


def _parse_response(text: str) -> dict[str, str]:
    """URL-encoded 응답을 파싱한다. key=value&key=value → dict."""
    return dict(urllib.parse.parse_qsl(text, keep_blank_values=True))


def _rebill_cycle_day() -> str:
    """
    오늘 날짜를 정기결제 주기일로 반환한다.
    29~31일은 월에 따라 해당 날짜가 없을 수 있으므로 90(말일)으로 처리.
    """
    day = date.today().day
    return "90" if day >= 29 else str(day)


async def register_rebill(
    *,
    userid: str,
    linkkey: str,
    good_name: str,
    price: int,
    user_id: str,
    plan_key: str,
    feedback_url: str,
    phone: str,
    return_url: str = "",
    cycle_day: int | None = None,
) -> dict[str, str]:
    """
    PayApp rebillRegist 호출 — 정기 결제 등록 URL을 반환한다.

    Args:
        userid: PayApp 가맹점 ID
        linkkey: PayApp 연동키
        good_name: 결제 상품명
        price: 결제 금액 (KRW)
        user_id: 내부 유저 ID (var1 — 웹훅 매칭용)
        plan_key: 플랜 키 (mcp:basic / logit:lite / logit:pro) (var2)
        feedback_url: 결제 완료 후 PayApp이 POST할 웹훅 URL
        phone: 구매자 전화번호
        return_url: 결제 완료 후 사용자 리다이렉트 URL (선택)
        cycle_day: 매월 결제일 (재구독 시 기존 만료일 기준, None이면 오늘 날짜)

    Returns:
        PayApp 응답 dict. 성공 시 'payurl', 'rebill_no' 포함.
    """
    expire_date = (date.today() + timedelta(days=365 * 10)).strftime("%Y-%m-%d")

    if cycle_day is not None:
        rebill_cycle_month = "90" if cycle_day >= 29 else str(cycle_day)
    else:
        rebill_cycle_month = _rebill_cycle_day()

    payload = {
        "cmd": "rebillRegist",
        "userid": userid,
        "linkkey": linkkey,
        "goodname": good_name,
        "goodprice": str(price),
        "rebillCycleType": "Month",
        "rebillCycleMonth": rebill_cycle_month,
        "rebillExpire": expire_date,
        "var1": user_id,
        "var2": plan_key,
        "smsuse": "n",
        "feedbackurl": feedback_url,
        "recvphone": phone,
    }
    if return_url:
        payload["returnurl"] = return_url

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            PAYAPP_API_URL,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()

    return _parse_response(resp.text)


async def cancel_rebill(
    *,
    userid: str,
    linkkey: str,
    rebill_no: str,
) -> dict[str, str]:
    """
    PayApp rebillOff 호출 — 정기결제를 해지한다.

    Returns:
        PayApp 응답 dict. 성공 시 state='1'.
    """
    payload = {
        "cmd": "rebillOff",
        "userid": userid,
        "linkkey": linkkey,
        "rebill_no": rebill_no,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            PAYAPP_API_URL,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()

    return _parse_response(resp.text)
