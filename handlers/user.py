"""
Обработчики команд пользователей
"""
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InputMediaPhoto

from config import config
from database import db, AdStatus

router = Router()

# Хранилище для сбора альбомов (media_group)
album_data: dict[str, dict] = {}


class AddAdStates(StatesGroup):
    """Состояния для добавления объявления"""
    waiting_for_content = State()  # Ожидаем фото с описанием
    confirm = State()


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Добавить объявление")],
            [KeyboardButton(text="📋 Мои объявления")],
            [KeyboardButton(text="📢 Реклама")],
            [KeyboardButton(text="📜 Правила"), KeyboardButton(text="📞 Контакты")],
        ],
        resize_keyboard=True
    )


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True
    )


def get_confirm_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура подтверждения"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Отправить на модерацию")],
            [KeyboardButton(text="🔄 Начать заново")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True
    )


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    await state.clear()
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Я бот для размещения объявлений.\n\n"
        "📝 <b>Добавить объявление</b> — разместить новое объявление\n"
        "📋 <b>Мои объявления</b> — посмотреть ваши объявления\n\n"
        "⚠️ Все объявления проходят модерацию перед публикацией.",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )


@router.message(F.text == "❌ Отмена")
async def cancel_action(message: Message, state: FSMContext):
    """Отмена текущего действия"""
    await state.clear()
    await message.answer(
        "❌ Действие отменено.",
        reply_markup=get_main_keyboard()
    )


@router.message(F.text == "📜 Правила")
@router.message(Command("rules"))
async def show_rules(message: Message):
    """Показать правила"""
    await message.answer(
        config.RULES,
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )


@router.message(F.text == "📞 Контакты")
@router.message(Command("contacts"))
async def show_contacts(message: Message):
    """Показать контакты"""
    await message.answer(
        config.CONTACTS,
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )


@router.message(F.text == "📢 Реклама")
@router.message(Command("ads"))
async def show_advertising(message: Message):
    """Показать информацию о рекламе"""
    await message.answer(
        config.ADVERTISING,
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )


