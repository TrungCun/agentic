from functools import lru_cache
from typing import Dict, Optional, Union
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from app.config.log import get_logger, setup_logging
from app.config.config import settings

logger = get_logger(__name__)

@lru_cache(maxsize=32)
def get_llm(
    stream: bool = False,
    reasoning: bool = False,
    profile: Optional[str] = None,
) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        api_key="not-required",
        streaming=stream,
        timeout=60,
        max_retries=2,
        top_p=0.95,
        extra_body={
            "top_k": 64,
            "min_p": 0.0,
            "chat_template_kwargs": {"enable_thinking": reasoning},
        }
    )

#  LLM được export để dùng cho các node
llm = get_llm(stream=False, reasoning=False)
llm_reasoning = get_llm(stream=False, reasoning=True)

llm_stream = get_llm(stream=True, reasoning=False)
llm_stream_reasoning = get_llm(stream=True, reasoning=True)

if __name__ == "__main__":
    setup_logging(service_name="llm_health_check", file_enabled=True)
    try:
        logger.info("LLM Health Check...")
        test_llm = get_llm(stream=False)
        response = test_llm.invoke([HumanMessage(content="Hello, respond with exactly 'OK'")])
        logger.info(f"LLM response: {response.content.strip()}")
    except Exception as e:
        logger.error(f"LLM health check failed: {e}", exc_info=True)
        raise SystemExit(1)
