import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from app.config.settings import settings
from app.database import init_db
from app.handlers import main_router
from app.services.monitoring_service import MonitoringService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    await init_db()
    
    bot = Bot(token=settings.TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(main_router)
    
    # Инициализация мониторинга
    monitoring = MonitoringService(bot)
    
    # Запускаем мониторинг в фоне
    monitoring_task = asyncio.create_task(monitoring.monitoring_loop())
    
    try:
        logger.info("Бот запущен")
        await dp.start_polling(bot)
    finally:
        monitoring.stop()
        monitoring_task.cancel()
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())