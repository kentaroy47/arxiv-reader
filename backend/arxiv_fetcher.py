"""arxiv API から論文を取得するモジュール。"""

import asyncio
import re
import httpx
import feedparser
from bs4 import BeautifulSoup
from datetime import date, timedelta
from typing import Any
from loguru import logger

ARXIV_API = "https://export.arxiv.org/api/query"
REQUEST_DELAY = 5.0   # カテゴリ間の待機 (秒)
MAX_RETRIES = 4       # 429 時の最大リトライ回数
HEADERS = {"User-Agent": "arxiv-reader/1.0 (research tool; mailto:local)"}


async def fetch_papers_for_date(
    categories: list[str],
    target_date: date,
    max_results: int = 200,
) -> list[dict[str, Any]]:
    """arxiv API で指定日・カテゴリの論文を取得する。"""
    all_papers: list[dict[str, Any]] = []

    date_str = target_date.strftime("%Y%m%d")
    next_str = (target_date + timedelta(days=1)).strftime("%Y%m%d")

    async with httpx.AsyncClient(timeout=30.0, headers=HEADERS) as client:
        for i, cat in enumerate(categories):
            if i > 0:
                await asyncio.sleep(REQUEST_DELAY)
            params = {
                "search_query": f"cat:{cat} AND submittedDate:[{date_str}0000 TO {next_str}0000]",
                "start": 0,
                "max_results": max_results,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
            try:
                logger.info(f"API 取得中: {cat} ({target_date}) ...")
                papers = await _fetch_with_retry(client, params)
                logger.info(f"  {cat}: {len(papers)} 件")
                all_papers.extend(papers)
            except Exception as exc:
                logger.error(f"API 取得失敗 [{cat}]: {exc}")

    # arxiv_id で重複除去
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for p in all_papers:
        if p["arxiv_id"] not in seen:
            seen.add(p["arxiv_id"])
            unique.append(p)

    logger.info(f"合計ユニーク論文数: {len(unique)}")
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
        return [p for e in feed.entries if (p := _parse_entry(e))]
    raise RuntimeError(f"{MAX_RETRIES} 回リトライしても 429 が解消しませんでした")


def _parse_entry(entry: Any) -> dict[str, Any] | None:
    try:
        arxiv_id = entry.id.split("/abs/")[-1]
        arxiv_id = re.sub(r"v\d+$", "", arxiv_id)

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
    except Exception as exc:
        logger.warning(f"エントリ解析失敗: {exc}")
        return None


async def fetch_affiliations(arxiv_id: str) -> list[str]:
    """arxiv HTML ページから所属機関リストを取得する。

    arxiv の HTML 論文ページ (/html/{id}) を解析する。
    HTML 版が存在しない場合は空リストを返す。
    """
    url = f"https://arxiv.org/html/{arxiv_id}"
    try:
        async with httpx.AsyncClient(timeout=20.0, headers=HEADERS, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
        soup = BeautifulSoup(resp.text, "html.parser")
        seen: set[str] = set()
        affiliations: list[str] = []
        for el in soup.select(".ltx_role_affiliation .ltx_note_content, .ltx_author_affiliation"):
            text = el.get_text(" ", strip=True)
            text = re.sub(r"\s+", " ", text).strip()
            if text and text not in seen:
                seen.add(text)
                affiliations.append(text)
        return affiliations
    except Exception as exc:
        logger.warning(f"所属機関取得失敗 [{arxiv_id}]: {exc}")
        return []
