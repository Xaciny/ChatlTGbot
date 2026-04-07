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
from pathlib import Path
from database import (
    init_db, is_user_banned, add_banned_user, remove_banned_user,
    get_all_banned_users, add_message_mapping, get_message_mapping,
    get_user_message_mapping, set_last_editor_reply, get_last_editor_reply
)

# логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv('TOKEN')
GROUP_ID = int(os.getenv('GROUP_ID'))

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Путь к файлу с приветственным сообщением
WELCOME_FILE = Path('/app/media/welcome_message.txt')

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
    """Извлекает ID пользователя из сообщения в группе"""
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
    """Отправка медиа с обработкой ошибок"""
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

def load_welcome_message() -> str:
    """Загружает приветственное сообщение из файла"""
    if WELCOME_FILE.exists():
        try:
            with open(WELCOME_FILE, 'r', encoding='utf-8') as f:
                message = f.read().strip()
                if message:
                    logger.info("Приветственное сообщение загружено из файла")
                    return message
        except Exception as e:
            logger.error(f"Ошибка при чтении файла welcome_message.txt: {e}")
    logger.warning("Используется стандартное приветственное сообщение")
    return "Вас приветствует редакция журнала смета-на-покаяние"

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    """Обработчик команды /start"""
    logger.info("Обработчик send_welcome вызван")
    welcome_text = load_welcome_message()
    await message.reply(welcome_text, parse_mode=ParseMode.HTML)

@dp.message(lambda message: message.chat.type == "private" and message.text and not message.text.startswith('/'))
async def forward_to_group(message: Message):
    """Пересылка текстовых сообщений из лички в группу"""
    logger.info("Обработчик forward_to_group вызван")

    if await is_user_banned(message.from_user.id):
        await message.reply("Вы заблокированы администратором. Обратитесь в редакцию для разрешения ситуации.")
        return

    # Проверяем, является ли сообщение ответом на сообщение редакции
    reply_to_group_id = None
    if message.reply_to_message:
        group_msg_id = await get_user_message_mapping(
            message.from_user.id, 
            message.reply_to_message.message_id
        )
        if group_msg_id:
            reply_to_group_id = group_msg_id
    
    # Если это не ответ, используем последний ответ редакции
    if reply_to_group_id is None:
        reply_to_group_id = await get_last_editor_reply(message.from_user.id)

    sent_message = await bot.send_message(
        chat_id=GROUP_ID,
        text=f"Сообщение от {message.from_user.full_name} (@{message.from_user.username or 'без юзернейма'}):\n\n{message.text}\n\nID пользователя: #ID{message.from_user.id}",
        reply_to_message_id=reply_to_group_id
    )
    
    await add_message_mapping(sent_message.message_id, message.from_user.id, message.message_id)

@dp.message(lambda message: message.chat.type == "private" and (message.photo or message.video or message.document or message.animation))
async def forward_media_to_group(message: Message):
    """Пересылка медиа из лички в группу"""
    logger.info("Обработчик forward_media_to_group вызван")

    if await is_user_banned(message.from_user.id):
        await message.reply("Вы заблокированы администратором. Обратитесь в редакцию для разрешения ситуации.")
        return

    # Определяем тип медиа
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

    # Проверяем, является ли сообщение ответом на сообщение редакции
    reply_to_group_id = None
    if message.reply_to_message:
        group_msg_id = await get_user_message_mapping(
            message.from_user.id,
            message.reply_to_message.message_id
        )
        if group_msg_id:
            reply_to_group_id = group_msg_id
    
    if reply_to_group_id is None:
        reply_to_group_id = await get_last_editor_reply(message.from_user.id)

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
            await add_message_mapping(sent_message.message_id, message.from_user.id, message.message_id)
    except Exception as e:
        logger.error(f"Ошибка при пересылке медиа в группу: {e}")

@dp.message(lambda message: message.chat.id == GROUP_ID and message.reply_to_message)
async def handle_reply(message: Message):
    """Обработка ответов редакции на сообщения в группе"""
    logger.info("Обработчик handle_reply вызван")

    if message.reply_to_message.from_user.id != bot.id:
        return
        
    try:
        original_user_id = extract_user_id(message.reply_to_message)
        logger.info(f"Извлечённый ID пользователя: {original_user_id}")
    except ValueError:
        return

    # Получаем маппинг исходного сообщения
    original_mapping = await get_message_mapping(message.reply_to_message.message_id)
    
    # Отправляем ответ пользователю в зависимости от типа контента
    sent_message = None
    
    if message.text:
        sent_message = await bot.send_message(
            chat_id=original_user_id,
            text=f"Ответ редакции:\n\n{message.text}",
            reply_to_message_id=original_mapping["user_message_id"] if original_mapping else None
        )
    elif message.photo or message.video or message.document or message.animation:
        # Определяем тип медиа
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
    
    # Сохраняем маппинг для ответа редакции (общая логика для всех типов)
    if sent_message:
        await add_message_mapping(message.message_id, original_user_id, sent_message.message_id)
        await set_last_editor_reply(original_user_id, message.message_id)
        logger.info(f"✅ Сохранён маппинг для ответа: {message.message_id} -> {original_user_id}:{sent_message.message_id}")
    else:
        logger.error("Не удалось отправить ответ пользователю.")

@dp.edited_message(lambda message: message.chat.id == GROUP_ID)
async def handle_edited_message(message: Message):
    """Обработка редактирования сообщений редакции"""
    logger.info(f"Обработчик handle_edited_message вызван. ID сообщения: {message.message_id}")

    mapping = await get_message_mapping(message.message_id)
    if not mapping:
        logger.error(f"Сообщение с ID {message.message_id} не найдено в отображении.")
        return

    user_id = mapping["user_id"]
    user_message_id = mapping["user_message_id"]

    now = datetime.now()
    message_date = message.date.replace(tzinfo=None) if message.date.tzinfo else message.date

    if now - message_date > timedelta(hours=48):
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
    """Блокировка пользователя"""
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

        if await is_user_banned(numeric_id):
            await message.reply(f"Пользователь с ID {original_id} уже заблокирован.")
            return

        await add_banned_user(numeric_id, message.from_user.id)
        
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
    """Разблокировка пользователя"""
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

        if not await is_user_banned(numeric_id):
            await message.reply(f"Пользователь с ID {original_id} не был заблокирован.")
            return

        await remove_banned_user(numeric_id)

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

@dp.message(Command("listbanned"))
async def list_banned_users(message: Message):
    """Список забаненных пользователей"""
    if message.chat.id != GROUP_ID:
        return
    
    if not await is_admin(message.from_user.id):
        await message.reply("У вас недостаточно прав для выполнения этой команды.")
        return
    
    banned_users = await get_all_banned_users()
    
    if not banned_users:
        await message.reply("Список забаненных пользователей пуст.")
        return
    
    # Формируем список для вывода (не более 20 пользователей за раз)
    banned_list = "\n".join([f"• #{user_id}" for user_id in list(banned_users)[:20]])
    if len(banned_users) > 20:
        banned_list += f"\n... и ещё {len(banned_users) - 20} пользователей"
    
    await message.reply(f"Забаненные пользователи:\n{banned_list}")

async def main():
    """Главная функция запуска бота"""
    # Инициализируем базу данных
    await init_db()
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())