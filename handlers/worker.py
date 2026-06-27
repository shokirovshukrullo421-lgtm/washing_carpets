# handlers/worker.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart

from states.states import WorkerStartStates, WorkerWashStates
from keyboards.worker import (
    worker_main_menu, unbooked_orders_keyboard,
    booked_orders_keyboard, cancel_bookings_keyboard,
    wash_confirm_keyboard, pending_payments_keyboard
)
from db.queries import (
    get_unbooked_orders, get_worker_booked_orders,
    book_order_carpets, cancel_order_booking,
    get_carpets_by_order, finish_order_carpets,
    get_worker_pending_payments, request_worker_payment,
    get_worker_workshop_by_tg, save_log
)
from utils.helpers import (
    is_valid_dimensions, parse_dimensions,
    calculate_area, fmt_money
)
from utils.formatter import format_worker_payment
from utils.logger import logger

router = Router()


def is_worker(role: str) -> bool:
    return role in ("worker", "admin_worker", "super_mini_admin_worker")


# ============================================================
# START
# ============================================================




# ============================================================
# ISHNI BOSHLASH
# ============================================================

@router.message(F.text == "🚀 Ishni boshlash")
async def worker_start_work(message: Message, state: FSMContext,
                             role=None, workshop=None):
    if not is_worker(role):
        return
    try:
        orders = await get_unbooked_orders(workshop["id"])
        if not orders:
            await message.answer("📭 Hozircha bron qilinmagan xonadon yo'q.")
            return
        text = "🏠 <b>Bron qilinmagan xonadonlar:</b>\n\n"
        for o in orders:
            text += (
                f"📋 #{o['order_id']} · "
                f"{o.get('client_note') or '—'} · "
                f"🪣 {o['carpet_count']} ta\n"
            )
        await message.answer(text)
        await state.set_state(WorkerStartStates.waiting_count)
        await state.update_data(orders=orders)
        await message.answer(
            f"Nechta xonadon gilamini yuvmoqchisiz?\n"
            f"(1 dan {len(orders)} gacha):"
        )
    except Exception as e:
        logger.error(f"worker_start_work: {e}")
        await message.answer("⚠️ Xatolik.")


@router.message(WorkerStartStates.waiting_count, F.text)
async def worker_book_count(message: Message, state: FSMContext,
                             role=None, workshop=None, user=None):
    if not is_worker(role):
        return
    try:
        count = int(message.text.strip())
        data  = await state.get_data()
        orders = data.get("orders", [])

        if count <= 0 or count > len(orders):
            await message.answer(
                f"⚠️ 1 dan {len(orders)} gacha son kiriting."
            )
            return

        # Effective worker price olish
        ws_data = await get_worker_workshop_by_tg(message.from_user.id)
        worker_price = float(ws_data["worker_price_per_m2"])

        # Navbat bilan bron qilish
        booked = []
        for o in orders[:count]:
            await book_order_carpets(o["order_id"], user["id"], worker_price)
            booked.append(o)

        await state.clear()
        text = f"✅ <b>{count} ta xonadon</b> bron qilindi:\n\n"
        for o in booked:
            text += (
                f"🔒 #{o['order_id']} · "
                f"{o.get('client_note') or '—'} · "
                f"🪣 {o['carpet_count']} ta\n"
            )
        await message.answer(text, reply_markup=worker_main_menu())
        await save_log(
            user["tg_id"], "worker_book",
            f"count={count}", workshop["id"]
        )
    except ValueError:
        await message.answer("⚠️ Faqat raqam kiriting.")
    except Exception as e:
        logger.error(f"worker_book_count: {e}")
        await message.answer("⚠️ Xatolik.")
        await state.clear()


# ============================================================
# BRONLARIM
# ============================================================

@router.message(F.text == "🔒 Bronlarim")
async def worker_my_bookings(message: Message, role=None,
                              workshop=None, user=None):
    if not is_worker(role):
        return
    try:
        orders = await get_worker_booked_orders(user["id"], workshop["id"])
        if not orders:
            await message.answer("📭 Bron qilingan xonadonlar yo'q.")
            return
        await message.answer(
            "🔒 <b>Bron qilingan xonadonlar:</b>\n"
            "Yuvilgan xonadonni tanlang:",
            reply_markup=booked_orders_keyboard(orders)
        )
    except Exception as e:
        logger.error(f"worker_my_bookings: {e}")
        await message.answer("⚠️ Xatolik.")


