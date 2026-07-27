from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.enums import ParseMode

from app.handlers.private import (
    forward_media_to_group,
    forward_to_group,
    send_welcome,
)


BANNED_TEXT = (
    "Вы заблокированы администратором. "
    "Обратитесь в редакцию для разрешения ситуации."
)


@pytest.mark.asyncio
async def test_send_welcome(message_factory):
    message = message_factory()

    with patch(
        "app.handlers.private.load_welcome_message",
        return_value="<b>Добро пожаловать!</b>",
    ):
        await send_welcome(message)

    message.reply.assert_awaited_once_with(
        "<b>Добро пожаловать!</b>",
        parse_mode=ParseMode.HTML,
    )


@pytest.mark.asyncio
async def test_text_message_banned(message_factory, bot):
    message = message_factory()

    with patch(
        "app.handlers.private.UserService.is_banned",
        new=AsyncMock(return_value=True),
    ):
        await forward_to_group(message, bot)

    message.reply.assert_awaited_once_with(BANNED_TEXT)
    bot.send_message.assert_not_awaited()


@pytest.mark.parametrize(
    ("mapping", "last_reply", "expected_reply"),
    [
        (700, None, 700),
        (None, 701, 701),
        (None, None, None),
    ],
)
@pytest.mark.asyncio
async def test_text_message_forwarding(
    message_factory,
    bot,
    mapping,
    last_reply,
    expected_reply,
):
    message = message_factory(
        text="Здравствуйте",
        message_id=44,
        reply_to_message=SimpleNamespace(message_id=77),
    )

    with (
        patch(
            "app.handlers.private.UserService.is_banned",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "app.handlers.private.MessageService.get_mapping_by_user",
            new=AsyncMock(return_value=mapping),
        ),
        patch(
            "app.handlers.private.MessageService.get_last_reply",
            new=AsyncMock(return_value=last_reply),
        ),
        patch(
            "app.handlers.private.MessageService.save_mapping",
            new=AsyncMock(),
        ) as save_mapping,
        patch("app.handlers.private.settings.GROUP_ID", -100555),
    ):
        await forward_to_group(message, bot)

    bot.send_message.assert_awaited_once()
    kwargs = bot.send_message.await_args.kwargs

    assert kwargs["chat_id"] == -100555
    assert kwargs["reply_to_message_id"] == expected_reply
    assert "Здравствуйте" in kwargs["text"]
    assert "#ID123" in kwargs["text"]

    save_mapping.assert_awaited_once_with(900, 123, 44)


@pytest.mark.asyncio
async def test_text_message_without_username(message_factory, bot):
    user = SimpleNamespace(
        id=123,
        full_name="Alex",
        username=None,
    )
    message = message_factory(from_user=user)

    with (
        patch(
            "app.handlers.private.UserService.is_banned",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "app.handlers.private.MessageService.get_last_reply",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.handlers.private.MessageService.save_mapping",
            new=AsyncMock(),
        ),
    ):
        await forward_to_group(message, bot)

    text = bot.send_message.await_args.kwargs["text"]
    assert "@без юзернейма" in text


@pytest.mark.asyncio
async def test_media_message_banned(message_factory, bot):
    message = message_factory(
        photo=[SimpleNamespace(file_id="photo-id")]
    )

    with patch(
        "app.handlers.private.UserService.is_banned",
        new=AsyncMock(return_value=True),
    ):
        await forward_media_to_group(message, bot)

    message.reply.assert_awaited_once_with(BANNED_TEXT)


@pytest.mark.parametrize(
    "media_type",
    ["photo", "video", "document", "animation"],
)
@pytest.mark.asyncio
async def test_media_forwarding(
    message_factory,
    bot,
    media_type,
):
    message = message_factory(
        message_id=55,
        caption="Описание",
    )

    media_service = MagicMock()
    media_service.get_media_info.return_value = (
        SimpleNamespace(file_id="file-id"),
        media_type,
        "Описание",
    )
    media_service.send_media = AsyncMock(
        return_value=SimpleNamespace(message_id=950)
    )

    with (
        patch(
            "app.handlers.private.UserService.is_banned",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "app.handlers.private.MediaService",
            return_value=media_service,
        ),
        patch(
            "app.handlers.private.MessageService.get_last_reply",
            new=AsyncMock(return_value=800),
        ),
        patch(
            "app.handlers.private.MessageService.save_mapping",
            new=AsyncMock(),
        ) as save_mapping,
        patch("app.handlers.private.settings.GROUP_ID", -100777),
    ):
        await forward_media_to_group(message, bot)

    media_service.send_media.assert_awaited_once()

    kwargs = media_service.send_media.await_args.kwargs
    assert kwargs["reply_to_message_id"] == 800
    assert "#ID123" in kwargs["caption"]

    save_mapping.assert_awaited_once_with(950, 123, 55)


@pytest.mark.asyncio
async def test_media_not_found(message_factory, bot):
    message = message_factory()

    media_service = MagicMock()
    media_service.get_media_info.return_value = (None, None, None)
    media_service.send_media = AsyncMock()

    with (
        patch(
            "app.handlers.private.UserService.is_banned",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "app.handlers.private.MediaService",
            return_value=media_service,
        ),
    ):
        await forward_media_to_group(message, bot)

    media_service.send_media.assert_not_awaited()


@pytest.mark.asyncio
async def test_media_send_failure_does_not_save_mapping(
    message_factory,
    bot,
):
    message = message_factory()

    media_service = MagicMock()
    media_service.get_media_info.return_value = (
        SimpleNamespace(file_id="file-id"),
        "photo",
        None,
    )
    media_service.send_media = AsyncMock(return_value=None)

    with (
        patch(
            "app.handlers.private.UserService.is_banned",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "app.handlers.private.MediaService",
            return_value=media_service,
        ),
        patch(
            "app.handlers.private.MessageService.get_last_reply",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.handlers.private.MessageService.save_mapping",
            new=AsyncMock(),
        ) as save_mapping,
    ):
        await forward_media_to_group(message, bot)

    save_mapping.assert_not_awaited()
