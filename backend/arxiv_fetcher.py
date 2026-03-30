"""arxiv RSS フィードから論文を取得するモジュール。

API (export.arxiv.org) の代わりに RSS を使用することで
レート制限を回避する。RSS は当日の最新バッチを返す。
"""

import asyncio
import re
import httpx
import feedparser
from datetime import date
from typing import Any
from loguru import logger

RSS_BASE = "https://rss.arxiv.org/rss"
REQUEST_DELAY = 3.0  # カテゴリ間の待機 (秒)
HEADERS = {"User-Agent": "arxiv-reader/1.0 (research tool; mailto:local)"}


async def fetch_papers_for_date(
    categories: list[str],
    target_date: date,
    max_results: int = 200,
) -> list[dict[str, Any]]:
    """RSS フィードから指定カテゴリの論文を取得する。

    RSS は「直近の提出バッチ」を返すため、target_date は
    取得後のフィルタリングに使用する（当日実行が前提）。
    """
    all_papers: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=30.0, headers=HEADERS) as client:
        for i, cat in enumerate(categories):
            if i > 0:
                await asyncio.sleep(REQUEST_DELAY)
            try:
                logger.info(f"RSS 取得中: {cat} ...")
                papers = await _fetch_rss(client, cat, max_results)
                logger.info(f"  {cat}: {len(papers)} 件")
                all_papers.extend(papers)
            except Exception as exc:
                logger.error(f"RSS 取得失敗 [{cat}]: {exc}")

    # arxiv_id で重複除去
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for p in all_papers:
        if p["arxiv_id"] not in seen:
            seen.add(p["arxiv_id"])
            unique.append(p)

    logger.info(f"合計ユニーク論文数: {len(unique)}")
    return unique


async def _fetch_rss(
    client: httpx.AsyncClient,
    category: str,
    max_results: int,
) -> list[dict[str, Any]]:
    url = f"{RSS_BASE}/{category}"
    resp = await client.get(url)
    resp.raise_for_status()

    feed = feedparser.parse(resp.text)
    papers = [_parse_entry(e) for e in feed.entries if _parse_entry(e)]
    return papers[:max_results]


def _parse_entry(entry: Any) -> dict[str, Any] | None:
    try:
        # arxiv_id を URL から抽出
        link = getattr(entry, "link", "") or getattr(entry, "id", "")
        m = re.search(r"arxiv\.org/abs/([^\sv]+)", link)
        if not m:
            return None
        arxiv_id = re.sub(r"v\d+$", "", m.group(1))

        # タイトル (RSS は "[category] Title" 形式のことがある)
        title = entry.title.strip()
        title = re.sub(r"^\[.+?\]\s*", "", title)

        # アブストラクト
        raw_summary = getattr(entry, "summary", "")
        abstract = re.sub(r"<[^>]+>", "", raw_summary).strip()
        abstract = re.sub(r"^Abstract:\s*", "", abstract)

        # 著者 (RSS では entry.author が文字列のことが多い)
        if hasattr(entry, "authors") and entry.authors:
            authors = [a.get("name", "") for a in entry.authors]
        elif hasattr(entry, "author"):
            authors = [a.strip() for a in entry.author.split(",")]
        else:
            authors = []

        # カテゴリ
        categories = [tag.term for tag in getattr(entry, "tags", [])]

        # 公開日
        published_date = ""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            from datetime import date as _date
            t = entry.published_parsed
            published_date = _date(t.tm_year, t.tm_mon, t.tm_mday).isoformat()
        elif hasattr(entry, "published"):
            published_date = entry.published[:10]

        arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

        return {
            "arxiv_id": arxiv_id,
            "title": title.replace("\n", " "),
            "authors": authors,
            "abstract": abstract.replace("\n", " "),
            "categories": categories,
            "published_date": published_date,
            "arxiv_url": arxiv_url,
            "pdf_url": pdf_url,
        }
    except Exception as exc:
        logger.warning(f"エントリ解析失敗: {exc}")
        return None
