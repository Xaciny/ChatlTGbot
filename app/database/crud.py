import logging
from datetime import datetime
from sqlalchemy import select, delete, text
from .engine import engine, AsyncSessionLocal
from .models import Base, BannedUser, MessageMapping, LastEditorReply

logger = logging.getLogger(__name__)

async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("База данных успешно инициализирована")
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            ))
            tables = [row[0] for row in result]
            logger.info(f"Таблицы в БД: {tables}")
            
    except Exception as e:
        logger.error(f"Ошибка при инициализации БД: {e}")
        raise

async def add_banned_user(user_id: int, banned_by: int = None):
    async with AsyncSessionLocal() as session:
        try:
            existing = await session.execute(
                select(BannedUser).where(BannedUser.user_id == user_id)
            )
            if not existing.scalar_one_or_none():
                banned_user = BannedUser(user_id=user_id, banned_by=banned_by)
                session.add(banned_user)
                await session.commit()
                logger.info(f"Пользователь {user_id} добавлен в бан-лист")
                return True
            return False
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при добавлении в бан: {e}")
            return False

async def remove_banned_user(user_id: int):
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                delete(BannedUser).where(BannedUser.user_id == user_id)
            )
            await session.commit()
            removed = result.rowcount > 0
            if removed:
                logger.info(f"Пользователь {user_id} удалён из бан-листа")
            return removed
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при удалении из бана: {e}")
            return False

async def is_user_banned(user_id: int) -> bool:
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(BannedUser).where(BannedUser.user_id == user_id)
            )
            return result.scalar_one_or_none() is not None
        except Exception as e:
            logger.error(f"Ошибка при проверке бана: {e}")
            return False

async def get_all_banned_users():
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(BannedUser.user_id))
            return {row[0] for row in result.all()}
        except Exception as e:
            logger.error(f"Ошибка при получении списка банов: {e}")
            return set()

async def add_message_mapping(group_message_id: int, user_id: int, user_message_id: int):
    async with AsyncSessionLocal() as session:
        try:
            mapping = MessageMapping(
                group_message_id=group_message_id,
                user_id=user_id,
                user_message_id=user_message_id
            )
            session.add(mapping)
            await session.commit()
            logger.debug(f"Добавлен маппинг: {group_message_id} -> {user_id}:{user_message_id}")
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при добавлении маппинга: {e}")

async def get_message_mapping(group_message_id: int):
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(MessageMapping).where(MessageMapping.group_message_id == group_message_id)
            )
            mapping = result.scalar_one_or_none()
            if mapping:
                return {
                    "user_id": mapping.user_id,
                    "user_message_id": mapping.user_message_id
                }
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении маппинга: {e}")
            return None

async def get_user_message_mapping(user_id: int, user_message_id: int):
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(MessageMapping).where(
                    MessageMapping.user_id == user_id,
                    MessageMapping.user_message_id == user_message_id
                )
            )
            mapping = result.scalar_one_or_none()
            return mapping.group_message_id if mapping else None
        except Exception as e:
            logger.error(f"Ошибка при получении маппинга по user: {e}")
            return None

async def set_last_editor_reply(user_id: int, group_message_id: int):
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(LastEditorReply).where(LastEditorReply.user_id == user_id)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                existing.last_group_message_id = group_message_id
                existing.updated_at = datetime.now()
            else:
                reply = LastEditorReply(user_id=user_id, last_group_message_id=group_message_id)
                session.add(reply)
            
            await session.commit()
            logger.debug(f"Обновлён последний ответ для {user_id}: {group_message_id}")
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при установке последнего ответа: {e}")

async def get_last_editor_reply(user_id: int):
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(LastEditorReply).where(LastEditorReply.user_id == user_id)
            )
            reply = result.scalar_one_or_none()
            return reply.last_group_message_id if reply else None
        except Exception as e:
            logger.error(f"Ошибка при получении последнего ответа: {e}")
            return None