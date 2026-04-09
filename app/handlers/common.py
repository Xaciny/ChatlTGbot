import logging
from aiogram import Bot
from app.config.settings import settings

logger = logging.getLogger(__name__)

async def is_admin(bot: Bot, user_id: int) -> bool:
    try:
        chat_member = await bot.get_chat_member(settings.GROUP_ID, user_id)
        return chat_member.status in ["administrator", "creator"]
    except Exception as e:
        logger.error(f"Ошибка при проверке статуса администратора: {e}")
        return False