from aiogram import Router

from .admin import admin_router
from .group import group_router
from .private import private_router

main_router = Router()
main_router.include_router(private_router)
main_router.include_router(group_router)
main_router.include_router(admin_router)

__all__ = ["main_router", "private_router", "group_router", "admin_router"]
