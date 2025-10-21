import asyncio
import json
import os
import random
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

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
CHECK_INTERVAL_MINUTES = float(os.environ.get("CHECK_INTERVAL_MINUTES", "15"))
PUBLISH_INTERVAL_SECONDS = int(os.environ.get("PUBLISH_INTERVAL_SECONDS", "30"))
RETRY_INTERVAL_MINUTES = float(os.environ.get("RETRY_INTERVAL_MINUTES", "5"))


def load_roles() -> List[Dict[str, Any]]:
    with open(ROLE_LIBRARY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_roles(roles: List[Dict[str, Any]]) -> None:
    """保存更新后的角色列表到 JSON 文件"""
    with open(ROLE_LIBRARY_PATH, "w", encoding="utf-8") as f:
        json.dump(roles, f, ensure_ascii=False, indent=2)


def should_publish_role(role: Dict[str, Any]) -> bool:
    """判断角色是否需要发布"""
    return 'created_at' not in role or not role.get('created_at')


def is_direct_image_url(url: str) -> bool:
    """判断是否为直链图片"""
    return bool(url and url.startswith('http') and 't.me/' not in url)


async def resolve_avatar_to_direct_url(client: TelegramClient, avatar_url: str) -> Optional[str]:
    """
    将任何头像URL转换为直链
    - 直链 → 直接返回
    - 非直链（Telegram链接）→ 解析为CDN直链
    """
    if not avatar_url:
        return None
        
    if is_direct_image_url(avatar_url):
        # 情况2：已经是直链（Supabase等）
        return avatar_url
    
    # 情况1：非直链，解析Telegram链接
    import re
    match = re.search(r't\.me/c/(\d+)/(\d+)', avatar_url)
    if not match:
        return None
        
    try:
        channel_id, message_id = int(match.group(1)), int(match.group(2))
        # Telegram 私有频道 ID 需要转换为负数
        channel_id = -1000000000000 - channel_id
        message = await client.get_messages(channel_id, ids=message_id)
        
        if message and message.media:
            # file=None → 只返回CDN URL，不下载
            cdn_url = await client.download_media(message.media, file=None)
            print(f"📸 解析头像CDN直链: {cdn_url}")
            return cdn_url
    except Exception as e:
        print(f"⚠️ 解析Telegram头像失败: {e}")
    
    return None


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


async def publish_role(client: TelegramClient, channel: str, role: Dict[str, Any], roles_list: List[Dict[str, Any]]) -> None:
    """发布单个角色并更新数据"""
    try:
        caption = build_caption(role)
        avatar_url = role.get('avatar')
        
        # 统一转换为直链
        direct_url = await resolve_avatar_to_direct_url(client, avatar_url)
        
        if direct_url:
            # 发送带图片的消息
            message = await client.send_file(channel, direct_url, caption=caption, parse_mode='md')
            print(f"📸 使用图片发布: {role.get('name', '未知')}")
        else:
            # 降级为纯文本
            message = await client.send_message(channel, caption, parse_mode='md')
            print(f"📝 降级为纯文本发布: {role.get('name', '未知')}")
        
        # 更新角色数据
        channel_username = channel.lstrip('@')
        post_link = f"https://t.me/{channel_username}/{message.id}"
        role['created_at'] = datetime.now().isoformat()
        role['post_link'] = post_link
        
        # 保存到文件
        save_roles(roles_list)
        
        print(f"✅ 发布角色 '{role.get('name', '未知')}' 完成，post_link: {post_link}")
        
    except Exception as e:
        print(f"❌ 发布角色 '{role.get('name', '未知')}' 失败: {e}")


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
        print(f"🚀 角色发布脚本启动，每 {CHECK_INTERVAL_MINUTES} 分钟检查一次...")
        
        while True:
            try:
                # 1. 重新加载角色列表（支持运行时添加新角色）
                roles = load_roles()
                if not roles:
                    print("⚠️ role_library.json 中没有角色数据")
                    await asyncio.sleep(CHECK_INTERVAL_MINUTES * 60)
                    continue
                
                # 2. 筛选未发布的角色
                unpublished_roles = [role for role in roles if should_publish_role(role)]
                
                # 3. 发布处理
                if unpublished_roles:
                    print(f"🔍 发现 {len(unpublished_roles)} 个未发布角色: {', '.join([r.get('name', '未知') for r in unpublished_roles])}")
                    
                    for role in unpublished_roles:
                        await publish_role(client, channel, role, roles)
                        # 发布间隔，避免频控
                        await asyncio.sleep(PUBLISH_INTERVAL_SECONDS)
                        
                    print("✅ 本轮发布完成")
                else:
                    print("✅ 所有角色都已发布，无需操作")
                
                # 4. 等待下一轮检查
                print(f"⏰ 等待 {CHECK_INTERVAL_MINUTES} 分钟后进行下次检查...")
                await asyncio.sleep(CHECK_INTERVAL_MINUTES * 60)
                
            except Exception as e:
                print(f"❌ 检查循环出错: {e}")
                print(f"⏰ 等待 {RETRY_INTERVAL_MINUTES} 分钟后重试...")
                await asyncio.sleep(RETRY_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    asyncio.run(main())


