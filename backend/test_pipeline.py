"""
パイプラインのテストスクリプト (arxiv fetch をスキップ)
  python test_pipeline.py
"""

import asyncio
import os
from datetime import date
from dotenv import load_dotenv
from supabase import create_client
from loguru import logger

from pipeline import run_pipeline

load_dotenv()

MOCK_PAPERS = [
    {
        "arxiv_id": "2210.03679",
        "title": "LiDAR-based SLAM for Autonomous Driving",
        "authors": ["Alice Smith", "Bob Lee"],
        "abstract": (
            "We present a robust LiDAR-based SLAM system for autonomous driving. "
            "Our approach fuses point cloud data with IMU measurements to achieve "
            "centimeter-level localization accuracy in urban environments."
        ),
        "categories": ["cs.RO"],
        "published_date": "2026-03-28",
        "arxiv_url": "https://arxiv.org/abs/2210.03679",
        "pdf_url": "https://arxiv.org/pdf/2210.03679",
    },
]


async def main():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    supabase = create_client(url, key)

    # Supabase から設定を読み込む
    resp = supabase.table("user_settings").select("*").eq("id", 1).execute()
    settings = resp.data[0] if resp.data else {}

    # fetch をモックに差し替え
    import arxiv_fetcher
    import pipeline

    async def _mock_fetch(*a, **kw):
        return MOCK_PAPERS

    pipeline.fetch_papers_for_date = _mock_fetch

    logger.info(f"モック論文 {len(MOCK_PAPERS)} 件でパイプラインをテスト開始")
    await run_pipeline(supabase, settings, date(2026, 3, 28))
    logger.info("テスト完了 — Supabase の papers テーブルを確認してください")


if __name__ == "__main__":
    asyncio.run(main())
