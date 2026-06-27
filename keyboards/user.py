# keyboards/user.py
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)


def user_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Buyurtma berish"),
             KeyboardButton(text="📞 Admin bilan bog'lanish")],
            [KeyboardButton(text="ℹ️ Biz haqimizda")],
        ],
        resize_keyboard=True
    )


def share_contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Kontaktni ulashish", request_contact=True)],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def share_location_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Lokatsiyani ulashish", request_location=True)],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def confirm_order_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha", callback_data="usr_confirm_yes"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data="usr_confirm_no"),
    ]])


def role_select_keyboard(roles: list[str]) -> ReplyKeyboardMarkup:
    """
    admin_worker va super_mini_admin_worker uchun rol tanlash
    """
    role_labels = {
        "admin":                  "👤 Admin panel",
        "worker":                 "👷 Worker panel",
        "super_admin":            "👑 Super admin panel",
        "super_mini_admin_worker": "👤 Admin / 👷 Worker / 👑 Super",
    }
    keyboard = []
    for role in roles:
        label = role_labels.get(role, role)
        keyboard.append([KeyboardButton(text=label)])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)