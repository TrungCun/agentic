"""Schema output của rewrite_node.

Hợp đồng (docs/process_query.md §3): model KHÔNG trả về chuỗi cuối. Nó trả về
danh sách cặp span/thay-thế, và code ghép lại sau khi xác minh từng cặp.

Cách này chặn bốn kiểu hỏng của model nhỏ mà một chuỗi tự do không chặn được:
phình chữ, bịa thực thể, rò rỉ khuôn mẫu ("Chắc chắn rồi! Đây là..."), và
trôi ngôn ngữ.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

__all__ = [
    "EditType",
    "SpanReplacement",
    "RewriteProposal",
    "RejectionReason",
    "RewriteResult",
]


class EditType(str, Enum):
    """Bốn phép sửa của Choi et al. (TACL 2021), mức rủi ro rất khác nhau."""

    RESOLVE_REFERENT = "resolve_referent"    # "nó" -> "Điều 15". Rủi ro thấp.
    DROP_MARKER = "drop_marker"              # "còn khoản 3" -> "khoản 3". Regex làm được.
    BRIDGE_SCOPE = "bridge_scope"            # thêm "theo Nghị định 15/2020". Rủi ro cao.
    ADD_BACKGROUND = "add_background"        # thêm cụm giới từ. Rủi ro cao nhất.


#: Phép xoá DUY NHẤT được phép. Mọi thứ bị xoá ngoài discourse marker là vi
#: phạm hợp đồng bảo toàn nghĩa (nguyên tắc N1).
DELETING_EDITS: frozenset[EditType] = frozenset({EditType.DROP_MARKER})


class SpanReplacement(BaseModel):
    """Một phép sửa. `span` phải khớp nguyên văn trong raw query."""

    span: str = Field(..., min_length=1, description="Đoạn nguyên văn trong câu hỏi gốc")
    replaces_with: str = Field(..., description="Thay bằng gì; rỗng nghĩa là xoá")
    edit_type: EditType


class RewriteProposal(BaseModel):
    """Output thô của LLM, chưa xác minh.

    Constrained decoding chỉ áp cho khối này ở cuối lần gọi — phần suy luận đi
    trước phải để tự do (format tax, docs/process_query.md §3).
    """

    needs_rewrite: bool = Field(
        default=False,
        description="False nếu câu đã độc lập ngữ cảnh; khi đó replacements rỗng",
    )
    replacements: list[SpanReplacement] = Field(default_factory=list)


class RejectionReason(str, Enum):
    """Vì sao một đề xuất bị loại.

    Bắt buộc log: không có trường này thì không phân biệt được "rewrite không
    cần thiết" với "rewrite luôn bị chặn" — hai trạng thái nhìn giống hệt nhau
    từ bên ngoài.
    """

    SPAN_NOT_IN_QUERY = "span_not_in_query"
    REPLACEMENT_NOT_GROUNDED = "replacement_not_grounded"
    LENGTH_BUDGET_EXCEEDED = "length_budget_exceeded"
    DELETION_NOT_ALLOWED = "deletion_not_allowed"


class RewriteResult(BaseModel):
    """Kết quả sau khi ghép và xác minh.

    Xác minh là all-or-nothing: một span hỏng thì loại toàn bộ đề xuất và giữ
    query gốc, không áp dụng một phần.
    """

    standalone: str = Field(..., description="Câu độc lập ngữ cảnh, hoặc raw query nếu loại")
    applied: bool = Field(default=False, description="Đề xuất có được áp dụng không")
    rejection: RejectionReason | None = None
    proposal: RewriteProposal | None = None
