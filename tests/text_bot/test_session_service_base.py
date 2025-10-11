import pytest
import asyncio
from tg_bot_picture_v1.src.domain.services.session_service_base import SessionService

@pytest.mark.asyncio
async def test_get_or_create_session_creates_new_session():
    service = SessionService()
    user_id = "user_123"

    session = await service.get_or_create_session(user_id)

    assert "session_id" in session
    assert session["user_id"] == user_id
    assert session["history"] == []

@pytest.mark.asyncio
async def test_get_or_create_session_returns_existing():
    service = SessionService()
    user_id = "user_456"

    session1 = await service.get_or_create_session(user_id)
    session2 = await service.get_or_create_session(user_id)

    # 同一个 user_id，返回的 session_id 应该相同
    assert session1["session_id"] == session2["session_id"]

@pytest.mark.asyncio
async def test_new_session_always_creates_new():
    service = SessionService()
    user_id = "user_789"

    session1 = await service.get_or_create_session(user_id)
    session2 = await service.new_session(user_id)

    # new_session 会强制生成新的 session_id
    assert session1["session_id"] != session2["session_id"]

@pytest.mark.asyncio
async def test_get_session_by_id():
    service = SessionService()
    user_id = "user_999"

    session = await service.get_or_create_session(user_id)
    found = await service.get_session(session["session_id"])

    assert found is not None
    assert found["session_id"] == session["session_id"]
    assert found["user_id"] == user_id

@pytest.mark.asyncio
async def test_get_session_not_found_returns_none():
    service = SessionService()
    result = await service.get_session("nonexistent-id")

    assert result is None
