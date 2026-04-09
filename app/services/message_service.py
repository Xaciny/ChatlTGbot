import logging
from app.database import crud

logger = logging.getLogger(__name__)

class MessageService:
    @staticmethod
    async def save_mapping(group_message_id: int, user_id: int, user_message_id: int):
        await crud.add_message_mapping(group_message_id, user_id, user_message_id)
    
    @staticmethod
    async def get_mapping_by_group(group_message_id: int):
        return await crud.get_message_mapping(group_message_id)
    
    @staticmethod
    async def get_mapping_by_user(user_id: int, user_message_id: int):
        return await crud.get_user_message_mapping(user_id, user_message_id)
    
    @staticmethod
    async def set_last_reply(user_id: int, group_message_id: int):
        await crud.set_last_editor_reply(user_id, group_message_id)
    
    @staticmethod
    async def get_last_reply(user_id: int):
        return await crud.get_last_editor_reply(user_id)