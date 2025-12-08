"""
Обработчики команд администратора
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InputMediaPhoto

from config import config
from database import db, AdStatus

router = Router()


class RejectStates(StatesGroup):
    """Состояния для отклонения объявления"""
    waiting_for_reason = State()


class BanStates(StatesGroup):
    """Состояния для бана пользователя"""
    waiting_for_reason = State()


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id in config.ADMIN_IDS


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Админ-панель"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к этой команде.")
        return
    
    pending_count = db.get_pending_count()
    banned_count = len(db.get_banned_users())
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📋 На модерации ({pending_count})", callback_data="admin_pending")],
        [InlineKeyboardButton(text=f"🚫 Забаненные ({banned_count})", callback_data="admin_banlist")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_refresh")]
    ])
    
    await message.answer(
        "🔧 <b>Админ-панель</b>\n\n"
        f"📋 Объявлений на модерации: {pending_count}\n"
        f"🚫 Забаненных пользователей: {banned_count}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_refresh")
async def refresh_admin(callback: CallbackQuery):
    """Обновить админ-панель"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    pending_count = db.get_pending_count()
    banned_count = len(db.get_banned_users())
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📋 На модерации ({pending_count})", callback_data="admin_pending")],
        [InlineKeyboardButton(text=f"🚫 Забаненные ({banned_count})", callback_data="admin_banlist")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_refresh")]
    ])
    
    await callback.message.edit_text(
        "🔧 <b>Админ-панель</b>\n\n"
        f"📋 Объявлений на модерации: {pending_count}\n"
        f"🚫 Забаненных пользователей: {banned_count}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer("✅ Обновлено")


@router.callback_query(F.data == "admin_banlist")
async def show_banlist_callback(callback: CallbackQuery):
    """Показать список забаненных по кнопке"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    banned_users = db.get_banned_users()
    
    if not banned_users:
        await callback.answer("✅ Нет забаненных пользователей!", show_alert=True)
        return
    
    await callback.answer()
    
    buttons = [[InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]]
    text = "🚫 <b>Забаненные пользователи:</b>\n\n"
    
    for i, user in enumerate(banned_users[:10]):
        username_text = f"@{user.username}" if user.username else "—"
        text += (
            f"{i+1}. <code>{user.user_id}</code> ({username_text})\n"
            f"   📝 {user.reason}\n"
            f"   📅 {user.banned_at.strftime('%d.%m.%Y')}\n\n"
        )
        buttons.insert(-1, [
            InlineKeyboardButton(
                text=f"✅ Разбанить {user.user_id}",
                callback_data=f"unban_{user.user_id}"
            )
        ])
    
    if len(banned_users) > 10:
        text += f"<i>...и ещё {len(banned_users) - 10}</i>"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    """Вернуться в админ-панель"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    pending_count = db.get_pending_count()
    banned_count = len(db.get_banned_users())
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📋 На модерации ({pending_count})", callback_data="admin_pending")],
        [InlineKeyboardButton(text=f"🚫 Забаненные ({banned_count})", callback_data="admin_banlist")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_refresh")]
    ])
    
    await callback.message.edit_text(
        "🔧 <b>Админ-панель</b>\n\n"
        f"📋 Объявлений на модерации: {pending_count}\n"
        f"🚫 Забаненных пользователей: {banned_count}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_pending")
