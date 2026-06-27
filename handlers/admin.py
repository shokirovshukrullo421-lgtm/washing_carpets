# handlers/admin.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart

from states.states import (
    AdminPickupStates, AdminPaymentStates,
    AdminDebtStates, AdminSettingsStates,
    AdminAddMemberStates, AdminManualOrderStates,
    AdminRejectStates, AdminAdStates, AdminFinanceStates
)
from keyboards.admin import (
    admin_main_menu, admin_carpet_filter_menu,
    admin_settings_full_menu, new_orders_keyboard,
    order_detail_keyboard, deliver_keyboard,
    pay_request_keyboard, debtors_keyboard,
    pagination_keyboard, inprogress_pagination,
    settings_add_role_keyboard, settings_edit_keyboard,
    settings_worker_price_keyboard, workers_list_keyboard,
    members_list_keyboard, confirm_keyboard,
    finance_menu, period_keyboard,
    expense_category_keyboard, ad_confirm_keyboard,
)
from keyboards.user import share_contact_keyboard, share_location_keyboard
from db.queries import (
    get_new_orders, get_order_by_id, pickup_order,
    get_inprogress_orders, get_inprogress_orders_count,
    get_washed_orders, get_all_carpets_paginated,
    get_all_carpets_count, deliver_order_carpets,
    get_client_payment, add_client_payment,
    set_debt_note, get_debtors, get_debtors_count,
    get_requested_payments, approve_worker_payment,
    reject_worker_payment, get_workshop_by_id,
    get_workshop_admins, get_workshop_workers,
    get_workshop_members, get_user_by_tg_id,
    check_user_active_role, add_user_to_workshop,
    deactivate_user_in_workshop, update_workshop_client_price,
    update_workshop_default_worker_price, update_worker_price,
    update_workshop_password, create_order, confirm_order,
    create_user, update_user_phone, save_log,
    add_or_reactivate_member,
    get_all_orders_by_workshop, get_all_orders_count,
    add_expense, get_expenses,
    get_income, get_finance_summary,
    get_workshop_users_tg_ids, save_ad_log,
    set_order_urgent
)
from utils.helpers import (
    hash_password, fmt_money, should_add_debt,
    generate_expires_at, is_valid_dimensions,
    parse_dimensions, calculate_area,
    calculate_discount, apply_discount
)
from utils.formatter import (
    format_order, format_washed_order_for_delivery,
    format_debtor, format_worker_payment
)
from utils.logger import logger

router = Router()


def is_admin(role: str) -> bool:
    return role in ("admin", "admin_worker", "super_mini_admin_worker")


# ============================================================
# YANGI BUYURTMALAR
# ============================================================

@router.message(F.text == "🆕 Yangi buyurtmalar")
async def admin_new_orders(message: Message, role=None, workshop=None):
    if not is_admin(role):
        return
    try:
        orders = await get_new_orders(workshop["id"])
        if not orders:
            await message.answer("📭 Hozircha yangi buyurtmalar yo'q.")
            return
        await message.answer(
            f"🆕 <b>Yangi buyurtmalar: {len(orders)} ta</b>",
            reply_markup=new_orders_keyboard(orders)
        )
    except Exception as e:
        logger.error(f"admin_new_orders: {e}")
        await message.answer("⚠️ Xatolik yuz berdi.")


