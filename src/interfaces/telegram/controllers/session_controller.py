import uuid
import time
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from src.domain.services.session_service_base import SessionService
from src.domain.services.message_service import message_service_singleton as message_service
from src.domain.services.ai_completion_port import AICompletionPort
from demo.api import GPTCaller
from demo.role import role_data
session_service = SessionService()

ai_port = AICompletionPort(GPTCaller())

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
    # user_id: str = Field(..., max_length=64, description="用户ID，必填 ≤64") 
    # #目前message_service.regenerate_reply只用session_id + user_message_id，如果未来想验证用户身份，可以保留 user_id
    user_message_id: str = Field(..., description="上一次消息的ID(UUID)")


class NewSessionInput(BaseModel):
    user_id: str = Field(..., max_length=64, description="用户ID，必填 ≤64")

# -------------------------
# Response Envelope
# -------------------------
def envelope_ok(data: Dict[str, Any]) -> Dict[str, Any]:
    return {"code": 0, "message": "OK", "data": data}


def envelope_error(code: int, message: str) -> Dict[str, Any]:
    return {"code": code, "message": message, "data": None}


# # -------------------------
# # Controller Routes
# # -------------------------
# @router.post("")
# async def create_session(input_dto: SessionMessageInput):
#     """
#     创建新会话并发送消息
#     - 输入：SessionMessageInput
#     - 输出：Envelope (Mock 数据)
#     """
#     # 1.使用 SessionService 获取或创建
#     session = await session_service.get_or_create_session(input_dto.user_id)
#     session_id = session["session_id"]

#     # 2. 保存用户消息
#     user_message_id = message_service.save_message(session_id, "user", input_dto.content)

#     # 3. 获取历史对话
#     history = message_service.get_history(session_id)

#     # 4. 调用 AICompletionPort 生成回复
#     try:
#         reply = await ai_port.generate_reply(role_data, history, input_dto.content)
#     except TimeoutError:
#         return envelope_error(4004, "生成超时，请重试")

#     # 5. 保存 bot 回复
#     bot_message_id = message_service.save_message(session_id, "assistant", reply)

#     # 6. 返回统一响应
#     data = {
#         "session_id": session_id,
#         "message_id": bot_message_id,
#         "reply": reply,
#         "actions": ["regenerate", "stop", "new_session"],
#     }
#     return envelope_ok(data)


@router.post("/{session_id}/regenerate")
async def regenerate_reply(session_id: str, input_dto: RegenerateInput):
    """
    重新生成回复
    - 输入：RegenerateInput
    - MVP 调试用入口，实际生产中应由 CallbackHandler 调用
    """
    try:
        result = await message_service.regenerate_reply(
            session_id=session_id,
            user_message_id=input_dto.user_message_id,
            ai_port=ai_port,
            role_data=role_data
        )
    except TimeoutError:
        return envelope_error(4004, "生成超时，请重试")

    data = {
        "message_id": result["message_id"],
        "reply": result["reply"],
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
        # "message_id": str(uuid.uuid4()),  #新会话，用户输入为空
        "reply": "已开启新对话",
        "actions": ["regenerate", "stop", "new_session"],
    }
    return envelope_ok(data)

# -------------------------
# Internal Process Function
# -------------------------
async def process_message(user_id: str, content: str) -> Dict[str, Any]:
    """供 Bot 内部直接调用的简化版接口（绕过 HTTP 层）"""
    # 简单校验
    if len(content) > 10000:
        return {"code": 4002, "message": "消息过长，最大长度 10000", "data": None}

    # 内部调用 create_session 流程
    session = await session_service.get_or_create_session(user_id)
    session_id = session["session_id"]

    user_message_id = message_service.save_message(session_id, "user", content)
    history = message_service.get_history(session_id)
    try:
        reply = await ai_port.generate_reply(role_data, history, content)
    except TimeoutError:
        return envelope_error(4004, "生成超时，请重试")

    bot_message_id = message_service.save_message(session_id, "assistant", reply)

    return envelope_ok({
        "session_id": session_id,
        "user_message_id": user_message_id,   
        "bot_message_id": bot_message_id,
        "reply": reply,
        "actions": ["regenerate", "stop", "new_session"],
    })