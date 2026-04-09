import logging
from pathlib import Path
from aiogram.types import Message
from app.config.settings import settings

logger = logging.getLogger(__name__)

def load_welcome_message() -> str:
    if settings.WELCOME_FILE.exists():
        try:
            with open(settings.WELCOME_FILE, 'r', encoding='utf-8') as f:
                message = f.read().strip()
                if message:
                    logger.info("Приветственное сообщение загружено из файла")
                    return message
        except Exception as e:
            logger.error(f"Ошибка при чтении файла welcome_message.txt: {e}")
    
    logger.warning("Используется стандартное приветственное сообщение")
    return "Вас приветствует редакция журнала смета-на-покаяние"

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