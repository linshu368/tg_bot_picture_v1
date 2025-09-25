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

    #未来可迁出为ConversationService
    async def regenerate_reply(self, session_id: str, last_message_id: str, ai_port, role_data):
        """
        基于上一次消息重新生成回复
        - 使用最后一条用户消息作为输入
        """
        history = self.get_history(session_id)

        # 找到最后一条用户消息
        last_user_message = next(
            (msg for msg in reversed(history) if msg["role"] == "user"),
            {"content": ""}
        )
        user_input = last_user_message["content"] 

        # regenerate 的关键点：输入为空，由 AI 自行决定基于 last_message_id 重生成
        reply = await ai_port.generate_reply(role_data, history, user_input)

        bot_message_id = self.save_message(session_id, "assistant", reply)

        return {"message_id": bot_message_id, "reply": reply}