@router.callback_query(F.data.startswith("ad_order_"))
async def admin_order_detail(callback: CallbackQuery, role=None, workshop=None):
    if not is_admin(role):
        return
    try:
        order_id = int(callback.data.split("_")[-1])
        order = await get_order_by_id(order_id)
        if not order or order["workshop_id"] != workshop["id"]:
            await callback.answer("Buyurtma topilmadi.", show_alert=True)
            return
        await callback.message.answer(
            format_order(order),
            reply_markup=order_detail_keyboard(
                order_id,
                order.get("location_lat"),
                order.get("location_lon")
            )
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"admin_order_detail: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


# ============================================================
# OLIB KELINDI
# ============================================================

@router.callback_query(F.data.startswith("ad_pickup_"))
async def admin_pickup_start(callback: CallbackQuery, state: FSMContext, role=None):
    if not is_admin(role):
        return
    try:
        order_id = int(callback.data.split("_")[-1])
        await state.update_data(order_id=order_id)
        await state.set_state(AdminPickupStates.waiting_client_note)
        await callback.message.answer(
            "📝 Mijozning laqabini/xususiyatini kiriting:\n"
            "Masalan: Yanga, savrak qishlogi, 5-qavat sariq eshik..."
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"admin_pickup_start: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


@router.message(AdminPickupStates.waiting_client_note, F.text)
async def admin_pickup_note(message: Message, state: FSMContext, role=None):
    if not is_admin(role):
        return
    await state.update_data(client_note=message.text.strip())
    await state.set_state(AdminPickupStates.waiting_carpet_count)
    await message.answer("🪣 Nechta gilam olib kelindi?")


@router.message(AdminPickupStates.waiting_carpet_count, F.text)
async def admin_pickup_count(message: Message, state: FSMContext,
                              role=None, workshop=None, user=None):
    if not is_admin(role):
        return
    try:
        if not message.text.isdigit() or int(message.text) <= 0:
            await message.answer("⚠️ To'g'ri son kiriting (masalan: 3).")
            return
        data         = await state.get_data()
        carpet_count = int(message.text)

        # Avval pickup qilamiz
        await pickup_order(
            data["order_id"],
            carpet_count,
            data["client_note"],
            workshop["id"]
        )

        await state.update_data(carpet_count=carpet_count)
        await state.clear()

        # Shoshilinchmi yoki yo'q — so'raymiz
        from keyboards.admin import urgent_keyboard
        await message.answer(
            f"✅ <b>{carpet_count} ta gilam</b> qo'shildi.\n"
            f"📝 Laqab: <b>{data['client_note']}</b>\n\n"
            f"Bu buyurtma shoshilinchmi?",
            reply_markup=urgent_keyboard(data["order_id"])
        )
        await save_log(
            user["tg_id"], "admin_pickup",
            f"order={data['order_id']} count={carpet_count}",
            workshop["id"]
        )
    except Exception as e:
        logger.error(f"admin_pickup_count: {e}")
        await message.answer("⚠️ Xatolik.")
        await state.clear()


@router.callback_query(F.data.startswith("ad_urgent_yes_"))
async def admin_urgent_yes(callback: CallbackQuery, role=None):
    if not is_admin(role):
        return
    try:
        order_id = int(callback.data.split("_")[-1])
        await set_order_urgent(order_id, True)
        await callback.message.edit_text(
            "🚨 <b>Shoshilinch</b> deb belgilandi!\n"
            "Bu buyurtma ishchilar ro'yxatida birinchi turadi.",
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"admin_urgent_yes: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)
@router.callback_query(F.data.startswith("ad_urgent_no_"))
async def admin_urgent_no(callback: CallbackQuery, role=None):
    if not is_admin(role):
        return
    try:
        order_id = int(callback.data.split("_")[-1])
        await set_order_urgent(order_id, False)
        await callback.message.edit_text(
            "📋 Oddiy navbatga qo'shildi.",
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"admin_urgent_no: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)

# ============================================================
# BARCHA GILAMLAR
# ============================================================

@router.message(F.text == "🪣 Barcha gilamlar")
async def admin_carpets_menu(message: Message, role=None):
    if not is_admin(role):
        return
    await message.answer(
        "Qaysi gilamlarni ko'rmoqchisiz?",
        reply_markup=admin_carpet_filter_menu()
    )


@router.message(F.text == "🔙 Orqaga")
async def admin_go_back(message: Message, role=None):
    if not is_admin(role):
        return
    await message.answer("Bosh menyu:", reply_markup=admin_main_menu())


@router.message(F.text == "✨ Yetkazilishi kerak")
async def admin_washed(message: Message, role=None, workshop=None):
    if not is_admin(role):
        return
    try:
        orders = await get_washed_orders(workshop["id"])
        if not orders:
            await message.answer("📭 Yetkazilishi kerak bo'lgan xonadon yo'q.")
            return
        for order in orders:
            await message.answer(
                format_washed_order_for_delivery(order),
                reply_markup=deliver_keyboard(
                    order["order_id"],
                    order.get("location_lat"),
                    order.get("location_lon")
                )
            )
    except Exception as e:
        logger.error(f"admin_washed: {e}")
        await message.answer("⚠️ Xatolik.")


@router.message(F.text == "🧺 Jarayondagi")
async def admin_inprogress(message: Message, state: FSMContext,
                            role=None, workshop=None):
    if not is_admin(role):
        return
    await _show_inprogress(message, state, workshop, page=0)


async def _show_inprogress(message: Message, state: FSMContext,
                            workshop: dict, page: int):
    try:
        limit = 10
        orders = await get_inprogress_orders(
            workshop["id"], offset=page * limit, limit=limit
        )
        total = await get_inprogress_orders_count(workshop["id"])
        if not orders:
            await message.answer("📭 Jarayondagi xonadon yo'q.")
            return
        text = (
            f"🧺 <b>Jarayondagi xonadonlar</b> "
            f"({page*limit+1}–{min((page+1)*limit, total)}/{total}):\n\n"
        )
        for i, o in enumerate(orders, start=page * limit + 1):
            workers = ", ".join(o.get("worker_names") or []) or "Bron qilinmagan"
            text += (
                f"<b>{i}.</b> #{o['order_id']} · "
                f"{o.get('client_note') or '—'}\n"
                f"👤 {o.get('user_name') or '—'} · "
                f"🪣 {o['carpet_count']} ta\n"
                f"📅 {str(o.get('picked_up_at', ''))[:10]}\n"
                f"👷 {workers}\n"
                f"─────────\n"
            )
        await message.answer(
            text,
            reply_markup=inprogress_pagination(page, total, limit)
        )
        await state.update_data(inp_page=page)
    except Exception as e:
        logger.error(f"_show_inprogress: {e}")
        await message.answer("⚠️ Xatolik.")


@router.callback_query(F.data.startswith("ad_inp_page_"))
async def admin_inprogress_page(callback: CallbackQuery,
                                 state: FSMContext, workshop=None):
    try:
        page = int(callback.data.split("_")[-1])
        await callback.message.delete()
        await _show_inprogress(callback.message, state, workshop, page)
        await callback.answer()
    except Exception as e:
        logger.error(f"admin_inprogress_page: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


@router.message(F.text == "📋 Barcha gilamlar")
async def admin_all_orders(message: Message, state: FSMContext,
                            role=None, workshop=None):
    if not is_admin(role):
        return
    await _show_all_orders(message, state, workshop, page=0)


async def _show_all_orders(message: Message, state: FSMContext,
                             workshop: dict, page: int):
    try:
        limit = 5
        orders = await get_all_orders_by_workshop(
            workshop["id"], offset=page * limit, limit=limit
        )
        total = await get_all_orders_count(workshop["id"])
        if not orders:
            await message.answer("📭 Gilamlar yo'q.")
            return
        text = (
            f"📋 <b>Barcha xonadonlar</b> "
            f"({page*limit+1}–{min((page+1)*limit, total)}/{total}):\n\n"
        )
        for o in orders:
            workers   = o.get("worker_names") or "Bron qilinmagan"
            date      = str(o.get("picked_up_at") or "")[:10]
            inp       = o.get("in_progress_count", 0)
            booked    = o.get("booked_count", 0)
            washed    = o.get("washed_count", 0)
            delivered = o.get("delivered_count", 0)
            total_c   = o.get("carpet_count", 0)
            if delivered == total_c and total_c > 0:
                status = "📦 Yetkazilgan"
            elif washed > 0:
                status = "✨ Yuvilgan"
            elif booked > 0:
                status = "🔒 Bron"
            else:
                status = "🧺 Jarayonda"
            text += (
                f"🏠 <b>#{o['order_id']}</b>"
                f"{' · ' + o['client_note'] if o.get('client_note') else ''}\n"
                f"👤 {o.get('user_name') or '—'}\n"
                f"🪣 {total_c} ta · {status}\n"
                f"👷 {workers}\n"
                f"📅 {date}\n"
            )
            if o.get("extra_note"):
                text += f"📝 {o['extra_note']}\n"
            text += "─────────\n"
        await message.answer(
            text,
            reply_markup=pagination_keyboard(page, total, limit, "ad_all_page")
        )
    except Exception as e:
        logger.error(f"_show_all_orders: {e}")
        await message.answer("⚠️ Xatolik.")


@router.callback_query(F.data.startswith("ad_all_page_"))
async def admin_all_page(callback: CallbackQuery, state: FSMContext, workshop=None):
    try:
        page = int(callback.data.split("_")[-1])
        await callback.message.delete()
        await _show_all_orders(callback.message, state, workshop, page)
        await callback.answer()
    except Exception as e:
        logger.error(f"admin_all_page: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


# ============================================================
# YETKAZILDI VA TO'LOV
# ============================================================

@router.callback_query(F.data.startswith("ad_deliver_"))
async def admin_deliver(callback: CallbackQuery, state: FSMContext,
                         role=None, workshop=None):
    if not is_admin(role):
        return
    try:
        order_id = int(callback.data.split("_")[-1])
        total_amount = await deliver_order_carpets(order_id)
        order = await get_order_by_id(order_id)
        client_note = order.get("client_note") or "—"
        await state.update_data(order_id=order_id, total_amount=total_amount)
        await state.set_state(AdminPaymentStates.waiting_amount)
        await callback.message.answer(
            f"📦 Yetkazildi!\n"
            f"📝 Mijoz: <b>{client_note}</b>\n"
            f"💰 To'lanishi kerak: <b>{fmt_money(total_amount)}</b>\n\n"
            f"Mijozdan qancha pul olindi? (so'mda):"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"admin_deliver: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


@router.message(AdminPaymentStates.waiting_amount, F.text)
async def admin_payment_amount(message: Message, state: FSMContext,
                                role=None, user=None, workshop=None):
    if not is_admin(role):
        return
    try:
        amount = float(message.text.replace(",", "").replace(" ", ""))
    except ValueError:
        await message.answer("⚠️ To'g'ri miqdor kiriting.")
        return
    try:
        data = await state.get_data()
        order_id = data["order_id"]
        total_amount = data["total_amount"]
        await add_client_payment(order_id, amount, "Yetkazib berganda", user["id"])
        if should_add_debt(total_amount, amount):
            debt = total_amount - amount
            await state.update_data(order_id=order_id)
            await state.set_state(AdminPaymentStates.waiting_debt_note)
            await message.answer(
                f"⚠️ Qarz: <b>{fmt_money(debt)}</b>\n\n"
                f"Muddat bering (masalan: 3 kun ichida):"
            )
        else:
            await state.clear()
            await message.answer(
                "✅ To'lov qabul qilindi!",
                reply_markup=admin_main_menu()
            )
        await save_log(
            user["tg_id"], "admin_payment",
            f"order={order_id} amount={amount}",
            workshop["id"]
        )
    except Exception as e:
        logger.error(f"admin_payment_amount: {e}")
        await message.answer("⚠️ Xatolik.")
        await state.clear()


@router.message(AdminPaymentStates.waiting_debt_note, F.text)
async def admin_debt_note(message: Message, state: FSMContext, role=None):
    if not is_admin(role):
        return
    try:
        data = await state.get_data()
        await set_debt_note(data["order_id"], message.text.strip())
        await state.clear()
        await message.answer(
            "✅ Qarz muddati belgilandi.",
            reply_markup=admin_main_menu()
        )
    except Exception as e:
        logger.error(f"admin_debt_note: {e}")
        await message.answer("⚠️ Xatolik.")
        await state.clear()


# ============================================================
# ISH HAQI SO'ROVLARI
# ============================================================

@router.message(F.text == "💵 Ish haqi so'rovlari")
async def admin_pay_requests(message: Message, role=None, workshop=None):
    if not is_admin(role):
        return
    try:
        payments = await get_requested_payments(workshop["id"])
        if not payments:
            await message.answer("📭 Hozircha so'rovlar yo'q.")
            return
        text = "💵 <b>Ish haqi so'rovlari:</b>\n\n"
        for p in payments:
            text += format_worker_payment(p) + "\n"
        await message.answer(text, reply_markup=pay_request_keyboard(payments))
    except Exception as e:
        logger.error(f"admin_pay_requests: {e}")
        await message.answer("⚠️ Xatolik.")


@router.callback_query(F.data.startswith("ad_pay_approve_"))
async def admin_pay_approve(callback: CallbackQuery, role=None):
    if not is_admin(role):
        return
    try:
        payment_id = int(callback.data.split("_")[-1])
        await approve_worker_payment(payment_id)
        await callback.message.edit_text("✅ Ish haqi tasdiqlandi va to'landi.")
        await callback.answer()
    except Exception as e:
        logger.error(f"admin_pay_approve: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


@router.callback_query(F.data.startswith("ad_pay_reject_"))
async def admin_pay_reject(callback: CallbackQuery, state: FSMContext, role=None):
    if not is_admin(role):
        return
    try:
        payment_id = int(callback.data.split("_")[-1])
        await state.update_data(reject_payment_id=payment_id)
        await state.set_state(AdminRejectStates.waiting_reason)
        await callback.message.answer(
            "❌ Rad etish sababini kiriting:\n"
            "(Gilam qayta yuvilish uchun jarayonga qaytariladi)"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"admin_pay_reject: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


@router.message(AdminRejectStates.waiting_reason, F.text)
async def admin_reject_reason(message: Message, state: FSMContext, role=None):
    if not is_admin(role):
        return
    try:
        data = await state.get_data()
        await reject_worker_payment(
            data["reject_payment_id"],
            message.text.strip()
        )
        await state.clear()
        await message.answer(
            "✅ Rad etildi. Gilam qayta yuvilish uchun jarayonga qaytarildi.",
            reply_markup=admin_main_menu()
        )
    except Exception as e:
        logger.error(f"admin_reject_reason: {e}")
        await message.answer("⚠️ Xatolik.")
        await state.clear()


# ============================================================
# QARZDORLAR
# ============================================================

@router.message(F.text == "💰 Qarzdorlar")
async def admin_debtors(message: Message, state: FSMContext,
                         role=None, workshop=None):
    if not is_admin(role):
        return
    await _show_debtors(message, state, workshop, page=0)


async def _show_debtors(message: Message, state: FSMContext,
                         workshop: dict, page: int):
    try:
        limit = 10
        debtors = await get_debtors(
            workshop["id"], offset=page * limit, limit=limit
        )
        total = await get_debtors_count(workshop["id"])
        if not debtors:
            await message.answer("✅ Qarzdor mijozlar yo'q!")
            return
        text = (
            f"💰 <b>Qarzdorlar</b> "
            f"({page*limit+1}–{min((page+1)*limit, total)}/{total}):\n\n"
        )
        for d in debtors:
            text += format_debtor(d) + "\n"
        await message.answer(
            text,
            reply_markup=debtors_keyboard(debtors, page, total, limit)
        )
    except Exception as e:
        logger.error(f"_show_debtors: {e}")
        await message.answer("⚠️ Xatolik.")


@router.callback_query(F.data.startswith("ad_debt_page_"))
async def admin_debt_page(callback: CallbackQuery, state: FSMContext, workshop=None):
    try:
        page = int(callback.data.split("_")[-1])
        await callback.message.delete()
        await _show_debtors(callback.message, state, workshop, page)
        await callback.answer()
    except Exception as e:
        logger.error(f"admin_debt_page: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


@router.callback_query(F.data.startswith("ad_debt_pay_"))
async def admin_debt_pay(callback: CallbackQuery, state: FSMContext, role=None):
    if not is_admin(role):
        return
    try:
        order_id = int(callback.data.split("_")[-1])
        payment = await get_client_payment(order_id)
        if not payment:
            await callback.answer("To'lov topilmadi.", show_alert=True)
            return
        await state.update_data(
            debt_order_id=order_id,
            debt_total=float(payment["total_amount"])
        )
        await state.set_state(AdminDebtStates.waiting_amount)
        await callback.message.answer(
            f"💸 Qarz: <b>{fmt_money(float(payment['debt_amount']))}</b>\n\n"
            f"Qancha pul olindi?"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"admin_debt_pay: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


@router.message(AdminDebtStates.waiting_amount, F.text)
async def admin_debt_amount(message: Message, state: FSMContext,
                             role=None, user=None):
    if not is_admin(role):
        return
    try:
        amount = float(message.text.replace(",", "").replace(" ", ""))
    except ValueError:
        await message.answer("⚠️ To'g'ri miqdor kiriting.")
        return
    try:
        data = await state.get_data()
        order_id = data["debt_order_id"]
        total = data["debt_total"]
        await add_client_payment(order_id, amount, "Qarz to'lovi", user["id"])
        payment = await get_client_payment(order_id)
        debt = float(payment["debt_amount"])
        if should_add_debt(total, float(payment["paid_amount"])) and debt > 0:
            await state.update_data(debt_order_id=order_id)
            await state.set_state(AdminDebtStates.waiting_debt_note)
            await message.answer(
                f"⚠️ Hali qarz bor: <b>{fmt_money(debt)}</b>\n\n"
                f"Yangi muddat bering:"
            )
        else:
            await state.clear()
            await message.answer(
                "✅ Qarz to'liq uzildi!",
                reply_markup=admin_main_menu()
            )
    except Exception as e:
        logger.error(f"admin_debt_amount: {e}")
        await message.answer("⚠️ Xatolik.")
        await state.clear()


@router.message(AdminDebtStates.waiting_debt_note, F.text)
async def admin_debt_new_note(message: Message, state: FSMContext, role=None):
    if not is_admin(role):
        return
    try:
        data = await state.get_data()
        await set_debt_note(data["debt_order_id"], message.text.strip())
        await state.clear()
        await message.answer(
            "✅ Yangi muddat belgilandi.",
            reply_markup=admin_main_menu()
        )
    except Exception as e:
        logger.error(f"admin_debt_new_note: {e}")
        await message.answer("⚠️ Xatolik.")
        await state.clear()


# ============================================================
# QO'LDA BUYURTMA QO'SHISH
# ============================================================

@router.message(F.text == "➕ Qo'lda qo'shish")
async def admin_manual_start(message: Message, state: FSMContext, role=None):
    if not is_admin(role):
        return
    await state.clear()
    await state.set_state(AdminManualOrderStates.waiting_phone)
    await message.answer(
        "📞 Mijozning telefon raqamini kiriting:\n"
        "Masalan: +998901234567"
    )


@router.message(AdminManualOrderStates.waiting_phone, F.text)
async def admin_manual_phone(message: Message, state: FSMContext, role=None):
    if not is_admin(role):
        return
    phone = message.text.strip()
    if len(phone) < 9:
        await message.answer("⚠️ To'g'ri telefon raqam kiriting.")
        return
    await state.update_data(manual_phone=phone)
    await state.set_state(AdminManualOrderStates.waiting_location)
    await message.answer(
        "📍 Mijozning lokatsiyasini ulashing\n"
        "yoki /skip bosing (lokatsiyasiz davom etish):",
        reply_markup=share_location_keyboard()
    )


@router.message(AdminManualOrderStates.waiting_location, F.location)
async def admin_manual_location(message: Message, state: FSMContext, role=None):
    if not is_admin(role):
        return
    await state.update_data(
        manual_lat=message.location.latitude,
        manual_lon=message.location.longitude
    )
    await state.set_state(AdminManualOrderStates.waiting_pickup_time)
    await message.answer(
        "🕐 Qachon borish kerak?\nMasalan: bugun kechga, ertaga ertalab",
        reply_markup=None
    )


@router.message(AdminManualOrderStates.waiting_location, F.text == "/skip")
async def admin_manual_location_skip(message: Message, state: FSMContext, role=None):
    if not is_admin(role):
        return
    await state.update_data(manual_lat=None, manual_lon=None)
    await state.set_state(AdminManualOrderStates.waiting_pickup_time)
    await message.answer(
        "🕐 Qachon borish kerak?\nMasalan: bugun kechga, ertaga ertalab",
        reply_markup=None
    )


@router.message(AdminManualOrderStates.waiting_pickup_time, F.text)
async def admin_manual_time(message: Message, state: FSMContext, role=None):
    if not is_admin(role):
        return
    await state.update_data(manual_time=message.text.strip())
    await state.set_state(AdminManualOrderStates.waiting_extra_note)
    await message.answer(
        "📝 Qo'shimcha izoh (ixtiyoriy)\n/skip — o'tkazib yuborish"
    )


@router.message(AdminManualOrderStates.waiting_extra_note, F.text == "/skip")
async def admin_manual_note_skip(message: Message, state: FSMContext, role=None):
    if not is_admin(role):
        return
    await state.update_data(manual_note=None)
    await state.set_state(AdminManualOrderStates.waiting_client_note)
    await message.answer(
        "🏷 Mijozning laqabini kiriting:\n"
        "Masalan: Yanga, savrak qishlogi, 5-qavat sariq eshik"
    )


@router.message(AdminManualOrderStates.waiting_extra_note, F.text)
async def admin_manual_note(message: Message, state: FSMContext, role=None):
    if not is_admin(role):
        return
    await state.update_data(manual_note=message.text.strip())
    await state.set_state(AdminManualOrderStates.waiting_client_note)
    await message.answer(
        "🏷 Mijozning laqabini kiriting:\n"
        "Masalan: Yanga, savrak qishlogi, 5-qavat sariq eshik"
    )


@router.message(AdminManualOrderStates.waiting_client_note, F.text)
async def admin_manual_client_note(message: Message, state: FSMContext, role=None):
    if not is_admin(role):
        return
    await state.update_data(manual_client_note=message.text.strip())
    await state.set_state(AdminManualOrderStates.waiting_carpet_count)
    await message.answer("🪣 Nechta gilam olib kelindi?")


@router.message(AdminManualOrderStates.waiting_carpet_count, F.text)
async def admin_manual_carpet_count(message: Message, state: FSMContext,
                                     role=None, workshop=None, user=None):
    if not is_admin(role):
        return
    try:
        if not message.text.isdigit() or int(message.text) <= 0:
            await message.answer("⚠️ To'g'ri son kiriting.")
            return
        data = await state.get_data()
        carpet_count = int(message.text)
        db_user = await get_user_by_tg_id(message.from_user.id)
        expires = generate_expires_at(workshop["confirm_timeout_sec"])
        order = await create_order(
            workshop_id=workshop["id"],
            user_id=db_user["id"],
            phone=data["manual_phone"],
            location_lat=data.get("manual_lat"),
            location_lon=data.get("manual_lon"),
            pickup_time_note=data["manual_time"],
            extra_note=data.get("manual_note"),
            expires_at=expires
        )
        await confirm_order(order["id"])
        await pickup_order(
            order_id=order["id"],
            carpet_count=carpet_count,
            client_note=data.get("manual_client_note", ""),
            workshop_id=workshop["id"]
        )
        await state.clear()
        await message.answer(
            f"✅ Buyurtma qo'lda yaratildi!\n\n"
            f"📋 Buyurtma #{order['id']}\n"
            f"📞 {data['manual_phone']}\n"
            f"🕐 {data['manual_time']}\n"
            f"🏷 {data.get('manual_client_note') or '—'}\n"
            f"🪣 {carpet_count} ta gilam",
            reply_markup=admin_main_menu()
        )
        await save_log(
            user["tg_id"], "admin_manual_order",
            f"order={order['id']} count={carpet_count}",
            workshop["id"]
        )
    except Exception as e:
        logger.error(f"admin_manual_carpet_count: {e}")
        await message.answer(f"⚠️ Xatolik: {e}")
        await state.clear()


# ============================================================
# SETTINGS
# ============================================================

@router.message(F.text == "⚙️ Settings")
async def admin_settings(message: Message, role=None):
    if not is_admin(role):
        return
    await message.answer(
        "⚙️ <b>Settings</b>\n\nNima qilmoqchisiz?",
        reply_markup=admin_settings_full_menu()
    )


# ── Kirim-Chiqim ──────────────────────────────────────────────

@router.message(F.text == "💰 Kirim-Chiqim")
async def finance_menu_handler(message: Message, role=None):
    if not is_admin(role):
        return
    await message.answer(
        "💰 <b>Kirim-Chiqim</b>\n\nNimani ko'rmoqchisiz?",
        reply_markup=finance_menu()
    )


@router.message(F.text == "📈 Kirim")
async def show_income(message: Message, role=None, workshop=None):
    if not is_admin(role):
        return
    await _show_income(message, workshop, "day")


async def _show_income(message: Message, workshop: dict, period: str):
    items = await get_income(workshop["id"], period)
    summary = await get_finance_summary(workshop["id"], period)
    period_names = {
        "day": "Kunlik", "week": "Haftalik",
        "month": "Oylik", "year": "Yillik"
    }
    pname = period_names.get(period, "Kunlik")
    text = (
        f"📈 <b>{pname} kirimlar</b>\n\n"
        f"💰 Jami: <b>{int(summary['income']):,} so'm</b>\n"
        f"─────────────\n"
    )
    if items:
        for item in items[:20]:
            client = item.get("client_note") or item.get("client_name") or "—"
            dt = str(item["created_at"])[:16].replace("T", " ")
            text += (
                f"👤 {client}\n"
                f"💵 {int(float(item['amount'])):,} so'm"
                f"{' · ' + item['note'] if item.get('note') else ''}\n"
                f"📅 {dt}\n\n"
            )
    else:
        text += "📭 Bu davrda kirim yo'q"
    await message.answer(text, reply_markup=period_keyboard(), parse_mode="HTML")


@router.message(F.text == "📉 Chiqim")
async def show_expenses_handler(message: Message, role=None, workshop=None):
    if not is_admin(role):
        return
    await _show_expenses(message, workshop, "day")


async def _show_expenses(message: Message, workshop: dict, period: str):
    items = await get_expenses(workshop["id"], period)
    summary = await get_finance_summary(workshop["id"], period)
    period_names = {
        "day": "Kunlik", "week": "Haftalik",
        "month": "Oylik", "year": "Yillik"
    }
    pname = period_names.get(period, "Kunlik")
    by_cat: dict = {}
    for item in items:
        cat = item["category"]
        if cat not in by_cat:
            by_cat[cat] = {"total": 0, "items": []}
        by_cat[cat]["total"] += float(item["amount"])
        by_cat[cat]["items"].append(item)
    text = (
        f"📉 <b>{pname} chiqimlar</b>\n\n"
        f"💸 Jami: <b>{int(summary['expense']):,} so'm</b>\n"
        f"─────────────\n"
    )
    if by_cat:
        for cat, data in by_cat.items():
            text += f"\n<b>{cat}</b> — {int(data['total']):,} so'm\n"
            for item in data["items"][:5]:
                who = item.get("created_by_name") or "—"
                dt = str(item["created_at"])[:16].replace("T", " ")
                note = item.get("note") or ""
                text += (
                    f"  • {int(float(item['amount'])):,} so'm"
                    f"{' · ' + note if note else ''}\n"
                    f"    👤 {who} · 📅 {dt}\n"
                )
    else:
        text += "📭 Bu davrda chiqim yo'q"
    await message.answer(text, reply_markup=period_keyboard(), parse_mode="HTML")


@router.callback_query(F.data.startswith("period_"))
async def period_handler(callback: CallbackQuery, role=None, workshop=None):
    if not is_admin(role):
        return
    period = callback.data.replace("period_", "")
    text = callback.message.text or ""
    await callback.message.delete()
    if "kirim" in text.lower():
        await _show_income(callback.message, workshop, period)
    else:
        await _show_expenses(callback.message, workshop, period)
    await callback.answer()


# ── Xarajat qo'shish ──────────────────────────────────────────

@router.message(F.text == "➕ Xarajat qo'shish")
async def add_expense_start(message: Message, state: FSMContext, role=None):
    if not is_admin(role):
        return
    await state.set_state(AdminFinanceStates.waiting_category)
    await message.answer(
        "📦 Xarajat kategoriyasini tanlang:",
        reply_markup=expense_category_keyboard()
    )


@router.callback_query(AdminFinanceStates.waiting_category, F.data.startswith("cat_"))
async def expense_category_chosen(callback: CallbackQuery, state: FSMContext):
    cat_map = {
        "cat_fuel":      "⛽ Yoqilg'i",
        "cat_clean":     "🧴 Tozalash vositasi",
        "cat_repair":    "🔧 Ta'mirlash",
        "cat_transport": "🚗 Transport",
        "cat_utility":   "💡 Kommunal",
        "cat_salary":    "👔 Maosh",
        "cat_other":     "📦 Boshqa",
    }
    cat = cat_map.get(callback.data, "📦 Boshqa")
    await state.update_data(category=cat)
    await state.set_state(AdminFinanceStates.waiting_amount)
    await callback.message.answer(
        f"✅ Kategoriya: <b>{cat}</b>\n\n💵 Miqdorni kiriting (so'mda):",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminFinanceStates.waiting_amount, F.text)
async def expense_amount_input(message: Message, state: FSMContext, role=None):
    if not is_admin(role):
        return
    try:
        amount = float(message.text.replace(",", "").replace(" ", ""))
        if amount <= 0:
            await message.answer("⚠️ Musbat son kiriting.")
            return
        await state.update_data(amount=amount)
        await state.set_state(AdminFinanceStates.waiting_note)
        await message.answer(
            f"💵 Miqdor: <b>{int(amount):,} so'm</b>\n\n"
            f"📝 Izoh kiriting (yoki /skip):",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("⚠️ To'g'ri son kiriting.")


@router.message(AdminFinanceStates.waiting_note, F.text)
async def expense_note_input(message: Message, state: FSMContext,
                              role=None, workshop=None, user=None):
    if not is_admin(role):
        return
    note = None if message.text == "/skip" else message.text.strip()
    data = await state.get_data()
    await add_expense(
        workshop_id=workshop["id"],
        amount=data["amount"],
        category=data["category"],
        note=note,
        created_by=user["id"]
    )
    await state.clear()
    await message.answer(
        f"✅ Xarajat qo'shildi!\n\n"
        f"📦 Kategoriya: {data['category']}\n"
        f"💵 Miqdor: {int(data['amount']):,} so'm\n"
        f"📝 Izoh: {note or '—'}",
        reply_markup=finance_menu(),
        parse_mode="HTML"
    )
    await save_log(
        user["tg_id"], "add_expense",
        f"cat={data['category']} amount={data['amount']}",
        workshop["id"]
    )


# ── Reklama ───────────────────────────────────────────────────

@router.message(F.text == "📢 Reklama")
async def ad_start(message: Message, state: FSMContext, role=None, workshop=None):
    if not is_admin(role):
        return
    users_count = len(await get_workshop_users_tg_ids(workshop["id"]))
    await state.set_state(AdminAdStates.waiting_message)
    await message.answer(
        f"📢 <b>Reklama yuborish</b>\n\n"
        f"👥 Shu sexning mijozlari: <b>{users_count} ta</b>\n\n"
        f"Yubormoqchi bo'lgan xabarni yozing:",
        parse_mode="HTML"
    )


@router.message(AdminAdStates.waiting_message)
async def ad_message_input(message: Message, state: FSMContext,
                            role=None, workshop=None):
    if not is_admin(role):
        return

    # Media turini aniqlaymiz
    media_type = None
    file_id    = None
    caption    = message.caption or ""

    if message.text:
        media_type = "text"
    elif message.photo:
        media_type = "photo"
        file_id    = message.photo[-1].file_id  # eng katta o'lcham
    elif message.video:
        media_type = "video"
        file_id    = message.video.file_id
    elif message.animation:
        media_type = "animation"
        file_id    = message.animation.file_id
    elif message.document:
        media_type = "document"
        file_id    = message.document.file_id
    elif message.sticker:
        media_type = "sticker"
        file_id    = message.sticker.file_id
    elif message.voice:
        media_type = "voice"
        file_id    = message.voice.file_id
    elif message.video_note:
        media_type = "video_note"
        file_id    = message.video_note.file_id
    else:
        await message.answer("⚠️ Bu turdagi xabar qo'llab-quvvatlanmaydi.")
        return

    ad_text = message.text or caption

    await state.update_data(
        ad_text=ad_text,
        ad_media_type=media_type,
        ad_file_id=file_id
    )

    users_count = len(await get_workshop_users_tg_ids(workshop["id"]))
    await state.set_state(AdminAdStates.waiting_confirm)

    # Preview
    preview = f"📝 Matn: {ad_text[:50]}..." if ad_text else ""
    media_labels = {
        "text":       "📝 Matn",
        "photo":      "🖼 Rasm",
        "video":      "🎥 Video",
        "animation":  "🎞 GIF",
        "document":   "📎 Fayl",
        "sticker":    "🎭 Sticker",
        "voice":      "🎤 Ovozli xabar",
        "video_note": "⭕ Video xabar",
    }
    media_label = media_labels.get(media_type, media_type)

    sep = "─" * 20
    await message.answer(
        f"📋 <b>Xabar ko'rinishi:</b>\n\n"
        f"📌 Tur: {media_label}\n"
        f"{preview}\n"
        f"{sep}\n\n"
        f"👥 Yuboriladi: <b>{users_count} ta</b> mijozga\n\n"
        f"Tasdiqlaysizmi?",
        reply_markup=ad_confirm_keyboard(),
        parse_mode="HTML"
    )



@router.callback_query(AdminAdStates.waiting_confirm, F.data == "ad_send_yes")
async def ad_send(callback: CallbackQuery, state: FSMContext,
                   role=None, workshop=None, user=None):
    if not is_admin(role):
        return

    data       = await state.get_data()
    ad_text    = data.get("ad_text", "")
    media_type = data.get("ad_media_type", "text")
    file_id    = data.get("ad_file_id")
    header     = f"📢 <b>{workshop['name']}</b>\n\n"

    tg_ids = await get_workshop_users_tg_ids(workshop["id"])
    await callback.message.edit_text(
        f"⏳ Yuborilmoqda... (0/{len(tg_ids)})"
    )
    await state.clear()

    sent = 0
    failed = 0

    for tg_id in tg_ids:
        try:
            if media_type == "text":
                await callback.bot.send_message(
                    tg_id,
                    header + ad_text,
                    parse_mode="HTML"
                )
            elif media_type == "photo":
                await callback.bot.send_photo(
                    tg_id,
                    photo=file_id,
                    caption=header + ad_text,
                    parse_mode="HTML"
                )
            elif media_type == "video":
                await callback.bot.send_video(
                    tg_id,
                    video=file_id,
                    caption=header + ad_text,
                    parse_mode="HTML"
                )
            elif media_type == "animation":
                await callback.bot.send_animation(
                    tg_id,
                    animation=file_id,
                    caption=header + ad_text,
                    parse_mode="HTML"
                )
            elif media_type == "document":
                await callback.bot.send_document(
                    tg_id,
                    document=file_id,
                    caption=header + ad_text,
                    parse_mode="HTML"
                )
            elif media_type == "sticker":
                # Sticker uchun avval xabar, keyin sticker
                if ad_text:
                    await callback.bot.send_message(
                        tg_id, header + ad_text, parse_mode="HTML"
                    )
                await callback.bot.send_sticker(tg_id, sticker=file_id)
            elif media_type == "voice":
                await callback.bot.send_voice(
                    tg_id,
                    voice=file_id,
                    caption=header + ad_text,
                    parse_mode="HTML"
                )
            elif media_type == "video_note":
                if ad_text:
                    await callback.bot.send_message(
                        tg_id, header + ad_text, parse_mode="HTML"
                    )
                await callback.bot.send_video_note(tg_id, video_note=file_id)
            sent += 1
        except Exception as e:
            logger.error(f"ad_send [{tg_id}]: {e}")
            failed += 1

    await save_ad_log(
        workshop_id=workshop["id"],
        sent_by=user["id"],
        message=f"[{media_type}] {ad_text[:100]}",
        sent_count=sent,
        media_type=media_type
    )

    await callback.message.answer(
        f"✅ <b>Reklama yuborildi!</b>\n\n"
        f"📨 Yuborildi: {sent} ta\n"
        f"❌ Yetmadi: {failed} ta",
        reply_markup=admin_settings_full_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(AdminAdStates.waiting_confirm, F.data == "ad_send_no")
async def ad_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Reklama bekor qilindi.")
    await callback.answer()


# ── Settings Ko'rish ──────────────────────────────────────────

@router.message(F.text == "👁 Ko'rish")
async def admin_settings_view(message: Message, role=None, workshop=None):
    if not is_admin(role):
        return
    try:
        ws = await get_workshop_by_id(workshop["id"])
        admins = await get_workshop_admins(workshop["id"])
        workers = await get_workshop_workers(workshop["id"])
        aw = await get_workshop_members(workshop["id"], "admin_worker")
        text = (
            f"🏭 <b>{ws['name']}</b>\n\n"
            f"💰 Gilam narxi: <b>{fmt_money(ws['price_per_m2'])}/m²</b>\n"
            f"💵 Default ishchi haqi: <b>{fmt_money(ws['default_worker_price'])}/m²</b>\n\n"
        )
        if admins:
            text += "👤 <b>Adminlar:</b>\n"
            for a in admins:
                text += f"  • {a.get('full_name') or '—'} ({a['tg_id']})\n"
        if workers:
            text += "\n👷 <b>Ishchilar:</b>\n"
            for w in workers:
                price = w.get("effective_price") or ws["default_worker_price"]
                text += f"  • {w.get('full_name') or '—'} — {fmt_money(price)}/m²\n"
        if aw:
            text += "\n👤👷 <b>Admin+Ishchi:</b>\n"
            for m in aw:
                text += f"  • {m.get('full_name') or '—'} ({m['tg_id']})\n"
        await message.answer(text)
    except Exception as e:
        logger.error(f"admin_settings_view: {e}")
        await message.answer("⚠️ Xatolik.")


# ── Settings Qo'shish ─────────────────────────────────────────

@router.message(F.text == "➕ Qo'shish")
async def admin_settings_add(message: Message, state: FSMContext, role=None):
    if not is_admin(role):
        return
    await message.answer(
        "Nima qo'shmoqchisiz?",
        reply_markup=settings_add_role_keyboard()
    )


@router.callback_query(F.data.startswith("ad_add_"))
async def admin_add_role(callback: CallbackQuery, state: FSMContext, role=None):
    if not is_admin(role):
        return
    try:
        role_map = {
            "ad_add_admin":        "admin",
            "ad_add_worker":       "worker",
            "ad_add_admin_worker": "admin_worker",
        }
        add_role = role_map.get(callback.data)
        if not add_role:
            await callback.answer("Noma'lum rol.", show_alert=True)
            return
        await state.update_data(add_role=add_role)
        await state.set_state(AdminAddMemberStates.waiting_tg_id)
        labels = {"admin": "admin", "worker": "ishchi", "admin_worker": "admin+ishchi"}
        await callback.message.answer(
            f"🆔 Yangi <b>{labels[add_role]}</b> Telegram ID sini kiriting:"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"admin_add_role: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


@router.message(AdminAddMemberStates.waiting_tg_id, F.text)
async def admin_add_tg_id(message: Message, state: FSMContext,
                           role=None, workshop=None):
    if not is_admin(role):
        return
    try:
        tg_id = int(message.text.strip())
        active = await check_user_active_role(tg_id, workshop["id"])
        if active:
            await message.answer(
                f"⚠️ Bu foydalanuvchi <b>{active['workshop_name']}</b> sexida "
                f"<b>{active['role']}</b> sifatida aktiv.\n\n"
                f"U avval o'sha sexdan chiqarilishi kerak."
            )
            await state.clear()
            return
        await state.update_data(member_tg_id=tg_id)
        await state.set_state(AdminAddMemberStates.waiting_name)
        await message.answer(
            f"✅ TG ID: <code>{tg_id}</code>\n\n"
            f"Ism-familiyasini kiriting (yoki /skip):"
        )
    except ValueError:
        await message.answer("⚠️ Faqat raqam kiriting.")
    except Exception as e:
        logger.error(f"admin_add_tg_id: {e}")
        await message.answer("⚠️ Xatolik.")
        await state.clear()


@router.message(AdminAddMemberStates.waiting_name, F.text)
async def admin_add_name(message: Message, state: FSMContext,
                          role=None, workshop=None):
    if not is_admin(role):
        return
    try:
        name = message.text.strip()
        if name.lower() in ("yo'q", "yoq", "no", "n"):
            await state.clear()
            await message.answer(
                "❌ Bekor qilindi.",
                reply_markup=admin_settings_full_menu()
            )
            return
        data = await state.get_data()
        tg_id = data["member_tg_id"]
        add_role = data["add_role"]
        full_name = None if name == "/skip" else name
        worker_price = (
            workshop["default_worker_price"]
            if add_role in ("worker", "admin_worker") else None
        )
        await add_or_reactivate_member(
            tg_id=tg_id,
            full_name=full_name or f"User {tg_id}",
            workshop_id=workshop["id"],
            role=add_role,
            worker_price=worker_price
        )
        labels = {"admin": "Admin", "worker": "Ishchi", "admin_worker": "Admin+Ishchi"}
        old_ws = data.get("old_workshop_name")
        extra = f"\n⬅️ Oldingi sex: {old_ws}" if old_ws else ""
        await state.clear()
        await message.answer(
            f"✅ <b>{labels.get(add_role, add_role)}</b> qo'shildi!\n"
            f"🆔 TG ID: <code>{tg_id}</code>{extra}",
            reply_markup=admin_settings_full_menu()
        )
        await save_log(tg_id, "admin_add_member",
                      f"role={add_role}", workshop["id"])
    except Exception as e:
        logger.error(f"admin_add_name: {e}")
        await message.answer("⚠️ Xatolik.")
        await state.clear()


# ── Settings O'chirish ────────────────────────────────────────

@router.message(F.text == "🗑 O'chirish")
async def admin_settings_del(message: Message, state: FSMContext,
                              role=None, workshop=None):
    if not is_admin(role):
        return
    try:
        members = await get_workshop_members(workshop["id"])
        me = await get_user_by_tg_id(message.from_user.id)
        my_id = me["id"] if me else None
        others = [m for m in members if m["id"] != my_id]
        if not others:
            await message.answer("O'chirish uchun boshqa a'zolar yo'q.")
            return
        await message.answer(
            "Kimni o'chirmoqchisiz?",
            reply_markup=members_list_keyboard(others, "ad_del_member")
        )
    except Exception as e:
        logger.error(f"admin_settings_del: {e}")
        await message.answer("⚠️ Xatolik.")


@router.callback_query(F.data.startswith("ad_del_member_"))
async def admin_del_member_confirm(callback: CallbackQuery, state: FSMContext,
                                    role=None):
    if not is_admin(role):
        return
    try:
        raw = callback.data.replace("ad_del_member_", "")
        user_id = int(raw.split("x")[0])
        await state.update_data(del_user_id=user_id)
        await callback.message.answer(
            "O'chirishni tasdiqlaysizmi?",
            reply_markup=confirm_keyboard(f"ad_del_ok_{user_id}")
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"admin_del_member_confirm: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


@router.callback_query(F.data.startswith("ad_del_ok_"))
async def admin_del_member_execute(callback: CallbackQuery,
                                    role=None, workshop=None):
    if not is_admin(role):
        return
    try:
        user_id = int(callback.data.replace("ad_del_ok_", ""))
        await deactivate_user_in_workshop(user_id, workshop["id"])
        await callback.message.edit_text("✅ A'zo bloklandi.")
        await callback.answer()
    except Exception as e:
        logger.error(f"admin_del_member_execute: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


# ── Settings O'zgartirish ─────────────────────────────────────

@router.message(F.text == "⚙️ O'zgartirish")
async def admin_settings_edit(message: Message, role=None):
    if not is_admin(role):
        return
    await message.answer(
        "Nimani o'zgartirmoqchisiz?",
        reply_markup=settings_edit_keyboard()
    )


@router.callback_query(F.data == "ad_edit_cprice")
async def admin_edit_cprice(callback: CallbackQuery,
                             state: FSMContext, role=None, workshop=None):
    if not is_admin(role):
        return
    ws = await get_workshop_by_id(workshop["id"])
    await state.set_state(AdminSettingsStates.waiting_price)
    await callback.message.answer(
        f"💰 Hozirgi narx: <b>{fmt_money(ws['price_per_m2'])}/m²</b>\n\n"
        f"Yangi narxni kiriting:"
    )
    await callback.answer()


@router.message(AdminSettingsStates.waiting_price, F.text)
async def admin_set_cprice(message: Message, state: FSMContext,
                            role=None, workshop=None):
    if not is_admin(role):
        return
    try:
        price = float(message.text.replace(",", "").replace(" ", ""))
        if price <= 0:
            await message.answer("⚠️ Narx musbat bo'lishi kerak.")
            return
        await update_workshop_client_price(workshop["id"], price)
        await state.clear()
        await message.answer(
            f"✅ Gilam narxi yangilandi: <b>{fmt_money(price)}/m²</b>",
            reply_markup=admin_settings_full_menu()
        )
    except ValueError:
        await message.answer("⚠️ To'g'ri narx kiriting.")
    except Exception as e:
        logger.error(f"admin_set_cprice: {e}")
        await message.answer("⚠️ Xatolik.")
        await state.clear()


@router.callback_query(F.data == "ad_edit_wprice")
async def admin_edit_wprice(callback: CallbackQuery, role=None):
    if not is_admin(role):
        return
    await callback.message.answer(
        "Qaysi ishchi narxini o'zgartirmoqchisiz?",
        reply_markup=settings_worker_price_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "ad_wprice_all")
async def admin_wprice_all(callback: CallbackQuery,
                            state: FSMContext, role=None, workshop=None):
    if not is_admin(role):
        return
    ws = await get_workshop_by_id(workshop["id"])
    await state.set_state(AdminSettingsStates.waiting_worker_price)
    await callback.message.answer(
        f"💵 Hozirgi default narx: <b>{fmt_money(ws['default_worker_price'])}/m²</b>\n\n"
        f"Yangi narxni kiriting (barcha ishchilarga):"
    )
    await callback.answer()


@router.message(AdminSettingsStates.waiting_worker_price, F.text)
async def admin_set_wprice_all(message: Message, state: FSMContext,
                                role=None, workshop=None):
    if not is_admin(role):
        return
    try:
        price = float(message.text.replace(",", "").replace(" ", ""))
        if price <= 0:
            await message.answer("⚠️ Narx musbat bo'lishi kerak.")
            return
        await update_workshop_default_worker_price(workshop["id"], price)
        await state.clear()
        await message.answer(
            f"✅ Barcha ishchilar narxi yangilandi: <b>{fmt_money(price)}/m²</b>",
            reply_markup=admin_settings_full_menu()
        )
    except ValueError:
        await message.answer("⚠️ To'g'ri narx kiriting.")
    except Exception as e:
        logger.error(f"admin_set_wprice_all: {e}")
        await message.answer("⚠️ Xatolik.")
        await state.clear()


@router.callback_query(F.data == "ad_wprice_one")
async def admin_wprice_one(callback: CallbackQuery,
                            state: FSMContext, role=None, workshop=None):
    if not is_admin(role):
        return
    workers = await get_workshop_workers(workshop["id"])
    if not workers:
        await callback.answer("Ishchilar yo'q.", show_alert=True)
        return
    await callback.message.answer(
        "Qaysi ishchini tanlaysiz?",
        reply_markup=workers_list_keyboard(workers, "ad_worker_sel")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ad_worker_sel_"))
async def admin_worker_selected(callback: CallbackQuery,
                                 state: FSMContext, role=None, workshop=None):
    if not is_admin(role):
        return
    try:
        user_id = int(callback.data.split("_")[-1])
        ws = await get_workshop_by_id(workshop["id"])
        await state.update_data(target_worker_id=user_id)
        await state.set_state(AdminSettingsStates.waiting_individual_price)
        await callback.message.answer(
            f"💵 Hozirgi narx: <b>{fmt_money(ws['default_worker_price'])}/m²</b>\n\n"
            f"Yangi narxni kiriting:"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"admin_worker_selected: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


@router.message(AdminSettingsStates.waiting_individual_price, F.text)
async def admin_set_individual_price(message: Message, state: FSMContext,
                                      role=None, workshop=None):
    if not is_admin(role):
        return
    try:
        price = float(message.text.replace(",", "").replace(" ", ""))
        if price <= 0:
            await message.answer("⚠️ Narx musbat bo'lishi kerak.")
            return
        data = await state.get_data()
        await update_worker_price(data["target_worker_id"], workshop["id"], price)
        await state.clear()
        await message.answer(
            f"✅ Ishchi narxi yangilandi: <b>{fmt_money(price)}/m²</b>",
            reply_markup=admin_settings_full_menu()
        )
    except ValueError:
        await message.answer("⚠️ To'g'ri narx kiriting.")
    except Exception as e:
        logger.error(f"admin_set_individual_price: {e}")
        await message.answer("⚠️ Xatolik.")
        await state.clear()


@router.callback_query(F.data == "ad_edit_pass")
async def admin_edit_pass(callback: CallbackQuery,
                           state: FSMContext, role=None):
    if not is_admin(role):
        return
    await state.set_state(AdminSettingsStates.waiting_new_password)
    await callback.message.answer("🔑 Yangi parolni kiriting (kamida 4 belgi):")
    await callback.answer()


@router.message(AdminSettingsStates.waiting_new_password, F.text)
async def admin_set_password(message: Message, state: FSMContext,
                              role=None, workshop=None):
    if not is_admin(role):
        return
    try:
        password = message.text.strip()
        if len(password) < 4:
            await message.answer("⚠️ Parol kamida 4 ta belgi bo'lishi kerak.")
            return
        await update_workshop_password(workshop["id"], hash_password(password))
        await state.clear()
        await message.answer(
            "✅ Parol yangilandi!",
            reply_markup=admin_settings_full_menu()
        )
    except Exception as e:
        logger.error(f"admin_set_password: {e}")
        await message.answer("⚠️ Xatolik.")
        await state.clear()


# ── Settings Token ────────────────────────────────────────────

@router.message(F.text == "🔗 Token havola")
async def admin_token(message: Message, role=None, workshop=None):
    if not is_admin(role):
        return
    try:
        bot_info = await message.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={workshop['token']}"
        await message.answer(
            f"🔗 <b>Mijozlar havolasi:</b>\n\n"
            f"<code>{link}</code>\n\n"
            f"Bu havolani mijozlarga yuboring.\n"
            f"Havola orqali kirgan mijozlar faqat "
            f"<b>{workshop['name']}</b> sexiga bog'lanadi."
        )
    except Exception as e:
        logger.error(f"admin_token: {e}")
        await message.answer("⚠️ Xatolik.")


# ── Bekor qilish ──────────────────────────────────────────────

@router.callback_query(F.data == "ad_cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi.")
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop_cb(callback: CallbackQuery):
    await callback.answer()