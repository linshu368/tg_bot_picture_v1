import asyncio
import json
import os
import random
from pathlib import Path
from typing import List, Dict, Any

from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv


env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    load_dotenv(env_path)

ROLE_LIBRARY_PATH = os.environ.get("ROLE_LIBRARY_PATH", str(Path(__file__).resolve().parents[1] / "demo" / "role_library.json"))
ROLE_CHANNEL_URL = os.environ.get("ROLE_CHANNEL_URL", "")
API_ID = int(os.environ.get("TG_API_ID", "0"))
API_HASH = os.environ.get("TG_API_HASH", "")
SESSION_STRING = os.environ.get("TG_SESSION_STRING", "")
PROXY_HOST = os.environ.get("TG_PROXY_HOST", "")
PROXY_PORT = int(os.environ.get("TG_PROXY_PORT", "0")) if os.environ.get("TG_PROXY_PORT") else None
PROXY_TYPE = os.environ.get("TG_PROXY_TYPE", "socks5")  # socks5, socks4, http
POST_INTERVAL_MINUTES = float(os.environ.get("POST_INTERVAL_MINUTES", "15"))
JITTER_SECONDS = int(os.environ.get("POST_JITTER_SECONDS", "10"))


def load_roles() -> List[Dict[str, Any]]:
    with open(ROLE_LIBRARY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_caption(role: Dict[str, Any]) -> str:
    name = role.get("name", "角色")
    summary = role.get("summary", "")
    tags = role.get("tags", [])
    deeplink = role.get("deeplink", "")
    tag_line = " ".join([f"#{t}" for t in tags])
    caption = (
        f"#{name}\n\n"
        f"{summary}\n\n"
        f"[🚀 启动酒馆AI]({deeplink})\n\n"
        f"{tag_line}"
    )
    return caption


def parse_channel_username(url_or_username: str) -> str:
    s = (url_or_username or "").strip()
    if not s:
        raise ValueError("ROLE_CHANNEL_URL is empty. Please set https://t.me/<username> in .env")
    if s.startswith("@"):  # already username
        return s
    prefixes = [
        "https://t.me/",
        "http://t.me/",
        "https://telegram.me/",
        "http://telegram.me/",
        "t.me/",
        "telegram.me/",
    ]
    for p in prefixes:
        if s.startswith(p):
            s = s[len(p):]
            break
    first = s.split("/")[0]
    if not first:
        raise ValueError("ROLE_CHANNEL_URL invalid")
    if first == "c" or first.startswith("+"):
        raise ValueError("Private/invite links not supported. Use public username URL like https://t.me/ai_role_list")
    return "@" + first


async def main() -> None:
    assert API_ID and API_HASH and SESSION_STRING, "Missing TG_API_ID/TG_API_HASH/TG_SESSION_STRING"
    channel = parse_channel_username(ROLE_CHANNEL_URL)

    roles = load_roles()
    if not roles:
        raise RuntimeError("No roles found in role_library.json")

    # 配置代理（如果设置了）
    proxy = None
    if PROXY_HOST and PROXY_PORT:
        import socks
        if PROXY_TYPE.lower() == "socks5":
            proxy = (socks.SOCKS5, PROXY_HOST, PROXY_PORT)
        elif PROXY_TYPE.lower() == "socks4":
            proxy = (socks.SOCKS4, PROXY_HOST, PROXY_PORT)
        elif PROXY_TYPE.lower() == "http":
            proxy = (socks.HTTP, PROXY_HOST, PROXY_PORT)
        else:
            raise ValueError(f"Unsupported proxy type: {PROXY_TYPE}")
        print(f"Using {PROXY_TYPE} proxy: {PROXY_HOST}:{PROXY_PORT}")
    
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH, proxy=proxy)
    async with client:
        index = 0
        while True:
            role = roles[index % len(roles)]
            caption = build_caption(role)

            # 先发纯文本，避免非直链图片失败；后续可扩展 send_file
            await client.send_message(channel, caption, parse_mode='md')

            index += 1
            base = POST_INTERVAL_MINUTES * 60
            jitter = random.randint(0, JITTER_SECONDS)
            await asyncio.sleep(base + jitter)


if __name__ == "__main__":
    asyncio.run(main())


