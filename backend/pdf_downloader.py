"""PDF をダウンロードしてテキストを抽出するモジュール。"""

import httpx
import fitz  # pymupdf
from loguru import logger

MAX_CHARS = 8000  # Ollama に渡すテキストの上限 (約2000トークン相当)


async def download_and_extract(pdf_url: str) -> str:
    """PDF をダウンロードしてテキストを返す。失敗時は空文字。"""
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(pdf_url)
            resp.raise_for_status()

        with fitz.open(stream=resp.content, filetype="pdf") as doc:
            text = ""
            for page in doc:
                text += page.get_text()
                if len(text) >= MAX_CHARS:
                    break

        extracted = text[:MAX_CHARS].strip()
        logger.debug(f"PDF 抽出完了: {len(extracted)} 文字")
        return extracted

    except Exception as exc:
        logger.warning(f"PDF 抽出失敗 [{pdf_url}]: {exc}")
        return ""
