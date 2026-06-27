# handlers/super_mini_admin_worker.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart
from utils.logger import logger

router = Router()

ROLE_LABELS = {
    "super_admin":  "👑 Super admin",
    "admin":        "👤 Admin",
    "worker":       "👷 Ishchi",
    "admin_worker": "👤👷 Admin+Ishchi",
}


def roles_keyboard(roles: list[dict]) -> InlineKeyboardMarkup:
    """
    Har bir rol uchun button yasaydi.
    admin_worker → 2 ta button (admin + worker).
    """
    buttons = []
    for r in roles:
        role    = r["role"]
        ws      = r.get("workshop")
        ws_name = ws["name"] if ws else ""
        blocked = ws and (
            not ws.get("uw_active", True) or
            not ws.get("ws_active",  True)
        )
        suffix = " 🚫" if blocked else ""

        if role == "admin_worker":
            # 2 ta alohida button
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


def _find_workshop_for(roles: list[dict], target: str) -> dict | None:
    """
    Berilgan target rol uchun workshop topadi.
    target: 'admin', 'worker', 'super_admin'
    """
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
# START — multi yoki admin_worker
# ============================================================

# ============================================================
# ROL TANLASH CALLBACK
# ============================================================

@router.callback_query(F.data.startswith("rsel_"))
async def role_selected(
    callback: CallbackQuery,
    state: FSMContext,
    roles=None,
    user=None,
    role=None
):
    try:
        selected = callback.data.replace("rsel_", "")
        # selected: "admin" | "worker" | "super_admin"

        data      = await state.get_data()
        all_roles = data.get("all_roles") or roles or []

        # Workshop topamiz
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

        # Panelni ochamiz
        if selected == "super_admin":
            from keyboards.super_admin import sa_main_menu
            await callback.message.answer(
                "👑 <b>Super admin panel</b>",
                reply_markup=sa_main_menu()
            )

        elif selected == "admin":
            if not workshop:
                await callback.answer(
                    "⚠️ Admin panel uchun sex topilmadi.",
                    show_alert=True
                )
                return
            from keyboards.admin import admin_main_menu
            await callback.message.answer(
                f"👤 <b>Admin panel</b> — {workshop['name']}",
                reply_markup=admin_main_menu()
            )

        elif selected == "worker":
            if not workshop:
                await callback.answer(
                    "⚠️ Ishchi panel uchun sex topilmadi.",
                    show_alert=True
                )
                return
            from keyboards.worker import worker_main_menu
            await callback.message.answer(
                f"👷 <b>Ishchi panel</b> — {workshop['name']}",
                reply_markup=worker_main_menu()
            )

        else:
            await callback.answer("Noma'lum rol.", show_alert=True)
            return

        # Tanlangan rolni state ga saqlaymiz
        await state.update_data(
            selected_role=selected,
            selected_workshop=workshop
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"role_selected: {e}", exc_info=True)
        await callback.answer("⚠️ Xatolik.", show_alert=True)