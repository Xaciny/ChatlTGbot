import asyncio
import logging
from datetime import datetime
from aiogram import Bot
from app.config.settings import settings
from app.services.timeweb_service import TimewebService

logger = logging.getLogger(__name__)

class MonitoringService:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.timeweb = TimewebService(settings.TIMEWEB_API_TOKEN)
        self.is_running = False
        self.group_id = settings.GROUP_ID
    
    async def get_admin_ids(self) -> list[int]:
        try:
            chat_admins = await self.bot.get_chat_administrators(self.group_id)
            admin_ids = [admin.user.id for admin in chat_admins if not admin.user.is_bot]
            return admin_ids
        except Exception as e:
            logger.error(f"Ошибка при получении списка администраторов: {e}")
            return []
    
    async def check_and_notify(self):
        balance_data = await self.timeweb.get_balance()
        
        if not balance_data:
            logger.error("Не удалось получить данные о балансе")
            return
        
        balance = balance_data['balance']
        currency = balance_data['currency']
        hourly_cost = balance_data['hourly_cost']
        daily_cost = hourly_cost * 24
        
        # Используем реальный расход из API
        days_remaining = int(balance / daily_cost) if daily_cost > 0 else 999
        
        logger.info(f"Проверка баланса: {balance:.2f} {currency}, расход в день: {daily_cost:.2f} {currency}, осталось дней: {days_remaining}")
        
        if days_remaining < 1:
            await self._send_low_balance_alert(balance, currency, days_remaining, daily_cost)
        elif days_remaining < 3:
            await self._send_warning_alert(balance, currency, days_remaining, daily_cost)
    
    async def _send_low_balance_alert(self, balance: float, currency: str, days: int, daily_cost: float):
        message = (
            f"🚨 **КРИТИЧЕСКОЕ ПРЕДУПРЕЖДЕНИЕ** 🚨\n\n"
            f"💰 Текущий баланс: **{balance:.2f} {currency}**\n"
            f"📊 Расход в день: **{daily_cost:.2f} {currency}**\n"
            f"📉 Средств хватит менее чем на **1 день**!\n\n"
            f"⚠️ **Пополните, пожалуйста, счет!** ⚠️\n\n"
            f"🕐 Время проверки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        admin_ids = await self.get_admin_ids()
        
        for admin_id in admin_ids:
            try:
                await self.bot.send_message(admin_id, message, parse_mode="Markdown")
                logger.info(f"Отправлено критическое уведомление администратору {admin_id}")
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")
    
    async def _send_warning_alert(self, balance: float, currency: str, days: int, daily_cost: float):
        message = (
            f"⚠️ **Предупреждение о низком балансе** ⚠️\n\n"
            f"💰 Текущий баланс: **{balance:.2f} {currency}**\n"
            f"📊 Расход в день: **{daily_cost:.2f} {currency}**\n"
            f"📉 Осталось дней: **{days}**\n\n"
            f"💡 Рекомендуем пополнить счет в ближайшее время.\n\n"
            f"🕐 Время проверки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        admin_ids = await self.get_admin_ids()
        
        for admin_id in admin_ids:
            try:
                await self.bot.send_message(admin_id, message, parse_mode="Markdown")
                logger.info(f"Отправлено предупреждение администратору {admin_id}")
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")
    
    async def monitoring_loop(self):
        self.is_running = True
        logger.info("Запущен цикл мониторинга баланса")
        
        while self.is_running:
            try:
                await self.check_and_notify()
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")
            
            # Ждем 24 часа
            await asyncio.sleep(24 * 60 * 60)
    
    def stop(self):
        self.is_running = False
        logger.info("Мониторинг баланса остановлен")