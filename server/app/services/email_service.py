"""
每日交易报告邮件服务
────────────────────
使用 Python 内置 smtplib + ssl，无需额外依赖。
支持 QQ / 163 / Gmail SMTP。
"""

import asyncio
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from loguru import logger

from app.core.config import settings


def _split_receivers(sender: str) -> List[str]:
    """
    支持多个收件人：
    - EMAIL_RECEIVER 为空：默认发给 sender
    - EMAIL_RECEIVER 用英文逗号分隔多个邮箱
    """
    raw = (settings.EMAIL_RECEIVER or "").strip()
    if not raw:
        return [sender]
    out = [x.strip() for x in raw.split(",") if x.strip()]
    return out or [sender]


def _build_html(report: dict) -> str:
    """将结构化报告数据渲染为 HTML 邮件正文（4节：绩效摘要/持仓明细/今日信号/近期成交）"""
    today = report["date"]
    sessions = report["sessions"]

    # ── 节1：各会话绩效摘要行 ─────────────────────────────
    session_rows = ""
    for s in sessions:
        ret_color = "#c0392b" if s["total_return_pct"] < 0 else "#27ae60"
        pnl_color = "#c0392b" if s["realized_profit"] < 0 else "#27ae60"
        unreal_color = "#c0392b" if s.get("unrealized_profit", 0) < 0 else "#27ae60"
        session_rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;">{s['name']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:center;">
            <span style="background:#e8f5e9;color:#27ae60;padding:2px 8px;border-radius:4px;font-size:12px;">{s['status']}</span>
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:right;color:{ret_color};font-weight:bold;">
            {s['total_return_pct']:+.2f}%
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:right;">{s.get('total_asset', 0):,.0f}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:right;">{s['available_cash']:,.0f}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:right;color:{pnl_color};">
            {s['realized_profit']:+,.0f}
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:right;color:{unreal_color};">
            {s.get('unrealized_profit', 0):+,.0f}
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:right;">{s['total_trades']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:right;">{s['win_rate']:.1f}%</td>
        </tr>"""

    # ── 节2：持仓明细（跨会话汇总）────────────────────────
    position_rows = ""
    for s in sessions:
        for p in s.get("positions", []):
            unreal = p.get("unrealized_profit", 0)
            unreal_pct = p.get("unrealized_profit_pct", 0)
            color = "#c0392b" if unreal < 0 else "#27ae60"
            position_rows += f"""
            <tr>
              <td style="padding:6px 10px;border-bottom:1px solid #f5f5f5;font-size:13px;">{s['name']}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #f5f5f5;font-size:13px;">{p.get('stock_code','')}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #f5f5f5;font-size:13px;">{p.get('stock_name','')}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #f5f5f5;font-size:13px;text-align:right;">{p.get('quantity',0)}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #f5f5f5;font-size:13px;text-align:right;">¥{p.get('avg_cost',0):.3f}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #f5f5f5;font-size:13px;text-align:right;">¥{p.get('current_price',0):.3f}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #f5f5f5;font-size:13px;text-align:right;color:{color};">
                {unreal:+,.0f}（{unreal_pct:+.2f}%）
              </td>
              <td style="padding:6px 10px;border-bottom:1px solid #f5f5f5;font-size:13px;text-align:right;">{p.get('holding_days',0)}天</td>
            </tr>"""

    if not position_rows:
        position_rows = '<tr><td colspan="8" style="padding:12px;text-align:center;color:#aaa;font-size:13px;">暂无持仓</td></tr>'

    # ── 节3：今日信号明细 ─────────────────────────────────
    signal_rows = ""
    for s in sessions:
        for sig in s.get("today_signals", []):
            mark = "买入" if sig["signal"] == "BUY" else "卖出"
            mark_color = "#27ae60" if sig["signal"] == "BUY" else "#c0392b"
            profit_str = f"¥{sig['profit']:+,.0f}" if sig["signal"] == "SELL" else "-"
            signal_rows += f"""
            <tr>
              <td style="padding:6px 10px;border-bottom:1px solid #f5f5f5;font-size:13px;">{sig['date']}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #f5f5f5;font-size:13px;">{s['name']}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #f5f5f5;font-size:13px;">{sig['stock_code']}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #f5f5f5;font-size:13px;color:{mark_color};font-weight:600;">{mark}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #f5f5f5;font-size:13px;">¥{sig['price']:.2f} × {sig['quantity']}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #f5f5f5;font-size:13px;color:#888;">{profit_str}</td>
            </tr>"""

    if not signal_rows:
        signal_rows = '<tr><td colspan="6" style="padding:12px;text-align:center;color:#aaa;font-size:13px;">今日无成交信号</td></tr>'

    # ── 节4：近期成交记录（跨会话汇总，最近10条）──────────
    trade_rows = ""
    for s in sessions:
        for t in s.get("recent_trades", []):
            direction = "买入" if t["signal"] == "BUY" else "卖出"
            dir_color = "#27ae60" if t["signal"] == "BUY" else "#c0392b"
            profit = t.get("profit", 0)
            profit_color = "#c0392b" if profit < 0 else ("#27ae60" if profit > 0 else "#888")
            profit_str = f"¥{profit:+,.0f}" if t["signal"] == "SELL" else "-"
            trade_rows += f"""
            <tr>
              <td style="padding:6px 10px;border-bottom:1px solid #f5f5f5;font-size:13px;">{t['date']}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #f5f5f5;font-size:13px;">{s['name']}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #f5f5f5;font-size:13px;">{t['stock_code']}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #f5f5f5;font-size:13px;color:{dir_color};font-weight:600;">{direction}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #f5f5f5;font-size:13px;">¥{t['price']:.2f} × {t['quantity']}</td>
              <td style="padding:6px 10px;border-bottom:1px solid #f5f5f5;font-size:13px;color:{profit_color};">{profit_str}</td>
            </tr>"""

    if not trade_rows:
        trade_rows = '<tr><td colspan="6" style="padding:12px;text-align:center;color:#aaa;font-size:13px;">暂无成交记录</td></tr>'

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="max-width:760px;margin:32px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#1a73e8,#0d47a1);padding:28px 32px;">
      <h1 style="margin:0;color:#fff;font-size:22px;">QuantFree 每日交易报告</h1>
      <p style="margin:6px 0 0;color:rgba(255,255,255,.8);font-size:14px;">{today} · 全自动交易系统</p>
    </div>

    <!-- 节1：会话绩效汇总 -->
    <div style="padding:24px 32px 0;">
      <h2 style="margin:0 0 14px;font-size:16px;color:#333;">会话绩效汇总</h2>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <thead>
          <tr style="background:#f8f9fa;">
            <th style="padding:10px 12px;text-align:left;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">会话</th>
            <th style="padding:10px 12px;text-align:center;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">状态</th>
            <th style="padding:10px 12px;text-align:right;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">累计收益</th>
            <th style="padding:10px 12px;text-align:right;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">总资产</th>
            <th style="padding:10px 12px;text-align:right;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">可用资金</th>
            <th style="padding:10px 12px;text-align:right;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">已实现盈亏</th>
            <th style="padding:10px 12px;text-align:right;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">浮动盈亏</th>
            <th style="padding:10px 12px;text-align:right;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">成交笔数</th>
            <th style="padding:10px 12px;text-align:right;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">胜率</th>
          </tr>
        </thead>
        <tbody>{session_rows}</tbody>
      </table>
    </div>

    <!-- 节2：持仓明细 -->
    <div style="padding:24px 32px 0;">
      <h2 style="margin:0 0 14px;font-size:16px;color:#333;">持仓明细</h2>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <thead>
          <tr style="background:#f8f9fa;">
            <th style="padding:8px 10px;text-align:left;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">会话</th>
            <th style="padding:8px 10px;text-align:left;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">股票代码</th>
            <th style="padding:8px 10px;text-align:left;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">股票名称</th>
            <th style="padding:8px 10px;text-align:right;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">持仓量</th>
            <th style="padding:8px 10px;text-align:right;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">成本价</th>
            <th style="padding:8px 10px;text-align:right;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">现价</th>
            <th style="padding:8px 10px;text-align:right;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">浮动盈亏</th>
            <th style="padding:8px 10px;text-align:right;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">持仓天数</th>
          </tr>
        </thead>
        <tbody>{position_rows}</tbody>
      </table>
    </div>

    <!-- 节3：今日信号 -->
    <div style="padding:24px 32px 0;">
      <h2 style="margin:0 0 14px;font-size:16px;color:#333;">今日成交信号</h2>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <thead>
          <tr style="background:#f8f9fa;">
            <th style="padding:8px 10px;text-align:left;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">时间</th>
            <th style="padding:8px 10px;text-align:left;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">会话</th>
            <th style="padding:8px 10px;text-align:left;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">股票</th>
            <th style="padding:8px 10px;text-align:left;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">操作</th>
            <th style="padding:8px 10px;text-align:left;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">价格×数量</th>
            <th style="padding:8px 10px;text-align:left;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">盈亏</th>
          </tr>
        </thead>
        <tbody>{signal_rows}</tbody>
      </table>
    </div>

    <!-- 节4：近期成交记录 -->
    <div style="padding:24px 32px 0;">
      <h2 style="margin:0 0 14px;font-size:16px;color:#333;">近期成交记录</h2>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <thead>
          <tr style="background:#f8f9fa;">
            <th style="padding:8px 10px;text-align:left;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">日期</th>
            <th style="padding:8px 10px;text-align:left;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">会话</th>
            <th style="padding:8px 10px;text-align:left;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">股票代码</th>
            <th style="padding:8px 10px;text-align:left;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">方向</th>
            <th style="padding:8px 10px;text-align:left;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">成交价×数量</th>
            <th style="padding:8px 10px;text-align:left;color:#666;font-weight:600;border-bottom:2px solid #e0e0e0;">盈亏</th>
          </tr>
        </thead>
        <tbody>{trade_rows}</tbody>
      </table>
    </div>

    <!-- Footer -->
    <div style="padding:24px 32px;margin-top:24px;border-top:1px solid #eee;text-align:center;color:#aaa;font-size:12px;">
      QuantFree 全自动交易系统 · 仅供参考，不构成投资建议
    </div>
  </div>
</body>
</html>"""


