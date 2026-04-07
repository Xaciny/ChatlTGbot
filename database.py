from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, BigInteger, DateTime, select, delete, Index, text
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

# Читаем параметры БД из переменных окружения
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'chatl_bot')
DB_USER = os.getenv('DB_USER', 'chatl_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'change_me')

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Создаём движок
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Поставь True для отладки
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)

# Фабрика сессий
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

# Таблица для забаненных пользователей
class BannedUser(Base):
    __tablename__ = 'banned_users'
    __table_args__ = {'schema': 'public'}
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    banned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    banned_by: Mapped[int] = mapped_column(BigInteger, nullable=True)
    
# Таблица для маппинга сообщений
class MessageMapping(Base):
    __tablename__ = 'message_mappings'
    __table_args__ = (
        Index('idx_user_message', 'user_id', 'user_message_id'),
        Index('idx_group_message', 'group_message_id'),
        {'schema': 'public'}
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_message_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

# Таблица для последних ответов редакции
class LastEditorReply(Base):
    __tablename__ = 'last_editor_replies'
    __table_args__ = {'schema': 'public'}
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    last_group_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

async def init_db():
    """Инициализация базы данных - создание таблиц"""
    try:
        async with engine.begin() as conn:
            # Создаём схему public если её нет
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
            # Создаём все таблицы
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("✅ База данных успешно инициализирована")
        
        # Проверяем создание таблиц
        async with AsyncSessionLocal() as session:
            result = await session.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            ))
            tables = [row[0] for row in result]
            logger.info(f"📊 Таблицы в БД: {tables}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации БД: {e}")
        raise

# Функции для работы с забаненными пользователями
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
                logger.info(f"✅ Пользователь {user_id} добавлен в бан-лист")
                return True
            return False
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Ошибка при добавлении в бан: {e}")
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
                logger.info(f"✅ Пользователь {user_id} удалён из бан-листа")
            return removed
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Ошибка при удалении из бана: {e}")
            return False

async def is_user_banned(user_id: int) -> bool:
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(BannedUser).where(BannedUser.user_id == user_id)
            )
            return result.scalar_one_or_none() is not None
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке бана: {e}")
            return False

async def get_all_banned_users():
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(BannedUser.user_id))
            return {row[0] for row in result.all()}
        except Exception as e:
            logger.error(f"❌ Ошибка при получении списка банов: {e}")
            return set()

# Функции для работы с маппингом сообщений
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
            logger.debug(f"✅ Добавлен маппинг: {group_message_id} -> {user_id}:{user_message_id}")
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Ошибка при добавлении маппинга: {e}")

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
            logger.error(f"❌ Ошибка при получении маппинга: {e}")
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
            logger.error(f"❌ Ошибка при получении маппинга по user: {e}")
            return None

# Функции для работы с последними ответами редакции
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
            logger.debug(f"✅ Обновлён последний ответ для {user_id}: {group_message_id}")
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Ошибка при установке последнего ответа: {e}")

async def get_last_editor_reply(user_id: int):
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(LastEditorReply).where(LastEditorReply.user_id == user_id)
            )
            reply = result.scalar_one_or_none()
            return reply.last_group_message_id if reply else None
        except Exception as e:
            logger.error(f"❌ Ошибка при получении последнего ответа: {e}")
            return None