from utils.helpers import fmt_money, fmt_area, calculate_discount


def format_order(order: dict) -> str:
    text = (
        f"📋 <b>Buyurtma #{order['id']}</b>\n\n"
        f"👤 {order.get('user_name') or '—'}\n"
        f"📞 {order.get('phone') or '—'}\n"
        f"📍 {order.get('address_text') or '—'}\n"
        f"🕐 {order.get('pickup_time_note') or '—'}\n"
    )
    if order.get("extra_note"):
        text += f"📝 {order['extra_note']}\n"
    if order.get("client_note"):
        text += f"🏷 Laqab: <b>{order['client_note']}</b>\n"
    return text


def format_order_short(order: dict) -> str:
    return (
        f"📋 <b>#{order['id']}</b> · "
        f"{order.get('user_name') or '—'} · "
        f"{order.get('phone') or '—'}"
        f"{' · ' + order['client_note'] if order.get('client_note') else ''}"
    )


def format_carpet_for_admin(carpet: dict, index: int) -> str:
    status_map = {
        "in_progress": "🧺 Jarayonda",
        "booked":      "🔒 Bron",
        "washed":      "✨ Yuvilgan",
        "delivered":   "📦 Yetkazilgan",
    }
    status = status_map.get(carpet.get("status", ""), carpet.get("status", ""))
    text = (
        f"🪣 <b>Gilam #{index}</b> (ID: {carpet['id']})\n"
        f"🔖 {status}\n"
    )
    if carpet.get("total_area_m2"):
        text += f"📏 {fmt_area(carpet['total_area_m2'])}\n"
    if carpet.get("dimensions_raw"):
        text += f"📐 {carpet['dimensions_raw']}\n"
    if carpet.get("worker_name"):
        text += f"👷 {carpet['worker_name']}\n"
    return text


def format_washed_order_for_delivery(order: dict) -> str:
    """Yetkazilishi kerak bo'lgan xonadon"""
    area = order.get("total_area", 0) or 0
    discount = calculate_discount(int(area))
    base_amount = float(order.get("base_amount", 0) or 0)
    final_amount = float(order.get("total_amount", 0) or 0)
    debt = float(order.get("debt_amount", 0) or 0)
    paid = float(order.get("paid_amount", 0) or 0)

    text = (
        f"🏠 <b>#{order['order_id']}</b>"
        f"{' · ' + order['client_note'] if order.get('client_note') else ''}\n"
        f"👤 {order.get('user_name') or '—'}\n"
        f"📞 {order.get('phone') or '—'}\n"
        f"🪣 {order['carpet_count']} ta gilam · {fmt_area(int(area))}\n"
    )
    if discount > 0:
        text += f"🏷 Chegirma: {discount}%\n"
    text += f"💰 Jami: <b>{fmt_money(final_amount)}</b>\n"
    if paid > 0:
        text += f"✅ To'langan: {fmt_money(paid)}\n"
    if debt > 0:
        text += f"⚠️ Qarz: <b>{fmt_money(debt)}</b>\n"
        if order.get("debt_note"):
            text += f"⏰ Muddat: {order['debt_note']}\n"
    return text


def format_inprogress_carpet(carpet: dict, index: int) -> str:
    """Jarayondagi gilamlar"""
    booked_by = carpet.get("worker_name") or "Bron qilinmagan"
    return (
        f"<b>{index}.</b> Gilam #{carpet['id']}\n"
        f"🏷 {carpet.get('client_note') or '—'}\n"
        f"📅 Kelgan: {str(carpet.get('created_at', ''))[:10]}\n"
        f"👷 {booked_by}\n"
    )


def format_worker_payment(p: dict) -> str:
    return (
        f"🏠 <b>#{p['order_id']}</b>"
        f"{' · ' + p['client_note'] if p.get('client_note') else ''}\n"
        f"📏 {fmt_area(p['area_m2'])}\n"
        f"💵 {fmt_money(p['worker_price_per_m2'])}/m² × {p['area_m2']} = "
        f"<b>{fmt_money(float(p['total_amount']))}</b>\n"
    )


def format_debtor(d: dict) -> str:
    return (
        f"👤 <b>{d.get('full_name') or '—'}</b>"
        f"{' · ' + d['client_note'] if d.get('client_note') else ''}\n"
        f"👷 {d.get('worker_name') or '—'}\n"
        f"📅 Kelgan: {str(d.get('picked_up_at', ''))[:10]}\n"
        f"📦 Yetkazilgan: {str(d.get('delivered_at', ''))[:10]}\n"
        f"💸 Qarz: <b>{fmt_money(float(d['debt_amount']))}</b>\n"
        f"⏰ Muddat: {d.get('debt_note') or '—'}\n"
    )
    
    
    
    
def format_all_carpet(carpet: dict) -> str:
    status_map = {
        "in_progress": "🧺 Jarayonda",
        "booked":      "🔒 Bron",
        "washed":      "✨ Yuvilgan",
        "delivered":   "📦 Yetkazilgan",
    }
    status = status_map.get(carpet.get("status", ""), "—")
    text = f"🪣 <b>#{carpet['id']}</b> · {carpet.get('client_note') or '—'} · {status}\n"
    if carpet.get("worker_name"):
        text += f"   👷 {carpet['worker_name']}\n"
    if carpet.get("total_area_m2"):
        text += f"   📏 {carpet['total_area_m2']} m²\n"
    if carpet.get("status") == "delivered":
        paid = float(carpet.get("paid_amount") or 0)
        debt = float(carpet.get("debt_amount") or 0)
        text += f"   ✅ {fmt_money(paid)}"
        if debt > 0:
            text += f" · ⚠️ {fmt_money(debt)} qarz"
        text += "\n"
    return text