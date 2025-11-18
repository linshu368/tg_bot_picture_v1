import uuid
import time
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from src.domain.services.session_service_base import session_service
from src.domain.services.message_service import message_service
from src.domain.services.ai_completion_port import ai_completion_port
from src.domain.services.role_service import role_service

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
#         reply = await ai_completion_port.generate_reply(role_data, history, input_dto.content)
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
        # 1. 从会话获取绑定的角色ID
        role_id = await session_service.get_session_role_id(session_id)
        
        # 2. 获取角色数据，如果角色不存在则使用默认角色
        if role_id:
            role_data = role_service.get_role_by_id(role_id)
        else:
            role_data = None
        
        if not role_data:
            # 降级到默认角色
            default_role_id = '46'
            role_data = role_service.get_role_by_id(default_role_id)
        
        if not role_data:
            return envelope_error(4001, "角色配置错误")
        
        # 3. 重新生成回复
        result = await message_service.regenerate_reply(
            session_id=session_id,
            user_message_id=input_dto.user_message_id,
            ai_port=ai_completion_port,
            role_data=role_data
        )
    except TimeoutError:
        return envelope_error(4004, "生成超时，请重试")
    except Exception as e:
        return envelope_error(5000, f"服务器错误: {str(e)}")

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
async def process_message(user_id: str, content: str, role_id: str = None) -> Dict[str, Any]:
    """供 Bot 内部直接调用的简化版接口（绕过 HTTP 层）
    
    注意：此函数已被 text_bot.py 中的流式处理替代，保留作为备用或非流式场景使用
    
    Args:
        user_id: 用户ID
        content: 消息内容
        role_id: 可选的角色ID，极少使用（仅作为兜底参数保留）
    
    说明：
        - 大部分情况下，会话已在 /start 命令时创建并绑定角色
        - 此函数主要处理用户消息，获取已存在的会话
        - 仅在极端情况（用户跳过 /start 直接发消息）才创建会话
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # 简单校验
    if len(content) > 10000:
        return {"code": 4002, "message": "消息过长，最大长度 10000", "data": None}

    # 检查每日消息限制
    limit_check = await message_service.check_daily_limit(user_id)
    if not limit_check["allowed"]:
        logger.warning(f"🚫 用户超出每日消息限制: user_id={user_id}, current_count={limit_check['current_count']}, limit={limit_check['limit']}")
        
        # 获取或创建会话（用于保存限制提示消息）
        session = await session_service.get_or_create_session(user_id)
        session_id = session["session_id"]
        
        # 保存用户消息（先增强后保存）
        try:
            from src.utils.enhance import enhance_user_input
            prev_history = message_service.get_history(session_id) or []
            prev_user_turns = sum(1 for m in prev_history if isinstance(m, dict) and m.get("role") == "user")
            current_turn_index = prev_user_turns + 1
            instruction_type = "system" if current_turn_index <= 3 else "ongoing"
            enhanced_content, _ = enhance_user_input(content, instruction_type, user_context=content)
        except Exception:
            enhanced_content = content
        user_message_id = message_service.save_message(session_id, "user", enhanced_content)
        
        # 保存Bot的限制提示回复
        limit_message = "您今日的免费体验次数已用完，明日0点重置。感谢您的使用！"
        bot_message_id = message_service.save_message(session_id, "assistant", limit_message)
        
        logger.info(f"💾 已保存限制提示消息: user_message_id={user_message_id}, bot_message_id={bot_message_id}")
        
        return envelope_error(4003, limit_message)

    # 获取或创建会话（大部分情况下是获取已存在的会话）
    session = await session_service.get_or_create_session(user_id)
    session_id = session["session_id"]
    
    # 1. 获取会话的角色ID
    current_role_id = session.get("role_id")
    
    # 2. 兜底机制：如果会话没有角色ID，设置默认角色
    # 注意：正常流程下，会话应该在 /start 时就已绑定角色，此处极少触发
    if not current_role_id:
        logger.warning(f"⚠️ 会话无角色ID，触发兜底机制: user_id={user_id}, session_id={session_id}")
        
        if role_id:
            # 使用传入的角色ID（极少使用）
            await session_service.set_session_role_id(session_id, role_id)
            current_role_id = role_id
            logger.info(f"📥 使用传入角色ID: {role_id}")
        else:
            # 使用默认角色（最常见的兜底情况）
            default_role_id = '46'
            await session_service.set_session_role_id(session_id, default_role_id)
            current_role_id = default_role_id
            logger.info(f"📥 使用默认角色ID: {default_role_id}")
    
    # 3. 获取角色数据
    role_data = role_service.get_role_by_id(current_role_id)
    if not role_data:
        # 二次降级：角色ID对应的角色不存在
        logger.warning(f"⚠️ 角色不存在: role_id={current_role_id}，降级到默认角色")
        default_role_id = '46'
        role_data = role_service.get_role_by_id(default_role_id)
        if role_data:
            await session_service.set_session_role_id(session_id, default_role_id)
    
    if not role_data:
        logger.error(f"❌ 角色配置错误: 默认角色也不存在")
        return envelope_error(4001, "角色配置错误")

    # 4. 保存用户消息并生成回复（先增强后保存）
    try:
        from src.utils.enhance import enhance_user_input
        prev_history = message_service.get_history(session_id) or []
        prev_user_turns = sum(1 for m in prev_history if isinstance(m, dict) and m.get("role") == "user")
        current_turn_index = prev_user_turns + 1
        instruction_type = "system" if current_turn_index <= 3 else "ongoing"
        enhanced_content, _ = enhance_user_input(content, instruction_type, user_context=content)
    except Exception:
        enhanced_content = content
    user_message_id = message_service.save_message(session_id, "user", enhanced_content)
    history = message_service.get_history(session_id)
    
    # 获取会话上下文来源（判断是否为快照会话）
    context_source = session.get("context_source") if session else None
    
    try:
        # 使用流式生成并收集完整回复
        reply = ""
        used_instructions_meta: Dict[str, Any] = {}
        def _on_used_instructions(meta: Dict[str, Any]) -> None:
            try:
                used_instructions_meta.clear()
                if isinstance(meta, dict):
                    used_instructions_meta.update(meta)
            except Exception:
                pass
        async for chunk in ai_completion_port.generate_reply_stream_with_retry(
            role_data=role_data,
            history=history,
            user_input=content,
            session_context_source=context_source,
            on_used_instructions=_on_used_instructions,
            apply_enhancement=False
        ):
            reply += chunk
            
        # 🆕 AI生成完成后，获取实际使用的指令并重新保存用户消息（带指令 + 100%复现的history）
        if message_service.message_repository:
            try:
                system_instructions = used_instructions_meta.get("system_instructions")
                ongoing_instructions = used_instructions_meta.get("ongoing_instructions")
                instruction_type = used_instructions_meta.get("instruction_type")
                
                if system_instructions or ongoing_instructions:
                    # 获取会话信息
                    session_info = await session_service.get_session(session_id)
                    if session_info:
                        role_id_for_save = session_info.get("role_id")
                        # 100%复现：final_messages 与模型名
                        model_name = used_instructions_meta.get("model_name") or used_instructions_meta.get("model")
                        final_messages = used_instructions_meta.get("final_messages")
                        if not isinstance(final_messages, list) or not final_messages:
                            constructed = []
                            if isinstance(role_data, dict) and role_data.get("system_prompt"):
                                constructed.append({"role": "system", "content": role_data.get("system_prompt")})
                            if context_source != "snapshot" and isinstance(role_data, dict) and role_data.get("history"):
                                constructed.extend(role_data.get("history") or [])
                            constructed.extend(history or [])
                            final_messages = constructed
                        try:
                            import json
                            history_json_str = json.dumps(final_messages, ensure_ascii=False)
                        except Exception:
                            history_json_str = None
                        # 异步保存带指令的用户消息（不阻塞主流程）
                        message_service.message_repository.save_user_message_with_real_instructions_async(
                            user_id=str(user_id),
                            role_id=str(role_id_for_save) if role_id_for_save else None,
                            session_id=session_id,
                            message=content,
                            system_instructions=system_instructions,
                            ongoing_instructions=ongoing_instructions,
                            history=history_json_str,
                            model_name=model_name,
                            user_input=content,
                            bot_reply=reply
                        )
                        logger.info(f"🔄 已异步保存带指令的用户消息: session_id={session_id}")
            except Exception as e:
                logger.error(f"❌ 保存带指令的用户消息失败: {e}")
                
    except TimeoutError:
        return envelope_error(4004, "生成超时，请重试")
    except Exception as e:
        logger.error(f"❌ AI生成失败: {e}")
        return envelope_error(5000, f"AI生成失败: {str(e)}")

    bot_message_id = message_service.save_message(session_id, "assistant", reply)

    return envelope_ok({
        "session_id": session_id,
        "user_message_id": user_message_id,   
        "bot_message_id": bot_message_id,
        "reply": reply,
        "actions": ["regenerate", "stop", "new_session"],
    })