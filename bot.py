"""
Telegram Bot для объявлений с модерацией
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from handlers import user, admin, channel


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


async def main():
    """Точка входа"""
    
    # Проверяем конфигурацию
    if config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ Ошибка: Укажите BOT_TOKEN в config.py или переменной окружения!")
        logger.error("   Получите токен у @BotFather в Telegram")
        return
    
    if not config.ADMIN_IDS:
        logger.warning("⚠️ Предупреждение: Не указаны ADMIN_IDS!")
        logger.warning("   Добавьте ID администраторов в config.py или переменную окружения")
    
    # Инициализация бота
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Хранилище состояний (в памяти)
    storage = MemoryStorage()
    
    # Диспетчер
    dp = Dispatcher(storage=storage)
    
    # Подключаем роутеры
    dp.include_router(user.router)
    dp.include_router(admin.router)
    dp.include_router(channel.router)
    
    # Запуск
    logger.info("🚀 Бот запускается...")
    logger.info(f"👤 Администраторы: {config.ADMIN_IDS}")
    logger.info(f"📢 Канал для публикации: {config.CHANNEL_ID}")
    
    try:
        # Удаляем вебхук (если был) и запускаем polling
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(
            bot, 
            allowed_updates=["message", "callback_query", "chat_member"]
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен")

