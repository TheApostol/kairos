from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fastapi import HTTPException, status

from config import settings


class TextGenerationProvider(Protocol):
    name: str

    def generate_text(self, prompt: str, *, max_tokens: int = 2000) -> str:
        ...


@dataclass
class AnthropicTextGenerationProvider:
    api_key: str
    name: str = "anthropic"

    def generate_text(self, prompt: str, *, max_tokens: int = 2000) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()


def get_text_generation_provider() -> TextGenerationProvider:
    provider = (settings.AI_PROVIDER or "anthropic").strip().lower()

    if provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ANTHROPIC_API_KEY not configured",
            )
        return AnthropicTextGenerationProvider(api_key=settings.ANTHROPIC_API_KEY)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported AI_PROVIDER: {settings.AI_PROVIDER}",
    )
