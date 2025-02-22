from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties  # Импортируем DefaultBotProperties
from aiogram.exceptions import TelegramForbiddenError
import logging
import asyncio
import os
from dotenv import load_dotenv


# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv('TOKEN')
print(f"TOKEN: {TOKEN}")
GROUP_ID = os.getenv('GROUP_ID')
print(f"GROUP_ID: {GROUP_ID}")

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Обработчик команды /start
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    logger.info("Обработчик send_welcome вызван")
    await message.reply("Приветственный текст для редакции")

# Обработчик сообщений из личных сообщений
@dp.message(lambda message: message.chat.type == "private")
async def forward_to_group(message: Message):
    logger.info("Обработчик forward_to_group вызван")
    await bot.send_message(
        chat_id=GROUP_ID,
        text=f"Сообщение от {message.from_user.full_name} (@{message.from_user.username}):\n\n{message.text}\n\nID пользователя: #{message.from_user.id}"
    )

# Обработчик ответов на сообщения бота в группе
@dp.message(lambda message: message.chat.id == GROUP_ID and message.reply_to_message)
async def handle_reply(message: Message):
    logger.info("Обработчик handle_reply вызван")

    # Проверяем, что это ответ на сообщение бота
    if message.reply_to_message.from_user.id == bot.id:
        # Извлекаем ID автора исходного сообщения (Пользователь А)
        try:
            # Убираем символ '#' и преобразуем в число
            original_user_id = int(message.reply_to_message.text.split("ID пользователя: ")[1].split("\n")[0].replace("#", ""))
            logger.info(f"Извлечённый ID пользователя: {original_user_id}")
        except (IndexError, ValueError) as e:
            logger.error(f"Ошибка при извлечении ID пользователя: {e}")
            return

        # Текст ответа
        reply_text = message.text

        if reply_text:
            logger.info(f"Ответ для User ID: {original_user_id}, Сообщение: {reply_text}")
            try:
                # Отправляем ответ в личные сообщения Пользователю А
                await bot.send_message(chat_id=original_user_id, text=f"Ответ редакции:\n\n{reply_text}")
            except TelegramForbiddenError:
                logger.error(f"Пользователь {original_user_id} заблокировал бота.")
            except Exception as e:
                logger.error(f"Ошибка: {e}")
        else:
            logger.warning("Сообщение не содержит текста.")

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())