from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramForbiddenError
import logging
import asyncio
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pytz import UTC
import json
from pathlib import Path


# логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv('TOKEN')
GROUP_ID = int(os.getenv('GROUP_ID'))

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Путь к файлу с забаненными пользователями
BANNED_USERS_FILE = Path('banned_users.json')

message_mapping = {}  # Маппинг сообщений
banned_users = set()
last_editor_reply = {}  # NEW: user_id -> последний ответ редакции в группе

# Словарь для методов отправки медиа
MEDIA_HANDLERS = {
    "photo": bot.send_photo,
    "video": bot.send_video,
    "document": bot.send_document,
    "animation": bot.send_animation,
}


async def is_admin(user_id: int) -> bool:
    try:
        chat_member = await bot.get_chat_member(GROUP_ID, user_id)
        return chat_member.status in ["administrator", "creator"]
    except Exception as e:
        logger.error(f"Ошибка при проверке статуса администратора: {e}")
        return False


def extract_user_id(reply_message: Message) -> int:
    try:
        if reply_message.text:
            id_str = reply_message.text.split("ID пользователя: ")[1].split("\n")[0].replace("#", "")
        elif reply_message.caption:
            id_str = reply_message.caption.split("ID пользователя: ")[1].split("\n")[0].replace("#", "")
        else:
            raise ValueError("Сообщение не содержит текста или подписи с ID пользователя")

        if id_str.startswith("ID"):
            id_str = id_str[2:]

        return int(id_str)
    except (IndexError, ValueError) as e:
        logger.error(f"Ошибка при извлечении ID пользователя: {e}")
        raise ValueError("Не удалось извлечь ID пользователя")


async def send_media(chat_id: int, media_type: str, file_id: str, caption: str = None):
    handler = MEDIA_HANDLERS.get(media_type)
    if not handler:
        raise ValueError(f"Неизвестный тип медиа: {media_type}")

    try:
        return await handler(chat_id=chat_id, **{media_type: file_id}, caption=caption)
    except TelegramForbiddenError:
        logger.error(f"Пользователь {chat_id} заблокировал бота.")
    except Exception as e:
        logger.error(f"Ошибка при отправке медиа: {e}")
    return None


