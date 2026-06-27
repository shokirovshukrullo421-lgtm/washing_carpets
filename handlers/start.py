# handlers/start.py
# BARCHA /start handlerlari shu yerda — bitta joy

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart

from config import settings
from db.queries import (
    get_workshop_by_token, get_user_workshop,
    add_user_to_workshop, create_user,
    get_user_by_tg_id, save_log
)
from keyboards.super_admin import sa_main_menu
from keyboards.admin import admin_main_menu
from keyboards.worker import worker_main_menu
from keyboards.user import user_main_menu
from utils.logger import logger

router = Router()
SA = settings.SUPER_ADMIN_TG_ID

ROLE_LABELS = {
    "super_admin":  "👑 Super admin",
    "admin":        "👤 Admin",
    "worker":       "👷 Ishchi",
    "admin_worker": "👤👷 Admin+Ishchi",
}


def roles_keyboard(roles: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for r in roles:
        role    = r["role"]
        ws      = r.get("workshop")
        ws_name = ws["name"] if ws else ""
        blocked = ws and (
            not ws.get("uw_active", True) or
            not ws.get("ws_active", True)
        )
        suffix = " 🚫" if blocked else ""

        if role == "admin_worker":
            buttons.append([InlineKeyboardButton(
                text=f"👤 Admin — {ws_name}{suffix}",
                callback_data="rsel_admin"
            )])
            buttons.append([InlineKeyboardButton(
                text=f"👷 Ishchi — {ws_name}{suffix}",
                callback_data="rsel_worker"
            )])
        elif role == "super_admin":
            buttons.append([InlineKeyboardButton(
                text=f"👑 Super admin{suffix}",
                callback_data="rsel_super_admin"
            )])
        elif role == "admin":
            buttons.append([InlineKeyboardButton(
                text=f"👤 Admin — {ws_name}{suffix}",
                callback_data="rsel_admin"
            )])
        elif role == "worker":
            buttons.append([InlineKeyboardButton(
                text=f"👷 Ishchi — {ws_name}{suffix}",
                callback_data="rsel_worker"
            )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _find_workshop_for(roles: list[dict], target: str):
    for r in roles:
        role = r["role"]
        if target == "super_admin" and role == "super_admin":
            return None
        if target == "admin" and role in ("admin", "admin_worker"):
            return r.get("workshop")
        if target == "worker" and role in ("worker", "admin_worker"):
            return r.get("workshop")
    return None


# ============================================================
# YAGONA /start HANDLER
# ============================================================

@router.message(CommandStart())
async def universal_start(
    message: Message,
    state: FSMContext,
    role=None,
    roles=None,
    user=None,
    workshop=None
):
    await state.clear()
    args  = message.text.split()
    token = args[1] if len(args) > 1 else None

    # ── 1. KO'P ROL — tanlash kerak ─────────────────────────
    if role == "multi" or (roles and len(roles) > 1):
        await state.update_data(all_roles=roles or [])
        await message.answer(
            f"👋 Xush kelibsiz, <b>{message.from_user.full_name}</b>!\n\n"
            f"Qaysi rolda ishlaysiz?",
            reply_markup=roles_keyboard(roles or [])
        )
        return

    # ── 2. SUPER ADMIN ───────────────────────────────────────
    if role == "super_admin":
        await message.answer(
            "👑 <b>Bosh admin paneli</b>\n\n"
            "Barcha sexlarni boshqaring.",
            reply_markup=sa_main_menu()
        )
        await save_log(SA, "sa_start")
        return

    # ── 3. ADMIN ─────────────────────────────────────────────
    if role == "admin":
        ws_name = workshop["name"] if workshop else "—"
        await message.answer(
            f"👋 Xush kelibsiz, <b>{message.from_user.full_name}</b>!\n"
            f"🏭 <b>{ws_name}</b> admin paneli",
            reply_markup=admin_main_menu()
        )
        return

    # ── 4. WORKER ────────────────────────────────────────────
    if role == "worker":
        ws_name = workshop["name"] if workshop else "—"
        await message.answer(
            f"👋 Xush kelibsiz, <b>{message.from_user.full_name}</b>!\n"
            f"🏭 <b>{ws_name}</b> ishchi paneli",
            reply_markup=worker_main_menu()
        )
        return

    # ── 5. ADMIN_WORKER — bitta rol, tanlash ─────────────────
    if role == "admin_worker":
        await state.update_data(all_roles=roles or [])
        await message.answer(
            f"👋 Xush kelibsiz, <b>{message.from_user.full_name}</b>!\n\n"
            f"Qaysi rolda ishlaysiz?",
            reply_markup=roles_keyboard(roles or [])
        )
        return

    # ── 6. USER ──────────────────────────────────────────────
    # Token bilan kelgan bo'lsa
    if token:
        try:
            ws = await get_workshop_by_token(token)
            if ws:
                # User yaratish yoki olish
                db_user = user
                if not db_user:
                    db_user = await create_user(
                        tg_id=message.from_user.id,
                        full_name=message.from_user.full_name or "Foydalanuvchi"
                    )

                # Sexga bog'lash
                existing = await get_user_workshop(db_user["id"], ws["id"])
                if not existing:
                    await add_user_to_workshop(db_user["id"], ws["id"], "user")

                await message.answer(
                    f"👋 Xush kelibsiz!\n"
                    f"🏭 <b>{ws['name']}</b> xizmatiga ulandingiz.\n\n"
                    f"Buyurtma berish uchun quyidagi tugmani bosing.",
                    reply_markup=user_main_menu()
                )
                await save_log(
                    db_user["tg_id"], "user_token_connect",
                    f"ws={ws['id']}", ws["id"]
                )
            else:
                await message.answer(
                    "⚠️ Havola noto'g'ri yoki muddati o'tgan.\n"
                    "Admindan yangi havola so'rang."
                )
        except Exception as e:
            logger.error(f"user_start token: {e}", exc_info=True)
            await message.answer("⚠️ Xatolik yuz berdi.")
        return

    # Token yo'q — allaqachon bog'langanmi?
    if workshop:
        await message.answer(
            f"👋 Xush kelibsiz, <b>{message.from_user.full_name}</b>!\n"
            f"🏭 <b>{workshop['name']}</b>",
            reply_markup=user_main_menu()
        )
    else:
        # User umuman yo'q yoki hech qaysi sexga bog'lanmagan
        # Avval yaratamiz
        if not user:
            try:
                await create_user(
                    tg_id=message.from_user.id,
                    full_name=message.from_user.full_name or "Foydalanuvchi"
                )
            except Exception as e:
                logger.error(f"create_user: {e}")

        await message.answer(
            f"👋 Xush kelibsiz, <b>{message.from_user.full_name}</b>!\n\n"
            f"Buyurtma berish uchun admindan havola so'rang.",
            reply_markup=user_main_menu()
        )


# ============================================================
# ROL TANLASH CALLBACK
# ============================================================

@router.callback_query(F.data.startswith("rsel_"))
async def role_selected(
    callback: CallbackQuery,
    state: FSMContext,
    roles=None,
    user=None
):
    try:
        selected  = callback.data.replace("rsel_", "")
        data      = await state.get_data()
        all_roles = data.get("all_roles") or roles or []

        workshop = _find_workshop_for(all_roles, selected)

        # Bloklangan tekshirish
        if workshop and (
            not workshop.get("uw_active", True) or
            not workshop.get("ws_active",  True)
        ):
            await callback.answer(
                "🚫 Siz bu rolda bloklangansiz.",
                show_alert=True
            )
            return

        if selected == "super_admin":
            await callback.message.answer(
                "👑 <b>Bosh admin paneli</b>",
                reply_markup=sa_main_menu()
            )

        elif selected == "admin":
            if not workshop:
                await callback.answer(
                    "⚠️ Sex topilmadi.", show_alert=True
                )
                return
            await callback.message.answer(
                f"👤 <b>Admin panel</b> — {workshop['name']}",
                reply_markup=admin_main_menu()
            )

        elif selected == "worker":
            if not workshop:
                await callback.answer(
                    "⚠️ Sex topilmadi.", show_alert=True
                )
                return
            await callback.message.answer(
                f"👷 <b>Ishchi panel</b> — {workshop['name']}",
                reply_markup=worker_main_menu()
            )
        else:
            await callback.answer("Noma'lum rol.", show_alert=True)
            return

        await state.update_data(
            selected_role=selected,
            selected_workshop=workshop
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"role_selected: {e}", exc_info=True)
        await callback.answer("⚠️ Xatolik.", show_alert=True)