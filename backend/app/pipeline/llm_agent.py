from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.pipeline.splitter import Section

_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "fact_extraction.txt"


class DeepSeekAgent:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
    ) -> None:
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self._prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    def extract(self, section: Section) -> dict[str, Any]:
        user_message = self._prompt.replace("{content}", section.content)
        response = self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": user_message}],
            temperature=0.1,
            max_tokens=8192,
        )
        return json.loads(response.choices[0].message.content)
