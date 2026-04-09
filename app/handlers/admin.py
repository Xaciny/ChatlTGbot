import logging
from aiogram import Router, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.enums import ParseMode
from app.config.settings import settings
from app.services import UserService
from app.services.timeweb_service import TimewebService
from app.handlers.common import is_admin

logger = logging.getLogger(__name__)
admin_router = Router()

@admin_router.message(Command("ban"))
async def ban_user(message: Message, command: CommandObject, bot: Bot):
    logger.info(f"Вызвана команда /ban с аргументами: {command.args}")

    if message.chat.id != settings.GROUP_ID:
        return

    if not await is_admin(bot, message.from_user.id):
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

        if await UserService.is_banned(numeric_id):
            await message.reply(f"Пользователь с ID {original_id} уже заблокирован.")
            return

        await UserService.ban_user(numeric_id, message.from_user.id)
        
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

@admin_router.message(Command("unban"))
async def unban_user(message: Message, command: CommandObject, bot: Bot):
    logger.info(f"Вызвана команда /unban с аргументами: {command.args}")

    if message.chat.id != settings.GROUP_ID:
        return

    if not await is_admin(bot, message.from_user.id):
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

        if not await UserService.is_banned(numeric_id):
            await message.reply(f"Пользователь с ID {original_id} не был заблокирован.")
            return

        await UserService.unban_user(numeric_id)

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

@admin_router.message(Command("listbanned"))
async def list_banned_users(message: Message, bot: Bot):
    if message.chat.id != settings.GROUP_ID:
        return
    
    if not await is_admin(bot, message.from_user.id):
        await message.reply("У вас недостаточно прав для выполнения этой команды.")
        return
    
    banned_users = await UserService.get_all_banned()
    
    if not banned_users:
        await message.reply("Список забаненных пользователей пуст.")
        return
    
    banned_list = "\n".join([f"• #{user_id}" for user_id in list(banned_users)[:20]])
    if len(banned_users) > 20:
        banned_list += f"\n... и ещё {len(banned_users) - 20} пользователей"
    
    await message.reply(f"Забаненные пользователи:\n{banned_list}")

@admin_router.message(Command("balance"))
async def check_balance(message: Message, bot: Bot):
    logger.info("Вызвана команда /balance")
    
    if message.chat.id != settings.GROUP_ID:
        return
    
    if not await is_admin(bot, message.from_user.id):
        await message.reply("У вас недостаточно прав для выполнения этой команды.")
        return
    
    timeweb = TimewebService(settings.TIMEWEB_API_TOKEN)
    
    loading_msg = await message.reply("🔄 Получаю информацию о балансе...")
    
    balance_data = await timeweb.get_balance()
    account_status = await timeweb.get_account_status()
    
    if not balance_data:
        await loading_msg.edit_text("❌ Не удалось получить информацию о балансе. Проверьте API токен.")
        return
    
    balance = balance_data['balance']
    currency = balance_data['currency']
    hourly_cost = balance_data['hourly_cost']
    monthly_cost = balance_data['monthly_cost']
    daily_cost = hourly_cost * 24
    days_remaining = int(balance / daily_cost) if daily_cost > 0 else 999
    
    status_text = "✅ Активен" if account_status and account_status.get('is_blocked', False) == False else "❌ Заблокирован"
    
    message_text = (
        f"💰 **Информация о балансе Timeweb Cloud**\n\n"
        f"💵 Текущий баланс: **{balance:.2f} {currency}**\n"
        f"📊 Статус аккаунта: {status_text}\n\n"
        f"📈 Расходы:\n"
        f"• В час: {hourly_cost:.2f} {currency}\n"
        f"• В день: {daily_cost:.2f} {currency}\n"
        f"• В месяц: {monthly_cost:.2f} {currency}\n\n"
        f"⏰ Дней до блокировки: **{days_remaining}**\n"
    )
    
    if days_remaining < 1:
        message_text += "\n🚨 **ВНИМАНИЕ! Средств хватит менее чем на 1 день! Пополните счет!**"
    elif days_remaining < 3:
        message_text += "\n⚠️ **Предупреждение: низкий баланс. Рекомендуется пополнить счет.**"
    else:
        message_text += "\n✅ Баланс в норме."
    
    await loading_msg.edit_text(message_text, parse_mode=ParseMode.MARKDOWN)