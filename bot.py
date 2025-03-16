from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramForbiddenError
import logging
import asyncio
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pytz import UTC


# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv('TOKEN')
GROUP_ID = int(os.getenv('GROUP_ID'))

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


message_mapping = {}  # Маппинг сообщений {group_message_id: user_message_id}

# Словарь для методов отправки медиа
MEDIA_HANDLERS = {
    "photo": bot.send_photo,
    "video": bot.send_video,
    "document": bot.send_document,
    "animation": bot.send_animation,  
}

# Функция для извлечения ID пользователя из сообщения
def extract_user_id(reply_message: Message) -> int:
    try:
        # Проверяем, есть ли текст в сообщении
        if reply_message.text:
            id_str = reply_message.text.split("ID пользователя: ")[1].split("\n")[0].replace("#", "")
        # Если текста нет, проверяем подпись медиа
        elif reply_message.caption:
            id_str = reply_message.caption.split("ID пользователя: ")[1].split("\n")[0].replace("#", "")
        else:
            raise ValueError("Сообщение не содержит текста или подписи с ID пользователя")
        
        # Удаляем префикс "ID", если он есть
        if id_str.startswith("ID"):
            id_str = id_str[2:]  # Убираем первые два символа ("ID")
        
        # Преобразуем в число
        return int(id_str)
    except (IndexError, ValueError) as e:
        logger.error(f"Ошибка при извлечении ID пользователя: {e}")
        raise ValueError("Не удалось извлечь ID пользователя")

# Функция для отправки медиа
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

# Обработчик команды /start
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    logger.info("Обработчик send_welcome вызван")
    await message.reply("Привет, автор!\n\nТы пишешь стихотворения или прозу? Тогда ты по адресу. Я — бот литературного журнала «Чатл», и через меня ты можешь отправить своё произведение на рассмотрение редакции.\n\nЧто дальше?\n— Мы внимательно прочитаем твой текст.\n— Дадим обратную связь, если она нужна.\n— А главное — у тебя есть шанс увидеть своё произведение на странице «Чатла»!\n\nПоэзия живёт, пока её читают. Делись своим творчеством — и, возможно, именно твой текст зацепит читателя за живое. Мы ждем тебя!")

# Обработчик текстовых сообщений от пользователя
@dp.message(lambda message: message.chat.type == "private" and message.text)
async def forward_to_group(message: Message):
    logger.info("Обработчик forward_to_group вызван")
    sent_message = await bot.send_message(
        chat_id=GROUP_ID,
        text=f"Сообщение от {message.from_user.full_name} (@{message.from_user.username}):\n\n{message.text}\n\nID пользователя: #ID{message.from_user.id}"
    )
    # Сохраняем ID сообщения в группе и у пользователя
    message_mapping[sent_message.message_id] = {
        "user_id": message.from_user.id,
        "user_message_id": message.message_id  # Сохраняем ID сообщения пользователя (нам это не нужно в данном случае)
    }

# Обработчик медиа вложений от пользователя
@dp.message(lambda message: message.chat.type == "private" and (message.photo or message.video or message.document or message.animation))
async def forward_media_to_group(message: Message):
    logger.info("Обработчик forward_media_to_group вызван")

    # Определяем тип медиа
    if message.photo:
        media = message.photo[-1]  # Берем самое большое фото
        media_type = "photo"
    elif message.video:
        media = message.video
        media_type = "video"
    elif message.document:
        media = message.document
        media_type = "document"
    elif message.animation:
        media = message.animation
        media_type = "animation"  # Обработка GIF
    else:
        return

    # Отправляем медиа в группу
    caption = f"Медиа от {message.from_user.full_name} (@{message.from_user.username}):\n\n{message.caption or ''}\n\nID пользователя: #ID{message.from_user.id}"
    sent_message = await send_media(GROUP_ID, media_type, media.file_id, caption)

    if sent_message:
        # Сохраняем ID сообщения в группе и у пользователя
        message_mapping[sent_message.message_id] = {
            "user_id": message.from_user.id,
            "user_message_id": message.message_id  # Сохраняем ID сообщения пользователя (нам это не нужно в данном случае)
        }

