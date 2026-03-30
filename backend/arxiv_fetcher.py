"""arxiv API から論文を取得するモジュール。"""

import asyncio
import httpx
import feedparser
from datetime import date, timedelta
from typing import Any
from loguru import logger

ARXIV_API = "https://export.arxiv.org/api/query"
REQUEST_DELAY = 5.0   # arxiv レート制限対応 (秒)
MAX_RETRIES = 4       # 429 時の最大リトライ回数


async def fetch_papers_for_date(
    categories: list[str],
    target_date: date,
    max_results: int = 200,
) -> list[dict[str, Any]]:
    """指定日・カテゴリの arxiv 論文を取得する。"""
    all_papers: list[dict[str, Any]] = []

    date_str = target_date.strftime("%Y%m%d")
    next_str = (target_date + timedelta(days=1)).strftime("%Y%m%d")

    headers = {"User-Agent": "arxiv-reader/1.0 (https://github.com/local/arxiv-reader; research tool)"}
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        for i, cat in enumerate(categories):
            if i > 0:
                await asyncio.sleep(REQUEST_DELAY)

            query = f"cat:{cat} AND submittedDate:[{date_str}0000 TO {next_str}0000]"
            params = {
                "search_query": query,
                "start": 0,
                "max_results": max_results,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }

            try:
                logger.info(f"Fetching {cat} for {target_date}...")
                papers = await _fetch_with_retry(client, params)
                logger.info(f"  {cat}: {len(papers)} papers")
                all_papers.extend(papers)

            except Exception as exc:
                logger.error(f"Failed to fetch {cat}: {exc}")

    # arxiv_id で重複除去
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for p in all_papers:
        if p["arxiv_id"] not in seen:
            seen.add(p["arxiv_id"])
            unique.append(p)

    logger.info(f"Total unique papers: {len(unique)}")
    return unique


async def _fetch_with_retry(client: httpx.AsyncClient, params: dict) -> list[dict[str, Any]]:
    """429 の場合はエクスポネンシャルバックオフでリトライ。"""
    for attempt in range(MAX_RETRIES):
        resp = await client.get(ARXIV_API, params=params)
        if resp.status_code == 429:
            wait = REQUEST_DELAY * (2 ** attempt)
            logger.warning(f"429 レート制限 — {wait:.0f}秒後にリトライ ({attempt+1}/{MAX_RETRIES})")
            await asyncio.sleep(wait)
            continue
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        return [_parse_entry(e) for e in feed.entries]
    raise RuntimeError(f"{MAX_RETRIES} 回リトライしても 429 が解消しませんでした")


def _parse_entry(entry: Any) -> dict[str, Any]:
    # arxiv_id: "2401.12345" 形式に正規化
    arxiv_id = entry.id.split("/abs/")[-1].split("v")[0]

    authors = [a.name for a in getattr(entry, "authors", [])]
    categories = [tag.term for tag in getattr(entry, "tags", [])]

    links = {lk.rel: lk.href for lk in getattr(entry, "links", [])}
    arxiv_url = links.get("alternate", entry.link)
    pdf_url = arxiv_url.replace("/abs/", "/pdf/")

    return {
        "arxiv_id": arxiv_id,
        "title": entry.title.replace("\n", " ").strip(),
        "authors": authors,
        "abstract": entry.summary.replace("\n", " ").strip(),
        "categories": categories,
        "published_date": entry.published[:10],
        "arxiv_url": arxiv_url,
        "pdf_url": pdf_url,
    }
