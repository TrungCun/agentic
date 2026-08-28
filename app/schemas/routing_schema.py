from enum import Enum

from pydantic import BaseModel, Field


class RouteType(str, Enum):
    """ Nhãn định tuyến luồng"""

    CLARIFY = "clarify"    # thiếu thông tin -> hỏi lại
    DIRECT   = "direct"     # chit-chat/meta -> trả lời thẳng
    DOWNSTREAM = "downstream" # cần gọi node downstream -> trả về node_id


class RouteDecision(BaseModel):
    """Schema output của route_node"""

    route: RouteType = Field(..., description="Nhãn định tuyến luồng: clarify | direct | downstream")
    route_reason: str = Field(..., description="Lý do định tuyến luồng")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
