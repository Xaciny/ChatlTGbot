import logging
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError

logger = logging.getLogger(__name__)

class MediaService:
    MEDIA_HANDLERS = {
        "photo": "send_photo",
        "video": "send_video",
        "document": "send_document",
        "animation": "send_animation",
    }
    
    def __init__(self, bot: Bot):
        self.bot = bot
    
    async def send_media(self, chat_id: int, media_type: str, file_id: str, caption: str = None, reply_to_message_id: int = None):
        method_name = self.MEDIA_HANDLERS.get(media_type)
        if not method_name:
            raise ValueError(f"Неизвестный тип медиа: {media_type}")
        
        method = getattr(self.bot, method_name)
        try:
            kwargs = {media_type: file_id}
            if caption:
                kwargs['caption'] = caption
            if reply_to_message_id:
                kwargs['reply_to_message_id'] = reply_to_message_id
            return await method(chat_id=chat_id, **kwargs)
        except TelegramForbiddenError:
            logger.error(f"Пользователь {chat_id} заблокировал бота.")
        except Exception as e:
            logger.error(f"Ошибка при отправке медиа: {e}")
        return None
    
    def get_media_info(self, message):
        if message.photo:
            return message.photo[-1], "photo", message.caption
        elif message.video:
            return message.video, "video", message.caption
        elif message.document:
            return message.document, "document", message.caption
        elif message.animation:
            return message.animation, "animation", message.caption
        return None, None, None