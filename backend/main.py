"""
arxiv-reader ローカルサーバー

使い方:
  # デーモンモード (スケジュール実行)
  python main.py

  # 今日の論文をすぐに処理
  python main.py --run-now

  # 特定日を指定して処理
  python main.py --run-now --date 2025-03-28
"""

import asyncio
import os
import sys
from datetime import date
from loguru import logger
from dotenv import load_dotenv
from supabase import create_client, Client
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from pipeline import run_pipeline

load_dotenv()


def build_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        raise ValueError(".env に SUPABASE_URL と SUPABASE_KEY を設定してください")
    return create_client(url, key)


def load_settings() -> dict:
    """ローカル .env から設定を読み込む。"""
    raw_keywords = os.getenv("INTEREST_KEYWORDS", "")
    raw_categories = os.getenv("INTEREST_CATEGORIES", "cs.AI,cs.LG")
    return {
        "interest_keywords": [k.strip() for k in raw_keywords.split(",") if k.strip()],
        "interest_categories": [c.strip() for c in raw_categories.split(",") if c.strip()],
        "score_threshold": float(os.getenv("SCORE_THRESHOLD", "0.6")),
        "max_results": int(os.getenv("MAX_RESULTS", "100")),
        "ollama_url": os.getenv("OLLAMA_URL", "http://localhost:11434"),
        "ollama_model": os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        "notification_type": os.getenv("NOTIFICATION_TYPE", "none"),
        "slack_webhook_url": os.getenv("SLACK_WEBHOOK_URL", ""),
        "email_to": os.getenv("EMAIL_TO", ""),
        "email_smtp_host": os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com"),
        "email_smtp_port": int(os.getenv("EMAIL_SMTP_PORT", "587")),
        "email_smtp_user": os.getenv("EMAIL_SMTP_USER", ""),
        "email_smtp_password": os.getenv("EMAIL_SMTP_PASSWORD", ""),
        "schedule_hour": int(os.getenv("SCHEDULE_HOUR", "8")),
        "schedule_minute": int(os.getenv("SCHEDULE_MINUTE", "0")),
    }


async def scheduled_job(supabase: Client) -> None:
    settings = load_settings()
    await run_pipeline(supabase, settings)


async def main() -> None:
    supabase = build_supabase()

    # ── 即時実行モード ────────────────────────────────────────────────
    if "--run-now" in sys.argv:
        target_date: date | None = None
        if "--date" in sys.argv:
            idx = sys.argv.index("--date")
            target_date = date.fromisoformat(sys.argv[idx + 1])
        settings = load_settings()
        await run_pipeline(supabase, settings, target_date)
        return

    # ── スケジューラーモード ─────────────────────────────────────────
    settings = load_settings()
    hour = int(settings.get("schedule_hour", 8))
    minute = int(settings.get("schedule_minute", 0))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        scheduled_job,
        CronTrigger(hour=hour, minute=minute),
        args=[supabase],
        name="daily_arxiv",
    )
    scheduler.start()
    logger.info(f"スケジューラー起動 — 毎日 {hour:02d}:{minute:02d} に実行")

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("停止しました")


if __name__ == "__main__":
    asyncio.run(main())
