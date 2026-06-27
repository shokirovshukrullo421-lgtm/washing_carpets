from aiogram.fsm.state import State, StatesGroup


# ============================================================
# SUPER ADMIN
# ============================================================

class SAWorkshopStates(StatesGroup):
    waiting_name     = State()   # sex nomi
    waiting_password = State()   # sex paroli


class SAMemberStates(StatesGroup):
    waiting_tg_id    = State()   # yangi admin/worker tg_id
    waiting_name     = State()   # ismi


class SAPriceStates(StatesGroup):
    waiting_price        = State()   # gilam narxi
    waiting_worker_price = State()   # ishchi narxi (umumiy)
    waiting_worker_individual_price = State()  # ishchi individual narxi


class SAPasswordStates(StatesGroup):
    waiting_new_password = State()


# ============================================================
# ADMIN (mini_admin)
# ============================================================

class AdminPickupStates(StatesGroup):
    waiting_client_note   = State()   # mijoz laqabi
    waiting_carpet_count  = State()   # gilam soni


class AdminPaymentStates(StatesGroup):
    waiting_amount    = State()   # to'lov miqdori
    waiting_debt_note = State()   # qarz muddati


class AdminDebtStates(StatesGroup):
    waiting_amount    = State()
    waiting_debt_note = State()


class AdminSettingsStates(StatesGroup):
    waiting_price            = State()
    waiting_worker_price     = State()
    waiting_individual_price = State()
    waiting_new_password     = State()


class AdminAddMemberStates(StatesGroup):
    waiting_tg_id = State()
    waiting_name  = State()


# ============================================================
# WORKER
# ============================================================

class WorkerStartStates(StatesGroup):
    waiting_count = State()   # nechta xonadon yuvmoqchi


class WorkerWashStates(StatesGroup):
    waiting_dimensions  = State()   # o'lchamlar
    waiting_area        = State()   # umumiy maydon tasdiqlash


# ============================================================
# USER
# ============================================================

class UserOrderStates(StatesGroup):
    waiting_contact      = State()
    waiting_location     = State()
    waiting_pickup_time  = State()
    waiting_extra_note   = State()
    waiting_confirm      = State()


# ============================================================
# ROLE TANLASH
# ============================================================

class RoleSelectStates(StatesGroup):
    waiting_role = State()   # admin_worker, super_mini_admin_worker uchun
    
    
    
    
    
class AdminManualOrderStates(StatesGroup):
    waiting_phone       = State()
    waiting_location    = State()
    waiting_pickup_time = State()
    waiting_extra_note  = State()
    waiting_confirm     = State()
    waiting_client_note = State()
    waiting_carpet_count = State()
    
    
    
    
class AdminRejectStates(StatesGroup):
    waiting_reason = State()
    
    
    
class AdminFinanceStates(StatesGroup):
    waiting_amount   = State()
    waiting_category = State()
    waiting_note     = State()

class AdminAdStates(StatesGroup):
    waiting_message  = State()
    waiting_confirm  = State()