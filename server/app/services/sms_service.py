"""
短信提醒服务
────────────────
支持两种发送模式（默认关闭）：
1) webhook：将短信请求转发给外部短信网关
2) twilio：直接调用 Twilio REST API
"""

import asyncio
from datetime import datetime
from typing import List

import httpx
from loguru import logger

from app.core.config import settings


def _split_receivers() -> List[str]:
    raw = (settings.SMS_RECEIVERS or "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


async def _send_via_webhook(to_phone: str, content: str, event: str) -> bool:
    url = (settings.SMS_WEBHOOK_URL or "").strip()
    if not url:
        logger.warning("[SMS] SMS_WEBHOOK_URL 未配置，跳过发送")
        return False

    headers = {"Content-Type": "application/json"}
    token = (settings.SMS_WEBHOOK_TOKEN or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {
        "to": to_phone,
        "content": content,
        "event": event,
        "channel": "sms",
        "timestamp": datetime.now().isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if 200 <= resp.status_code < 300:
                return True
            logger.warning(f"[SMS] webhook 返回异常 status={resp.status_code} body={resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"[SMS] webhook 发送失败: {e}")
        return False


async def _send_via_twilio(to_phone: str, content: str, event: str) -> bool:
    sid = (settings.SMS_TWILIO_ACCOUNT_SID or "").strip()
    token = (settings.SMS_TWILIO_AUTH_TOKEN or "").strip()
    from_phone = (settings.SMS_TWILIO_FROM or "").strip()
    if not sid or not token or not from_phone:
        logger.warning("[SMS] Twilio 配置不完整，跳过发送")
        return False

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = {"To": to_phone, "From": from_phone, "Body": content}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, data=data, auth=(sid, token))
            if 200 <= resp.status_code < 300:
                return True
            logger.warning(f"[SMS] Twilio 返回异常 status={resp.status_code} body={resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"[SMS] Twilio 发送失败: {e}")
        return False


async def send_sms(content: str, event: str = "general", receivers: List[str] = None) -> bool:
    """
    发送短信（异步）
    - content: 短信正文
    - event: 事件类型（signal / intraday_stop / eod_summary / daily_report 等）
    - receivers: 可选覆盖接收人，不传则使用 SMS_RECEIVERS
    """
    if not settings.SMS_ENABLED:
        return False

    to_list = receivers or _split_receivers()
    if not to_list:
        logger.warning("[SMS] 未配置接收号码，跳过发送")
        return False

    provider = (settings.SMS_PROVIDER or "webhook").strip().lower()

    async def _send_one(phone: str) -> bool:
        if provider == "twilio":
            return await _send_via_twilio(phone, content, event)
        return await _send_via_webhook(phone, content, event)

    results = await asyncio.gather(*[_send_one(p) for p in to_list], return_exceptions=True)
    ok = 0
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            logger.error(f"[SMS] 发送异常 to={to_list[i]} err={r}")
            continue
        if r:
            ok += 1

    logger.info(f"[SMS] event={event} sent={ok}/{len(to_list)}")
    return ok > 0


async def send_event_sms(session_name: str, content: str, event: str) -> bool:
    """
    统一事件短信格式，便于后续集中替换模板。
    """
    ts = datetime.now().strftime("%m-%d %H:%M")
    msg = f"[QuantFree][{event}] {ts} {session_name} {content}"
    if len(msg) > 300:
        msg = msg[:297] + "..."
    return await send_sms(msg, event=event)

