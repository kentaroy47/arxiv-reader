"""arxiv 論文取得モジュール。

日次実行: RSS フィード（今日アナウンスされたバッチ）
日付指定: arxiv API（submittedDate フィルタ）
"""

import asyncio
import re
import httpx
import feedparser
from bs4 import BeautifulSoup
from datetime import date, timedelta
from typing import Any
from loguru import logger

ARXIV_API = "https://export.arxiv.org/api/query"
RSS_BASE = "https://rss.arxiv.org/rss"
REQUEST_DELAY = 15.0
MAX_RETRIES = 5
HEADERS = {"User-Agent": "arxiv-reader/1.0 (research tool; mailto:local)"}


class RateLimitError(Exception):
    """arxiv API がレート制限を返し続けた場合に送出される。"""


async def fetch_papers_for_date(
    categories: list[str],
    target_date: date,
    max_results: int = 200,
    use_rss: bool = False,
) -> list[dict[str, Any]]:
    """論文を取得する。use_rss=True または日付未指定時は RSS を使用。
    レート制限が解消しない場合は RateLimitError を送出する。
    """
    if use_rss:
        return await _fetch_rss_all(categories, max_results)
    return await _fetch_api_all(categories, target_date, max_results)


async def _fetch_rss_all(categories: list[str], max_results: int) -> list[dict[str, Any]]:
    """RSS フィードから最新アナウンスバッチを取得。"""
    all_papers: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=30.0, headers=HEADERS) as client:
        for i, cat in enumerate(categories):
            if i > 0:
                await asyncio.sleep(3.0)
            try:
                logger.info(f"RSS 取得中: {cat} ...")
                resp = await client.get(f"{RSS_BASE}/{cat}")
                resp.raise_for_status()
                feed = feedparser.parse(resp.text)
                papers = [p for e in feed.entries if (p := _parse_rss_entry(e))]
                logger.info(f"  {cat}: {len(papers)} 件")
                all_papers.extend(papers[:max_results])
            except Exception as exc:
                logger.error(f"RSS 取得失敗 [{cat}]: {exc}")
    return _dedup(all_papers)


async def _fetch_api_all(
    categories: list[str], target_date: date, max_results: int
) -> list[dict[str, Any]]:
    """arxiv API で指定日の論文を取得。レート制限が解消しない場合は RateLimitError を送出する。"""
    all_papers: list[dict[str, Any]] = []
    rate_limited = False
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
            except RateLimitError:
                rate_limited = True
                logger.error(f"API レート制限 [{cat}]: スキップして続行")
            except Exception as exc:
                logger.error(f"API 取得失敗 [{cat}]: {exc}")

    if rate_limited and not all_papers:
        raise RateLimitError("全カテゴリがレート制限されました")
    return _dedup(all_papers)


async def _fetch_with_retry(client: httpx.AsyncClient, params: dict) -> list[dict[str, Any]]:
    for attempt in range(MAX_RETRIES):
        resp = await client.get(ARXIV_API, params=params)
        if resp.status_code == 429:
            wait = REQUEST_DELAY * (2 ** attempt)
            logger.warning(f"429 レート制限 — {wait:.0f}秒後にリトライ ({attempt+1}/{MAX_RETRIES})")
            await asyncio.sleep(wait)
            continue
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        return [p for e in feed.entries if (p := _parse_api_entry(e))]
    raise RateLimitError(f"{MAX_RETRIES} 回リトライしても 429 が解消しませんでした")


def _dedup(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique = []
    for p in papers:
        if p["arxiv_id"] not in seen:
            seen.add(p["arxiv_id"])
            unique.append(p)
    logger.info(f"合計ユニーク論文数: {len(unique)}")
    return unique


def _parse_api_entry(entry: Any) -> dict[str, Any] | None:
    try:
        arxiv_id = re.sub(r"v\d+$", "", entry.id.split("/abs/")[-1])
        authors = [a.name for a in getattr(entry, "authors", [])]
        categories = [tag.term for tag in getattr(entry, "tags", [])]
        links = {lk.rel: lk.href for lk in getattr(entry, "links", [])}
        arxiv_url = links.get("alternate", entry.link)
        return {
            "arxiv_id": arxiv_id,
            "title": entry.title.replace("\n", " ").strip(),
            "authors": authors,
            "abstract": entry.summary.replace("\n", " ").strip(),
            "categories": categories,
            "published_date": entry.published[:10],
            "arxiv_url": arxiv_url,
            "pdf_url": arxiv_url.replace("/abs/", "/pdf/"),
        }
    except Exception as exc:
        logger.warning(f"API エントリ解析失敗: {exc}")
        return None


def _parse_rss_entry(entry: Any) -> dict[str, Any] | None:
    try:
        link = getattr(entry, "link", "") or getattr(entry, "id", "")
        m = re.search(r"arxiv\.org/abs/([^\sv]+)", link)
        if not m:
            return None
        arxiv_id = re.sub(r"v\d+$", "", m.group(1))
        title = re.sub(r"^\[.+?\]\s*", "", entry.title.strip())
        abstract = re.sub(r"<[^>]+>", "", getattr(entry, "summary", "")).strip()
        abstract = re.sub(r"^Abstract:\s*", "", abstract)
        if hasattr(entry, "authors") and entry.authors:
            authors = [a.get("name", "") for a in entry.authors]
        elif hasattr(entry, "author"):
            authors = [a.strip() for a in entry.author.split(",")]
        else:
            authors = []
        categories = [tag.term for tag in getattr(entry, "tags", [])]
        published_date = ""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            t = entry.published_parsed
            published_date = date(t.tm_year, t.tm_mon, t.tm_mday).isoformat()
        elif hasattr(entry, "published"):
            published_date = entry.published[:10]
        arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"
        return {
            "arxiv_id": arxiv_id,
            "title": title.replace("\n", " "),
            "authors": authors,
            "abstract": abstract.replace("\n", " "),
            "categories": categories,
            "published_date": published_date,
            "arxiv_url": arxiv_url,
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
        }
    except Exception as exc:
        logger.warning(f"RSS エントリ解析失敗: {exc}")
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