async def show_pending(callback: CallbackQuery, bot: Bot):
    """Показать объявления на модерации"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    ads = db.get_pending_advertisements()
    
    if not ads:
        await callback.answer("✅ Нет объявлений на модерации!", show_alert=True)
        return
    
    await callback.answer()
    
    for ad in ads[:5]:  # Показываем первые 5
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{ad.id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{ad.id}")
            ],
            [
                InlineKeyboardButton(text="🚫 Забанить автора", callback_data=f"ban_user_{ad.user_id}")
            ]
        ])
        
        username_text = f"@{ad.username}" if ad.username else "нет username"
        
        caption = (
            f"📋 <b>Объявление #{ad.id}</b>\n\n"
            f"👤 От: {ad.first_name} ({username_text})\n"
            f"🆔 User ID: <code>{ad.user_id}</code>\n"
            f"📅 Создано: {ad.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"📝 <b>Описание:</b>\n{ad.description}"
        )
        
        try:
            if len(ad.photo_ids) == 1:
                await bot.send_photo(
                    chat_id=callback.from_user.id,
                    photo=ad.photo_ids[0],
                    caption=caption,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                media = [InputMediaPhoto(media=photo) for photo in ad.photo_ids]
                media[0].caption = caption
                media[0].parse_mode = "HTML"
                
                await bot.send_media_group(chat_id=callback.from_user.id, media=media)
                await bot.send_message(
                    chat_id=callback.from_user.id,
                    text=f"⬆️ Объявление #{ad.id} — выберите действие:",
                    reply_markup=keyboard
                )
        except Exception as e:
            await bot.send_message(
                chat_id=callback.from_user.id,
                text=f"❌ Ошибка загрузки объявления #{ad.id}: {e}"
            )


@router.callback_query(F.data.startswith("approve_"))
async def approve_ad(callback: CallbackQuery, bot: Bot):
    """Одобрить объявление"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    ad_id = int(callback.data.split("_")[1])
    ad = db.get_advertisement(ad_id)
    
    if not ad:
        await callback.answer("❌ Объявление не найдено", show_alert=True)
        return
    
    if ad.status != AdStatus.PENDING:
        await callback.answer("⚠️ Объявление уже обработано", show_alert=True)
        return
    
    # Публикуем в канал
    try:
        username_text = f"@{ad.username}" if ad.username else ad.first_name
        
        caption = (
            f"📢 <b>Новое объявление</b>\n\n"
            f"{ad.description}\n\n"
            f"👤 Автор: {username_text}"
        )
        
        if len(ad.photo_ids) == 1:
            msg = await bot.send_photo(
                chat_id=config.CHANNEL_ID,
                photo=ad.photo_ids[0],
                caption=caption,
                parse_mode="HTML"
            )
            message_id = msg.message_id
        else:
            media = [InputMediaPhoto(media=photo) for photo in ad.photo_ids]
            media[0].caption = caption
            media[0].parse_mode = "HTML"
            
            msgs = await bot.send_media_group(chat_id=config.CHANNEL_ID, media=media)
            message_id = msgs[0].message_id
        
        # Обновляем статус в БД
        db.approve_advertisement(ad_id, message_id)
        
        # Уведомляем пользователя
        try:
            await bot.send_message(
                chat_id=ad.user_id,
                text=f"✅ <b>Ваше объявление #{ad_id} одобрено и опубликовано!</b>\n\n"
                     f"Посмотреть: {config.CHANNEL_ID}",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Не удалось уведомить пользователя {ad.user_id}: {e}")
        
        await callback.answer("✅ Объявление опубликовано!", show_alert=True)
        
        # Обновляем сообщение с объявлением
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
            if callback.message.text:
                await callback.message.edit_text(
                    callback.message.text + "\n\n✅ <b>ОДОБРЕНО</b>",
                    parse_mode="HTML"
                )
        except:
            pass
            
    except Exception as e:
        await callback.answer(f"❌ Ошибка публикации: {e}", show_alert=True)


@router.callback_query(F.data.startswith("reject_"))
async def start_reject(callback: CallbackQuery, state: FSMContext):
    """Начать отклонение объявления"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    ad_id = int(callback.data.split("_")[1])
    ad = db.get_advertisement(ad_id)
    
    if not ad:
        await callback.answer("❌ Объявление не найдено", show_alert=True)
        return
    
    if ad.status != AdStatus.PENDING:
        await callback.answer("⚠️ Объявление уже обработано", show_alert=True)
        return
    
    await state.set_state(RejectStates.waiting_for_reason)
    await state.update_data(reject_ad_id=ad_id, reject_message=callback.message)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_reject")]
    ])
    
    await callback.message.answer(
        f"📝 <b>Отклонение объявления #{ad_id}</b>\n\n"
        "Напишите причину отклонения.\n"
        "Это сообщение получит автор объявления.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_reject")
async def cancel_reject(callback: CallbackQuery, state: FSMContext):
    """Отмена отклонения"""
    await state.clear()
    await callback.message.edit_text("❌ Отклонение отменено.")
    await callback.answer()


@router.message(RejectStates.waiting_for_reason, F.text)
async def receive_reject_reason(message: Message, state: FSMContext, bot: Bot):
    """Получение причины отклонения"""
    if not is_admin(message.from_user.id):
        return
    
    reason = message.text.strip()
    
    if len(reason) < 5:
        await message.answer("⚠️ Укажите более подробную причину (минимум 5 символов).")
        return
    
    data = await state.get_data()
    ad_id = data.get("reject_ad_id")
    original_message = data.get("reject_message")
    
    if not ad_id:
        await message.answer("❌ Ошибка: не найден ID объявления.")
        await state.clear()
        return
    
    ad = db.get_advertisement(ad_id)
    
    if not ad:
        await message.answer("❌ Объявление не найдено.")
        await state.clear()
        return
    
    # Отклоняем объявление
    db.reject_advertisement(ad_id, reason)
    
    await state.clear()
    
    # Уведомляем пользователя
    try:
        await bot.send_message(
            chat_id=ad.user_id,
            text=f"❌ <b>Ваше объявление #{ad_id} отклонено</b>\n\n"
                 f"📝 <b>Причина:</b>\n{reason}\n\n"
                 f"Вы можете создать новое объявление с учётом замечаний.",
            parse_mode="HTML"
        )
        notification_status = "✅ Пользователь уведомлён"
    except Exception as e:
        notification_status = f"⚠️ Не удалось уведомить пользователя: {e}"
    
    await message.answer(
        f"✅ <b>Объявление #{ad_id} отклонено</b>\n\n"
        f"📝 Причина: {reason}\n\n"
        f"{notification_status}",
        parse_mode="HTML"
    )
    
    # Обновляем оригинальное сообщение с объявлением
    if original_message:
        try:
            await original_message.edit_reply_markup(reply_markup=None)
        except:
            pass


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика (для админов)"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к этой команде.")
        return
    
    pending = db.get_pending_count()
    banned_count = len(db.get_banned_users())
    
    await message.answer(
        "📊 <b>Статистика</b>\n\n"
        f"⏳ На модерации: {pending}\n"
        f"🚫 Забанено: {banned_count}\n",
        parse_mode="HTML"
    )


@router.message(Command("ban"))
async def cmd_ban(message: Message, state: FSMContext):
    """Забанить пользователя: /ban USER_ID"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к этой команде.")
        return
    
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer(
            "🚫 <b>Бан пользователя</b>\n\n"
            "Использование: <code>/ban USER_ID</code>\n\n"
            "Пример: <code>/ban 123456789</code>\n\n"
            "💡 User ID можно скопировать из объявления на модерации.",
            parse_mode="HTML"
        )
        return
    
    try:
        user_id = int(args[1].strip())
    except ValueError:
        await message.answer("❌ Неверный формат ID. Укажите числовой ID пользователя.")
        return
    
    # Проверяем, не забанен ли уже
    if db.is_banned(user_id):
        ban_info = db.get_ban_info(user_id)
        await message.answer(
            f"⚠️ Пользователь <code>{user_id}</code> уже забанен.\n\n"
            f"📝 Причина: {ban_info.reason}\n"
            f"📅 Дата: {ban_info.banned_at.strftime('%d.%m.%Y %H:%M')}",
            parse_mode="HTML"
        )
        return
    
    # Сохраняем ID и запрашиваем причину
    await state.set_state(BanStates.waiting_for_reason)
    await state.update_data(ban_user_id=user_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_ban")]
    ])
    
    await message.answer(
        f"🚫 <b>Бан пользователя {user_id}</b>\n\n"
        "Напишите причину бана:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "cancel_ban")
async def cancel_ban(callback: CallbackQuery, state: FSMContext):
    """Отмена бана"""
    await state.clear()
    await callback.message.edit_text("❌ Бан отменён.")
    await callback.answer()


@router.message(BanStates.waiting_for_reason, F.text)
async def receive_ban_reason(message: Message, state: FSMContext, bot: Bot):
    """Получение причины бана"""
    if not is_admin(message.from_user.id):
        return
    
    reason = message.text.strip()
    
    if len(reason) < 3:
        await message.answer("⚠️ Укажите причину бана (минимум 3 символа).")
        return
    
    data = await state.get_data()
    user_id = data.get("ban_user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка: не найден ID пользователя.")
        await state.clear()
        return
    
    # Баним пользователя
    db.ban_user(
        user_id=user_id,
        username=None,  # Можно было бы получить из объявлений
        reason=reason,
        banned_by=message.from_user.id
    )
    
    await state.clear()
    
    # Пытаемся уведомить пользователя
    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"🚫 <b>Вы заблокированы</b>\n\n"
                 f"📝 Причина: {reason}\n\n"
                 f"Для разблокировки обратитесь к администратору.",
            parse_mode="HTML"
        )
        notification_status = "✅ Пользователь уведомлён"
    except Exception:
        notification_status = "⚠️ Не удалось уведомить пользователя"
    
    await message.answer(
        f"✅ <b>Пользователь {user_id} забанен</b>\n\n"
        f"📝 Причина: {reason}\n\n"
        f"{notification_status}",
        parse_mode="HTML"
    )


