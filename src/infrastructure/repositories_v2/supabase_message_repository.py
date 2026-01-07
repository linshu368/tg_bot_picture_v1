"""
Supabase消息仓储
负责消息数据的持久化操作
"""

import logging
import uuid
import asyncio
import builtins
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from .supabase_manager import SupabaseManager


class SupabaseMessageRepository:
    """Supabase消息仓储"""
    
    def __init__(self, supabase_manager: SupabaseManager):
        self.supabase_manager = supabase_manager
        self.logger = logging.getLogger(__name__)
        self.table_name = "messages"
    
    async def save_message(self, user_id: str, role_id: Optional[str], session_id: str, 
                          sender: str,
                          # 🆕 新字段写入逻辑
                          instructions: Optional[str] = None,
                          bot_reply: Optional[str] = None,
                          history: Optional[str] = None,
                          model_name: Optional[str] = None,
                          user_input: Optional[str] = None,
                          round: Optional[int] = None,
                          full_response_latency: Optional[float] = None,
                          first_response_latency: Optional[float] = None,
                          attempt_count: Optional[int] = None) -> Optional[str]:
        """
        保存消息到Supabase
        
        Args:
            user_id: 用户ID (TEXT格式，如Telegram用户ID)
            role_id: 角色ID (TEXT格式，可为None) 
            session_id: 会话ID (TEXT格式，如sess_xxxxxxxx)
            sender: 发送者 ('user' 或 'bot')
            instructions: 本轮使用的指令内容
            bot_reply: 机器人回复内容
            history: 对话历史记录
            model_name: 使用的AI模型名称
            user_input: 用户输入内容
            round: 对话轮次
            full_response_latency: 完整响应耗时（秒）
            first_response_latency: 首响耗时（秒）
            attempt_count: 尝试次数（第几次调用成功）
            
        Returns:
            消息记录的ID，失败返回None
        """
        try:
            client = self.supabase_manager.get_client()
            
            # 数据验证和转换
            if not user_id or not user_id.strip():
                self.logger.error("❌ user_id 不能为空")
                return None
            # sender 参数仅用于兼容旧接口，入库时不再写入，也不做强校验
            
            # 轻量数据验证（兼容当前先写bot后补user的流程）
            if round is not None:
                try:
                    if int(round) <= 0:
                        self.logger.error(f"❌ round 必须为正整数，当前值: {round}")
                        return None
                except Exception:
                    self.logger.error(f"❌ round 必须为整数，当前值: {round}")
                    return None
            if user_input is None and bot_reply is None:
                # 允许短暂不完整（例如先写bot_reply），但记录警告
                self.logger.warning("⚠️ 本次写入未包含 user_input 或 bot_reply，可能为临时不完整行（将于后续补全）")
            if user_input is not None and instructions is None:
                # 用户输入通常伴随指令与历史，缺省并非致命，提醒优化
                self.logger.debug("ℹ️ 用户输入未携带 instructions（允许，但建议补充以便复现）")
            if bot_reply is not None and user_input is None and round is None:
                # 允许 bot 先写，但建议尽快补充 round 以实现一轮一行管理
                self.logger.debug("ℹ️ 检测到仅 bot_reply 写入且 round 缺失（允许短暂存在，建议后续补充 round 与 user_input）")
            
            # 构造消息数据
            message_data = {
                "user_id": str(user_id).strip(),
                "role_id": str(role_id).strip() if role_id else None, 
                "session_id": str(session_id).strip() if session_id else None
                # timestamp 由数据库触发器自动设置为东八区时间
            }
            # 🆕 新字段写入逻辑：按需添加新字段
            if instructions is not None:
                message_data["instructions"] = instructions
            if bot_reply is not None:
                message_data["bot_reply"] = bot_reply
            if history is not None:
                message_data["history"] = history
            if model_name is not None:
                message_data["model_name"] = model_name
            if user_input is not None:
                message_data["user_input"] = user_input
            if round is not None:
                message_data["round"] = round
            if full_response_latency is not None:
                # 数据库字段为 Integer 类型，需将秒数四舍五入为整数
                try:
                    # 确保是浮点数或数字
                    if isinstance(full_response_latency, (int, float)):
                        message_data["full_response"] = int(builtins.round(float(full_response_latency)))
                    else:
                         self.logger.warning(f"⚠️ full_response_latency 类型错误: {type(full_response_latency)}")
                         message_data["full_response"] = None
                except Exception as e:
                    self.logger.warning(f"⚠️ full_response_latency 转换整数失败: {full_response_latency}, error: {e}")
                    message_data["full_response"] = None
            
            # 🆕 新增字段：首响耗时（保留小数，存为 float）
            if first_response_latency is not None:
                try:
                    message_data["first_response_latency"] = float(first_response_latency)
                except Exception:
                    self.logger.warning(f"⚠️ first_response_latency 转换失败: {first_response_latency}")

            # 🆕 新增字段：尝试次数（整数）
            if attempt_count is not None:
                try:
                    message_data["attempt_count"] = int(attempt_count)
                except Exception:
                    self.logger.warning(f"⚠️ attempt_count 转换失败: {attempt_count}")
            
            # 异步插入数据（使用线程池避免阻塞主线程）
            def _sync_insert():
                return client.table(self.table_name).insert(message_data).execute()
            
            result = await asyncio.to_thread(_sync_insert)
            
            if result.data and len(result.data) > 0:
                record_id = result.data[0].get('id')
                self.logger.info(f"✅ 消息已保存到Supabase: id={record_id}, user_id={user_id}, sender={sender}")
                return str(record_id)
            else:
                self.logger.error(f"❌ 保存消息失败: 无返回数据")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ 保存消息到Supabase失败: {e}")
            return None
    
    async def get_messages_by_session(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        根据会话ID获取消息历史
        
        Args:
            session_id: 会话ID
            limit: 返回消息数量限制
            
        Returns:
            消息列表，按时间戳排序
        """
        try:
            client = self.supabase_manager.get_client()
            
            def _sync_select():
                return client.table(self.table_name)\
                    .select("*")\
                    .eq("session_id", session_id)\
                    .order("timestamp", desc=False)\
                    .limit(limit)\
                    .execute()
            
            result = await asyncio.to_thread(_sync_select)
            
            if result.data:
                self.logger.info(f"📚 获取会话消息: session_id={session_id}, count={len(result.data)}")
                return result.data
            else:
                return []
                
        except Exception as e:
            self.logger.error(f"❌ 获取会话消息失败: {e}")
            return []
    
    async def get_user_message_count(self, user_id: str, date_from: Optional[datetime] = None) -> int:
        """
        获取用户消息数量统计
        
        Args:
            user_id: 用户ID
            date_from: 统计起始时间，None表示全部时间
            
        Returns:
            消息数量
        """
        try:
            client = self.supabase_manager.get_client()
            
            def _sync_count():
                query = client.table(self.table_name)\
                    .select("id", count="exact")\
                    .eq("user_id", user_id)\
                    .gt("round", 0)  # 使用 round 统计用户消息轮数
                
                if date_from:
                    query = query.gte("timestamp", date_from.isoformat())
                
                return query.execute()
            
            result = await asyncio.to_thread(_sync_count)
            
            return result.count or 0
            
        except Exception as e:
            self.logger.error(f"❌ 获取用户消息数量失败: {e}")
            return 0
    
    async def get_user_daily_message_count(self, user_id: str) -> int:
        """
        获取用户今日消息数量统计（按东八区时间计算）
        
        Args:
            user_id: 用户ID
            
        Returns:
            今日消息数量
        """
        try:
            client = self.supabase_manager.get_client()
            
            # 获取东八区今日开始时间（UTC+8）
            from datetime import datetime, timezone, timedelta
            beijing_tz = timezone(timedelta(hours=8))
            now_beijing = datetime.now(beijing_tz)
            today_start_beijing = now_beijing.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # 转换为UTC时间用于数据库查询
            today_start_utc = today_start_beijing.astimezone(timezone.utc)
            
            def _sync_daily_count():
                return client.table(self.table_name)\
                    .select("id", count="exact")\
                    .eq("user_id", user_id)\
                    .gt("round", 0)\
                    .gte("timestamp", today_start_utc.isoformat())\
                    .execute()
            
            result = await asyncio.to_thread(_sync_daily_count)
            
            count = result.count or 0
            self.logger.info(f"📊 用户今日消息统计: user_id={user_id}, count={count}")
            return count
            
        except Exception as e:
            self.logger.error(f"❌ 获取用户今日消息数量失败: {e}")
            return 0
    
    async def delete_messages_by_session(self, session_id: str) -> bool:
        """
        删除指定会话的所有消息
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否删除成功
        """
        try:
            client = self.supabase_manager.get_client()
            
            def _sync_delete():
                return client.table(self.table_name)\
                    .delete()\
                    .eq("session_id", session_id)\
                    .execute()
            
            result = await asyncio.to_thread(_sync_delete)
            
            self.logger.info(f"🗑️ 删除会话消息: session_id={session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 删除会话消息失败: {e}")
            return False
    
    def save_user_message_with_real_instructions_async(self, user_id: str, role_id: Optional[str], 
                                                      session_id: str,
                                                      # 🆕 新字段写入逻辑
                                                      instructions: Optional[str] = None,
                                                      bot_reply: Optional[str] = None,
                                                      history: Optional[str] = None,
                                                      model_name: Optional[str] = None,
                                                      user_input: Optional[str] = None,
                                                      round: Optional[int] = None,
                                                      full_response_latency: Optional[float] = None,
                                                      first_response_latency: Optional[float] = None,
                                                      retry_attempt: Optional[int] = None) -> asyncio.Task:
        """
        异步保存用户消息（使用AI生成时的真实数据内容）
        
        这是推荐的保存方式，确保保存的数据与AI调用时完全一致
        
        Args:
            user_id: 用户ID
            role_id: 角色ID
            session_id: 会话ID
            instructions: AI生成时实际使用的指令内容
            bot_reply: 机器人回复内容
            history: 对话历史记录
            model_name: 使用的AI模型名称
            user_input: 用户输入内容
            round: 对话轮次
            full_response_latency: 完整响应耗时（秒）
            first_response_latency: 首响耗时（秒）
            retry_attempt: 尝试次数（对应 attempt_count）
            
        Returns:
            asyncio.Task: 可以await的任务对象
        """
        async def _safe_save():
            try:
                result = await self.save_message(
                    user_id=user_id,
                    role_id=role_id,
                    session_id=session_id,
                    sender="user",
                    # 🆕 新字段写入逻辑：透传到基础保存方法
                    instructions=instructions,
                    bot_reply=bot_reply,
                    history=history,
                    model_name=model_name,
                    user_input=user_input,
                    round=round,
                    full_response_latency=full_response_latency,
                    first_response_latency=first_response_latency,
                    attempt_count=retry_attempt
                )
                
                if result:
                    self.logger.debug(f"🔄 异步保存用户消息成功: id={result}")
                else:
                    self.logger.warning(f"⚠️ 异步保存用户消息失败: session={session_id}")
            except Exception as e:
                self.logger.error(f"❌ 异步保存用户消息异常: {e}")
        
        return asyncio.create_task(_safe_save())
    
    async def get_session_user_turn_count(self, session_id: str) -> int:
        """
        统计会话中用户消息的轮数
        
        Args:
            session_id: 会话ID
            
        Returns:
            用户消息数量
        """
        try:
            client = self.supabase_manager.get_client()
            
            def _sync_count():
                # 简单统计 user_id 对应的 user 消息数
                # 或者更严谨地：统计 session_id 下 sender='user' (或 role_id不为空) 的记录数
                # 这里使用 sender='user' 来区分
                return client.table(self.table_name)\
                    .select("id", count="exact")\
                    .eq("session_id", session_id)\
                    .gt("round", 0)\
                    .execute()
            
            result = await asyncio.to_thread(_sync_count)
            
            count = result.count or 0
            # self.logger.info(f"📊 会话用户轮数统计: session_id={session_id}, count={count}")
            return count
            
        except Exception as e:
            self.logger.error(f"❌ 获取会话用户轮数失败: {e}")
            return 0

    async def update_message_usage(self, session_id: str, generation_id: str, usage_data: Dict[str, Any]) -> bool:
        """
        更新消息的AI使用统计数据
        通过 session_id 找到最新的一条消息（或者通过 generation_id 如果之前存了的话，
        但目前主要靠 session_id 找到最近的一条 bot 消息，或者我们在 save_message 时返回了 id，
        但这里是异步回调，可能只知道 session_id）

        更严谨的做法是：update_last_message_by_session_id
        或者我们在 execution_context 里如果能拿到 message_id 就更好了，但 save_message 是在流式结束时调用的。
        
        Args:
            session_id: 会话ID
            generation_id: OpenRouter生成的ID (用于校验或存储)
            usage_data: 统计数据字典
            
        Returns:
            是否更新成功
        """
        try:
            # 1. 获取该会话最新的一条消息 (且是 assistant/bot 发送的)
            # 或者直接获取最新的一条消息（不论是谁，因为我们存的是 snapshot row，通常包含 bot_reply）
            last_row = await self._get_last_round_row(session_id)
            if not last_row:
                self.logger.warning(f"⚠️ 更新统计失败: 未找到会话 {session_id} 的最新消息")
                return False
                
            msg_id = last_row.get("id")
            
            # 2. 准备更新的数据
            update_payload = {}
            
            # 映射字段 (OpenRouter API -> DB Columns)
            # API: data.model -> DB: model (注意这里可能会覆盖之前的 model_name，视需求而定，OpenRouter返回的模型名可能更精确)
            # 但用户指示的是：[model, generation_time, latency, ...] 写入 messages 表
            
            api_data = usage_data.get("data", {})
            
            # 字段映射表
            # key: DB字段名, value: (API字段名, 类型转换函数)
            field_map = {
                "model": ("model", str),
                "generation_time": ("generation_time", lambda x: float(x) / 1000.0 if x is not None else None), # ms -> s
                "latency": ("latency", lambda x: float(x) / 1000.0 if x is not None else None), # ms -> s
                "native_tokens_prompt": ("native_tokens_prompt", int),
                "native_tokens_completion": ("native_tokens_completion", int),
                "native_tokens_reasoning": ("native_tokens_reasoning", int),
                "native_tokens_cached": ("native_tokens_cached", int),
                "cache_discount": ("cache_discount", float),
                "usage": ("usage", float),
                "finish_reason": ("finish_reason", str),
                "provider_name": ("provider_name", str),
            }
            
            for db_col, (api_key, converter) in field_map.items():
                val = api_data.get(api_key)
                if val is not None:
                    try:
                        update_payload[db_col] = converter(val)
                    except Exception as _e:
                        self.logger.warning(f"字段 {db_col} 转换失败: val={val}, err={_e}")
                        
            if not update_payload:
                self.logger.warning("⚠️ 没有有效的统计数据需要更新")
                return False
                
            # 3. 执行更新
            client = self.supabase_manager.get_client()
            
            def _sync_update():
                return client.table(self.table_name)\
                    .update(update_payload)\
                    .eq("id", msg_id)\
                    .execute()
                    
            result = await asyncio.to_thread(_sync_update)
            
            if result.data:
                self.logger.info(f"✅ 成功更新 AI 使用统计: session_id={session_id}, msg_id={msg_id}, usage={update_payload.get('usage')}")
                return True
            else:
                self.logger.warning(f"⚠️ 更新统计返回空数据: session_id={session_id}, msg_id={msg_id}")
                return False

        except Exception as e:
            self.logger.error(f"❌ 更新消息统计数据失败: {e}")
            return False

    async def _get_last_round_row(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话中最新一轮（最大 round）的行"""
        try:
            client = self.supabase_manager.get_client()
            def _sync_select_last_round():
                return client.table(self.table_name)\
                    .select("id, round")\
                    .eq("session_id", session_id)\
                    .gt("round", 0)\
                    .order("round", desc=True)\
                    .limit(1)\
                    .execute()
            result = await asyncio.to_thread(_sync_select_last_round)
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            self.logger.error(f"❌ 获取最新轮次失败: session_id={session_id}, err={e}")
            return None
    
    async def delete_last_bot_message(self, session_id: str) -> bool:
        """删除会话中最新一条机器人消息（用于重新生成时清理旧回复）"""
        try:
            last_round_row = await self._get_last_round_row(session_id)
            if not last_round_row:
                return True
            msg_id = last_round_row.get("id")
            client = self.supabase_manager.get_client()
            # 清空该轮的回复相关字段，而不是删除整行
            def _sync_update_clear():
                return client.table(self.table_name)\
                    .update({"bot_reply": None, "history": None, "model_name": None})\
                    .eq("id", msg_id)\
                    .execute()
            await asyncio.to_thread(_sync_update_clear)
            self.logger.info(f"🧹 已清空最新一轮的机器人回复字段: session_id={session_id}, id={msg_id}")
            return True
        except Exception as e:
            self.logger.error(f"❌ 删除最新机器人消息失败: session_id={session_id}, err={e}")
            return False
    
    async def update_last_user_message_reply(self, session_id: str, 
                                            bot_reply: Optional[str] = None,
                                            history: Optional[str] = None,
                                            model_name: Optional[str] = None) -> bool:
        """
        更新会话中最新一条用户消息的回复相关字段（用于重新生成时覆盖旧 bot_reply/history/model）
        """
        try:
            last_round_row = await self._get_last_round_row(session_id)
            if not last_round_row:
                return False
            msg_id = last_round_row.get("id")
            payload: Dict[str, Any] = {}
            if bot_reply is not None:
                payload["bot_reply"] = bot_reply
            if history is not None:
                payload["history"] = history
            if model_name is not None:
                payload["model_name"] = model_name
            if not payload:
                return True
            client = self.supabase_manager.get_client()
            def _sync_update():
                return client.table(self.table_name)\
                    .update(payload)\
                    .eq("id", msg_id)\
                    .execute()
            await asyncio.to_thread(_sync_update)
            self.logger.info(f"✏️ 已更新最新用户消息: session_id={session_id}, id={msg_id}, fields={list(payload.keys())}")
            return True
        except Exception as e:
            self.logger.error(f"❌ 更新最新用户消息失败: session_id={session_id}, err={e}")
            return False
    
    def save_bot_message_async(self, user_id: str, role_id: Optional[str], 
                              session_id: str, bot_reply: str) -> asyncio.Task:
        """
        异步保存机器人消息（不阻塞主流程）
        
        Args:
            user_id: 用户ID
            role_id: 角色ID
            session_id: 会话ID
            bot_reply: 机器人回复内容
            
        Returns:
            asyncio.Task: 可以await的任务对象
        """
        async def _safe_save():
            try:
                result = await self.save_message(
                    user_id=user_id, 
                    role_id=role_id, 
                    session_id=session_id, 
                    sender="bot",
                    bot_reply=bot_reply
                    # bot消息主要保存回复内容，其他字段使用默认的None值
                )
                if result:
                    self.logger.debug(f"🔄 异步保存机器人消息成功: id={result}")
                else:
                    self.logger.warning(f"⚠️ 异步保存机器人消息失败: session={session_id}")
            except Exception as e:
                self.logger.error(f"❌ 异步保存机器人消息异常: {e}")
        
        return asyncio.create_task(_safe_save())
