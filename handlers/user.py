# handlers/user.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states.states import UserOrderStates
from keyboards.user import (
    user_main_menu, share_contact_keyboard,
    share_location_keyboard, confirm_order_keyboard
)
from db.queries import (
    get_user_by_tg_id, create_user, update_user_phone,
    get_workshop_by_id, create_order, confirm_order,
    get_workshop_admins, save_log
)
from utils.helpers import generate_expires_at
from utils.logger import logger

router = Router()

ABOUT_TEXT = """
🧹 <b>Gilam yuvish xizmati</b>

Biz professional gilam yuvish xizmatini taqdim etamiz.

✅ Yuqori sifat
✅ Tez yetkazib berish  
✅ Qulay narxlar
✅ Tajribali mutaxassislar
"""


# ============================================================
# BIZ HAQIMIZDA
# ============================================================

@router.message(F.text == "ℹ️ Biz haqimizda")
async def user_about(message: Message, role=None):
    if role in ("super_admin", "admin", "worker",
                "admin_worker", "multi"):
        return
    await message.answer(ABOUT_TEXT)


# ============================================================
# ADMIN BILAN BOG'LANISH
# ============================================================

@router.message(F.text == "📞 Admin bilan bog'lanish")
async def user_contact_admin(
    message: Message,
    role=None,
    workshop=None,
    user=None
):
    if role in ("super_admin", "admin", "worker",
                "admin_worker", "multi"):
        return

    # workshop middleware dan keladi
    if not workshop:
        await message.answer(
            "⚠️ Siz hali hech qaysi sexga bog'lanmagansiz.\n"
            "Admindan havola olib, u orqali kiring."
        )
        return

    try:
        admins = await get_workshop_admins(workshop["id"])
        sent   = 0
        for admin in admins:
            try:
                await message.bot.send_message(
                    admin["tg_id"],
                    f"📞 <b>Foydalanuvchi bog'lanmoqchi:</b>\n\n"
                    f"👤 {message.from_user.full_name}\n"
                    f"🆔 <code>{message.from_user.id}</code>\n"
                    f"📱 @{message.from_user.username or '—'}"
                )
                sent += 1
            except Exception:
                pass

        if sent > 0:
            await message.answer(
                "✅ So'rovingiz adminga yuborildi!\n"
                "Tez orada siz bilan bog'lanamiz."
            )
        else:
            await message.answer(
                "⚠️ Admin hozirda mavjud emas.\n"
                "Keyinroq urinib ko'ring."
            )
    except Exception as e:
        logger.error(f"user_contact_admin: {e}", exc_info=True)
        await message.answer("⚠️ Xatolik yuz berdi.")


# ============================================================
# BUYURTMA BERISH — BOSHLASH
# ============================================================

@router.message(F.text == "📝 Buyurtma berish")
async def user_order_start(
    message: Message,
    state: FSMContext,
    role=None,
    workshop=None
):
    if role in ("super_admin", "admin", "worker",
                "admin_worker", "multi"):
        return

    if not workshop:
        await message.answer(
            "⚠️ Buyurtma berish uchun avval havola orqali "
            "sexga ulaning.\n"
            "Admindan havola so'rang."
        )
        return

    # workshop_id ni state ga saqlaymiz
    await state.update_data(workshop_id=workshop["id"])
    await state.set_state(UserOrderStates.waiting_contact)
    await message.answer(
        "📞 Telefon raqamingizni ulashing:",
        reply_markup=share_contact_keyboard()
    )


# ============================================================
# QADAM 1 — KONTAKT
# ============================================================

@router.message(UserOrderStates.waiting_contact)
async def user_contact(message: Message, state: FSMContext):
    # Bekor qilish
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer(
            "❌ Bekor qilindi.",
            reply_markup=user_main_menu()
        )
        return

    # Kontakt ulashildi
    if message.contact:
        phone = message.contact.phone_number
        if not phone.startswith("+"):
            phone = "+" + phone
        await update_user_phone(message.from_user.id, phone)
        await state.update_data(phone=phone)
        await state.set_state(UserOrderStates.waiting_location)
        await message.answer(
            "📍 Manzilingizni ulashing\n"
            "yoki /skip — lokatsiyasiz davom etish:",
            reply_markup=share_location_keyboard()
        )
        return

    # Boshqa matn keldi
    await message.answer(
        "⚠️ Iltimos tugma orqali kontaktingizni ulashing.",
        reply_markup=share_contact_keyboard()
    )


# ============================================================
# QADAM 2 — LOKATSIYA
# ============================================================

@router.message(UserOrderStates.waiting_location)
async def user_location(message: Message, state: FSMContext):
    # Bekor qilish
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer(
            "❌ Bekor qilindi.",
            reply_markup=user_main_menu()
        )
        return

    # Skip
    if message.text == "/skip":
        await state.update_data(location_lat=None, location_lon=None)
        await state.set_state(UserOrderStates.waiting_pickup_time)
        await message.answer(
            "🕐 Uyingizga qachon boraylik?\n\n"
            "Masalan: bugun kechga, ertaga ertalab...",
            reply_markup=None
        )
        return

    # Lokatsiya ulashildi
    if message.location:
        await state.update_data(
            location_lat=message.location.latitude,
            location_lon=message.location.longitude
        )
        await state.set_state(UserOrderStates.waiting_pickup_time)
        await message.answer(
            "🕐 Uyingizga qachon boraylik?\n\n"
            "Masalan: bugun kechga, ertaga ertalab...",
            reply_markup=None
        )
        return

    # Boshqa matn
    await message.answer(
        "⚠️ Iltimos tugma orqali lokatsiyangizni ulashing.\n"
        "Yoki /skip yozing.",
        reply_markup=share_location_keyboard()
    )