@router.message(Command("unban"))
async def cmd_unban(message: Message, bot: Bot):
    """Разбанить пользователя: /unban USER_ID"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к этой команде.")
        return
    
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer(
            "✅ <b>Разбан пользователя</b>\n\n"
            "Использование: <code>/unban USER_ID</code>\n\n"
            "Пример: <code>/unban 123456789</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        user_id = int(args[1].strip())
    except ValueError:
        await message.answer("❌ Неверный формат ID. Укажите числовой ID пользователя.")
        return
    
    if not db.is_banned(user_id):
        await message.answer(f"⚠️ Пользователь <code>{user_id}</code> не забанен.", parse_mode="HTML")
        return
    
    db.unban_user(user_id)
    
    # Пытаемся уведомить пользователя
    try:
        await bot.send_message(
            chat_id=user_id,
            text="✅ <b>Вы разблокированы!</b>\n\n"
                 "Теперь вы снова можете размещать объявления.",
            parse_mode="HTML"
        )
        notification_status = "✅ Пользователь уведомлён"
    except Exception:
        notification_status = "⚠️ Не удалось уведомить пользователя"
    
    await message.answer(
        f"✅ <b>Пользователь {user_id} разбанен</b>\n\n"
        f"{notification_status}",
        parse_mode="HTML"
    )


@router.message(Command("banlist"))
async def cmd_banlist(message: Message):
    """Список забаненных пользователей"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к этой команде.")
        return
    
    banned_users = db.get_banned_users()
    
    if not banned_users:
        await message.answer("✅ Нет забаненных пользователей.")
        return
    
    # Создаём кнопки разбана для каждого пользователя
    buttons = []
    text = "🚫 <b>Забаненные пользователи:</b>\n\n"
    
    for i, user in enumerate(banned_users[:10]):  # Максимум 10
        username_text = f"@{user.username}" if user.username else "—"
        text += (
            f"{i+1}. <code>{user.user_id}</code> ({username_text})\n"
            f"   📝 {user.reason}\n"
            f"   📅 {user.banned_at.strftime('%d.%m.%Y')}\n\n"
        )
        buttons.append([
            InlineKeyboardButton(
                text=f"✅ Разбанить {user.user_id}",
                callback_data=f"unban_{user.user_id}"
            )
        ])
    
    if len(banned_users) > 10:
        text += f"<i>...и ещё {len(banned_users) - 10}</i>\n"
        text += f"<i>Для полного списка: /banlist_all</i>"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("unban_"))
