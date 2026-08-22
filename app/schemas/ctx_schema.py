"""Schema cho Context Card Kernel.

Bộ khung ngữ cảnh bất biến qua mọi usecase. Đặc tả: docs/ctx_kernel.md

Nguyên tắc: file này KHÔNG chứa tên trường của bất kỳ domain nào.
Tên trường sống trong manifest (domains/*.yaml). Đây là bất biến I6.

Các bất biến được cưỡng chế ngay tại đây, không phụ thuộc lời nhắc:
    I1  fact chỉ nằm trong ô hợp lệ (FORBIDDEN_CELLS)
    I3  mọi fact có source thuộc enum đóng; không có nguồn "prose"
    I4  fact source=verdict chỉ tồn tại ở neo dialogue (WRITE_PERMISSIONS)
    I5  không có op xoá — CardOp không định nghĩa "delete"
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

__all__ = [
    "Anchor",
    "Dimension",
    "Cell",
    "FORBIDDEN_CELLS",
    "QUERY_STRING_CELL",
    "PERSISTENT_ANCHORS",
    "TOPIC_SCOPED_ANCHORS",
    "valid_cells",
    "FactSource",
    "WRITE_PERMISSIONS",
    "Projection",
    "PROJECTION_BY_SOURCE",
    "Polarity",
    "Confidence",
    "ConvSpan",
    "WorldSpan",
    "Fact",
    "ContextCard",
    "AssertOp",
    "CloseOp",
    "ExcludeOp",
    "OpenGapOp",
    "ResolveGapOp",
    "CardOp",
    "CardUpdate",
]


# ---------------------------------------------------------------------------
# Lưới 4 neo x 5 chiều (ctx_kernel.md §1, §2)
# ---------------------------------------------------------------------------


class Anchor(str, Enum):
    """Fact này nói về cái gì."""

    ASKER = "asker"        # ai đang hỏi
    TARGET = "target"      # hỏi về ai / cái gì
    SOURCE = "source"      # câu trả lời nằm ở đâu
    DIALOGUE = "dialogue"  # trạng thái cuộc hội thoại


class Dimension(str, Enum):
    """Khía cạnh nào của neo."""

    IDENTITY = "identity"
    ATTRIBUTE = "attribute"
    SPACE = "space"
    TIME = "time"
    TOPIC = "topic"


Cell = tuple[Anchor, Dimension]

#: Ba ô bị cấm. Không phải "chưa dùng tới" — là bất biến I1.
#: asker.topic     : người hỏi không có chủ đề; chủ đề thuộc về cái được hỏi.
#: dialogue.space  : trục hội thoại đã nằm trong ConvSpan của mọi fact.
#: dialogue.time   : như trên.
FORBIDDEN_CELLS: frozenset[Cell] = frozenset(
    {
        (Anchor.ASKER, Dimension.TOPIC),
        (Anchor.DIALOGUE, Dimension.SPACE),
        (Anchor.DIALOGUE, Dimension.TIME),
    }
)

#: Ô DUY NHẤT được phép nối vào chuỗi query (bất biến I2).
#: Đây là nguyên tắc N3 của process_query.md phát biểu dưới dạng hằng số.
QUERY_STRING_CELL: Cell = (Anchor.TARGET, Dimension.TOPIC)

#: Vòng đời suy ra từ neo, không cần bảng tra (ctx_kernel.md §6).
PERSISTENT_ANCHORS: frozenset[Anchor] = frozenset({Anchor.ASKER, Anchor.DIALOGUE})
TOPIC_SCOPED_ANCHORS: frozenset[Anchor] = frozenset({Anchor.TARGET, Anchor.SOURCE})


def valid_cells(anchor: Anchor) -> set[Cell]:
    """Mọi ô hợp lệ của một neo."""
    return {(anchor, d) for d in Dimension if (anchor, d) not in FORBIDDEN_CELLS}


# ---------------------------------------------------------------------------
# Phân tầng nguồn tin (ctx_kernel.md §7)
# ---------------------------------------------------------------------------


class FactSource(str, Enum):
    """Enum đóng. Thứ tự khai báo là thứ tự quyền ghi đè.

    Không có thành viên nào cho văn xuôi do model sinh: prose không bao giờ
    vào card, kể cả gián tiếp.
    """

    SESSION = "session"
    EXTERNAL_SYSTEM = "external_system"
    USER_STATED = "user_stated"
    RETRIEVED = "retrieved"
    SQL_RESULT = "sql_result"
    VERDICT = "verdict"


#: Nguồn nào được ghi vào ô nào. Đây là chỗ bất biến I4 được cưỡng chế:
#: VERDICT chỉ chạm được neo dialogue, nên nó không thể ghi đè điều mà
#: citation hay người dùng đã nói.
WRITE_PERMISSIONS: dict[FactSource, frozenset[Cell]] = {
    FactSource.SESSION: frozenset(
        valid_cells(Anchor.ASKER) | {(Anchor.DIALOGUE, Dimension.IDENTITY)}
    ),
    FactSource.EXTERNAL_SYSTEM: frozenset(valid_cells(Anchor.ASKER)),
    FactSource.USER_STATED: frozenset(
        valid_cells(Anchor.ASKER)
        | valid_cells(Anchor.TARGET)
        | valid_cells(Anchor.SOURCE)
    ),
    FactSource.RETRIEVED: frozenset(valid_cells(Anchor.SOURCE) | {QUERY_STRING_CELL}),
    FactSource.SQL_RESULT: frozenset(valid_cells(Anchor.SOURCE) | {QUERY_STRING_CELL}),
    FactSource.VERDICT: frozenset(valid_cells(Anchor.DIALOGUE)),
}


class Projection(str, Enum):
    """Fact chiếu xuống retrieval thành cái gì."""

    HARD_FILTER = "hard_filter"
    BOOST = "boost"


#: verdict là model tự chấm chính mình, nên chỉ được sinh boost.
#: Filter cứng là nguồn duy nhất khiến hệ thống trả về rỗng.
PROJECTION_BY_SOURCE: dict[FactSource, Projection] = {
    FactSource.SESSION: Projection.HARD_FILTER,
    FactSource.EXTERNAL_SYSTEM: Projection.HARD_FILTER,
    FactSource.USER_STATED: Projection.HARD_FILTER,
    FactSource.RETRIEVED: Projection.HARD_FILTER,
    FactSource.SQL_RESULT: Projection.HARD_FILTER,
    FactSource.VERDICT: Projection.BOOST,
}


class Polarity(str, Enum):
    """Thay cho một danh sách ràng buộc phủ định riêng (ctx_kernel.md §5).

    Nhờ nằm trên envelope, mọi ô đều loại trừ được — không chỉ chủ đề.
    """

    INCLUDE = "include"
    EXCLUDE = "exclude"


class Confidence(str, Enum):
    CERTAIN = "certain"
    PROBABLE = "probable"
    INFERRED = "inferred"


# ---------------------------------------------------------------------------
# Hai trục thời gian nằm trên envelope (ctx_kernel.md §3.1)
# ---------------------------------------------------------------------------


class ConvSpan(BaseModel):
    """Trục hội thoại: biết fact này từ lượt nào, tới lượt nào."""

    from_turn: int = Field(..., ge=0)
    to_turn: int | None = Field(default=None, ge=0)

    @computed_field
    @property
    def active(self) -> bool:
        """Suy ra, không lưu — tránh hai nguồn sự thật lệch nhau."""
        return self.to_turn is None

    @model_validator(mode="after")
    def _ordered(self) -> ConvSpan:
        if self.to_turn is not None and self.to_turn < self.from_turn:
            raise ValueError(f"to_turn ({self.to_turn}) < from_turn ({self.from_turn})")
        return self


class WorldSpan(BaseModel):
    """Trục thế giới thực: fact đúng từ khi nào đến khi nào.

    Chuỗi thay vì date vì domain cần mốc thiếu độ chính xác: "2026",
    "2026-03", "2026-03-01" đều hợp lệ.
    """

    model_config = ConfigDict(populate_by_name=True)

    from_: str | None = Field(default=None, alias="from")
    to: str | None = None


# ---------------------------------------------------------------------------
# Envelope (ctx_kernel.md §4)
# ---------------------------------------------------------------------------


class Fact(BaseModel):
    """Đơn vị duy nhất của card. Mọi giá trị đều có đúng hình dạng này.

    Sự đồng nhất này là điều kiện để project() và update_card() là code tổng
    quát, thay vì một chuỗi nhánh if theo tên trường.
    """

    anchor: Anchor
    dim: Dimension
    key: str = Field(..., min_length=1)
    seq: int = Field(default=0, ge=0)

    value: Any
    polarity: Polarity = Polarity.INCLUDE
    source: FactSource
    confidence: Confidence = Confidence.CERTAIN

    t_conv: ConvSpan
    t_world: WorldSpan | None = None

    evidence: str | None = None

    @computed_field
    @property
    def id(self) -> str:
        return f"{self.anchor.value}.{self.dim.value}.{self.key}#{self.seq}"

    @property
    def cell(self) -> Cell:
        return (self.anchor, self.dim)

    @property
    def projection(self) -> Projection:
        return PROJECTION_BY_SOURCE[self.source]

    @property
    def is_persistent(self) -> bool:
        """Fact có sống qua lần đổi chủ đề không (ctx_kernel.md §6).

        Luật: asker/dialogue thì bền, target/source thì theo chủ đề.
        Ngoại lệ có chủ ý: điều người dùng tự khai không bao giờ bị bỏ
        tự động — chỉ đóng khoảng khi chính họ phủ nhận.
        """
        return self.anchor in PERSISTENT_ANCHORS or self.source is FactSource.USER_STATED

    @property
    def goes_to_query_string(self) -> bool:
        return self.cell == QUERY_STRING_CELL

    @model_validator(mode="after")
    def _enforce_kernel(self) -> Fact:
        if self.cell in FORBIDDEN_CELLS:
            raise ValueError(
                f"ô bị cấm: {self.anchor.value}.{self.dim.value} (ctx_kernel.md §2)"
            )
        if self.cell not in WRITE_PERMISSIONS[self.source]:
            raise ValueError(
                f"nguồn {self.source.value} không được ghi vào "
                f"{self.anchor.value}.{self.dim.value} (ctx_kernel.md §7)"
            )
        if self.source is FactSource.USER_STATED and not self.evidence:
            raise ValueError(
                "fact user_stated phải có evidence trích nguyên văn (ctx_kernel.md §4)"
            )
        return self


class ContextCard(BaseModel):
    """Card của một phiên. Chỉ thay đổi qua ops (ctx_kernel.md §11)."""

    session_id: str
    turn: int = Field(default=0, ge=0)
    facts: list[Fact] = Field(default_factory=list)

    def active(self) -> list[Fact]:
        return [f for f in self.facts if f.t_conv.active]

    def in_cell(self, anchor: Anchor, dim: Dimension) -> list[Fact]:
        return [f for f in self.active() if f.cell == (anchor, dim)]

    def query_string_facts(self) -> list[Fact]:
        """Bất biến I2: chỉ ô này được nối vào chuỗi query."""
        return [f for f in self.active() if f.goes_to_query_string]

    def by_id(self, fact_id: str) -> Fact | None:
        return next((f for f in self.facts if f.id == fact_id), None)

    def next_seq(self, anchor: Anchor, dim: Dimension, key: str) -> int:
        same = [
            f.seq for f in self.facts if (f.anchor, f.dim, f.key) == (anchor, dim, key)
        ]
        return max(same) + 1 if same else 0


# ---------------------------------------------------------------------------
# Ops (ctx_kernel.md §11) — danh sách đóng, năm phép
# ---------------------------------------------------------------------------
# Cố tình KHÔNG có "delete": không bao giờ xoá, chỉ close. Đây là bất biến I5.
# Op log cho phép tái dựng card từ đầu để debug và rollback khi nhiễm độc.


class AssertOp(BaseModel):
    op: Literal["assert"]
    anchor: Anchor
    dim: Dimension
    key: str
    value: Any
    source: FactSource
    confidence: Confidence = Confidence.CERTAIN
    t_world: WorldSpan | None = None
    evidence: str | None = None


class CloseOp(BaseModel):
    op: Literal["close"]
    id: str
    to_turn: int = Field(..., ge=0)


class ExcludeOp(BaseModel):
    op: Literal["exclude"]
    anchor: Anchor
    dim: Dimension
    key: str
    value: Any
    source: FactSource
    evidence: str | None = None


class OpenGapOp(BaseModel):
    """Câu hỏi đã hỏi nhưng chưa được thoả mãn — dialogue.topic."""

    op: Literal["open_gap"]
    value: str
    gap: str
    lead: str | None = None
    source: FactSource = FactSource.VERDICT


class ResolveGapOp(BaseModel):
    op: Literal["resolve_gap"]
    id: str


CardOp = Annotated[
    Union[AssertOp, CloseOp, ExcludeOp, OpenGapOp, ResolveGapOp],
    Field(discriminator="op"),
]


class CardUpdate(BaseModel):
    """Output của update_card. Model sinh phép biến đổi, không chép lại card.

    Bắt model chép lại toàn bộ card mỗi lượt là chép lại cơ hội bóp méo.
    """

    ops: list[CardOp] = Field(default_factory=list)
