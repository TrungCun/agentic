from typing import Annotated, List, TypedDict

from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage

from app.schemas.ctx_schema import ContextCard


class AppState(TypedDict, total=False):
    """Base state của app.

    `raw_query` và mọi dạng query đã xử lý là hai thứ tách biệt về mặt cấu
    trúc, không phải hai biến cùng kiểu string. Node `generate` nhận
    `raw_query`; query đã rewrite chết sau `project` và không bao giờ chạm
    tới generation (nguyên tắc N2, docs/process_query.md).
    """

    raw_query: str                                    # nguyên văn người dùng, không sửa
    turn: int                                         # lượt hiện tại, dùng cho ConvSpan
    history: Annotated[List[BaseMessage], add_messages]

    ctx_card: ContextCard                             # xem docs/ctx_kernel.md
