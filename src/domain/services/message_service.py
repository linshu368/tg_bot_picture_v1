import uuid

class MessageService:
    def __init__(self):
        self._store = {}  # { session_id: [ {role, content, message_id} ] }

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
        
        return message_id

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


# ✅ 全局唯一实例
message_service = MessageService()

    # # 未来可迁出为ConversationService
    # async def regenerate_reply(self, session_id: str, last_message_id: str, ai_port, role_data):
    #     """
    #     基于指定用户消息重新生成回复
    #     - 精确定位 last_message_id
    #     - 删除旧的 Bot 回复
    #     - 保存新的 Bot 回复
    #     """
    #     history = self.get_history(session_id)
    #     if not history:
    #         return {"message_id": None, "reply": "⚠️ 没有找到历史记录"}

    #     # 1. 定位到用户消息
    #     target_index = next((i for i, msg in enumerate(history) if msg["message_id"] == last_message_id and msg["role"] == "user"), None)
    #     if target_index is None:
    #         return {"message_id": None, "reply": "⚠️ 无法找到指定的用户消息"}

    #     user_input = history[target_index]["content"]

    #     # 2. 删除该用户消息之后的 Bot 回复（保持一问一答的配对）
    #     history = history[:target_index + 1]  # 保留到用户消息
    #     self._store[session_id] = history

    #     # 3. 重新生成 AI 回复
    #     reply = await ai_port.generate_reply(role_data, history, user_input)

    #     # 4. 保存新的 Bot 回复
    #     bot_message_id = self.save_message(session_id, "assistant", reply)

    #     return {"message_id": bot_message_id, "reply": reply}
