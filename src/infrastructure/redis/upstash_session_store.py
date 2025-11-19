import json
import time
from typing import Any, List, Optional, Dict
import httpx
from urllib.parse import quote


class UpstashSessionStore:
    """
    Upstash Redis REST 适配器（基于 RedisJSON）
    - 使用 JSON.GET / JSON.SET / JSON.ARRAPPEND
    - 会话按 key: session:{session_id}:messages 进行隔离
    """
    def __init__(self, rest_url: str, token: str, namespace: str = "session", timeout: float = 10.0):
        if not rest_url or not token:
            raise ValueError("UpstashSessionStore requires non-empty rest_url and token")
        self._base_url = rest_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        self._ns = namespace
        self._client = httpx.AsyncClient(timeout=timeout)

    def _key_messages(self, session_id: str) -> str:
        return f"{self._ns}:{session_id}:messages"

    async def _cmd(self, *args: str) -> Any:
        """
        发送 Upstash REST 命令（路径式）
        使用 {base}/{command}/{arg1}/{arg2}...，并对参数进行 URL 编码，避免内容截断
        """
        if not args:
            raise ValueError("Upstash _cmd requires at least one argument")
        command = args[0].lower()
        encoded_args = [quote(str(a), safe="") for a in args[1:]]
        url = f"{self._base_url}/{command}"
        if encoded_args:
            url = f"{url}/" + "/".join(encoded_args)
        print(f"🔍 DEBUG: 发送到 Upstash - URL: {url}")
        print(f"🔍 DEBUG: 请求头: {self._headers}")

        resp = await self._client.post(url, headers=self._headers)
        
        print(f"🔍 DEBUG: 响应状态: {resp.status_code}")
        print(f"🔍 DEBUG: 响应头: {dict(resp.headers)}")
        try:
            resp_json = resp.json()
            print(f"🔍 DEBUG: 响应体: {resp_json}")
        except Exception as e:
            print(f"🔍 DEBUG: 响应体解析失败: {e}")
            print(f"🔍 DEBUG: 原始响应: {resp.text}")
        
        if resp.status_code != 200:
            resp.raise_for_status()
        
        return resp.json()

    async def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """
        获取整个会话消息数组；若不存在则返回 []
        """
        key = self._key_messages(session_id)
        result = await self._cmd("GET", key)
    
        if isinstance(result, dict) and 'result' in result:
            raw = result['result']
            if raw is None or raw == "null" or raw == "":
                return []
            try:
                return json.loads(raw)
            except Exception:
                return []
        return []


    async def set_messages(self, session_id: str, messages: List[Dict[str, Any]]) -> None:
        """
        覆盖写入整个会话消息数组
        """
        key = self._key_messages(session_id)
        value_json = json.dumps(messages, ensure_ascii=False)
        await self._cmd("SET", key, value_json)

        # 等待一段时间，确保数据同步到 Redis
        # time.sleep(1)  # 等待 3 秒，确保数据完全写入
        # print(f"🔍 Debug: 写入完成，等待 1 秒后继续")

    async def append_message(self, session_id: str, message: Dict[str, Any]) -> None:
        """
        追加单条消息到会话数组；若 key 不存在则先初始化空数组
        """
        key = self._key_messages(session_id)
        current_messages = await self.get_messages(session_id)
        current_messages.append(message)
        await self.set_messages(session_id, current_messages)
    
        # 确认写入后的消息
        print(f"🔍 Debug: 当前历史记录 {current_messages}")

