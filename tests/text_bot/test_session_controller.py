import pytest
from fastapi.testclient import TestClient
from src.interfaces.telegram.controllers.session_controller import router
from fastapi import FastAPI

# -------------------------
# Setup Test App
# -------------------------
@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# -------------------------
# Tests
# -------------------------
def test_create_session_success(client):
    """验证：正常输入时返回 Mock 响应"""
    payload = {"user_id": "u123", "content": "你好"}
    response = client.post("/v1/sessions", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["message"] == "OK"
    assert "session_id" in body["data"]
    assert "message_id" in body["data"]
    assert "reply" in body["data"]
    assert set(body["data"]["actions"]) == {"regenerate", "stop", "new_session"}


def test_create_session_content_too_long(client):
    """验证：content 超过 10000 字符时返回错误码 4002"""
    payload = {"user_id": "u123", "content": "a" * 10001}
    response = client.post("/v1/sessions", json=payload)

    # FastAPI 捕获 HTTPException → 仍然是 400
    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["code"] == 4002
    assert body["detail"]["message"].startswith("消息过长")
    assert body["detail"]["data"] is None


def test_create_session_missing_user_id(client):
    """验证：缺少 user_id 时返回 422"""
    payload = {"content": "hello"}
    response = client.post("/v1/sessions", json=payload)

    assert response.status_code == 422
    body = response.json()
    # FastAPI 默认返回 Pydantic 校验错误
    assert "detail" in body
    assert any(err["loc"][-1] == "user_id" for err in body["detail"])
