"""Nạp prompt từ file .md.

Biến trong .md dùng {{ten}} (mustache) chứ không phải {ten} (f-string mặc định
của LangChain)
"""

from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

_PROMPT_DIR = Path(__file__).resolve().parent


def load_prompt(name: str) -> ChatPromptTemplate:
    """Nạp `app/prompt/<name>.md` làm system prompt.

    Args:
        name: đường dẫn tương đối trong app/prompt, không có `.md`.
            Ví dụ ``"rewrite/rewrite_node"``.

    Returns:
        ChatPromptTemplate gồm system (nội dung .md) + history + message,
        ghép thẳng: ``load_prompt(...) | llm``.

    Thiếu biến sẽ raise khi ``invoke`` — không điền rỗng âm thầm.
    """
    path = (_PROMPT_DIR / f"{name}.md").resolve()
    if not path.is_relative_to(_PROMPT_DIR):
        raise ValueError(f"prompt nằm ngoài {_PROMPT_DIR}: {name!r}")
    if not path.is_file():
        raise FileNotFoundError(f"không có prompt: {path}")

    return ChatPromptTemplate.from_messages(
        [
            ("system", path.read_text(encoding="utf-8").strip()),
            MessagesPlaceholder("history"),
            ("human", "{{message}}"),
        ],
        template_format="mustache",
    )
