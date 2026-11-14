import config
from services.llm.base import LLMError, LLMProvider


def make_provider(name: str) -> LLMProvider:
    if name == "anthropic":
        from services.llm.anthropic_provider import AnthropicProvider

        if not config.ANTHROPIC_API_KEY:
            raise LLMError("ANTHROPIC_API_KEY is not set (put it in .env)")
        return AnthropicProvider(config.MODELS["anthropic"], config.ANTHROPIC_API_KEY)
    if name == "openai":
        from services.llm.openai_provider import OpenAIProvider

        if not config.OPENAI_API_KEY:
            raise LLMError("OPENAI_API_KEY is not set (put it in .env)")
        return OpenAIProvider(config.MODELS["openai"], config.OPENAI_API_KEY)
    if name == "local":
        from services.llm.openai_provider import OpenAIProvider

        if not config.LOCAL_BASE_URL:
            raise LLMError("LOCAL_LLM_BASE_URL is not set (put it in .env)")
        if not config.LOCAL_MODEL:
            raise LLMError("LOCAL_LLM_MODEL is not set (put it in .env)")
        return OpenAIProvider(
            config.LOCAL_MODEL, config.LOCAL_API_KEY, base_url=config.LOCAL_BASE_URL, name="local"
        )
    raise ValueError(f"unknown provider {name!r}")