async def unban_callback(callback: CallbackQuery, bot: Bot):
    """Разбанить пользователя по кнопке"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[1])
    
    if not db.is_banned(user_id):
        await callback.answer("⚠️ Пользователь уже разбанен", show_alert=True)
        return
    
    db.unban_user(user_id)
    
    # Пытаемся уведомить пользователя
    try:
        await bot.send_message(
            chat_id=user_id,
            text="✅ <b>Вы разблокированы!</b>\n\n"
                 "Теперь вы снова можете размещать объявления.",
            parse_mode="HTML"
        )
    except Exception:
        pass
    
    await callback.answer(f"✅ Пользователь {user_id} разбанен!", show_alert=True)
    
    # Обновляем список
    banned_users = db.get_banned_users()
    
    if not banned_users:
        await callback.message.edit_text("✅ Нет забаненных пользователей.")
        return
    
    buttons = []
    text = "🚫 <b>Забаненные пользователи:</b>\n\n"
    
    for i, user in enumerate(banned_users[:10]):
        username_text = f"@{user.username}" if user.username else "—"
        text += (
            f"{i+1}. <code>{user.user_id}</code> ({username_text})\n"
            f"   📝 {user.reason}\n"
            f"   📅 {user.banned_at.strftime('%d.%m.%Y')}\n\n"
        )
        buttons.append([
            InlineKeyboardButton(
                text=f"✅ Разбанить {user.user_id}",
                callback_data=f"unban_{user.user_id}"
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("ban_user_"))
async def ban_from_ad(callback: CallbackQuery, state: FSMContext):
    """Забанить пользователя из объявления"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[2])
    
    if db.is_banned(user_id):
        await callback.answer("⚠️ Пользователь уже забанен", show_alert=True)
        return
    
    await state.set_state(BanStates.waiting_for_reason)
    await state.update_data(ban_user_id=user_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_ban")]
    ])
    
    await callback.message.answer(
        f"🚫 <b>Бан пользователя {user_id}</b>\n\n"
        "Напишите причину бана:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()

