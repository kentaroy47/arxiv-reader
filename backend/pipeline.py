"""日次パイプライン: arxiv取得 → LLMスコアリング → Supabase保存 → PDF要約 → 通知。"""

import asyncio
from datetime import date, timedelta
from typing import Any
from loguru import logger
from supabase import Client

from arxiv_fetcher import fetch_papers_for_date, fetch_affiliations, RateLimitError
from llm_scorer import score_papers_batch, summarize_paper
from pdf_downloader import download_and_extract
from notifier import send_notification

MAX_PDF_DOWNLOADS = 20  # 1回のパイプラインでダウンロードする最大件数


async def run_pipeline(
    supabase: Client,
    settings: dict[str, Any],
    target_date: date | None = None,
) -> None:
    use_rss = target_date is None  # 日付未指定 → RSS、指定あり → API
    if target_date is None:
        target_date = date.today()

    logger.info(f"=== パイプライン開始: {target_date} ({'RSS' if use_rss else 'API'}) ===")

    categories: list[str] = settings.get("interest_categories", ["cs.AI", "cs.LG"])
    interests: list[str] = settings.get("interest_keywords", [])
    threshold: float = float(settings.get("score_threshold", 0.6))
    max_results: int = int(settings.get("max_results", 100))
    ollama_url: str = settings.get("ollama_url", "http://localhost:11434")
    model: str = settings.get("ollama_model", "qwen3:8b")
    notif_type: str = settings.get("notification_type", "none")

    # ── Stage 1: Fetch ──────────────────────────────────────────────────
    _log(supabase, "fetch", "running", 0, None, target_date)
    try:
        papers = await fetch_papers_for_date(categories, target_date, max_results, use_rss=use_rss)
        if not papers and not use_rss:
            logger.warning("API で論文が見つかりませんでした — RSS にフォールバック")
            papers = await fetch_papers_for_date(categories, target_date, max_results, use_rss=True)
        _log(supabase, "fetch", "success", len(papers), None, target_date)
    except RateLimitError as exc:
        logger.error(f"API レート制限: {exc} — しばらく待ってから再実行してください")
        _log(supabase, "fetch", "failed", 0, str(exc), target_date)
        return
    except Exception as exc:
        _log(supabase, "fetch", "failed", 0, str(exc), target_date)
        logger.error(f"Fetch 失敗: {exc}")
        return

    if not papers:
        logger.info("論文なし — スキップ")
        return

    # ── 既存 ID を除外 ────────────────────────────────────────────────
    existing = _existing_ids(supabase, [p["arxiv_id"] for p in papers])
    new_papers = [p for p in papers if p["arxiv_id"] not in existing]
    logger.info(f"新規論文: {len(new_papers)} 件 (既存スキップ: {len(papers) - len(new_papers)} 件)")

    # ── Stage 2: Score ──────────────────────────────────────────────────
    if new_papers:
        _log(supabase, "score", "running", 0, None, target_date)
        try:
            if interests:
                scored = await score_papers_batch(new_papers, interests, ollama_url, model)
            else:
                logger.warning("interest_keywords が未設定。スコア 0 で保存します。")
                scored = [{**p, "score": 0.0, "score_reason": ""} for p in new_papers]
            _save_papers(supabase, scored, target_date)
            _log(supabase, "score", "success", len(scored), None, target_date)
        except Exception as exc:
            _log(supabase, "score", "failed", 0, str(exc), target_date)
            logger.error(f"Score 失敗: {exc}")
            return

    # ── Stage 3: 所属機関取得 ────────────────────────────────────────────
    above = _get_above_threshold(supabase, target_date, threshold)
    if above:
        logger.info(f"所属機関取得: {len(above)} 件")
        for i, paper in enumerate(above):
            if i > 0:
                await asyncio.sleep(2.0)
            affiliations = await fetch_affiliations(paper["arxiv_id"])
            if affiliations:
                try:
                    supabase.table("papers").update(
                        {"affiliations": affiliations}
                    ).eq("arxiv_id", paper["arxiv_id"]).execute()
                    logger.info(f"  所属機関保存: {paper['arxiv_id']} — {affiliations[:2]}")
                except Exception as exc:
                    logger.warning(f"  所属機関保存失敗 [{paper['arxiv_id']}]: {exc}")

    # ── Stage 4: PDF 要約 ───────────────────────────────────────────────
    above = _get_above_threshold(supabase, target_date, threshold)
    if above and interests:
        _log(supabase, "summarize", "running", 0, None, target_date)
        try:
            await _summarize_and_save(supabase, above, ollama_url, model)
            _log(supabase, "summarize", "success", min(len(above), MAX_PDF_DOWNLOADS), None, target_date)
        except Exception as exc:
            _log(supabase, "summarize", "failed", 0, str(exc), target_date)
            logger.error(f"Summarize 失敗: {exc}")
        # 要約を含む最新データを再取得
        above = _get_above_threshold(supabase, target_date, threshold)

    # ── Stage 4: Notify ─────────────────────────────────────────────────
    if notif_type != "none":
        above = above if above else _get_above_threshold(supabase, target_date, threshold)
        if above:
            _log(supabase, "notify", "running", 0, None, target_date)
            ok = await send_notification(notif_type, above, target_date, settings)
            _log(supabase, "notify", "success" if ok else "failed", len(above), None, target_date)
        else:
            logger.info("閾値超え論文なし — 通知スキップ")

    logger.info(f"=== パイプライン完了: {target_date} ===")


