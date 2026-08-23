"""Hugging Face Inference API client for patch generation."""

from __future__ import annotations

import logging
import re

import httpx

from app.config import settings
from app.logging_config import log_stage

logger = logging.getLogger(__name__)

HF_MODEL_ID = "Qwen/Qwen2.5-Coder-7B-Instruct"
HF_INFERENCE_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL_ID}"

PATCH_PROMPT = """You are an expert Python engineer fixing a failing CI test.

Given the test failure traceback and relevant source code, produce ONLY a valid unified diff patch.
Do not include explanations or markdown fences — output raw unified diff format only.

## Traceback
{traceback}

## Relevant source code
{context}

## Requirements
- Fix the failing test with the smallest correct change.
- Output must start with --- and include +++ and @@ hunk headers.
"""


def parse_hf_response(data: object) -> str:
    if isinstance(data, list) and data:
        item = data[0]
        if isinstance(item, dict):
            return str(item.get("generated_text") or item.get("text") or "")
        return str(item)
    if isinstance(data, dict):
        return str(data.get("generated_text") or data.get("text") or data.get("output") or "")
    return str(data)


def extract_unified_diff(text: str) -> str:
    fenced = re.search(r"```(?:diff)?\s*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1).strip()
        if is_valid_unified_diff(candidate):
            return candidate

    lines: list[str] = []
    capturing = False
    for line in text.splitlines():
        if line.startswith("--- ") or line.startswith("+++ ") or line.startswith("@@"):
            capturing = True
        if capturing:
            lines.append(line)

    candidate = "\n".join(lines).strip()
    if is_valid_unified_diff(candidate):
        return candidate

    raise ValueError("Model output did not contain a valid unified diff")


def is_valid_unified_diff(diff: str) -> bool:
    stripped = diff.strip()
    return (
        stripped.startswith("--- ")
        and "\n+++ " in stripped
        and "@@" in stripped
    )


def generate_patch_diff(traceback: str, context: str, *, token: str | None = None) -> str:
    api_token = token or settings.hf_api_token
    if not api_token:
        raise RuntimeError("HF_API_TOKEN is required for patch generation")

    prompt = PATCH_PROMPT.format(traceback=traceback, context=context)
    log_stage(logger, "generate_patch", "Calling Hugging Face Inference API", model=HF_MODEL_ID)

    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            HF_INFERENCE_URL,
            headers={"Authorization": f"Bearer {api_token}"},
            json={
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 2048,
                    "temperature": 0.1,
                    "return_full_text": False,
                },
            },
        )
        response.raise_for_status()
        raw_text = parse_hf_response(response.json())

    diff = extract_unified_diff(raw_text)
    log_stage(logger, "generate_patch", "Patch diff extracted", diff_lines=len(diff.splitlines()))
    return diff
