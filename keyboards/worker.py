# keyboards/worker.py
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)


def worker_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Ishni boshlash"),
             KeyboardButton(text="🔒 Bronlarim")],
            [KeyboardButton(text="❌ Bronni bekor qilish"),
             KeyboardButton(text="💵 Ish haqqim")],
        ],
        resize_keyboard=True
    )


def unbooked_orders_keyboard(orders: list[dict]) -> InlineKeyboardMarkup:
    """Bron qilinmagan xonadonlar ro'yxati"""
    buttons = []
    for o in orders:
        client = o.get("client_note") or "—"
        count = o.get("carpet_count", 0)
        buttons.append([
            InlineKeyboardButton(
                text=f"🏠 #{o['order_id']} · {client} · {count} ta",
                callback_data=f"wr_view_{o['order_id']}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def booked_orders_keyboard(orders: list[dict]) -> InlineKeyboardMarkup:
    """Bron qilingan xonadonlar + yuvildi tugmasi"""
    buttons = []
    for o in orders:
        client = o.get("client_note") or "—"
        count = o.get("carpet_count", 0)
        buttons.append([
            InlineKeyboardButton(
                text=f"🏠 #{o['order_id']} · {client} · {count} ta",
                callback_data=f"wr_washed_{o['order_id']}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_bookings_keyboard(orders: list[dict]) -> InlineKeyboardMarkup:
    """Bron bekor qilish"""
    buttons = []
    for o in orders:
        client = o.get("client_note") or "—"
        buttons.append([
            InlineKeyboardButton(
                text=f"❌ #{o['order_id']} · {client}",
                callback_data=f"wr_cancel_{o['order_id']}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def wash_confirm_keyboard(order_id: int, area: int) -> InlineKeyboardMarkup:
    """Yuvildi tasdiqlash"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"✅ {area} m² — Tasdiqlash",
                callback_data=f"wr_wash_confirm_{order_id}_{area}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="✏️ O'zgartirish",
                callback_data=f"wr_wash_edit_{order_id}"
            ),
        ]
    ])


def pending_payments_keyboard(payments: list[dict]) -> InlineKeyboardMarkup:
    """Ish haqi so'rovlari"""
    buttons = []
    for p in payments:
        client = p.get("client_note") or "—"
        amount = int(float(p["total_amount"]))
        buttons.append([
            InlineKeyboardButton(
                text=f"📨 #{p['order_id']} · {client} · {amount:,} so'm",
                callback_data=f"wr_pay_req_{p['order_id']}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)




def unbooked_orders_keyboard(orders: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for o in orders:
        client  = o.get("client_note") or "—"
        count   = o.get("carpet_count", 0)
        urgent  = "🚨 " if o.get("is_urgent") else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"{urgent}#{o['order_id']} · {client} · {count} ta",
                callback_data=f"wr_view_{o['order_id']}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)