@router.message(F.text == "📝 Добавить объявление")
async def start_add_ad(message: Message, state: FSMContext):
    """Начало добавления объявления"""
    # Проверяем бан
    if db.is_banned(message.from_user.id):
        ban_info = db.get_ban_info(message.from_user.id)
        await message.answer(
            f"🚫 <b>Вы заблокированы</b>\n\n"
            f"📝 Причина: {ban_info.reason}\n\n"
            f"Для разблокировки обратитесь к администратору.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return
    
    # Проверяем лимит объявлений за день
    ads_today = db.get_user_ads_today(message.from_user.id)
    if ads_today >= config.MAX_ADS_PER_DAY:
        await message.answer(
            f"⚠️ <b>Вы достигли лимита объявлений на сегодня!</b>\n\n"
            f"Максимум {config.MAX_ADS_PER_DAY} объявлений в день.\n"
            f"Сегодня вы уже создали: {ads_today}\n\n"
            f"Попробуйте завтра 🙏",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return
    
    await state.clear()
    await state.set_state(AddAdStates.waiting_for_content)
    
    remaining_today = config.MAX_ADS_PER_DAY - ads_today - 1
    
    await message.answer(
        f"📸 <b>Создание объявления</b>\n\n"
        f"Отправьте фото (от {config.MIN_PHOTOS} до {config.MAX_PHOTOS} шт.) "
        f"с описанием в подписи.\n\n"
        f"<b>Как это сделать:</b>\n"
        f"1. Выберите фото (от 1 до 5 шт.)\n"
        f"2. В описании укажите название товара, описание, цену, локацию\n"
        f"3. Отправьте\n\n"
        f"📝 Описание: от {config.MIN_DESCRIPTION_LENGTH} до {config.MAX_DESCRIPTION_LENGTH} символов\n\n"
        f"<i>💡 Осталось объявлений сегодня: {remaining_today + 1}</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(AddAdStates.waiting_for_content, F.photo)
async def receive_photo_with_caption(message: Message, state: FSMContext, bot: Bot):
    """Получение фото с описанием"""
    
    # Если это часть альбома (media_group)
    if message.media_group_id:
        await handle_album(message, state)
        return
    
    # Одиночное фото
    photo_id = message.photo[-1].file_id
    caption = message.caption or ""
    
    # Проверяем описание
    if not caption or len(caption.strip()) < config.MIN_DESCRIPTION_LENGTH:
        await message.answer(
            f"⚠️ <b>Добавьте описание!</b>\n\n"
            f"Отправьте фото с подписью (минимум {config.MIN_DESCRIPTION_LENGTH} символов).\n"
            f"Описание пишется в поле под фото перед отправкой.",
            parse_mode="HTML"
        )
        return
    
    if len(caption) > config.MAX_DESCRIPTION_LENGTH:
        await message.answer(
            f"⚠️ Описание слишком длинное!\n"
            f"Максимум {config.MAX_DESCRIPTION_LENGTH} символов.\n"
            f"Сейчас: {len(caption)}"
        )
        return
    
    # Сохраняем данные и переходим к подтверждению
    await state.update_data(photos=[photo_id], description=caption.strip())
    await state.set_state(AddAdStates.confirm)
    
    await message.answer(
        f"📋 <b>Превью объявления:</b>\n\n"
        f"📸 Фотографий: 1\n"
        f"📝 Описание:\n{caption.strip()}\n\n"
        f"Отправить на модерацию?",
        reply_markup=get_confirm_keyboard(),
        parse_mode="HTML"
    )


async def handle_album(message: Message, state: FSMContext):
    """Обработка альбома (несколько фото)"""
    media_group_id = message.media_group_id
    user_id = message.from_user.id
    key = f"{user_id}_{media_group_id}"
    
    # Инициализируем хранилище для этого альбома
    if key not in album_data:
        album_data[key] = {
            "photos": [],
            "caption": None,
            "message": message,
            "state": state,
            "processed": False
        }
    
    # Добавляем фото
    photo_id = message.photo[-1].file_id
    album_data[key]["photos"].append(photo_id)
    
    # Сохраняем подпись (берём из первого фото с подписью)
    if message.caption and not album_data[key]["caption"]:
        album_data[key]["caption"] = message.caption.strip()
    
    # Запускаем обработку с задержкой (ждём все фото альбома)
    asyncio.create_task(process_album_delayed(key, state))


async def process_album_delayed(key: str, state: FSMContext):
    """Обработка альбома после небольшой задержки"""
    await asyncio.sleep(0.5)  # Ждём все фото альбома
    
    if key not in album_data or album_data[key]["processed"]:
        return
    
    album_data[key]["processed"] = True
    data = album_data[key]
    photos = data["photos"]
    caption = data["caption"]
    message = data["message"]
    
    # Очищаем данные
    del album_data[key]
    
    # Проверяем количество фото
    if len(photos) > config.MAX_PHOTOS:
        await message.answer(
            f"⚠️ Максимум {config.MAX_PHOTOS} фотографий!\n"
            f"Вы отправили: {len(photos)}\n"
            f"Попробуйте ещё раз с меньшим количеством."
        )
        return
    
    # Проверяем описание
    if not caption or len(caption) < config.MIN_DESCRIPTION_LENGTH:
        await message.answer(
            f"⚠️ <b>Добавьте описание!</b>\n\n"
            f"Отправьте фото с подписью (минимум {config.MIN_DESCRIPTION_LENGTH} символов).\n"
            f"Описание пишется в поле под фото перед отправкой.",
            parse_mode="HTML"
        )
        return
    
    if len(caption) > config.MAX_DESCRIPTION_LENGTH:
        await message.answer(
            f"⚠️ Описание слишком длинное!\n"
            f"Максимум {config.MAX_DESCRIPTION_LENGTH} символов.\n"
            f"Сейчас: {len(caption)}"
        )
        return
    
    # Сохраняем данные и переходим к подтверждению
    await state.update_data(photos=photos, description=caption)
    await state.set_state(AddAdStates.confirm)
    
    await message.answer(
        f"📋 <b>Превью объявления:</b>\n\n"
        f"📸 Фотографий: {len(photos)}\n"
        f"📝 Описание:\n{caption}\n\n"
        f"Отправить на модерацию?",
        reply_markup=get_confirm_keyboard(),
        parse_mode="HTML"
    )


@router.message(AddAdStates.waiting_for_content)
async def invalid_content_input(message: Message):
    """Неверный ввод"""
    await message.answer(
        f"⚠️ Отправьте фото с описанием в подписи.\n\n"
        f"<b>Как это сделать:</b>\n"
        f"1. Нажмите на скрепку 📎\n"
        f"2. Выберите фото\n"
        f"3. В поле «Добавить подпись» напишите описание\n"
        f"4. Отправьте",
        parse_mode="HTML"
    )


@router.message(AddAdStates.confirm, F.text == "✅ Отправить на модерацию")
async def confirm_ad(message: Message, state: FSMContext, bot: Bot):
    """Подтверждение и отправка на модерацию"""
    data = await state.get_data()
    photos = data.get("photos", [])
    description = data.get("description", "")
    
    if not photos or not description:
        await message.answer("❌ Ошибка: данные объявления не найдены. Начните заново.")
        await state.clear()
        return
    
    # Сохраняем в БД
    ad_id = db.add_advertisement(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        description=description,
        photo_ids=photos
    )
    
    await state.clear()
    
    await message.answer(
        f"✅ <b>Объявление #{ad_id} отправлено на модерацию!</b>\n\n"
        "Вы получите уведомление после проверки.",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )
    
    # Отправляем уведомление админам
    await notify_admins_new_ad(bot, ad_id, message.from_user, photos, description)


@router.message(AddAdStates.confirm, F.text == "🔄 Начать заново")
async def restart_ad(message: Message, state: FSMContext):
    """Начать создание объявления заново"""
    await start_add_ad(message, state)


@router.message(F.text == "📋 Мои объявления")
async def my_ads(message: Message):
    """Показать объявления пользователя"""
    ads = db.get_user_advertisements(message.from_user.id)
    
    if not ads:
        await message.answer(
            "📭 У вас пока нет объявлений.\n"
            "Нажмите «📝 Добавить объявление» чтобы создать первое!",
            reply_markup=get_main_keyboard()
        )
        return
    
    status_emoji = {
        AdStatus.PENDING: "⏳ На модерации",
        AdStatus.APPROVED: "✅ Опубликовано",
        AdStatus.REJECTED: "❌ Отклонено"
    }
    
    text = "📋 <b>Ваши объявления:</b>\n\n"
    
    for ad in ads[:10]:  # Показываем последние 10
        status = status_emoji.get(ad.status, "❓")
        text += f"<b>#{ad.id}</b> — {status}\n"
        text += f"📝 {ad.description[:50]}...\n" if len(ad.description) > 50 else f"📝 {ad.description}\n"
        
        if ad.status == AdStatus.REJECTED and ad.reject_reason:
            text += f"💬 Причина: {ad.reject_reason}\n"
        
        text += "\n"
    
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="HTML")


async def notify_admins_new_ad(bot: Bot, ad_id: int, user, photos: list, description: str):
    """Отправляет уведомление админам о новом объявлении"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    # Клавиатура для модерации
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{ad_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{ad_id}")
        ],
        [
            InlineKeyboardButton(text="🚫 Забанить", callback_data=f"ban_user_{user.id}")
        ]
    ])
    
    username_text = f"@{user.username}" if user.username else "нет username"
    
    # Получаем количество объявлений пользователя за сегодня
    ads_today = db.get_user_ads_today(user.id)
    
    caption = (
        f"🆕 <b>Новое объявление #{ad_id}</b>\n\n"
        f"👤 От: {user.first_name} ({username_text})\n"
        f"🆔 User ID: <code>{user.id}</code>\n"
        f"📊 Объявление за сутки: <b>{ads_today}/{config.MAX_ADS_PER_DAY}</b>\n\n"
        f"📝 <b>Описание:</b>\n{description}"
    )
    
    # Отправляем админам
    for admin_id in config.ADMIN_IDS:
        try:
            if len(photos) == 1:
                await bot.send_photo(
                    chat_id=admin_id,
                    photo=photos[0],
                    caption=caption,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                # Отправляем альбом
                media = [InputMediaPhoto(media=photo) for photo in photos]
                media[0].caption = caption
                media[0].parse_mode = "HTML"
                
                await bot.send_media_group(chat_id=admin_id, media=media)
                # Кнопки отправляем отдельным сообщением
                await bot.send_message(
                    chat_id=admin_id,
                    text=f"⬆️ Объявление #{ad_id} — выберите действие:",
                    reply_markup=keyboard
                )
        except Exception as e:
            print(f"Ошибка отправки админу {admin_id}: {e}")
    
    # Также отправляем в чат модерации, если указан
    if config.MODERATION_CHAT_ID:
        try:
            if len(photos) == 1:
                await bot.send_photo(
                    chat_id=config.MODERATION_CHAT_ID,
                    photo=photos[0],
                    caption=caption,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                media = [InputMediaPhoto(media=photo) for photo in photos]
                media[0].caption = caption
                media[0].parse_mode = "HTML"
                
                await bot.send_media_group(chat_id=config.MODERATION_CHAT_ID, media=media)
                await bot.send_message(
                    chat_id=config.MODERATION_CHAT_ID,
                    text=f"⬆️ Объявление #{ad_id} — выберите действие:",
                    reply_markup=keyboard
                )
        except Exception as e:
            print(f"Ошибка отправки в чат модерации: {e}")
