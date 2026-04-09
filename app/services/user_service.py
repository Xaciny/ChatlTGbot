import logging
from app.database import crud

logger = logging.getLogger(__name__)

class UserService:
    @staticmethod
    async def is_banned(user_id: int) -> bool:
        return await crud.is_user_banned(user_id)
    
    @staticmethod
    async def ban_user(user_id: int, banned_by: int = None) -> bool:
        return await crud.add_banned_user(user_id, banned_by)
    
    @staticmethod
    async def unban_user(user_id: int) -> bool:
        return await crud.remove_banned_user(user_id)
    
    @staticmethod
    async def get_all_banned() -> set:
        return await crud.get_all_banned_users()