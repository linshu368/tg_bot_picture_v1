import uuid
import time
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from src.domain.services.session_service_base import SessionService
session_service = SessionService()

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

class RegenerateInput(BaseModel):
    user_id: str = Field(..., max_length=64, description="用户ID，必填 ≤64")
    last_message_id: str = Field(..., description="上一次消息的ID(UUID)")


class NewSessionInput(BaseModel):
    user_id: str = Field(..., max_length=64, description="用户ID，必填 ≤64")

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
    # 使用 SessionService 获取或创建
    session = await session_service.get_or_create_session(input_dto.user_id)

    data = {
        "session_id": session["session_id"],
        "message_id": str(uuid.uuid4()),
        "reply": f"Mock 回复：你说的是「{input_dto.content}」",
        "actions": ["regenerate", "stop", "new_session"],
    }
    return envelope_ok(data)

@router.post("/{session_id}/regenerate")
async def regenerate_reply(session_id: str, input_dto: RegenerateInput):
    """
    重新生成回复
    - 输入：RegenerateInput
    - 输出：Envelope (Mock 数据)
    """
    mock_message_id = str(uuid.uuid4())
    mock_reply = f"这是重新生成的回复 (基于 last_message_id={input_dto.last_message_id})"

    data = {
        "message_id": mock_message_id,
        "reply": mock_reply,
        "actions": ["regenerate", "stop", "new_session"],
    }
    return envelope_ok(data)


@router.post("/new")
async def new_session(input_dto: NewSessionInput):
    """
    开启新对话
    - 输入：NewSessionInput
    - 输出：Envelope (Mock 数据)
    """
    session = await session_service.new_session(input_dto.user_id)

    data = {
        "session_id": session["session_id"],
        "message_id": str(uuid.uuid4()),
        "reply": "已开启新对话",
        "actions": ["regenerate", "stop", "new_session"],
    }
    return envelope_ok(data)

# -------------------------
# Internal Process Function
# -------------------------
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