@router.callback_query(F.data.startswith("wr_washed_"))
async def worker_washed_start(callback: CallbackQuery,
                               state: FSMContext, role=None, workshop=None):
    if not is_worker(role):
        return
    try:
        order_id = int(callback.data.split("_")[-1])
        carpets  = await get_carpets_by_order(order_id)
        booked   = [c for c in carpets if c["status"] == "booked"]
        count    = len(booked)

        await state.update_data(
            wash_order_id=order_id,
            wash_carpet_count=count
        )
        await state.set_state(WorkerWashStates.waiting_dimensions)
        await callback.message.answer(
            f"🏠 <b>Buyurtma #{order_id}</b>\n"
            f"🪣 <b>{count} ta gilam</b>\n\n"
            f"📐 {count} ta gilamning o'lchamlarini kiriting:\n"
            f"Har bir gilam vergul bilan ajratilsin\n\n"
            f"Masalan: <code>2*3, 3.5*4, 2*2.5</code>\n\n"
            f"Yoki umumiy maydonni ham qo'shishingiz mumkin:\n"
            f"<code>2*3, 3.5*4</code> — bot hisoblaydi\n"
            f"Keyin tasdiqlash so'raladi."
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"worker_washed_start: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


@router.message(WorkerWashStates.waiting_dimensions, F.text)
async def worker_dimensions(message: Message, state: FSMContext, role=None):
    if not is_worker(role):
        return
    try:
        text = message.text.strip()
        if not is_valid_dimensions(text):
            await message.answer(
                "⚠️ Noto'g'ri format.\n"
                "Masalan: <code>2*3, 3.5*4</code>"
            )
            return
        dims = parse_dimensions(text)
        area = calculate_area(dims)

        await state.update_data(dimensions_raw=text, calculated_area=area)
        await state.set_state(WorkerWashStates.waiting_area)

        data = await state.get_data()
        order_id = data["wash_order_id"]

        await message.answer(
            f"📐 Kiritilgan o'lchamlar: <code>{text}</code>\n"
            f"📏 Hisoblangan maydon: <b>{area} m²</b>\n\n"
            f"Tasdiqlaysizmi yoki o'zgartirasizmi?\n"
            f"(O'zgartirish uchun yangi son kiriting)",
            reply_markup=wash_confirm_keyboard(order_id, area)
        )
    except Exception as e:
        logger.error(f"worker_dimensions: {e}")
        await message.answer("⚠️ Xatolik.")


@router.message(WorkerWashStates.waiting_area, F.text)
async def worker_area_manual(message: Message, state: FSMContext, role=None):
    """Ishchi maydonni qo'lda kiritadi"""
    if not is_worker(role):
        return
    try:
        area = int(float(message.text.strip()))
        if area <= 0:
            await message.answer("⚠️ Maydon musbat bo'lishi kerak.")
            return
        data = await state.get_data()
        await state.update_data(final_area=area)
        await message.answer(
            f"📏 Yangi maydon: <b>{area} m²</b>\n\n"
            f"Tasdiqlaysizmi?",
            reply_markup=wash_confirm_keyboard(data["wash_order_id"], area)
        )
    except ValueError:
        await message.answer("⚠️ Faqat raqam kiriting.")
    except Exception as e:
        logger.error(f"worker_area_manual: {e}")
        await message.answer("⚠️ Xatolik.")


@router.callback_query(F.data.startswith("wr_wash_confirm_"))
async def worker_wash_confirm(callback: CallbackQuery,
                               state: FSMContext, role=None,
                               workshop=None, user=None):
    if not is_worker(role):
        return
    try:
        parts    = callback.data.split("_")
        order_id = int(parts[3])
        area     = int(parts[4])

        data = await state.get_data()
        dims = data.get("dimensions_raw", "")

        ws_data = await get_worker_workshop_by_tg(callback.from_user.id)
        worker_price = float(ws_data["worker_price_per_m2"])
        client_price = float(ws_data["price_per_m2"])

        await finish_order_carpets(
            order_id=order_id,
            worker_id=user["id"],
            dimensions_raw=dims,
            total_area_m2=area,
            worker_price=worker_price,
            client_price=client_price,
            workshop_id=workshop["id"]
        )
        await state.clear()
        await callback.message.answer(
            f"✅ <b>#{order_id}</b> xonadon gilamlari yuvilgan deb belgilandi!\n"
            f"📐 O'lchamlar: {dims}\n"
            f"📏 Umumiy maydon: <b>{area} m²</b>",
            reply_markup=worker_main_menu()
        )
        await save_log(
            user["tg_id"], "worker_wash",
            f"order={order_id} area={area}", workshop["id"]
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"worker_wash_confirm: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


@router.callback_query(F.data.startswith("wr_wash_edit_"))
async def worker_wash_edit(callback: CallbackQuery,
                            state: FSMContext, role=None):
    """Maydonni qayta kiritish"""
    if not is_worker(role):
        return
    await state.set_state(WorkerWashStates.waiting_area)
    await callback.message.answer(
        "📏 Umumiy maydonni kiriting (m²):"
    )
    await callback.answer()


# ============================================================
# BRONNI BEKOR QILISH
# ============================================================

@router.message(F.text == "❌ Bronni bekor qilish")
async def worker_cancel_bookings(message: Message, role=None,
                                  workshop=None, user=None):
    if not is_worker(role):
        return
    try:
        orders = await get_worker_booked_orders(user["id"], workshop["id"])
        if not orders:
            await message.answer("📭 Bekor qilish uchun bronlar yo'q.")
            return
        await message.answer(
            "Qaysi xonadon bronini bekor qilmoqchisiz?",
            reply_markup=cancel_bookings_keyboard(orders)
        )
    except Exception as e:
        logger.error(f"worker_cancel_bookings: {e}")
        await message.answer("⚠️ Xatolik.")


@router.callback_query(F.data.startswith("wr_cancel_"))
async def worker_cancel_booking(callback: CallbackQuery,
                                 role=None, workshop=None, user=None):
    if not is_worker(role):
        return
    try:
        order_id = int(callback.data.split("_")[-1])
        await cancel_order_booking(order_id, user["id"])
        await callback.message.edit_text(
            f"✅ #{order_id} xonadon broni bekor qilindi."
        )
        await save_log(
            user["tg_id"], "worker_cancel_booking",
            f"order={order_id}", workshop["id"]
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"worker_cancel_booking: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


# ============================================================
# ISH HAQQIM
# ============================================================

@router.message(F.text == "💵 Ish haqqim")
async def worker_payments(message: Message, role=None,
                           workshop=None, user=None):
    if not is_worker(role):
        return
    try:
        payments = await get_worker_pending_payments(user["id"], workshop["id"])
        if not payments:
            await message.answer("📭 Tasdiqlanmagan ish haqlari yo'q.")
            return
        text  = "💵 <b>Yuvilgan xonadonlar (ish haqi):</b>\n\n"
        total = 0
        for p in payments:
            text  += format_worker_payment(p) + "\n"
            total += float(p["total_amount"])
        text += f"💰 <b>Jami: {fmt_money(total)}</b>"
        await message.answer(
            text,
            reply_markup=pending_payments_keyboard(payments)
        )
    except Exception as e:
        logger.error(f"worker_payments: {e}")
        await message.answer("⚠️ Xatolik.")


@router.callback_query(F.data.startswith("wr_pay_req_"))
async def worker_pay_request(callback: CallbackQuery,
                              role=None, workshop=None, user=None):
    if not is_worker(role):
        return
    try:
        order_id = int(callback.data.split("_")[-1])
        await request_worker_payment(order_id, user["id"])
        await callback.message.edit_text(
            f"✅ #{order_id} uchun ish haqi so'rovi adminga yuborildi.\n"
            f"Admin tasdiqlashini kuting."
        )
        await save_log(
            user["tg_id"], "worker_pay_request",
            f"order={order_id}", workshop["id"]
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"worker_pay_request: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)