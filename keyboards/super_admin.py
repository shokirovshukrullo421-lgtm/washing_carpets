# keyboards/super_admin.py
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)


def sa_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏭 Sexlar"), KeyboardButton(text="➕ Sex qo'shish")],
            [KeyboardButton(text="🔑 Parollar")],
        ],
        resize_keyboard=True
    )


def sa_workshops_keyboard(workshops: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for w in workshops:
        status = "✅" if w["is_active"] else "❌"
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {w['name']}",
                callback_data=f"sa_ws_{w['id']}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sa_workshop_actions(workshop_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👁 Ko'rish", callback_data=f"sa_view_{workshop_id}"),
            InlineKeyboardButton(text="➕ Qo'shish", callback_data=f"sa_add_{workshop_id}"),
        ],
        [
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"sa_del_{workshop_id}"),
            InlineKeyboardButton(text="⚙️ O'zgartirish", callback_data=f"sa_edit_{workshop_id}"),
        ],
    ])


def sa_add_role_keyboard(workshop_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Admin", callback_data=f"sa_add_admin_{workshop_id}")],
        [InlineKeyboardButton(text="👷 Worker", callback_data=f"sa_add_worker_{workshop_id}")],
        [InlineKeyboardButton(text="👤👷 Admin+Worker", callback_data=f"sa_add_admin_worker_{workshop_id}")],
        [InlineKeyboardButton(text="❌ Bekor", callback_data="sa_cancel")],
    ])


def sa_edit_actions(workshop_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Gilam yuvish narxi", callback_data=f"sa_edit_cprice_{workshop_id}")],
        [InlineKeyboardButton(text="💵 Ishchi narxi", callback_data=f"sa_edit_wprice_{workshop_id}")],
        [InlineKeyboardButton(text="🔑 Parol", callback_data=f"sa_edit_pass_{workshop_id}")],
        [InlineKeyboardButton(text="❌ Bekor", callback_data="sa_cancel")],
    ])


def sa_worker_price_keyboard(workshop_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="👥 Barcha ishchilar narxi",
            callback_data=f"sa_wprice_all_{workshop_id}"
        )],
        [InlineKeyboardButton(
            text="👤 Tanlangan ishchi narxi",
            callback_data=f"sa_wprice_one_{workshop_id}"
        )],
        [InlineKeyboardButton(text="❌ Bekor", callback_data="sa_cancel")],
    ])


def sa_members_keyboard(
    members: list[dict],
    action: str,
    workshop_id: int
) -> InlineKeyboardMarkup:
    buttons = []
    for m in members:
        name   = m.get("full_name") or f"ID: {m['tg_id']}"
        status = "✅" if m.get("uw_active", True) else "❌"
        # x separator ishlatamiz — _ bilan chalkashmaydi
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {name}",
                callback_data=f"{action}_{m['id']}x{workshop_id}"
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="❌ Bekor", callback_data="sa_cancel")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)



def sa_confirm_keyboard(yes_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=yes_data),
        InlineKeyboardButton(text="❌ Bekor", callback_data="sa_cancel"),
    ]])