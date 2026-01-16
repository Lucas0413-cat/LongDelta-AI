from __future__ import annotations

from langchain.chat_models import init_chat_model

from src.utils.config import get_settings


def init_llm():
    s = get_settings()
    if not s.llm_api_key:
        raise RuntimeError("LLM_API_KEY is empty. Please set it in .env")

    # 关键：百炼 qwen-* 模型名无法自动推断 provider，必须显式指定为 openai（OpenAI-compatible）
    try:
        return init_chat_model(
            model=s.llm_model,
            model_provider="openai",
            base_url=s.llm_base_url,
            api_key=s.llm_api_key,
            temperature=s.llm_temperature,
            timeout=s.llm_timeout,
        )
    except TypeError:
        # 兼容某些旧版本 langchain 参数名叫 provider
        return init_chat_model(
            model=s.llm_model,
            provider="openai",
            base_url=s.llm_base_url,
            api_key=s.llm_api_key,
            temperature=s.llm_temperature,
            timeout=s.llm_timeout,
        )
