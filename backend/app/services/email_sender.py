"""
# email_sender.py - SMTP Email Sender
# Version: 0.2.0
# Description: 관리자 리포트 이메일 발송 (SMTP)
# Changes:
#   - 0.2.0: KST 시간 표시, AI 내러티브 포함, 뱃지/시간 간격 수정
#   - 0.1.0: 초기 구현
"""

import logging
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import get_settings

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


def _build_html_email(
    title: str,
    summary: str,
    report_type: str,
    severity: str,
    report_id: str | None = None,
    narrative: str | None = None,
) -> str:
    """리포트 이메일 HTML 템플릿"""
    settings = get_settings()
    severity_color = {
        "info": "#3b82f6",
        "warning": "#f59e0b",
        "critical": "#ef4444",
    }.get(severity, "#6b7280")

    type_label = {
        "weekly": "주간 리포트",
        "monthly": "월간 리포트",
        "alert": "알림 리포트",
        "mlops": "MLOps 학습 리포트",
    }.get(report_type, report_type)

    now_kst = datetime.now(KST)
    time_str = now_kst.strftime("%Y-%m-%d %H:%M") + " KST"

    # 대시보드 링크 (CORS_ORIGINS의 첫 번째 origin 사용)
    base_url = settings.cors_origin_list[0] if settings.cors_origin_list else "http://localhost:10880"
    dashboard_url = f"{base_url}/admin/reports"

    link_html = f"""<div style="margin-top: 20px; text-align: center;">
        <a href="{dashboard_url}" style="display: inline-block; background: #3b82f6; color: #ffffff; padding: 10px 24px; border-radius: 6px; text-decoration: none; font-size: 14px; font-weight: 500;">대시보드에서 상세 보기</a>
      </div>"""

    # AI 내러티브 섹션
    narrative_html = ""
    if narrative:
        narrative_escaped = narrative.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        narrative_html = f"""<div style="background: #eef2ff; border: 1px solid #c7d2fe; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
        <div style="font-size: 12px; font-weight: 600; color: #4338ca; margin-bottom: 8px;">AI 운영 요약</div>
        <div style="font-size: 13px; color: #312e81; line-height: 1.7; white-space: pre-line;">{narrative_escaped}</div>
      </div>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8fafc; padding: 20px;">
  <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
    <div style="background: #0f172a; padding: 20px 24px;">
      <h1 style="color: #ffffff; font-size: 18px; margin: 0;">News Origin</h1>
      <div style="display: flex; align-items: center; gap: 12px; margin-top: 8px;">
        <span style="background: {severity_color}; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 12px;">{type_label}</span>
        <span style="color: #94a3b8; font-size: 12px;">{time_str}</span>
      </div>
    </div>
    <div style="padding: 24px;">
      <h2 style="color: #1e293b; font-size: 16px; margin: 0 0 16px 0;">{title}</h2>
      {narrative_html}
      <div style="color: #475569; font-size: 14px; line-height: 1.6; white-space: pre-line;">{summary}</div>
      {link_html}
      <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
      <p style="color: #94a3b8; font-size: 12px; margin: 0;">
        이 메일은 News Origin 시스템에서 자동 발송되었습니다.
      </p>
    </div>
  </div>
</body>
</html>"""


def send_report_email(
    title: str,
    summary: str,
    report_type: str,
    severity: str = "info",
    report_id: str | None = None,
    narrative: str | None = None,
) -> bool:
    """
    리포트 이메일 발송.
    Returns True on success, False if SMTP not configured.
    Raises on SMTP connection/send failure.
    """
    settings = get_settings()

    if not all([settings.smtp_host, settings.smtp_user, settings.smtp_pass, settings.admin_email]):
        logger.warning("SMTP 설정 미완료 — 이메일 발송 스킵")
        return False

    from_email = settings.smtp_from_email or settings.smtp_user

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[News Origin] {title}"
    msg["From"] = from_email
    msg["To"] = settings.admin_email

    # Plain text fallback (내러티브 포함)
    plain_parts = [title, ""]
    if narrative:
        plain_parts.append("[AI 운영 요약]")
        plain_parts.append(narrative)
        plain_parts.append("")
    plain_parts.append(summary)
    msg.attach(MIMEText("\n".join(plain_parts), "plain", "utf-8"))

    # HTML version
    html = _build_html_email(title, summary, report_type, severity, report_id, narrative)
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        if settings.smtp_use_tls:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10)

        server.login(settings.smtp_user, settings.smtp_pass)
        server.sendmail(from_email, [settings.admin_email], msg.as_string())
        server.quit()
        logger.info(f"리포트 이메일 발송 완료: {title}")
        return True
    except Exception as e:
        logger.error(f"이메일 발송 실패: {e}")
        raise
