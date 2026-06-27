# handlers/super_admin.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart

from config import settings
from states.states import (
    SAWorkshopStates, SAMemberStates,
    SAPriceStates, SAPasswordStates
)
from keyboards.super_admin import (
    sa_main_menu, sa_workshops_keyboard,
    sa_workshop_actions, sa_add_role_keyboard,
    sa_edit_actions, sa_worker_price_keyboard,
    sa_members_keyboard, sa_confirm_keyboard
)
from db.queries import (
    get_all_workshops, get_workshop_by_id,
    create_workshop, update_workshop_client_price,
    update_workshop_default_worker_price,
    update_worker_price, update_workshop_password,
    toggle_workshop, get_workshop_admins,
    get_workshop_workers, get_workshop_members,
    get_user_by_tg_id, create_user,
    add_user_to_workshop, deactivate_user_in_workshop,
    check_user_role_exists, save_log,
    check_user_active_role, add_or_reactivate_member
)
from utils.helpers import hash_password, fmt_money
from utils.logger import logger

router = Router()
SA = settings.SUPER_ADMIN_TG_ID


# ============================================================
# START
# ============================================================

# handlers/super_admin.py — faqat START qismini ko'rsataman
# Qolgan qismi o'zgarishsiz





# ============================================================
# SEXLAR RO'YXATI
# ============================================================

@router.message(F.text == "🏭 Sexlar", F.from_user.id == SA)
async def sa_workshops(message: Message):
    try:
        workshops = await get_all_workshops()
        if not workshops:
            await message.answer(
                "📭 Hozircha sexlar yo'q.\n"
                "➕ Sex qo'shish tugmasini bosing."
            )
            return
        await message.answer(
            f"🏭 <b>Jami: {len(workshops)} ta sex</b>\n"
            f"Boshqarish uchun tanlang:",
            reply_markup=sa_workshops_keyboard(workshops)
        )
    except Exception as e:
        logger.error(f"sa_workshops: {e}")
        await message.answer("⚠️ Xatolik yuz berdi.")


# ============================================================
# SEX TANLASH → AMALLAR
# ============================================================

