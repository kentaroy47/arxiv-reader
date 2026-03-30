"""Ollama (Qwen3 8B) で論文のスコアリングと要約を行うモジュール。"""

import asyncio
import json
import re
import httpx
from typing import Any
from loguru import logger

CONCURRENCY = 3  # Ollama への同時リクエスト数


async def score_papers_batch(
    papers: list[dict[str, Any]],
    interests: list[str],
    ollama_url: str,
    model: str,
) -> list[dict[str, Any]]:
    """全論文をスコアリング (非同期・並列制御あり)。"""
    semaphore = asyncio.Semaphore(CONCURRENCY)
    tasks = [
        _score_one(paper, interests, ollama_url, model, semaphore)
        for paper in papers
    ]
    results = await asyncio.gather(*tasks)
    for paper, (score, reason) in zip(papers, results):
        paper["score"] = score
        paper["score_reason"] = reason
    return papers


async def _score_one(
    paper: dict[str, Any],
    interests: list[str],
    ollama_url: str,
    model: str,
    semaphore: asyncio.Semaphore,
) -> tuple[float, str]:
    """1論文のスコアを返す (score: 0.0–1.0, reason: 日本語)。"""
    interests_str = "、".join(interests) if interests else "機械学習、AI"
    prompt = f"""You are a research assistant. Rate this paper's relevance to the researcher's interests.

Researcher's interests: {interests_str}

Title: {paper["title"]}
Abstract: {paper["abstract"][:1500]}

Respond with JSON only (no markdown, no explanation outside JSON):
{{"score": <float 0.0-1.0>, "reason": "<1-2 sentences in Japanese explaining the score>"}}"""

    async with semaphore:
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.post(
                    f"{ollama_url}/api/chat",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "options": {"temperature": 0.1},
                        "think": False,
                        "stream": False,
                    },
                )
                resp.raise_for_status()
                content = resp.json()["message"]["content"]
                data = _extract_json(content)
                score = float(data.get("score", 0.0))
                reason = str(data.get("reason", ""))
                return max(0.0, min(1.0, score)), reason
        except Exception as exc:
            logger.warning(f"Score failed [{paper['arxiv_id']}]: {exc}")
            return 0.0, ""


async def summarize_paper(
    paper: dict[str, Any],
    ollama_url: str,
    model: str,
    full_text: str = "",
) -> str:
    """論文を日本語で要約する。full_text があれば全文、なければ abstract を使用。"""
    body = full_text if full_text else paper["abstract"][:2000]
    prompt = f"""以下の論文を日本語で200〜300字程度に要約してください。
重要な貢献・手法・結果に焦点を当て、専門家向けに簡潔にまとめてください。
要約のみを出力し、前置きは不要です。

タイトル: {paper["title"]}
本文: {body}"""

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{ollama_url}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "options": {"temperature": 0.3},
                    "stream": False,
                },
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()
    except Exception as exc:
        logger.warning(f"Summarize failed [{paper['arxiv_id']}]: {exc}")
        return ""


def _extract_json(text: str) -> dict:
    """LLM 出力から JSON を抽出する。"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}
