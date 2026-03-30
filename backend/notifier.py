"""メール・Slack で論文リストを通知するモジュール。"""

import asyncio
import smtplib
import httpx
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any
from loguru import logger


async def send_notification(
    notification_type: str,
    papers: list[dict[str, Any]],
    target_date: date,
    settings: dict[str, Any],
) -> bool:
    if notification_type == "slack":
        return await _send_slack(papers, target_date, settings)
    if notification_type == "email":
        return await _send_email(papers, target_date, settings)
    return False


# ---------- Slack ----------

async def _send_slack(
    papers: list[dict[str, Any]],
    target_date: date,
    settings: dict[str, Any],
) -> bool:
    url = settings.get("slack_webhook_url", "")
    if not url:
        logger.error("Slack webhook URL が設定されていません")
        return False

    text = _slack_body(papers, target_date)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json={"text": text})
            resp.raise_for_status()
        logger.info(f"Slack 通知送信: {len(papers)} 件")
        return True
    except Exception as exc:
        logger.error(f"Slack 通知失敗: {exc}")
        return False


def _slack_body(papers: list[dict[str, Any]], target_date: date) -> str:
    lines = [
        f"*📄 arxiv 新着論文レポート ({target_date})*",
        f"スコア閾値を超えた論文: *{len(papers)} 件*",
        "",
    ]
    for p in papers[:15]:
        pct = int(p.get("score", 0) * 100)
        reason = p.get("score_reason", "")
        summary = p.get("summary", "")
        authors = p.get("authors") or []
        if len(authors) > 3:
            author_str = ", ".join(authors[:3]) + " et al."
        else:
            author_str = ", ".join(authors)
        lines.append(f"• *[{pct}%]* <{p['arxiv_url']}|{p['title']}>")
        affiliations = p.get("affiliations") or []
        affil_str = " / ".join(affiliations[:2])
        if affil_str and len(affiliations) > 2:
            affil_str += f" 他{len(affiliations)-2}機関"
        if author_str:
            line = f"  👤 {author_str}"
            if affil_str:
                line += f"  ({affil_str})"
            lines.append(line)
        if reason:
            lines.append(f"  _{reason}_")
        if summary:
            short = summary[:200] + "…" if len(summary) > 200 else summary
            lines.append(f"  {short}")
    if len(papers) > 15:
        lines.append(f"\n... 他 {len(papers) - 15} 件")
    return "\n".join(lines)


# ---------- Email ----------

async def _send_email(
    papers: list[dict[str, Any]],
    target_date: date,
    settings: dict[str, Any],
) -> bool:
    smtp_host = settings.get("email_smtp_host", "smtp.gmail.com")
    smtp_port = int(settings.get("email_smtp_port", 587))
    smtp_user = settings.get("email_smtp_user", "")
    smtp_pass = settings.get("email_smtp_password", "")
    email_to = settings.get("email_to", "")

    if not all([smtp_user, smtp_pass, email_to]):
        logger.error("メール設定が不完全です")
        return False

    subject = f"[arxiv-reader] {target_date} — {len(papers)} 件の新着論文"
    body = _email_body(papers, target_date)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = email_to
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _smtp_send(smtp_host, smtp_port, smtp_user, smtp_pass, email_to, msg),
        )
        logger.info(f"メール送信: {email_to} ({len(papers)} 件)")
        return True
    except Exception as exc:
        logger.error(f"メール送信失敗: {exc}")
        return False


def _smtp_send(host, port, user, password, to, msg):
    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(user, to, msg.as_string())


def _email_body(papers: list[dict[str, Any]], target_date: date) -> str:
    lines = [
        f"arxiv 新着論文レポート ({target_date})",
        f"スコア閾値を超えた論文: {len(papers)} 件",
        "=" * 60,
        "",
    ]
    for i, p in enumerate(papers, 1):
        pct = int(p.get("score", 0) * 100)
        authors = p.get("authors", [])
        author_str = ", ".join(authors[:3])
        if len(authors) > 3:
            author_str += " et al."
        lines += [
            f"{i}. [{pct}%] {p['title']}",
            f"   著者: {author_str}",
            f"   評価: {p.get('score_reason', '')}",
            f"   URL:  {p['arxiv_url']}",
            "",
        ]
    return "\n".join(lines)
