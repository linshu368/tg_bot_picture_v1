import json
import time
from typing import Any, List, Optional, Dict
import httpx
from urllib.parse import quote
import logging


class UpstashSessionStore:
    """
    Upstash Redis REST 适配器（基于 RedisJSON）
    - 优先使用原子列表操作：RPUSH / LRANGE（避免并发覆盖）
    - 兼容旧数据（字符串化 JSON 数组存储），按需回退读取并可迁移
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
        logging.getLogger(__name__).info(f"UpstashSessionStore 初始化: base_url={self._base_url}, namespace={self._ns}")

    def _key_messages(self, session_id: str) -> str:
        return f"{self._ns}:{session_id}:messages"
    
    def _key_current_session(self, user_id: str) -> str:
        return f"{self._ns}:current:{user_id}"
    
    def _key_session_data(self, session_id: str) -> str:
        return f"{self._ns}:data:{session_id}"
    
    def _key_last_session(self, user_id: str) -> str:
        return f"{self._ns}:last:{user_id}"
    
    # 限制每个会话最多存储 20 轮 (40条消息)，避免 Token 超限和成本失控
    MAX_HISTORY_ITEMS = 40

    async def _cmd(self, *args: str) -> Any:
        """
        发送 Upstash REST 命令
        - GET: GET {base}/get/{key}
        - SET: POST {base}/set/{key} with JSON body {"value": <any JSON-able>}
        - 其他命令（如 lrange/rpush/del 等）: POST {base}/{command}/{arg1}/{arg2}/...
        - 其他: 路径式 + URL 编码参数（尽量避免大内容）
        """
        if not args:
            raise ValueError("Upstash _cmd requires at least one argument")
        command = args[0].lower()
        if command == "get":
            if len(args) < 2:
                raise ValueError("GET requires key")
            key = quote(str(args[1]), safe="")
            url = f"{self._base_url}/get/{key}"
            # print(f"🔍 DEBUG: 发送到 Upstash - URL: {url}")
            # print(f"🔍 DEBUG: 请求头: {self._headers}")
            resp = await self._client.get(url, headers=self._headers)
        elif command == "set":
            if len(args) < 3:
                raise ValueError("SET requires key and value")
            key = quote(str(args[1]), safe="")
            value = args[2]
            url = f"{self._base_url}/set/{key}"
            # print(f"🔍 DEBUG: 发送到 Upstash - URL: {url}")
            # print(f"🔍 DEBUG: 请求头: {self._headers}")
            resp = await self._client.post(url, headers=self._headers, json={"value": value})
        else:
            encoded_args = [quote(str(a), safe="") for a in args[1:]]
            url = f"{self._base_url}/{command}"
            if encoded_args:
                url = f"{url}/" + "/".join(encoded_args)
            # print(f"🔍 DEBUG: 发送到 Upstash - URL: {url}")
            # print(f"🔍 DEBUG: 请求头: {self._headers}")
            resp = await self._client.post(url, headers=self._headers)
        
        # print(f"🔍 DEBUG: 响应状态: {resp.status_code}")
        # print(f"🔍 DEBUG: 响应头: {dict(resp.headers)}")
        # try:
        #     resp_json = resp.json()
        #     print(f"🔍 DEBUG: 响应体: {resp_json}")
        # except Exception as e:
        #     print(f"🔍 DEBUG: 响应体解析失败: {e}")
        #     print(f"🔍 DEBUG: 原始响应: {resp.text}")
        
        if resp.status_code != 200:
            resp.raise_for_status()
        
        data = resp.json()
        # 标准化 Upstash 返回：当返回 {"error": "..."} 时抛出异常，便于上层回退处理
        if isinstance(data, dict) and data.get("error"):
            raise RuntimeError(str(data.get("error")))
        return data

    def _decode_get_result(self, result: Any) -> Any:
        """
        统一解码 Upstash GET 返回，提取 result/value，并在为字符串时尽力解析 JSON。
        """
        raw = None
        if isinstance(result, dict):
            raw = result.get("result")
            if raw is None:
                raw = result.get("value")
            # 兼容多层嵌套结构：反复展开 result/value，直到拿到最终原子值或包含 session_id 的对象
            while isinstance(raw, dict) and ("session_id" not in raw) and (("result" in raw) or ("value" in raw)):
                raw = raw.get("result") if "result" in raw else raw.get("value")
        if raw in (None, "null", ""):
            return None
        if isinstance(raw, (list, dict)):
            return raw
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                return parsed
            except json.JSONDecodeError:
                return raw
        return raw

    async def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """
        获取整个会话消息数组；若不存在则返回 []
        """
        key = self._key_messages(session_id)
        # 优先尝试列表读取（LRANGE），避免并发覆盖导致只剩最后一条
        try:
            result = await self._cmd("lrange", key, 0, -1)
            raw_list = None
            if isinstance(result, dict):
                raw_list = result.get("result")
                if raw_list is None:
                    raw_list = result.get("value")
            if not raw_list:
                return []
            messages: List[Dict[str, Any]] = []
            for item in raw_list:
                if isinstance(item, str):
                    try:
                        obj = json.loads(item)
                        if isinstance(obj, dict):
                            messages.append(obj)
                    except json.JSONDecodeError:
                        # 跳过无法解析的元素
                        pass
                elif isinstance(item, dict):
                    messages.append(item)
            return messages
        except Exception:
            # 兼容旧数据：尝试从简单 KV 中读取（可能是 JSON 字符串化的数组）
            try:
                result = await self._cmd("GET", key)
            except Exception:
                return []
            raw = None
            if isinstance(result, dict):
                raw = result.get("result")
                if raw is None:
                    raw = result.get("value")
            if raw in (None, "null", ""):
                return []
            if isinstance(raw, list):
                return raw  # 已经是数组
            if isinstance(raw, dict):
                # 不是数组，无法作为历史
                return []
            if isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return parsed
                except json.JSONDecodeError:
                    return []
            return []


    async def set_messages(self, session_id: str, messages: List[Dict[str, Any]]) -> None:
        """
        覆盖写入整个会话消息数组（原子：先 DEL 后 RPUSH 批量追加）
        """
        key = self._key_messages(session_id)
        # 清空旧值（兼容从 KV/JSON 迁移到 list）
        try:
            await self._cmd("del", key)
        except Exception:
            # 忽略不存在等错误
            pass
        if not messages:
            print(f"ℹ️ INFO: 会话 {session_id} 消息已更新，共 0 条")
            return
        # 批量 RPUSH
        # Upstash 支持：/rpush/{key}/{value1}/{value2}/...
        values = [json.dumps(m, ensure_ascii=False) for m in messages]
        await self._cmd("rpush", key, *values)
        
        # 强制截断：防止全量重写导致列表过长
        try:
            await self._cmd("ltrim", key, -self.MAX_HISTORY_ITEMS, -1)
        except Exception as e:
            logging.getLogger(__name__).warning(f"set_messages ltrim 失败: {e}")

        # 等待一段时间，确保数据同步到 Redis
        # time.sleep(1)  # 等待 3 秒，确保数据完全写入
        # print(f"🔍 Debug: 写入完成，等待 1 秒后继续")
        print(f"ℹ️ INFO: 会话 {session_id} 消息已更新，共 {len(messages)} 条")

    async def append_message(self, session_id: str, message: Dict[str, Any]) -> None:
        """
        追加单条消息到会话（原子 RPUSH）；兼容旧存储会自动覆盖为 list
        """
        key = self._key_messages(session_id)
        try:
            # 原子追加，避免“读-改-写”并发覆盖
            await self._cmd("rpush", key, json.dumps(message, ensure_ascii=False))
            # 自动滑动窗口：只保留最近 MAX_HISTORY_ITEMS 条
            await self._cmd("ltrim", key, -self.MAX_HISTORY_ITEMS, -1)
        except Exception:
            # 可能是旧 KV/JSON 存储导致类型冲突：回退迁移
            try:
                existing = await self.get_messages(session_id)
            except Exception:
                existing = []
            existing.append(message)
            await self.set_messages(session_id, existing)
    
        # 确认写入后的消息
        # print(f"🔍 Debug: 当前历史记录 {current_messages}")
        try:
            result = await self._cmd("llen", key)
            length = 0
            if isinstance(result, dict):
                length = result.get("result") or result.get("value") or 0
            print(f"ℹ️ INFO: 会话 {session_id} 追加消息成功，当前共 {int(length)} 条")
        except Exception:
            print(f"ℹ️ INFO: 会话 {session_id} 追加消息成功")

    # ----------------------------
    # Session pointer & metadata
    # ----------------------------
    async def get_current_session_id(self, user_id: str) -> Optional[str]:
        key = self._key_current_session(user_id)
        try:
            result = await self._cmd("GET", key)
        except Exception:
            logging.getLogger(__name__).info(f"get_current_session_id GET 失败: key={key}")
            return None
        value = self._decode_get_result(result)
        logging.getLogger(__name__).info(f"get_current_session_id 读取: key={key}, value={value}")
        if isinstance(value, dict):
            # 若误存为对象，优先 'session_id'，其次 'value'
            sid = value.get("session_id") or value.get("value")
            return sid or None
        if isinstance(value, str):
            return value or None
        return None

    async def set_current_session_id(self, user_id: str, session_id: str) -> None:
        key = self._key_current_session(user_id)
        await self._cmd("SET", key, session_id)
        logging.getLogger(__name__).info(f"set_current_session_id 写入: key={key}, session_id={session_id}")
    
    async def get_last_session_id(self, user_id: str) -> Optional[str]:
        key = self._key_last_session(user_id)
        try:
            result = await self._cmd("GET", key)
        except Exception:
            logging.getLogger(__name__).info(f"get_last_session_id GET 失败: key={key}")
            return None
        value = self._decode_get_result(result)
        logging.getLogger(__name__).info(f"get_last_session_id 读取: key={key}, value={value}")
        if isinstance(value, dict):
            sid = value.get("session_id") or value.get("value")
            return sid or None
        if isinstance(value, str):
            return value or None
        return None
    
    async def set_last_session_id(self, user_id: str, session_id: str) -> None:
        key = self._key_last_session(user_id)
        await self._cmd("SET", key, session_id)
        logging.getLogger(__name__).info(f"set_last_session_id 写入: key={key}, session_id={session_id}")

    async def get_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        key = self._key_session_data(session_id)
        try:
            result = await self._cmd("GET", key)
        except Exception:
            return None
        value = self._decode_get_result(result)
        try:
            logging.getLogger(__name__).info(f"get_session_data 读取: key={key}, value={value}")
        except Exception:
            pass
        return value if isinstance(value, dict) else None

    async def set_session_data(self, session_id: str, data: Dict[str, Any]) -> None:
        key = self._key_session_data(session_id)
        await self._cmd("SET", key, data)
        try:
            rid = None
            try:
                rid = data.get("role_id") if isinstance(data, dict) else None
            except Exception:
                rid = None
            logging.getLogger(__name__).info(f"set_session_data 写入: key={key}, role_id={rid}, keys={list(data.keys()) if isinstance(data, dict) else 'n/a'}")
        except Exception:
            pass

