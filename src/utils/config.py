from __future__ import annotations

import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class Settings(BaseModel):
    llm_base_url: str = Field(default="https://api.openai.com/v1")
    llm_api_key: str = Field(default="")
    llm_model: str = Field(default="gpt-4o-mini")
    llm_temperature: float = Field(default=0.2)
    llm_timeout: int = Field(default=60)


def get_settings() -> Settings:
    return Settings(
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
        llm_timeout=int(os.getenv("LLM_TIMEOUT", "60")),
    )
