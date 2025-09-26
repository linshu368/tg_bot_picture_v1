import uuid

class MessageService:
    def __init__(self):
        self._store = {}  # { session_id: [ {role, content, message_id} ] }

    def save_message(self, session_id, role, content):
        if len(content) > 10000:
            raise ValueError("4002: 消息过长，最大长度 10000")
        message_id = str(uuid.uuid4())
        self._store.setdefault(session_id, []).append({
            "message_id": message_id,
            "role": role,
            "content": content
        })
        return message_id

    def get_history(self, session_id):
        return self._store.get(session_id, [])

    # 未来可迁出为ConversationService
    async def regenerate_reply(self, session_id: str, last_message_id: str, ai_port, role_data):
        """
        基于指定用户消息重新生成回复
        - 精确定位 last_message_id
        - 删除旧的 Bot 回复
        - 保存新的 Bot 回复
        """
        history = self.get_history(session_id)
        if not history:
            return {"message_id": None, "reply": "⚠️ 没有找到历史记录"}

        # 1. 定位到用户消息
        target_index = next((i for i, msg in enumerate(history) if msg["message_id"] == last_message_id and msg["role"] == "user"), None)
        if target_index is None:
            return {"message_id": None, "reply": "⚠️ 无法找到指定的用户消息"}

        user_input = history[target_index]["content"]

        # 2. 删除该用户消息之后的 Bot 回复（保持一问一答的配对）
        history = history[:target_index + 1]  # 保留到用户消息
        self._store[session_id] = history

        # 3. 重新生成 AI 回复
        reply = await ai_port.generate_reply(role_data, history, user_input)

        # 4. 保存新的 Bot 回复
        bot_message_id = self.save_message(session_id, "assistant", reply)

        return {"message_id": bot_message_id, "reply": reply}
