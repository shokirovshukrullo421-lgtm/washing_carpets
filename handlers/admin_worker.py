# handlers/admin_worker.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart

from keyboards.user import role_select_keyboard
from utils.logger import logger

router = Router()




@router.message(F.text == "👤 Admin panel")
async def aw_admin_panel(message: Message, state: FSMContext,
                          role=None, workshop=None):
    if role != "admin_worker":
        return
    from keyboards.admin import admin_main_menu
    await message.answer(
        f"👤 <b>Admin panel</b> — {workshop['name']}",
        reply_markup=admin_main_menu()
    )


@router.message(F.text == "👷 Worker panel")
async def aw_worker_panel(message: Message, state: FSMContext,
                           role=None, workshop=None):
    if role != "admin_worker":
        return
    from keyboards.worker import worker_main_menu
    await message.answer(
        f"👷 <b>Worker panel</b> — {workshop['name']}",
        reply_markup=worker_main_menu()
    )