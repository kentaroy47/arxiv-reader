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
    prompt = f"""You are a strict senior reviewer filtering ~500 daily arxiv papers for a busy researcher.
Only a handful per day (about 3%) deserve their attention. Be harsh: the default for a typical paper is LOW.

Researcher's interests: {interests_str}

Rate two things as integers 1–10.

relevance — how central the paper is to the interests:
- 9–10: The core contribution IS one of the interests (e.g. a new LLM serving system, a LiDAR 3D detector for driving).
- 6–8: Clearly within an interest area, but a narrower or adjacent angle.
- 3–5: Shares a keyword only (e.g. "efficient", "3D", "caching") but the actual subject is different
  (video generation, diffusion models, agents, reasoning methods, robot manipulation, weather models, etc.).
- 1–2: Unrelated.

novelty — how new the core idea is (judge the idea, not the claimed numbers):
- 9–10: Rare. A genuinely new problem framing, mechanism, or system design that changes how people approach the area.
- 6–8: A clearly new idea or surprising finding with convincing evidence; not just a recombination of known tricks.
- 3–5: Incremental: a variant/combination of known methods, a new heuristic in a crowded line of work, tuning,
  applying an existing technique to a new model/domain, or a benchmark/dataset/survey without a new insight.
- 1–2: No real new idea.

CROWDED TOPICS — the researcher finds these repetitive: KV cache compression/eviction/offloading,
post-training quantization (low-bit weights/activations/KV), pruning/sparsification, token pruning/merging.
For papers in these topics, novelty must be at most 4 unless the abstract shows a fundamentally different
approach (not another scoring rule, bit-width, grouping, or calibration trick).

Most papers should get novelty 3–5. Do not reward buzzwords, catchy names, or "we achieve X× speedup" alone.

Title: {paper["title"]}
Abstract: {paper["abstract"][:1500]}

Respond with JSON only (no markdown):
{{"relevance": <int>, "novelty": <int>, "reason": "<1-2 sentences in Japanese: what the paper does and what is (or is not) new about it>"}}"""

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
                relevance = max(1.0, min(10.0, float(data.get("relevance", 1))))
                novelty = max(1.0, min(10.0, float(data.get("novelty", 1))))
                reason = str(data.get("reason", ""))
                return _combine(relevance, novelty), reason
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
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{ollama_url}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "options": {"temperature": 0.3},
                    "think": False,
                    "stream": False,
                },
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()
    except Exception as exc:
        logger.warning(f"Summarize failed [{paper['arxiv_id']}]: {exc}")
        return ""


def _combine(relevance: float, novelty: float) -> float:
    """relevance/novelty (1–10) を 0.0–1.0 のスコアに変換。新規性を重視し、両方高くないと高得点にならない。"""
    return round((relevance / 10) ** 0.45 * (novelty / 10) ** 0.55, 3)


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
