import uuid
import time
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


# -------------------------
# Request DTOs
# -------------------------
class SessionMessageInput(BaseModel):
    user_id: str = Field(..., max_length=64, description="用户ID，必填 ≤64")
    content: str = Field(..., description="消息内容，必填 ≤10000")
    role_id: Optional[str] = Field(None, max_length=64, description="角色ID，可选")
    timestamp: int = Field(default_factory=lambda: int(time.time()), description="Unix时间戳，秒级")

    @field_validator("content")
    @classmethod
    def validate_content_length(cls, v: str) -> str:
        if len(v) > 10000:
            # 符合接口契约的错误码
            raise HTTPException(
                status_code=400,
                detail={"code": 4002, "message": "消息过长，最大长度 10000", "data": None},
            )
        return v


# -------------------------
# Response Envelope
# -------------------------
def envelope_ok(data: Dict[str, Any]) -> Dict[str, Any]:
    return {"code": 0, "message": "OK", "data": data}


def envelope_error(code: int, message: str) -> Dict[str, Any]:
    return {"code": code, "message": message, "data": None}


# -------------------------
# Controller Routes
# -------------------------
@router.post("")
async def create_session(input_dto: SessionMessageInput):
    """
    创建新会话并发送消息
    - 输入：SessionMessageInput
    - 输出：Envelope (Mock 数据)
    """
    # Mock 数据，固定返回
    mock_session_id = "mock-session-001"
    mock_message_id = str(uuid.uuid4())
    mock_reply = "这是一个Mock回复"

    data = {
        "session_id": mock_session_id,
        "message_id": mock_message_id,
        "reply": mock_reply,
        "actions": ["regenerate", "stop", "new_session"],
    }
    return envelope_ok(data)

def process_message(user_id: str, content: str) -> Dict[str, Any]:
    """供 Bot 内部直接调用的简化版接口（绕过 HTTP 层）"""
    # 简单校验
    if len(content) > 10000:
        return {"code": 4002, "message": "消息过长，最大长度 10000", "data": None}

    data = {
        "session_id": "mock-session-001",
        "message_id": str(uuid.uuid4()),
        "reply": f"Mock 回复：你说的是「{content}」",
        "actions": ["regenerate", "stop", "new_session"],
    }
    return {"code": 0, "message": "OK", "data": data}
