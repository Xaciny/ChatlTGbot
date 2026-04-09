import logging
from aiogram import Router, Bot, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from app.config.settings import settings
from app.services import UserService, MessageService, MediaService
from app.utils import load_welcome_message

logger = logging.getLogger(__name__)
private_router = Router()

@private_router.message(Command("start"))
async def send_welcome(message: types.Message):
    logger.info("Обработчик send_welcome вызван")
    welcome_text = load_welcome_message()
    await message.reply(welcome_text, parse_mode=ParseMode.HTML)

@private_router.message(lambda message: message.chat.type == "private" and message.text and not message.text.startswith('/'))
async def forward_to_group(message: Message, bot: Bot):
    logger.info("Обработчик forward_to_group вызван")

    if await UserService.is_banned(message.from_user.id):
        await message.reply("Вы заблокированы администратором. Обратитесь в редакцию для разрешения ситуации.")
        return

    reply_to_group_id = None
    if message.reply_to_message:
        group_msg_id = await MessageService.get_mapping_by_user(
            message.from_user.id, 
            message.reply_to_message.message_id
        )
        if group_msg_id:
            reply_to_group_id = group_msg_id
    
    if reply_to_group_id is None:
        reply_to_group_id = await MessageService.get_last_reply(message.from_user.id)

    sent_message = await bot.send_message(
        chat_id=settings.GROUP_ID,
        text=f"Сообщение от {message.from_user.full_name} (@{message.from_user.username or 'без юзернейма'}):\n\n{message.text}\n\nID пользователя: #ID{message.from_user.id}",
        reply_to_message_id=reply_to_group_id
    )
    
    await MessageService.save_mapping(sent_message.message_id, message.from_user.id, message.message_id)

@private_router.message(lambda message: message.chat.type == "private" and (message.photo or message.video or message.document or message.animation))
async def forward_media_to_group(message: Message, bot: Bot):
    logger.info("Обработчик forward_media_to_group вызван")

    if await UserService.is_banned(message.from_user.id):
        await message.reply("Вы заблокированы администратором. Обратитесь в редакцию для разрешения ситуации.")
        return

    media_service = MediaService(bot)
    media, media_type, _ = media_service.get_media_info(message)
    
    if not media:
        return

    caption = (
        f"Медиа от {message.from_user.full_name} "
        f"(@{message.from_user.username or 'без юзернейма'}):\n\n"
        f"{message.caption or ''}\n\n"
        f"ID пользователя: #ID{message.from_user.id}"
    )

    reply_to_group_id = None
    if message.reply_to_message:
        group_msg_id = await MessageService.get_mapping_by_user(
            message.from_user.id,
            message.reply_to_message.message_id
        )
        if group_msg_id:
            reply_to_group_id = group_msg_id
    
    if reply_to_group_id is None:
        reply_to_group_id = await MessageService.get_last_reply(message.from_user.id)

    try:
        sent_message = await media_service.send_media(
            settings.GROUP_ID,
            media_type,
            media.file_id,
            caption=caption,
            reply_to_message_id=reply_to_group_id
        )

        if sent_message:
            await MessageService.save_mapping(sent_message.message_id, message.from_user.id, message.message_id)
    except Exception as e:
        logger.error(f"Ошибка при пересылке медиа в группу: {e}")