async def save_banned_users():
    try:
        data = list(banned_users)
        with open(BANNED_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Список забаненных пользователей сохранен ({len(data)} записей)")
    except Exception as e:
        logger.error(f"Ошибка сохранения списка забаненных пользователей: {e}")


async def load_banned_users():
    global banned_users
    if not BANNED_USERS_FILE.exists():
        logger.info("Файл banned_users.json не найден, будет создан новый")
        banned_users = set()
        await save_banned_users()
        return

    try:
        with open(BANNED_USERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        banned_users = set(data)
        logger.info(f"Загружено {len(banned_users)} забаненных пользователей")
    except json.JSONDecodeError:
        logger.error("Ошибка чтения JSON файла, используется пустой список")
        banned_users = set()
    except Exception as e:
        logger.error(f"Ошибка загрузки списка забаненных пользователей: {e}")
        banned_users = set()


async def periodic_save():
    while True:
        await asyncio.sleep(3600)
        await save_banned_users()


@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    logger.info("Обработчик send_welcome вызван")
    await message.reply(
        "Вас приветствует редакция журнала смета-на-покаяние\n"
        "оставьте Ваш текст боту\n"
        "в ближайшее время мы примем решение о публикации\n" 
        "спасибо за участие в поэтическом процессе!\n"
    )


@dp.message(lambda message: message.chat.type == "private" and message.text and not message.text.startswith('/'))
async def forward_to_group(message: Message):
    logger.info("Обработчик forward_to_group вызван")

    if message.from_user.id in banned_users:
        await message.reply("Вы заблокированы администратором. Обратитесь в редакцию для разрешения ситуации.")
        return

    reply_to_group_id = None
    if message.reply_to_message:
        for group_msg_id, info in message_mapping.items():
            if info["user_id"] == message.from_user.id and info["user_message_id"] == message.reply_to_message.message_id:
                reply_to_group_id = group_msg_id
                break
            
    if reply_to_group_id is None:
        reply_to_group_id = last_editor_reply.get(message.from_user.id)

    sent_message = await bot.send_message(
        chat_id=GROUP_ID,
        text=f"Сообщение от {message.from_user.full_name} (@{message.from_user.username or 'без юзернейма'}):\n\n{message.text}\n\nID пользователя: #ID{message.from_user.id}",
        reply_to_message_id=reply_to_group_id
    )
    message_mapping[sent_message.message_id] = {
        "user_id": message.from_user.id,
        "user_message_id": message.message_id
    }


@dp.message(lambda message: message.chat.type == "private" and (message.photo or message.video or message.document or message.animation))
async def forward_media_to_group(message: Message):
    logger.info("Обработчик forward_media_to_group вызван")

    if message.from_user.id in banned_users:
        await message.reply("Вы заблокированы администратором. Обратитесь в редакцию для разрешения ситуации.")
        return

    if message.photo:
        media = message.photo[-1]
        media_type = "photo"
    elif message.video:
        media = message.video
        media_type = "video"
    elif message.document:
        media = message.document
        media_type = "document"
    elif message.animation:
        media = message.animation
        media_type = "animation"
    else:
        return

    caption = (
        f"Медиа от {message.from_user.full_name} "
        f"(@{message.from_user.username or 'без юзернейма'}):\n\n"
        f"{message.caption or ''}\n\n"
        f"ID пользователя: #ID{message.from_user.id}"
    )

    reply_to_group_id = None
    if message.reply_to_message:
        for group_msg_id, info in message_mapping.items():
            if (
                info["user_id"] == message.from_user.id
                and info["user_message_id"] == message.reply_to_message.message_id
            ):
                reply_to_group_id = group_msg_id
                break

    if reply_to_group_id is None:
        reply_to_group_id = last_editor_reply.get(message.from_user.id)

    try:
        if reply_to_group_id:
            sent_message = await MEDIA_HANDLERS[media_type](
                chat_id=GROUP_ID,
                **{media_type: media.file_id},
                caption=caption,
                reply_to_message_id=reply_to_group_id
            )
        else:
            sent_message = await send_media(
                GROUP_ID,
                media_type,
                media.file_id,
                caption=caption
            )

        if sent_message:
            message_mapping[sent_message.message_id] = {
                "user_id": message.from_user.id,
                "user_message_id": message.message_id
            }
    except Exception as e:
        logger.error(f"Ошибка при пересылке медиа в группу: {e}")


@dp.message(lambda message: message.chat.id == GROUP_ID and message.reply_to_message)
async def handle_reply(message: Message):
    logger.info("Обработчик handle_reply вызван")

    if message.reply_to_message.from_user.id == bot.id:
        try:
            original_user_id = extract_user_id(message.reply_to_message)
            logger.info(f"Извлечённый ID пользователя: {original_user_id}")
        except ValueError:
            return

        if message.text:
            try:
                sent_message = await bot.send_message(
                    chat_id=original_user_id,
                    text=f"Ответ редакции:\n\n{message.text}",
                    reply_to_message_id=message_mapping[message.reply_to_message.message_id]["user_message_id"]
                    if message.reply_to_message.message_id in message_mapping else None
                )
                message_mapping[message.message_id] = {
                    "user_id": original_user_id,
                    "user_message_id": sent_message.message_id
                }
                last_editor_reply[original_user_id] = message.message_id  # NEW
            except Exception as e:
                logger.error(f"Ошибка при отправке текстового сообщения: {e}")

        elif message.photo or message.video or message.document or message.animation:
            if message.photo:
                media = message.photo[-1]
                media_type = "photo"
            elif message.video:
                media = message.video
                media_type = "video"
            elif message.document:
                media = message.document
                media_type = "document"
            elif message.animation:
                media = message.animation
                media_type = "animation"
            else:
                return

            caption = f"Материалы от редакции:\n\n{message.caption}" if message.caption else "Материалы от редакции"
            sent_message = await send_media(original_user_id, media_type, media.file_id, caption)

            if sent_message:
                message_mapping[message.message_id] = {
                    "user_id": original_user_id,
                    "user_message_id": sent_message.message_id
                }
                last_editor_reply[original_user_id] = message.message_id  # NEW
            else:
                logger.error("Не удалось отправить медиа пользователю.")


@dp.edited_message(lambda message: message.chat.id == GROUP_ID)
async def handle_edited_message(message: Message):
    logger.info(f"Обработчик handle_edited_message вызван. ID сообщения: {message.message_id}")

    mapping_info = message_mapping.get(message.message_id)
    if not mapping_info:
        logger.error(f"Сообщение с ID {message.message_id} не найдено в отображении.")
        return

    user_id = mapping_info["user_id"]
    user_message_id = mapping_info["user_message_id"]

    now = datetime.now(UTC)

    if now - message.date > timedelta(hours=48):
        await bot.send_message(
            chat_id=user_id,
            text="Сообщение слишком старое для редактирования. Пожалуйста, свяжитесь с редакцией для уточнения."
        )
        return

    if message.text:
        try:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=user_message_id,
                text=f"Ответ редакции (исправлено):\n\n{message.text}"
            )
        except Exception as e:
            logger.error(f"Ошибка при редактировании текста: {e}")
            await bot.send_message(
                chat_id=user_id,
                text="Сообщение нельзя отредактировать. Пожалуйста, свяжитесь с редакцией для уточнения."
            )
    elif message.photo or message.video or message.document or message.animation:
        await bot.send_message(
            chat_id=user_id,
            text="Редактирование медиа невозможно. Пожалуйста, свяжитесь с редакцией для уточнения."
        )


@dp.message(Command("ban"))
async def ban_user(message: Message, command: CommandObject):
    logger.info(f"Вызвана команда /ban с аргументами: {command.args}")

    if message.chat.id != GROUP_ID:
        return

    if not await is_admin(message.from_user.id):
        await message.reply("У вас недостаточно прав для выполнения этой команды.")
        return

    if not command.args:
        await message.reply("Пожалуйста, укажите ID пользователя для блокировки.\nПример: /ban #ID12345")
        return

    try:
        user_id_str = command.args.strip()
        if user_id_str.startswith("#ID"):
            original_id = user_id_str
            numeric_id = int(user_id_str[3:])
        else:
            numeric_id = int(user_id_str)
            original_id = str(numeric_id)

        banned_users.add(numeric_id)
        await save_banned_users()

        try:
            await bot.send_message(
                chat_id=numeric_id,
                text="Вы были заблокированы администратором журнала. Если вы считаете, что произошла ошибка, пожалуйста, свяжитесь с редакцией другим способом."
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление о бане пользователю {original_id}: {e}")

        await message.reply(f"Пользователь с ID {original_id} успешно заблокирован.")
    except ValueError:
        await message.reply("Некорректный ID пользователя. Формат должен быть '#ID12345' или числовой ID.")
    except Exception as e:
        logger.error(f"Ошибка при блокировке пользователя: {e}")
        await message.reply(f"Произошла ошибка при блокировке пользователя: {str(e)}")


@dp.message(Command("unban"))
async def unban_user(message: Message, command: CommandObject):
    logger.info(f"Вызвана команда /unban с аргументами: {command.args}")

    if message.chat.id != GROUP_ID:
        return

    if not await is_admin(message.from_user.id):
        await message.reply("У вас недостаточно прав для выполнения этой команды.")
        return

    if not command.args:
        await message.reply("Пожалуйста, укажите ID пользователя для разблокировки.\nПример: /unban #ID12345")
        return

    try:
        user_id_str = command.args.strip()
        if user_id_str.startswith("#ID"):
            original_id = user_id_str
            numeric_id = int(user_id_str[3:])
        else:
            numeric_id = int(user_id_str)
            original_id = str(numeric_id)

        if numeric_id not in banned_users:
            await message.reply(f"Пользователь с ID {original_id} не был заблокирован.")
            return

        banned_users.remove(numeric_id)
        await save_banned_users()

        try:
            await bot.send_message(
                chat_id=numeric_id,
                text="Ваша блокировка была снята администратором журнала. Теперь вы снова можете отправлять свои произведения."
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление о разбане пользователю {original_id}: {e}")

        await message.reply(f"Пользователь с ID {original_id} успешно разблокирован.")
    except ValueError:
        await message.reply("Некорректный ID пользователя. Формат должен быть '#ID12345' или числовой ID.")
    except Exception as e:
        logger.error(f"Ошибка при разблокировке пользователя: {e}")
        await message.reply(f"Произошла ошибка при разблокировке пользователя: {str(e)}")


async def main():
    await load_banned_users()
    asyncio.create_task(periodic_save())
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