@router.callback_query(F.data.startswith("sa_ws_"), F.from_user.id == SA)
async def sa_workshop_selected(callback: CallbackQuery, state: FSMContext):
    try:
        workshop_id = int(callback.data.split("_")[-1])
        ws = await get_workshop_by_id(workshop_id)
        if not ws:
            await callback.answer("Sex topilmadi.", show_alert=True)
            return
        await state.update_data(workshop_id=workshop_id)
        status = "✅ Faol" if ws["is_active"] else "❌ Faol emas"
        await callback.message.answer(
            f"🏭 <b>{ws['name']}</b>\n"
            f"📊 {status}\n\n"
            f"Nima qilmoqchisiz?",
            reply_markup=sa_workshop_actions(workshop_id)
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"sa_workshop_selected: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


# ============================================================
# KO'RISH
# ============================================================

@router.callback_query(F.data.startswith("sa_view_"), F.from_user.id == SA)
async def sa_view_workshop(callback: CallbackQuery):
    try:
        workshop_id = int(callback.data.split("_")[-1])
        ws      = await get_workshop_by_id(workshop_id)
        admins  = await get_workshop_admins(workshop_id)
        workers = await get_workshop_workers(workshop_id)
        members = await get_workshop_members(workshop_id, "admin_worker")

        text = (
            f"🏭 <b>{ws['name']}</b>\n\n"
            f"📊 Holat: {'✅ Faol' if ws['is_active'] else '❌ Faol emas'}\n"
            f"💰 Gilam narxi: <b>{fmt_money(ws['price_per_m2'])}/m²</b>\n"
            f"💵 Ishchi haqi (default): <b>{fmt_money(ws['default_worker_price'])}/m²</b>\n\n"
        )
        if admins:
            text += "👤 <b>Adminlar:</b>\n"
            for a in admins:
                text += f"  • {a.get('full_name') or '—'} (ID: {a['tg_id']})\n"
        else:
            text += "👤 Adminlar: yo'q\n"

        if workers:
            text += "\n👷 <b>Ishchilar:</b>\n"
            for w in workers:
                price = w.get("effective_price") or ws["default_worker_price"]
                text += (
                    f"  • {w.get('full_name') or '—'} "
                    f"(ID: {w['tg_id']}) — {fmt_money(price)}/m²\n"
                )
        else:
            text += "\n👷 Ishchilar: yo'q\n"

        if members:
            text += "\n👤👷 <b>Admin+Worker:</b>\n"
            for m in members:
                text += f"  • {m.get('full_name') or '—'} (ID: {m['tg_id']})\n"

        await callback.message.answer(text)
        await callback.answer()
    except Exception as e:
        logger.error(f"sa_view_workshop: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


# ============================================================
# QO'SHISH
# ============================================================

@router.callback_query(F.data.startswith("sa_add_"), F.from_user.id == SA)
async def sa_add_menu(callback: CallbackQuery, state: FSMContext):
    try:
        parts = callback.data.split("_")
        # sa_add_{workshop_id} — menyu
        if len(parts) == 3 and parts[2].isdigit():
            workshop_id = int(parts[2])
            await state.update_data(workshop_id=workshop_id)
            await callback.message.answer(
                "Nima qo'shmoqchisiz?",
                reply_markup=sa_add_role_keyboard(workshop_id)
            )
            await callback.answer()
            return

        # sa_add_admin_{id}, sa_add_worker_{id}, sa_add_admin_worker_{id}
        workshop_id = int(parts[-1])
        role_map = {
            "admin":        "admin",
            "worker":       "worker",
            "adminworker": "admin_worker",
        }
        role_key = "".join(parts[2:-1])
        role = role_map.get(role_key)
        if not role:
            await callback.answer("Noma'lum rol.", show_alert=True)
            return

        await state.update_data(workshop_id=workshop_id, add_role=role)
        await state.set_state(SAMemberStates.waiting_tg_id)
        role_labels = {
            "admin":        "admin",
            "worker":       "ishchi",
            "admin_worker": "admin+ishchi"
        }
        await callback.message.answer(
            f"👤 Yangi <b>{role_labels[role]}</b> Telegram ID sini kiriting:\n\n"
            f"(U avval botga /start bosgan bo'lishi kerak)"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"sa_add_menu: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)
        
        
        

@router.message(SAMemberStates.waiting_tg_id, F.from_user.id == SA)
async def sa_member_tg_id(message: Message, state: FSMContext):
    try:
        tg_id = int(message.text.strip())
        data  = await state.get_data()
        workshop_id = data["workshop_id"]

        # Faqat BOSHQA sexda aktiv tekshirish
        active = await check_user_active_role(tg_id, workshop_id)
        if active:
            await message.answer(
                f"⚠️ Bu foydalanuvchi <b>{active['workshop_name']}</b> "
                f"sexida <b>{active['role']}</b> sifatida aktiv.\n\n"
                f"U avval o'sha sexdan chiqarilishi kerak."
            )
            await state.clear()
            return

        # DB da bor-yo'qligidan qat'iy nazar qo'shamiz
        await state.update_data(member_tg_id=tg_id)
        await state.set_state(SAMemberStates.waiting_name)
        await message.answer(
            f"✅ TG ID: <code>{tg_id}</code>\n\n"
            f"Ism-familiyasini kiriting\n"
            f"(yoki /skip):"
        )
    except ValueError:
        await message.answer("⚠️ Faqat raqam kiriting.")
    except Exception as e:
        logger.error(f"sa_member_tg_id: {e}")
        await message.answer("⚠️ Xatolik.")
        await state.clear()
        
        
        


@router.message(SAMemberStates.waiting_name, F.from_user.id == SA)
async def sa_member_name(message: Message, state: FSMContext):
    try:
        data        = await state.get_data()
        workshop_id = data["workshop_id"]
        tg_id       = data["member_tg_id"]
        role        = data["add_role"]
        name        = message.text.strip()

        if name.lower() in ("yo'q", "yoq", "no", "n"):
            await state.clear()
            await message.answer(
                "❌ Bekor qilindi.",
                reply_markup=sa_main_menu()
            )
            return

        full_name = None if name == "/skip" else name
        ws = await get_workshop_by_id(workshop_id)
        worker_price = ws["default_worker_price"] if role in ("worker", "admin_worker") else None

        result = await add_or_reactivate_member(
            tg_id=tg_id,
            full_name=full_name or f"User {tg_id}",
            workshop_id=workshop_id,
            role=role,
            worker_price=worker_price
        )

        role_labels = {
            "admin": "Admin", "worker": "Ishchi", "admin_worker": "Admin+Ishchi"
        }
        old_ws = data.get("old_workshop_name")
        extra = f"\n⬅️ Oldingi sex: {old_ws}" if old_ws else ""

        await state.clear()
        await message.answer(
            f"✅ <b>{role_labels.get(role, role)}</b> qo'shildi!\n"
            f"🏭 Sex: {ws['name']}\n"
            f"🆔 TG ID: <code>{tg_id}</code>"
            f"{extra}",
            reply_markup=sa_main_menu()
        )
        await save_log(SA, "sa_add_member",
                      f"ws={workshop_id} role={role} tg={tg_id}")
    except Exception as e:
        logger.error(f"sa_member_name: {e}")
        await message.answer("⚠️ Xatolik.")
        await state.clear()


# ============================================================
# O'CHIRISH
# ============================================================

@router.callback_query(F.data.startswith("sa_del_"), F.from_user.id == SA)
async def sa_del_menu(callback: CallbackQuery, state: FSMContext):
    try:
        workshop_id = int(callback.data.split("_")[-1])
        all_members = await get_workshop_members(workshop_id)
        if not all_members:
            await callback.answer("Bu sexda a'zolar yo'q.", show_alert=True)
            return
        await state.update_data(workshop_id=workshop_id)
        await callback.message.answer(
            "Kimni o'chirmoqchisiz?",
            reply_markup=sa_members_keyboard(
                all_members, "sa_delm", workshop_id
            )
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"sa_del_menu: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)




@router.callback_query(
    F.data.startswith("sa_delm_ok_"),
    F.from_user.id == SA
)
async def sa_del_execute(callback: CallbackQuery, state: FSMContext):
    try:
        raw         = callback.data.replace("sa_delm_ok_", "")
        user_id     = int(raw.split("x")[0])
        workshop_id = int(raw.split("x")[1])
        await deactivate_user_in_workshop(user_id, workshop_id)
        await state.clear()
        await callback.message.edit_text("✅ A'zo bloklandi.")
        await save_log(SA, "sa_del_member",
                      f"user={user_id} ws={workshop_id}")
        await callback.answer()
    except Exception as e:
        logger.error(f"sa_del_execute: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)
        
@router.callback_query(
    F.data.startswith("sa_delm_"),
    F.from_user.id == SA
)
async def sa_del_confirm(callback: CallbackQuery, state: FSMContext):
    try:
        raw         = callback.data.replace("sa_delm_", "")
        user_id     = int(raw.split("x")[0])
        workshop_id = int(raw.split("x")[1])
        await state.update_data(
            del_user_id=user_id,
            del_workshop_id=workshop_id
        )
        await callback.message.answer(
            "O'chirishni tasdiqlaysizmi?",
            reply_markup=sa_confirm_keyboard(
                f"sa_delm_ok_{user_id}x{workshop_id}"
            )
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"sa_del_confirm: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


# ============================================================
# O'ZGARTIRISH
# ============================================================

@router.callback_query(F.data.startswith("sa_edit_"), F.from_user.id == SA)
async def sa_edit_menu(callback: CallbackQuery, state: FSMContext):
    try:
        parts = callback.data.split("_")
        # sa_edit_{workshop_id}
        if len(parts) == 3 and parts[2].isdigit():
            workshop_id = int(parts[2])
            await state.update_data(workshop_id=workshop_id)
            await callback.message.answer(
                "Nimani o'zgartirmoqchisiz?",
                reply_markup=sa_edit_actions(workshop_id)
            )
            await callback.answer()
            return

        action      = parts[2]   # cprice | wprice | pass
        workshop_id = int(parts[3])
        ws = await get_workshop_by_id(workshop_id)
        await state.update_data(workshop_id=workshop_id)

        if action == "cprice":
            await state.set_state(SAPriceStates.waiting_price)
            await callback.message.answer(
                f"💰 Hozirgi gilam yuvish narxi: "
                f"<b>{fmt_money(ws['price_per_m2'])}/m²</b>\n\n"
                f"Yangi narxni kiriting (so'm/m²):"
            )

        elif action == "wprice":
            await callback.message.answer(
                "Qaysi ishchi narxini o'zgartirmoqchisiz?",
                reply_markup=sa_worker_price_keyboard(workshop_id)
            )

        elif action == "pass":
            await state.set_state(SAPasswordStates.waiting_new_password)
            await callback.message.answer("🔑 Yangi parolni kiriting:")

        await callback.answer()
    except Exception as e:
        logger.error(f"sa_edit_menu: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


# Gilam narxi
@router.message(SAPriceStates.waiting_price, F.from_user.id == SA)
async def sa_set_client_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(",", "").replace(" ", ""))
        if price <= 0:
            await message.answer("⚠️ Narx musbat bo'lishi kerak.")
            return
        data = await state.get_data()
        await update_workshop_client_price(data["workshop_id"], price)
        await state.clear()
        await message.answer(
            f"✅ Gilam yuvish narxi yangilandi!\n"
            f"💰 Yangi narx: <b>{fmt_money(price)}/m²</b>",
            reply_markup=sa_main_menu()
        )
        await save_log(SA, "sa_update_price", f"ws={data['workshop_id']} price={price}")
    except ValueError:
        await message.answer("⚠️ To'g'ri narx kiriting (faqat raqam).")
    except Exception as e:
        logger.error(f"sa_set_client_price: {e}")
        await message.answer("⚠️ Xatolik.")
        await state.clear()


# Ishchi narxi — barcha
@router.callback_query(F.data.startswith("sa_wprice_all_"), F.from_user.id == SA)
async def sa_wprice_all(callback: CallbackQuery, state: FSMContext):
    try:
        workshop_id = int(callback.data.split("_")[-1])
        ws = await get_workshop_by_id(workshop_id)
        await state.update_data(workshop_id=workshop_id, wprice_target="all")
        await state.set_state(SAPriceStates.waiting_worker_price)
        await callback.message.answer(
            f"💵 Hozirgi default ishchi narxi: "
            f"<b>{fmt_money(ws['default_worker_price'])}/m²</b>\n\n"
            f"Yangi narxni kiriting (barcha ishchilarga qo'llanadi):"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"sa_wprice_all: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


################## Ishchi narxi — tanlangan
@router.callback_query(F.data.startswith("sa_wprice_one_"), F.from_user.id == SA)
async def sa_wprice_one(callback: CallbackQuery, state: FSMContext):
    try:
        workshop_id = int(callback.data.split("_")[-1])
        workers = await get_workshop_workers(workshop_id)
        if not workers:
            await callback.answer("Ishchilar yo'q.", show_alert=True)
            return
        await state.update_data(workshop_id=workshop_id, wprice_target="one")
        await callback.message.answer(
            "Qaysi ishchining narxini o'zgartirmoqchisiz?",
            reply_markup=sa_members_keyboard(workers, "sa_wprice_worker", workshop_id)
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"sa_wprice_one: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


@router.callback_query(F.data.startswith("sa_wprice_worker_"), F.from_user.id == SA)
async def sa_wprice_worker_selected(callback: CallbackQuery, state: FSMContext):
    try:
        parts       = callback.data.split("_")
        user_id     = int(parts[3])
        workshop_id = int(parts[4])
        ws = await get_workshop_by_id(workshop_id)
        await state.update_data(
            workshop_id=workshop_id,
            target_user_id=user_id,
            wprice_target="one"
        )
        await state.set_state(SAPriceStates.waiting_worker_individual_price)
        await callback.message.answer(
            f"💵 Hozirgi narx: <b>{fmt_money(ws['default_worker_price'])}/m²</b>\n\n"
            f"Yangi narxni kiriting:"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"sa_wprice_worker_selected: {e}")
        await callback.answer("⚠️ Xatolik.", show_alert=True)


# Ishchi narxi kiritish (barcha)
@router.message(SAPriceStates.waiting_worker_price, F.from_user.id == SA)
async def sa_set_worker_price_all(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(",", "").replace(" ", ""))
        if price <= 0:
            await message.answer("⚠️ Narx musbat bo'lishi kerak.")
            return
        data = await state.get_data()
        await update_workshop_default_worker_price(data["workshop_id"], price)
        await state.clear()
        await message.answer(
            f"✅ Barcha ishchilar uchun narx yangilandi!\n"
            f"💵 Yangi narx: <b>{fmt_money(price)}/m²</b>",
            reply_markup=sa_main_menu()
        )
        await save_log(SA, "sa_update_worker_price_all",
                      f"ws={data['workshop_id']} price={price}")
    except ValueError:
        await message.answer("⚠️ To'g'ri narx kiriting.")
    except Exception as e:
        logger.error(f"sa_set_worker_price_all: {e}")
        await message.answer("⚠️ Xatolik.")
        await state.clear()


# Ishchi narxi kiritish (individual)
@router.message(SAPriceStates.waiting_worker_individual_price, F.from_user.id == SA)
async def sa_set_worker_price_individual(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(",", "").replace(" ", ""))
        if price <= 0:
            await message.answer("⚠️ Narx musbat bo'lishi kerak.")
            return
        data = await state.get_data()
        await update_worker_price(
            data["target_user_id"],
            data["workshop_id"],
            price
        )
        await state.clear()
        await message.answer(
            f"✅ Ishchi narxi yangilandi!\n"
            f"💵 Yangi narx: <b>{fmt_money(price)}/m²</b>",
            reply_markup=sa_main_menu()
        )
        await save_log(SA, "sa_update_worker_price_individual",
                      f"ws={data['workshop_id']} user={data['target_user_id']} price={price}")
    except ValueError:
        await message.answer("⚠️ To'g'ri narx kiriting.")
    except Exception as e:
        logger.error(f"sa_set_worker_price_individual: {e}")
        await message.answer("⚠️ Xatolik.")
        await state.clear()


# Parol o'zgartirish
@router.message(SAPasswordStates.waiting_new_password, F.from_user.id == SA)
async def sa_set_password(message: Message, state: FSMContext):
    try:
        password = message.text.strip()
        if len(password) < 4:
            await message.answer("⚠️ Parol kamida 4 ta belgi bo'lishi kerak.")
            return
        data = await state.get_data()
        pw_hash = hash_password(password)
        await update_workshop_password(data["workshop_id"], pw_hash)
        ws = await get_workshop_by_id(data["workshop_id"])
        await state.clear()
        await message.answer(
            f"✅ <b>{ws['name']}</b> sexi paroli yangilandi!",
            reply_markup=sa_main_menu()
        )
        await save_log(SA, "sa_update_password", f"ws={data['workshop_id']}")
    except Exception as e:
        logger.error(f"sa_set_password: {e}")
        await message.answer("⚠️ Xatolik.")
        await state.clear()


# ============================================================
# SEX QO'SHISH
# ============================================================

@router.message(F.text == "➕ Sex qo'shish", F.from_user.id == SA)
async def sa_add_workshop(message: Message, state: FSMContext):
    await state.set_state(SAWorkshopStates.waiting_name)
    await message.answer("🏭 Yangi sex nomini kiriting:")


@router.message(SAWorkshopStates.waiting_name, F.from_user.id == SA)
async def sa_workshop_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("⚠️ Nom kamida 2 ta harfdan iborat bo'lishi kerak.")
        return
    await state.update_data(workshop_name=name)
    await state.set_state(SAWorkshopStates.waiting_password)
    await message.answer(
        f"🔑 <b>{name}</b> uchun parol o'rnating:\n"
        f"(Kamida 4 ta belgi)"
    )


@router.message(SAWorkshopStates.waiting_password, F.from_user.id == SA)
async def sa_workshop_password(message: Message, state: FSMContext):
    try:
        password = message.text.strip()
        if len(password) < 4:
            await message.answer("⚠️ Parol kamida 4 ta belgi bo'lishi kerak.")
            return
        data    = await state.get_data()
        pw_hash = hash_password(password)
        ws      = await create_workshop(data["workshop_name"], pw_hash)
        bot_info = await message.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={ws['token']}"
        await state.clear()
        await message.answer(
            f"✅ <b>{ws['name']}</b> sexi yaratildi!\n\n"
            f"🔗 Mijozlar havolasi:\n"
            f"<code>{link}</code>\n\n"
            f"Bu havolani mijozlarga yuboring.\n"
            f"Havola orqali kirgan mijozlar "
            f"faqat shu sexga bog'lanadi.",
            reply_markup=sa_main_menu()
        )
        await save_log(SA, "sa_create_workshop", f"ws={ws['id']} name={ws['name']}")
    except Exception as e:
        logger.error(f"sa_workshop_password: {e}")
        await message.answer("⚠️ Xatolik.")
        await state.clear()


# ============================================================
# PAROLLAR RO'YXATI
# ============================================================

@router.message(F.text == "🔑 Parollar", F.from_user.id == SA)
async def sa_passwords(message: Message):
    try:
        workshops = await get_all_workshops()
        if not workshops:
            await message.answer("📭 Sexlar yo'q.")
            return
        bot_info = await message.bot.get_me()
        text = "🔑 <b>Sexlar va tokenlar:</b>\n\n"
        for ws in workshops:
            status = "✅" if ws["is_active"] else "❌"
            link = f"https://t.me/{bot_info.username}?start={ws['token']}"
            text += (
                f"{status} <b>{ws['name']}</b>\n"
                f"🔗 <code>{link}</code>\n"
                f"─────────────\n"
            )
        await message.answer(text)
    except Exception as e:
        logger.error(f"sa_passwords: {e}")
        await message.answer("⚠️ Xatolik.")


# ============================================================
# BEKOR QILISH
# ============================================================

@router.callback_query(F.data == "sa_cancel", F.from_user.id == SA)
async def sa_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi.")
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()