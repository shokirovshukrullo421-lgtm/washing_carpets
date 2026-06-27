# keyboards/admin.py
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)


def admin_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🆕 Yangi buyurtmalar"),
             KeyboardButton(text="🪣 Barcha gilamlar")],
            [KeyboardButton(text="💵 Ish haqi so'rovlari"),
             KeyboardButton(text="💰 Qarzdorlar")],
            [KeyboardButton(text="➕ Qo'lda qo'shish"),
             KeyboardButton(text="⚙️ Settings")],
        ],
        resize_keyboard=True
    )


def admin_carpet_filter_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✨ Yetkazilishi kerak"),
             KeyboardButton(text="🧺 Jarayondagi")],
            [KeyboardButton(text="📋 Barcha gilamlar"),
             KeyboardButton(text="🔙 Orqaga")],
        ],
        resize_keyboard=True
    )


def admin_settings_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👁 Ko'rish"),
             KeyboardButton(text="➕ Qo'shish")],
            [KeyboardButton(text="🗑 O'chirish"),
             KeyboardButton(text="⚙️ O'zgartirish")],
            [KeyboardButton(text="🔗 Token havola"),
             KeyboardButton(text="🔙 Orqaga")],
        ],
        resize_keyboard=True
    )


# --- Yangi buyurtmalar ---

def new_orders_keyboard(orders: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for o in orders:
        name = o.get("user_name") or o.get("phone") or "—"
        client = f" · {o['client_note']}" if o.get("client_note") else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"📋 #{o['id']} {name}{client}",
                callback_data=f"ad_order_{o['id']}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def order_detail_keyboard(
    order_id: int,
    lat: float = None,
    lon: float = None
) -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(
            text="🚗 Olib kelindi",
            callback_data=f"ad_pickup_{order_id}"
        )
    ]
    if lat and lon:
        row.append(InlineKeyboardButton(
            text="🗺 Manzil",
            url=f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"
        ))
    return InlineKeyboardMarkup(inline_keyboard=[row])


# --- Yetkazilishi kerak ---

def deliver_keyboard(
    order_id: int,
    lat: float = None,
    lon: float = None
) -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(
            text="📦 Yetkazildi",
            callback_data=f"ad_deliver_{order_id}"
        )
    ]
    if lat and lon:
        row.append(InlineKeyboardButton(
            text="🗺 Manzil",
            url=f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"
        ))
    return InlineKeyboardMarkup(inline_keyboard=[row])


# --- Ish haqi so'rovlari ---

def pay_request_keyboard(payments: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for p in payments:
        worker = p.get("worker_name") or "—"
        client = p.get("client_note") or "—"
        amount = int(float(p["total_amount"]))
        buttons.append([
            InlineKeyboardButton(
                text=f"✅ {worker} · {client} · {amount:,}",
                callback_data=f"ad_pay_approve_{p['id']}"
            ),
            InlineKeyboardButton(
                text="❌",
                callback_data=f"ad_pay_reject_{p['id']}"
            ),
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# --- Qarzdorlar ---

def debtors_keyboard(
    debtors: list[dict],
    page: int,
    total: int,
    limit: int = 10
) -> InlineKeyboardMarkup:
    buttons = []
    for d in debtors:
        name = d.get("full_name") or "—"
        client = f" · {d['client_note']}" if d.get("client_note") else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"✅ #{d['order_id']} {name}{client} berdi",
                callback_data=f"ad_debt_pay_{d['order_id']}"
            )
        ])
    nav = _nav_buttons(page, total, limit, "ad_debt_page")
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# --- Barcha gilamlar paginatsiya ---

def pagination_keyboard(
    page: int,
    total: int,
    limit: int,
    prefix: str
) -> InlineKeyboardMarkup:
    nav = _nav_buttons(page, total, limit, prefix)
    if not nav:
        return InlineKeyboardMarkup(inline_keyboard=[])
    return InlineKeyboardMarkup(inline_keyboard=[nav])


# --- Jarayondagi paginatsiya ---

def inprogress_pagination(
    page: int,
    total: int,
    limit: int = 10
) -> InlineKeyboardMarkup:
    return pagination_keyboard(page, total, limit, "ad_inp_page")


# --- Settings: qo'shish ---

def settings_add_role_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Admin", callback_data="ad_add_admin")],
        [InlineKeyboardButton(text="👷 Worker", callback_data="ad_add_worker")],
        [InlineKeyboardButton(
            text="👤👷 Admin+Worker",
            callback_data="ad_add_admin_worker"
        )],
        [InlineKeyboardButton(text="❌ Bekor", callback_data="ad_cancel")],
    ])


# --- Settings: o'zgartirish ---

def settings_edit_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💰 Gilam yuvish narxi",
            callback_data="ad_edit_cprice"
        )],
        [InlineKeyboardButton(
            text="💵 Ishchi narxi",
            callback_data="ad_edit_wprice"
        )],
        [InlineKeyboardButton(
            text="🔑 Parol",
            callback_data="ad_edit_pass"
        )],
        [InlineKeyboardButton(text="❌ Bekor", callback_data="ad_cancel")],
    ])