# Обработчик ответов на сообщения бота в группе
@dp.message(lambda message: message.chat.id == GROUP_ID and message.reply_to_message)
async def handle_reply(message: Message):
    logger.info("Обработчик handle_reply вызван")

    # Проверяем, что это ответ на сообщение бота
    if message.reply_to_message.from_user.id == bot.id:
        try:
            # Извлекаем ID автора исходного сообщения (Пользователь А)
            original_user_id = extract_user_id(message.reply_to_message)
            logger.info(f"Извлечённый ID пользователя: {original_user_id}")
        except ValueError:
            return

        # Если это текстовое сообщение
        if message.text:
            logger.info(f"Ответ для User ID: {original_user_id}, Сообщение: {message.text}")
            try:
                sent_message = await bot.send_message(
                    chat_id=original_user_id,
                    text=f"Ответ редакции:\n\n{message.text}"
                )
                # Сохраняем связь между ID сообщения в группе и ID сообщения у пользователя
                message_mapping[message.message_id] = {
                    "user_id": original_user_id,
                    "user_message_id": sent_message.message_id
                }
            except Exception as e:
                logger.error(f"Ошибка при отправке текстового сообщения: {e}")

        # Если это медиа
        elif message.photo or message.video or message.document or message.animation:
            if message.photo:
                media = message.photo[-1]  # Берем самое большое фото
                media_type = "photo"
            elif message.video:
                media = message.video
                media_type = "video"
            elif message.document:
                media = message.document
                media_type = "document"
            elif message.animation:
                media = message.animation
                media_type = "animation"  # Обработка GIF
            else:
                return

            # Формируем подпись для медиа
            if message.caption:
                caption = f"Материалы от редакции:\n\n{message.caption}"
            else:
                caption = "Материалы от редакции"

            # Отправляем медиа пользователю
            sent_message = await send_media(original_user_id, media_type, media.file_id, caption)
            
            # Проверяем, что медиа было успешно отправлено
            if sent_message:
                # Сохраняем связь между ID сообщения в группе и ID сообщения у пользователя
                message_mapping[message.message_id] = {
                    "user_id": original_user_id,
                    "user_message_id": sent_message.message_id
                }
            else:
                logger.error("Не удалось отправить медиа пользователю.")


@dp.edited_message(lambda message: message.chat.id == GROUP_ID)
async def handle_edited_message(message: Message):
    logger.info(f"Обработчик handle_edited_message вызван. ID сообщения: {message.message_id}")
    
    # Проверяем, есть ли это сообщение в нашем отображении
    mapping_info = message_mapping.get(message.message_id)
    if not mapping_info:
        logger.error(f"Сообщение с ID {message.message_id} не найдено в отображении.")
        return
    
    user_id = mapping_info["user_id"]
    user_message_id = mapping_info["user_message_id"]
    
    logger.info(f"Найдено соответствие: User ID: {user_id}, User Message ID: {user_message_id}")
    
    # Получаем текущее время с временной зоной (offset-aware)
    now = datetime.now(UTC)  # Используем UTC
    
    # Проверяем, что сообщение не старше 48 часов
    if now - message.date > timedelta(hours=48):
        await bot.send_message(
            chat_id=user_id,
            text="Сообщение слишком старое для редактирования. Пожалуйста, свяжитесь с редакцией для уточнения."
        )
        return
    
    # Если это текстовое сообщение
    if message.text:
        logger.info(f"Редактирование текста для User ID: {user_id}, Сообщение: {message.text}")
        try:
            # Пытаемся отредактировать существующее сообщение
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=user_message_id,
                text=f"Ответ редакции (исправлено):\n\n{message.text}"
            )
            logger.info(f"Сообщение успешно отредактировано для пользователя {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при редактировании текста: {e}")
            logger.error(f"Chat ID: {user_id}, Message ID: {user_message_id}")
            # Уведомляем пользователя, что сообщение нельзя отредактировать
            await bot.send_message(
                chat_id=user_id,
                text="Сообщение нельзя отредактировать. Пожалуйста, свяжитесь с редакцией для уточнения."
            )
    
    # Если это медиа, уведомляем пользователя, что редактирование медиа невозможно
    elif message.photo or message.video or message.document or message.animation:
        logger.info(f"Попытка редактирования медиа для User ID: {user_id}")
        await bot.send_message(
            chat_id=user_id,
            text="Редактирование медиа невозможно. Пожалуйста, свяжитесь с редакцией для уточнения."
        )

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

    