import uuid
import asyncio
import logging
from typing import Optional, Dict, Any, List

class MessageService:
    def __init__(self, message_repository=None, session_service=None):
        self._store = {}  # { session_id: [ {role, content, message_id} ] }
        self.message_repository = message_repository
        self.session_service = session_service
        self.logger = logging.getLogger(__name__)
        
        # 用于存储会话相关信息的缓存
        self._session_cache = {}  # { session_id: { user_id, role_id } }

    def save_message(self, session_id, role, content):
        if len(content) > 10000:
            raise ValueError("4002: 消息过长，最大长度 10000")
        message_id = uuid.uuid4().hex[:8]  
        
        message_data = {
            "message_id": message_id,
            "role": role,
            "content": content
        }
        
        self._store.setdefault(session_id, []).append(message_data)
        
        # 打印保存的消息信息
        print(f"💾 保存消息 | Session: {session_id} | Role: {role} | ID: {message_id}")
        print(f"📝 内容: {content}")
        print(f"📊 当前会话消息数: {len(self._store[session_id])}")
        print("-" * 50)
        
        # 异步写入Supabase（如果配置了message_repository）
        if self.message_repository and self.session_service:
            # 在后台异步执行，不阻塞主流程
            asyncio.create_task(self._async_save_to_supabase(session_id, role, content, message_id))
        
        return message_id
    
    async def _async_save_to_supabase(self, session_id: str, role: str, content: str, message_id: str):
        """异步保存消息到Supabase"""
        try:
            # 获取会话信息（用户ID和角色ID）
            session_info = await self._get_session_info(session_id)
            if not session_info:
                self.logger.warning(f"⚠️ 无法获取会话信息: session_id={session_id}")
                return
            
            user_id = session_info.get("user_id")
            role_id = session_info.get("role_id")  # 可以为 None
            
            if not user_id:
                self.logger.warning(f"⚠️ 会话缺少用户ID: session_id={session_id}")
                return
            
            # 转换为字符串类型（适配 TEXT 字段）
            user_id = str(user_id)
            role_id = str(role_id) if role_id is not None else None
            
            # 转换role格式：assistant -> bot
            sender = "bot" if role == "assistant" else "user"
            
            # 保存到Supabase
            await self.message_repository.save_message(
                user_id=user_id,
                role_id=role_id,
                session_id=session_id,
                message=content,
                sender=sender
            )
            
            self.logger.info(f"✅ 消息已异步保存到Supabase: session_id={session_id}, sender={sender}, user_id={user_id}, role_id={role_id}")
            
        except Exception as e:
            self.logger.error(f"❌ 异步保存消息到Supabase失败: {e}")
    
    async def _get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息（带缓存）"""
        # 先检查缓存
        if session_id in self._session_cache:
            return self._session_cache[session_id]
        
        # 从session_service获取
        try:
            session = await self.session_service.get_session(session_id)
            if session:
                session_info = {
                    "user_id": session.get("user_id"),
                    "role_id": session.get("role_id")  # 保持 None 而不是空字符串
                }
                # 缓存结果
                self._session_cache[session_id] = session_info
                return session_info
        except Exception as e:
            self.logger.error(f"❌ 获取会话信息失败: {e}")
        
        return None

    def get_history(self, session_id):
        history = self._store.get(session_id, [])
        
        # 打印历史记录信息
        print(f"📚 获取历史记录 | Session: {session_id} | 消息数量: {len(history)}")
        if history:
            print("📖 历史消息内容:")
            for i, msg in enumerate(history):
                role_emoji = "👤" if msg["role"] == "user" else "🤖"
                print(f"  [{i+1}] {role_emoji} {msg['role']} (ID: {msg['message_id']})")
                # 限制内容长度避免输出过长
                content_preview = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
                print(f"      📝 {content_preview}")
            print("📚" + "="*48)
        else:
            print("📚 历史记录为空")
            print("📚" + "="*48)
        
        return history
       

    async def regenerate_reply(self, session_id: str, last_message_id: str, ai_port, role_data, session_context_source=None):
        """
        基于指定用户消息重新生成回复
        - 精确定位 last_message_id
        - 删除旧的 Bot 回复
        - 保存新的 Bot 回复
        
        Args:
            session_context_source: 会话上下文来源，"snapshot" 表示快照会话
        """
        history = self.get_history(session_id)
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[DEBUG] regenerate_reply: session_id={session_id}, last_message_id={last_message_id}")
        logger.info(f"[DEBUG] regenerate_reply: current history={history}")

        if not history:
            logger.warning(f"[DEBUG] regenerate_reply: history is empty for session_id={session_id}")
            return {"message_id": None, "reply": "⚠️ 没有找到历史记录"}

        # 1. 定位到用户消息
        target_index = next(
            (i for i, msg in enumerate(history) if msg["message_id"] == last_message_id and msg["role"] == "user"),
            None
        )
        logger.info(f"[DEBUG] regenerate_reply: target_index={target_index}")

        if target_index is None:
            logger.warning(
                f"[DEBUG] regenerate_reply: cannot find user message_id={last_message_id} in history "
                f"(session_id={session_id})"
            )
            return {"message_id": None, "reply": "⚠️ 无法找到指定的用户消息"}

        user_input = history[target_index]["content"]
        logger.info(f"[DEBUG] regenerate_reply: found user_input={user_input}")

        # 2. 删除该用户消息之后的 Bot 回复
        history = history[:target_index + 1]
        self._store[session_id] = history
        logger.info(f"[DEBUG] regenerate_reply: trimmed history={history}")

        # 3. 重新生成 AI 回复（传入上下文来源避免重复添加角色预置对话）
        reply = await ai_port.generate_reply(role_data, history, user_input, session_context_source=session_context_source)
        logger.info(f"[DEBUG] regenerate_reply: new reply={reply}")

        # 4. 保存新的 Bot 回复
        bot_message_id = self.save_message(session_id, "assistant", reply)
        logger.info(f"[DEBUG] regenerate_reply: saved new bot_message_id={bot_message_id}")
        
        # 额外打印重新生成的回复信息
        print(f"🔄 重新生成回复 | Session: {session_id} | 基于用户消息ID: {last_message_id}")
        print(f"🤖 新Bot回复ID: {bot_message_id}")
        print("=" * 50)

        return {"message_id": bot_message_id, "reply": reply}


# ✅ 全局唯一实例（临时占位，实际使用时应通过容器获取）
# 在应用启动时，应该通过容器创建并替换这个实例
message_service = None  # 将在容器中初始化