def settings_worker_price_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="👥 Barcha ishchilar",
            callback_data="ad_wprice_all"
        )],
        [InlineKeyboardButton(
            text="👤 Tanlangan ishchi",
            callback_data="ad_wprice_one"
        )],
        [InlineKeyboardButton(text="❌ Bekor", callback_data="ad_cancel")],
    ])


def workers_list_keyboard(
    workers: list[dict],
    prefix: str
) -> InlineKeyboardMarkup:
    buttons = []
    for w in workers:
        name = w.get("full_name") or f"ID: {w['tg_id']}"
        price = w.get("effective_price") or w.get("worker_price_per_m2") or "—"
        buttons.append([
            InlineKeyboardButton(
                text=f"👷 {name} · {int(float(price)):,} so'm",
                callback_data=f"{prefix}_{w['id']}"
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="❌ Bekor", callback_data="ad_cancel")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def members_list_keyboard(
    members: list[dict],
    prefix: str
) -> InlineKeyboardMarkup:
    buttons = []
    for m in members:
        name      = m.get("full_name") or f"ID: {m['tg_id']}"
        role      = m.get("role", "")
        role_icon = {
            "admin":        "👤",
            "worker":       "👷",
            "admin_worker": "👤👷"
        }.get(role, "👤")
        # x separator
        buttons.append([
            InlineKeyboardButton(
                text=f"{role_icon} {name}",
                callback_data=f"{prefix}_{m['id']}x1"
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="❌ Bekor", callback_data="ad_cancel")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def confirm_keyboard(yes_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=yes_data),
        InlineKeyboardButton(text="❌ Bekor", callback_data="ad_cancel"),
    ]])


def price_confirm_keyboard(price: float, key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"✅ {int(price):,} so'm — Tasdiqlash",
            callback_data=f"ad_price_confirm_{key}"
        ),
        InlineKeyboardButton(text="❌ Bekor", callback_data="ad_cancel"),
    ]])


# --- Helper ---

def _nav_buttons(
    page: int,
    total: int,
    limit: int,
    prefix: str
) -> list:
    pages = (total + limit - 1) // limit
    if pages <= 1:
        return []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="◀️", callback_data=f"{prefix}_{page - 1}"
        ))
    nav.append(InlineKeyboardButton(
        text=f"{page + 1}/{pages}", callback_data="noop"
    ))
    if (page + 1) * limit < total:
        nav.append(InlineKeyboardButton(
            text="▶️", callback_data=f"{prefix}_{page + 1}"
        ))
    return nav

def admin_settings_full_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👁 Ko'rish"),
             KeyboardButton(text="➕ Qo'shish")],
            [KeyboardButton(text="🗑 O'chirish"),
             KeyboardButton(text="⚙️ O'zgartirish")],
            [KeyboardButton(text="🔗 Token havola"),
             KeyboardButton(text="💰 Kirim-Chiqim")],
            [KeyboardButton(text="📢 Reklama"),
             KeyboardButton(text="🔙 Orqaga")],
        ],
        resize_keyboard=True
    )


def finance_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📈 Kirim"),
             KeyboardButton(text="📉 Chiqim")],
            [KeyboardButton(text="➕ Xarajat qo'shish"),
             KeyboardButton(text="🔙 Orqaga")],
        ],
        resize_keyboard=True
    )


def period_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📅 Kunlik",  callback_data="period_day"),
        InlineKeyboardButton(text="📅 Haftalik", callback_data="period_week"),
        InlineKeyboardButton(text="📅 Oylik",   callback_data="period_month"),
        InlineKeyboardButton(text="📅 Yillik",  callback_data="period_year"),
    ]])


def expense_category_keyboard() -> InlineKeyboardMarkup:
    categories = [
        ("⛽ Yoqilg'i",        "cat_fuel"),
        ("🧴 Tozalash vositasi", "cat_clean"),
        ("🔧 Ta'mirlash",       "cat_repair"),
        ("🚗 Transport",        "cat_transport"),
        ("💡 Kommunal",         "cat_utility"),
        ("👔 Maosh",            "cat_salary"),
        ("📦 Boshqa",           "cat_other"),
    ]
    buttons = [[InlineKeyboardButton(text=name, callback_data=data)]
               for name, data in categories]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def ad_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Yuborish", callback_data="ad_send_yes"),
        InlineKeyboardButton(text="❌ Bekor",    callback_data="ad_send_no"),
    ]])
    
def urgent_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🚨 Shoshilinch",
            callback_data=f"ad_urgent_yes_{order_id}"
        ),
        InlineKeyboardButton(
            text="📋 Shoshilinch emas",
            callback_data=f"ad_urgent_no_{order_id}"
        ),
    ]])