async def _summarize_and_save(
    supabase: Client,
    papers: list[dict],
    ollama_url: str,
    model: str,
) -> None:
    """閾値超え論文の PDF をダウンロードして要約し Supabase に保存。"""
    targets = papers[:MAX_PDF_DOWNLOADS]
    logger.info(f"PDF 要約開始: {len(targets)} 件")

    for i, paper in enumerate(targets):
        if i > 0:
            await asyncio.sleep(5.0)  # arxiv に優しく

        pdf_url = paper.get("pdf_url", "")
        if not pdf_url:
            continue

        logger.info(f"  [{i+1}/{len(targets)}] {paper['arxiv_id']} ダウンロード中...")
        full_text = await download_and_extract(pdf_url)
        summary = await summarize_paper(paper, ollama_url, model, full_text=full_text)

        if summary:
            try:
                supabase.table("papers").update(
                    {"summary": summary}
                ).eq("arxiv_id", paper["arxiv_id"]).execute()
                logger.info(f"  要約保存完了: {paper['arxiv_id']}")
            except Exception as exc:
                logger.error(f"  要約保存失敗 [{paper['arxiv_id']}]: {exc}")


# ── Supabase ヘルパー ─────────────────────────────────────────────────────

def _existing_ids(supabase: Client, ids: list[str]) -> set[str]:
    try:
        resp = supabase.table("papers").select("arxiv_id").in_("arxiv_id", ids).execute()
        return {r["arxiv_id"] for r in resp.data}
    except Exception as exc:
        logger.warning(f"既存 ID 取得失敗: {exc}")
        return set()


def _save_papers(supabase: Client, papers: list[dict], fetch_date: date) -> None:
    for p in papers:
        try:
            supabase.table("papers").upsert({
                "arxiv_id": p["arxiv_id"],
                "title": p["title"],
                "authors": p["authors"],
                "abstract": p["abstract"],
                "categories": p["categories"],
                "published_date": p["published_date"],
                "arxiv_url": p["arxiv_url"],
                "pdf_url": p.get("pdf_url"),
                "fetch_date": str(fetch_date),
                "score": p.get("score", 0.0),
                "score_reason": p.get("score_reason", ""),
            }).execute()
        except Exception as exc:
            logger.error(f"保存失敗 [{p['arxiv_id']}]: {exc}")


def _get_above_threshold(
    supabase: Client,
    target_date: date,
    threshold: float,
) -> list[dict]:
    try:
        resp = (
            supabase.table("papers")
            .select("*")
            .eq("fetch_date", str(target_date))
            .gte("score", threshold)
            .order("score", desc=True)
            .execute()
        )
        return resp.data
    except Exception as exc:
        logger.error(f"閾値超え論文取得失敗: {exc}")
        return []


def _log(
    supabase: Client,
    stage: str,
    status: str,
    count: int,
    error: str | None,
    target_date: date,
) -> None:
    try:
        supabase.table("pipeline_logs").insert({
            "stage": stage,
            "status": status,
            "papers_processed": count,
            "error_message": error,
            "target_date": str(target_date),
        }).execute()
    except Exception as exc:
        logger.warning(f"ログ保存失敗: {exc}")