def _send_email_sync(subject: str, html_body: str) -> bool:
    """同步发送邮件（在线程池中调用）"""
    sender = settings.EMAIL_SENDER
    auth_code = settings.EMAIL_AUTH_CODE

    if not sender or not auth_code:
        logger.warning("[Email] EMAIL_SENDER 或 EMAIL_AUTH_CODE 未配置，跳过发送")
        return False
    receivers = _split_receivers(sender)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"QuantFree <{sender}>"
    msg["To"] = ", ".join(receivers)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            settings.EMAIL_SMTP_HOST, settings.EMAIL_SMTP_PORT, context=context
        ) as srv:
            srv.login(sender, auth_code)
            srv.sendmail(sender, receivers, msg.as_string())
        logger.info(f"[Email] 报告已发送至 {receivers}")
        return True
    except Exception as e:
        logger.error(f"[Email] 发送失败: {e}")
        return False


async def send_daily_report(report: dict) -> bool:
    """异步发送每日报告（不阻塞事件循环）"""
    if not settings.EMAIL_ENABLED:
        return False

    today = report["date"]
    # 计算总收益（多会话平均）
    sessions = report["sessions"]
    avg_ret = sum(s["total_return_pct"] for s in sessions) / len(sessions) if sessions else 0.0
    trend = "📈" if avg_ret >= 0 else "📉"
    subject = f"{trend} QuantFree 交易日报 {today} · 平均收益 {avg_ret:+.2f}%"

    html = _build_html(report)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _send_email_sync, subject, html)
