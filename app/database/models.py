from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, BigInteger, DateTime, Index
from datetime import datetime

class Base(DeclarativeBase):
    pass

class BannedUser(Base):
    __tablename__ = 'banned_users'
    __table_args__ = {'schema': 'public'}
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    banned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    banned_by: Mapped[int] = mapped_column(BigInteger, nullable=True)

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

class LastEditorReply(Base):
    __tablename__ = 'last_editor_replies'
    __table_args__ = {'schema': 'public'}
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    last_group_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)