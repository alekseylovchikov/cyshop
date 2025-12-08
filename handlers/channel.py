"""
Обработчики событий канала
"""
from aiogram import Router, Bot, F
from aiogram.types import ChatMemberUpdated
from aiogram.filters import ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER

from config import config

router = Router()


@router.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_user_joined_channel(event: ChatMemberUpdated, bot: Bot):
    """Обработка подписки на канал"""
    
    # Проверяем, что это наш канал
    if event.chat.username and f"@{event.chat.username}" != config.CHANNEL_ID:
        # Если CHANNEL_ID указан как @username
        if not config.CHANNEL_ID.startswith("@"):
            return
        if f"@{event.chat.username}" != config.CHANNEL_ID:
            return
    
    user = event.new_chat_member.user
    
    # Не отправляем сообщение ботам
    if user.is_bot:
        return
    
    # Отправляем приветственное сообщение в личку
    try:
        await bot.send_message(
            chat_id=user.id,
            text=config.WELCOME_MESSAGE,
            parse_mode="HTML"
        )
    except Exception as e:
        # Пользователь не начал диалог с ботом - это нормально
        print(f"Не удалось отправить приветствие {user.id}: {e}")

