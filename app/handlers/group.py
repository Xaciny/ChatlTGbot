import logging
from datetime import datetime, timedelta
from aiogram import Router, Bot
from aiogram.types import Message
from app.config.settings import settings
from app.services import MessageService, MediaService
from app.utils import extract_user_id

logger = logging.getLogger(__name__)
group_router = Router()

@group_router.message(lambda message: message.chat.id == settings.GROUP_ID and message.reply_to_message)
async def handle_reply(message: Message, bot: Bot):
    logger.info("Обработчик handle_reply вызван")

    if message.reply_to_message.from_user.id != bot.id:
        return
        
    try:
        original_user_id = extract_user_id(message.reply_to_message)
        logger.info(f"Извлечённый ID пользователя: {original_user_id}")
    except ValueError:
        return

    original_mapping = await MessageService.get_mapping_by_group(message.reply_to_message.message_id)
    
    sent_message = None
    media_service = MediaService(bot)
    
    if message.text:
        sent_message = await bot.send_message(
            chat_id=original_user_id,
            text=f"Ответ редакции:\n\n{message.text}",
            reply_to_message_id=original_mapping["user_message_id"] if original_mapping else None
        )
    elif message.photo or message.video or message.document or message.animation:
        media, media_type, _ = media_service.get_media_info(message)
        
        if media:
            caption = f"Материалы от редакции:\n\n{message.caption}" if message.caption else "Материалы от редакции"
            sent_message = await media_service.send_media(original_user_id, media_type, media.file_id, caption)
    
    if sent_message:
        await MessageService.save_mapping(message.message_id, original_user_id, sent_message.message_id)
        await MessageService.set_last_reply(original_user_id, message.message_id)
        logger.info(f"Сохранён маппинг для ответа: {message.message_id} -> {original_user_id}:{sent_message.message_id}")
    else:
        logger.error("Не удалось отправить ответ пользователю.")

@group_router.edited_message(lambda message: message.chat.id == settings.GROUP_ID)
async def handle_edited_message(message: Message, bot: Bot):
    logger.info(f"Обработчик handle_edited_message вызван. ID сообщения: {message.message_id}")

    mapping = await MessageService.get_mapping_by_group(message.message_id)
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