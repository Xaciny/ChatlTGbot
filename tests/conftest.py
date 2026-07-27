import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("TOKEN", "test-token")
os.environ.setdefault("GROUP_ID", "-1001234567890")


@pytest.fixture
def user():
    return SimpleNamespace(
        id=123,
        full_name="Alex",
        username="alex",
    )


@pytest.fixture
def message_factory(user):
    def factory(**overrides):
        data = {
            "text": "Тестовое сообщение",
            "message_id": 10,
            "from_user": user,
            "reply_to_message": None,
            "caption": None,
            "photo": None,
            "video": None,
            "document": None,
            "animation": None,
            "chat": SimpleNamespace(type="private"),
            "reply": AsyncMock(),
        }
        data.update(overrides)
        return SimpleNamespace(**data)

    return factory


@pytest.fixture
def bot():
    return SimpleNamespace(
        send_message=AsyncMock(
            return_value=SimpleNamespace(message_id=900)
        )
    )