# ============================================================
# QADAM 3 — VAQT
# ============================================================

@router.message(UserOrderStates.waiting_pickup_time)
async def user_pickup_time(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("⚠️ Matn kiriting.")
        return

    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer(
            "❌ Bekor qilindi.",
            reply_markup=user_main_menu()
        )
        return

    await state.update_data(pickup_time_note=message.text.strip())
    await state.set_state(UserOrderStates.waiting_extra_note)
    await message.answer(
        "📝 Qo'shimcha izoh (ixtiyoriy)\n"
        "/skip — o'tkazib yuborish:"
    )


# ============================================================
# QADAM 4 — IZOH
# ============================================================

@router.message(UserOrderStates.waiting_extra_note)
async def user_extra_note(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("⚠️ Matn kiriting yoki /skip yozing.")
        return

    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer(
            "❌ Bekor qilindi.",
            reply_markup=user_main_menu()
        )
        return

    if message.text == "/skip":
        await state.update_data(extra_note=None)
    else:
        await state.update_data(extra_note=message.text.strip())

    await _show_order_summary(message, state)


# ============================================================
# BUYURTMA XULOSA
# ============================================================

async def _show_order_summary(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.set_state(UserOrderStates.waiting_confirm)

    text = (
        f"📋 <b>Buyurtma ma'lumotlari:</b>\n\n"
        f"📞 Telefon: {data.get('phone', '—')}\n"
        f"🕐 Vaqt: {data.get('pickup_time_note', '—')}\n"
    )
    if data.get("location_lat"):
        text += f"📍 Lokatsiya: ulashildi ✅\n"
    if data.get("extra_note"):
        text += f"📝 Izoh: {data['extra_note']}\n"
    text += "\n✅ Tasdiqlaysizmi?"

    await message.answer(
        text,
        reply_markup=confirm_order_keyboard()
    )


# ============================================================
# TASDIQLASH — HA
# ============================================================

@router.callback_query(
    UserOrderStates.waiting_confirm,
    F.data == "usr_confirm_yes"
)
async def user_order_confirmed(
    callback: CallbackQuery,
    state: FSMContext,
    user=None,
    workshop=None
):
    try:
        data = await state.get_data()

        # workshop — avval middleware dan, bo'lmasa state dan
        ws_id = None
        if workshop:
            ws_id = workshop["id"]
        elif data.get("workshop_id"):
            ws_id = data["workshop_id"]

        if not ws_id:
            await callback.message.answer(
                "⚠️ Sex topilmadi. /start bosing."
            )
            await state.clear()
            await callback.answer()
            return

        # User
        db_user = user
        if not db_user:
            db_user = await get_user_by_tg_id(callback.from_user.id)
        if not db_user:
            db_user = await create_user(
                tg_id=callback.from_user.id,
                full_name=callback.from_user.full_name or "Foydalanuvchi"
            )

        # Workshop ma'lumotlari
        ws = await get_workshop_by_id(ws_id)
        if not ws:
            await callback.message.answer("⚠️ Sex topilmadi.")
            await state.clear()
            await callback.answer()
            return

        timeout = ws.get("confirm_timeout_sec") or 300
        expires = generate_expires_at(timeout)

        # Buyurtma yaratish
        order = await create_order(
            workshop_id=ws_id,
            user_id=db_user["id"],
            phone=data["phone"],
            location_lat=data.get("location_lat"),
            location_lon=data.get("location_lon"),
            pickup_time_note=data["pickup_time_note"],
            extra_note=data.get("extra_note"),
            expires_at=expires
        )
        await confirm_order(order["id"])
        await state.clear()

        await callback.message.edit_text(
            "✅ Buyurtmangiz qabul qilindi!\n"
            "Tez orada siz bilan bog'lanamiz. 📞"
        )
        await callback.message.answer(
            "Bosh menyu:",
            reply_markup=user_main_menu()
        )

        # Adminlarga xabar
        try:
            admins = await get_workshop_admins(ws_id)
            for admin in admins:
                try:
                    await callback.bot.send_message(
                        admin["tg_id"],
                        f"🆕 <b>Yangi buyurtma #{order['id']}!</b>\n\n"
                        f"👤 {callback.from_user.full_name}\n"
                        f"📞 {data['phone']}\n"
                        f"🕐 {data['pickup_time_note']}"
                    )
                except Exception:
                    pass
        except Exception:
            pass

        await save_log(
            db_user["tg_id"], "user_order",
            f"order={order['id']}", ws_id
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"user_order_confirmed: {e}", exc_info=True)
        await callback.message.answer("⚠️ Xatolik yuz berdi.")
        await state.clear()
        await callback.answer()


# ============================================================
# TASDIQLASH — YO'Q
# ============================================================

@router.callback_query(
    UserOrderStates.waiting_confirm,
    F.data == "usr_confirm_no"
)
async def user_order_cancelled(
    callback: CallbackQuery,
    state: FSMContext
):
    await state.clear()
    await callback.message.edit_text("❌ Buyurtma bekor qilindi.")
    await callback.message.answer(
        "Bosh menyu:",
        reply_markup=user_main_menu()
    )
    await callback.answer()