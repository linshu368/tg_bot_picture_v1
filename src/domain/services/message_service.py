import uuid
import asyncio
import logging
from typing import Optional, Dict, Any, List

class MessageService:
    def __init__(self, message_repository=None, session_service=None, redis_store=None):
        self._store = {}  # { session_id: [ {role, content, message_id} ] }
        self.message_repository = message_repository
        self.session_service = session_service
        self.redis_store = redis_store
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
        
        # 写穿到 Redis（Upstash REST / RedisJSON）
        if self.redis_store:
            try:
                asyncio.create_task(self.redis_store.append_message(session_id, message_data))
            except Exception as _e:
                self.logger.debug(f"写穿 Redis 失败: {session_id}, err={_e}")
        
        # 打印保存的消息信息
        print(f"💾 保存消息 | Session: {session_id} | Role: {role} | ID: {message_id}")
        # print(f"📝 内容: {content}")
        print(f"📊 当前会话消息数: {len(self._store[session_id])}")
        print("-" * 50)
        
        # 异步写入Supabase（如果配置了message_repository）
        if self.message_repository and self.session_service:
            # 只保存机器人消息，用户消息等AI处理完成后带指令一起保存
            # 这样避免重复保存：一次不带指令，一次带指令
            if role == "assistant":  # 机器人消息立即保存
                asyncio.create_task(self._async_save_to_supabase(session_id, role, content, message_id))
            # 用户消息不在这里保存，等AI处理完成后通过save_user_message_with_real_instructions_async保存
        
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
            
            # 新策略（单行单轮）：bot 回复不再单独入库，避免产生 bot-only 行
            # 最终持久化通过 save_user_message_with_real_instructions_async（写整轮）
            # 或通过 update_last_user_message_reply（覆盖最新一轮的回复字段）完成
            if sender == "bot":
                return
            
            self.logger.info(f"✅ 消息已异步保存到Supabase: session_id={session_id}, sender={sender}, user_id={user_id}, role_id={role_id}")
            
        except Exception as e:
            self.logger.error(f"❌ 异步保存消息到Supabase失败: {e}")
    
    async def get_user_message_count(self, user_id: str) -> int:
        """
        获取用户历史发送消息数量（以 Supabase 为准；无仓储时返回 0）
        """
        try:
            if self.message_repository is None:
                return 0
            # 仓储方法已按 sender='user' 过滤
            return await self.message_repository.get_user_message_count(str(user_id))
        except Exception as e:
            self.logger.error(f"❌ 获取用户消息数量失败: {e}")
            return 0
    
    async def check_daily_limit(self, user_id: str, daily_limit: int = None) -> dict:
        """
        检查用户今日消息数量是否超过限制
        
        Args:
            user_id: 用户ID
            daily_limit: 每日限制数量，None时从配置读取
            
        Returns:
            dict: {
                "allowed": bool,  # 是否允许发送
                "current_count": int,  # 当前已发送数量
                "limit": int,  # 限制数量
                "remaining": int  # 剩余数量
            }
        """
        # 如果没有传入daily_limit，从配置中读取
        if daily_limit is None:
            try:
                from src.utils.config.settings import get_settings
                settings = get_settings()
                daily_limit = settings.daily_limit
            except Exception as e:
                self.logger.error(f"❌ 无法读取配置中的daily_limit，请检查环境变量DAILY_LIMIT是否设置: {e}")
                raise ValueError("DAILY_LIMIT环境变量未设置或配置错误")
        
        try:
            if self.message_repository is None:
                # 无数据库连接时，默认允许
                return {
                    "allowed": True,
                    "current_count": 0,
                    "limit": daily_limit,
                    "remaining": daily_limit
                }
            
            # 获取今日已发送消息数量
            current_count = await self.message_repository.get_user_daily_message_count(str(user_id))
            remaining = max(0, daily_limit - current_count)
            allowed = current_count < daily_limit
            
            result = {
                "allowed": allowed,
                "current_count": current_count,
                "limit": daily_limit,
                "remaining": remaining
            }
            
            self.logger.info(f"🔍 每日限制检查: user_id={user_id}, result={result}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 检查每日限制失败: {e}")
            # 发生错误时默认允许，避免影响用户体验
            return {
                "allowed": True,
                "current_count": 0,
                "limit": daily_limit,
                "remaining": daily_limit
            }
    
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
        
        # 若内存为空，尝试从 Redis 回填（同步场景下使用；异步场景建议使用 ensure_history_loaded）
        if not history and self.redis_store:
            try:
                loop = asyncio.get_running_loop()
                # 已在事件循环内：后台加载，不阻塞当前调用
                asyncio.create_task(self._load_history_from_redis(session_id))
            except RuntimeError:
                # 无事件循环：可直接阻塞获取
                try:
                    history_from_redis = asyncio.run(self.redis_store.get_messages(session_id))
                    if history_from_redis:
                        self._store[session_id] = history_from_redis
                        history = history_from_redis
                except Exception as _e:
                    self.logger.debug(f"同步加载 Redis 历史失败: {session_id}, err={_e}")
        
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
    
    async def ensure_history_loaded(self, session_id: str, force: bool = False) -> int:
        """
        异步确保内存中存在会话历史；若为空或 force=True 则从 Redis 读取回填
        Returns: 加载后的消息数
        """
        if not self.redis_store:
            return len(self._store.get(session_id, []))
        if self._store.get(session_id) and not force:
            return len(self._store.get(session_id, []))
        try:
            await self._load_history_from_redis(session_id)
        except Exception as _e:
            self.logger.debug(f"ensure_history_loaded 失败: {session_id}, err={_e}")
        return len(self._store.get(session_id, []))
    
    async def _load_history_from_redis(self, session_id: str) -> None:
        """
        从 Redis 读取整个会话历史并回填到内存缓存
        """
        if not self.redis_store:
            return
        try:
            messages = await self.redis_store.get_messages(session_id)
            if messages:
                self._store[session_id] = messages
                self.logger.info(f"🧩 Redis 历史已回填: session_id={session_id}, count={len(messages)}")
        except Exception as _e:
            self.logger.debug(f"加载 Redis 历史失败: {session_id}, err={_e}")
       

    async def regenerate_reply(self, session_id: str, last_message_id: str, ai_port, role_data, session_context_source=None):
        """
        基于指定用户消息重新生成回复
        - 精确定位 last_message_id
        - 删除旧的 Bot 回复
        - 保存新的 Bot 回复
        
        Args:
            session_context_source: 会话上下文来源，"snapshot" 表示快照会话
        """
        # 确保在异步上下文中优先从 Redis 回填历史
        await self.ensure_history_loaded(session_id)
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
        # 覆盖写回 Redis
        if self.redis_store:
            try:
                asyncio.create_task(self.redis_store.set_messages(session_id, history))
            except Exception as _e:
                logger.debug(f"回写 Redis 失败(regenerate trim): {session_id}, err={_e}")
        logger.info(f"[DEBUG] regenerate_reply: trimmed history={history}")

        # 3. 重新生成 AI 回复（使用流式生成并收集完整回复）
        reply = ""
        used_instructions_meta: Dict[str, Any] = {}
        def _on_used_instructions(meta: Dict[str, Any]) -> None:
            try:
                used_instructions_meta.clear()
                if isinstance(meta, dict):
                    used_instructions_meta.update(meta)
            except Exception:
                pass
        async for chunk in ai_port.generate_reply_stream_with_retry(
            role_data=role_data,
            history=history,
            user_input=user_input,
            session_context_source=session_context_source,
            on_used_instructions=_on_used_instructions,
            apply_enhancement=False
        ):
            reply += chunk
        logger.info(f"[DEBUG] regenerate_reply: new reply={reply}")

        # 4. 删除旧的 Bot 回复并保存新的 Bot 回复（保持严格 user-bot 交替）
        try:
            if self.message_repository:
                await self.message_repository.delete_last_bot_message(session_id)
        except Exception as e:
            logger.debug(f"删除旧机器人消息失败(regenerate): {e}")
        bot_message_id = self.save_message(session_id, "assistant", reply)
        logger.info(f"[DEBUG] regenerate_reply: saved new bot_message_id={bot_message_id}")
        
        # 4.1 覆盖最新用户消息中的 bot_reply/history/model（不新增用户行）
        try:
            if self.message_repository:
                model_name = used_instructions_meta.get("model_name") or used_instructions_meta.get("model")
                final_messages = used_instructions_meta.get("final_messages")
                if not isinstance(final_messages, list) or not final_messages:
                    # 兜底构造
                    constructed = []
                    if isinstance(role_data, dict) and role_data.get("system_prompt"):
                        constructed.append({"role": "system", "content": role_data.get("system_prompt")})
                    if session_context_source != "snapshot" and isinstance(role_data, dict) and role_data.get("history"):
                        constructed.extend(role_data.get("history") or [])
                    constructed.extend(history or [])
                    final_messages = constructed
                import json
                try:
                    history_json_str = json.dumps(final_messages, ensure_ascii=False)
                except Exception:
                    history_json_str = None
                await self.message_repository.update_last_user_message_reply(
                    session_id=session_id,
                    bot_reply=reply,
                    history=history_json_str,
                    model_name=model_name
                )
        except Exception as e:
            logger.debug(f"覆盖最新用户消息失败(regenerate): {e}")
        
        # 额外打印重新生成的回复信息
        print(f"🔄 重新生成回复 | Session: {session_id} | 基于用户消息ID: {last_message_id}")
        print(f"🤖 新Bot回复ID: {bot_message_id}")
        print("=" * 50)

        return {"message_id": bot_message_id, "reply": reply}

    def truncate_history_after_message(self, session_id: str, user_message_id: str) -> Optional[str]:
        """
        截断指定用户消息之后的所有回复，并返回用户消息内容
        
        Args:
            session_id: 会话ID
            user_message_id: 用户消息ID
            
        Returns:
            用户消息内容，如果找不到则返回None
        """
        history = self.get_history(session_id)
        logger = logging.getLogger(__name__)
        logger.info(f"[DEBUG] truncate_history_after_message: session_id={session_id}, user_message_id={user_message_id}")

        if not history:
            logger.warning(f"[DEBUG] truncate_history_after_message: history is empty for session_id={session_id}")
            return None

        # 1. 定位到用户消息
        target_index = next(
            (i for i, msg in enumerate(history) if msg["message_id"] == user_message_id and msg["role"] == "user"),
            None
        )
        logger.info(f"[DEBUG] truncate_history_after_message: target_index={target_index}")

        if target_index is None:
            logger.warning(
                f"[DEBUG] truncate_history_after_message: cannot find user message_id={user_message_id} in history "
                f"(session_id={session_id})"
            )
            return None

        user_input = history[target_index]["content"]
        logger.info(f"[DEBUG] truncate_history_after_message: found user_input={user_input}")

        # 2. 删除该用户消息之后的所有回复
        truncated_history = history[:target_index + 1]
        self._store[session_id] = truncated_history
        # 覆盖写回 Redis
        if self.redis_store:
            try:
                asyncio.create_task(self.redis_store.set_messages(session_id, truncated_history))
            except Exception as _e:
                logger.debug(f"回写 Redis 失败(truncate): {session_id}, err={_e}")
        logger.info(f"[DEBUG] truncate_history_after_message: truncated history length={len(truncated_history)}")
        
        # 打印截断信息
        print(f"✂️ 截断历史记录 | Session: {session_id} | 基于用户消息ID: {user_message_id}")
        print(f"📊 截断前: {len(history)} 条消息 | 截断后: {len(truncated_history)} 条消息")
        print("=" * 50)

        return user_input

    def restore_history_to_memory(self, session_id: str, messages: List[Dict[str, str]]) -> int:
        """
        仅在内存中恢复历史消息（用于快照会话），不保存到数据库
        
        Args:
            session_id: 会话ID
            messages: 历史消息列表 [{"role": "user/assistant", "content": "..."}]
            
        Returns:
            恢复的消息数量
        """
        if not messages:
            return 0
        
        # 生成消息ID并构造内存格式
        restored_messages = []
        for m in messages:
            role = m.get("role", "")
            content = m.get("content", "")
            
            if role and content:
                message_id = uuid.uuid4().hex[:8]
                message_data = {
                    "message_id": message_id,
                    "role": role,
                    "content": content
                }
                restored_messages.append(message_data)
        
        # 直接写入内存存储，不触发数据库保存
        self._store[session_id] = restored_messages
        # 覆盖写回 Redis
        if self.redis_store:
            try:
                asyncio.create_task(self.redis_store.set_messages(session_id, restored_messages))
            except Exception as _e:
                self.logger.debug(f"回写 Redis 失败(restore): {session_id}, err={_e}")
        
        self.logger.info(f"🔄 快照历史已恢复到内存: session_id={session_id}, count={len(restored_messages)}")
        print(f"🔄 快照历史恢复 | Session: {session_id} | 恢复消息数: {len(restored_messages)}")
        print("📋 恢复的消息:")
        for i, msg in enumerate(restored_messages):
            role_emoji = "👤" if msg["role"] == "user" else "🤖"
            print(f"  [{i+1}] {role_emoji} {msg['role']} (ID: {msg['message_id']})")
            content_preview = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
            print(f"      📝 {content_preview}")
        print("🔄" + "="*48)
        
        return len(restored_messages)


# ✅ 全局唯一实例（临时占位，实际使用时应通过容器获取）
# 在应用启动时，应该通过容器创建并替换这个实例
message_service = None  # 将在容器中初始化
