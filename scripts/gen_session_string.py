import asyncio
import os
from pathlib import Path
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv


env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    load_dotenv(env_path)

API_ID = int(os.environ.get("TG_API_ID", "0"))
API_HASH = os.environ.get("TG_API_HASH", "")
PROXY_HOST = os.environ.get("TG_PROXY_HOST", "")
PROXY_PORT = int(os.environ.get("TG_PROXY_PORT", "0")) if os.environ.get("TG_PROXY_PORT") else None
PROXY_TYPE = os.environ.get("TG_PROXY_TYPE", "socks5")  # socks5, socks4, http


async def main() -> None:
    assert API_ID and API_HASH, "Please set TG_API_ID and TG_API_HASH in environment"
    
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
    
    async with TelegramClient(StringSession(), API_ID, API_HASH, proxy=proxy) as client:
        string = client.session.save()
        print("\nYour TG_SESSION_STRING (keep secret):\n")
        print(string)


if __name__ == "__main__":
    asyncio.run(main())


