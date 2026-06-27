# middlewares/auth.py
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from config import settings
from utils.logger import logger


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        tg_id   = None
        message = None

        if isinstance(event, Update):
            if event.message:
                tg_id   = event.message.from_user.id
                message = event.message
            elif event.callback_query:
                tg_id = event.callback_query.from_user.id

        if not tg_id:
            data.update(role="user", roles=[], user=None, workshop=None)
            return await handler(event, data)

        try:
            from db.database import get_pool
            pool = get_pool()
            async with pool.acquire() as conn:

                # 1. Userni tg_id orqali topamiz
                user_row = await conn.fetchrow(
                    "SELECT id, tg_id, full_name, phone, is_active "
                    "FROM users WHERE tg_id = $1",
                    tg_id
                )

                # 2. Super admin tekshirish
                is_super = (tg_id == settings.SUPER_ADMIN_TG_ID)

                # 3. Rollar listini yasaymiz
                all_roles = []

                if is_super:
                    all_roles.append({
                        "role":     "super_admin",
                        "workshop": None,
                        "active":   True
                    })

                if user_row:
                    user_dict = dict(user_row)

                    # Bloklangan user
                    if not user_row["is_active"]:
                        if message:
                            await message.answer(
                                "🚫 Akkauntingiz bloklangan."
                            )
                        return

                    # user_id orqali barcha user_workshops
                    uid = user_row["id"]  # ← bu users.id
                    
                    ws_rows = await conn.fetch(
                        """
                        SELECT
                            uw.role,
                            uw.is_active        AS uw_active,
                            uw.worker_price_per_m2,
                            w.id                AS ws_id,
                            w.name              AS ws_name,
                            w.token             AS ws_token,
                            w.price_per_m2      AS ws_price,
                            w.default_worker_price AS ws_worker_price,
                            w.confirm_timeout_sec  AS ws_timeout,
                            w.is_active         AS ws_active
                        FROM user_workshops uw
                        JOIN workshops w ON w.id = uw.workshop_id
                        WHERE uw.user_id = $1
                        ORDER BY uw.created_at DESC
                        """,
                        uid
                    )

                    logger.info(
                        f"AUTH [{tg_id}] uid={uid} "
                        f"ws_rows={len(ws_rows)} "
                        f"roles={[r['role'] for r in ws_rows]}"
                    )

                    for row in ws_rows:
                        r = dict(row)
                        if r["role"] == "user":
                            # user role — workshop saqlaymiz, rol emas
                            continue

                        workshop = {
                            "id":                   r["ws_id"],
                            "name":                 r["ws_name"],
                            "token":                r["ws_token"],
                            "price_per_m2":         r["ws_price"],
                            "default_worker_price": r["ws_worker_price"],
                            "confirm_timeout_sec":  r["ws_timeout"],
                            "worker_price_per_m2":  r.get("worker_price_per_m2"),
                            "uw_active":            r["uw_active"],
                            "ws_active":            r["ws_active"],
                        }
                        all_roles.append({
                            "role":     r["role"],
                            "workshop": workshop,
                            "active":   r["uw_active"] and r["ws_active"]
                        })

                    # user sifatida sexga bog'langanmi?
                    user_ws_row = await conn.fetchrow(
                        """
                        SELECT w.id, w.name, w.token,
                        w.price_per_m2,
                        w.confirm_timeout_sec
                        FROM user_workshops uw
                        JOIN workshops w ON w.id = uw.workshop_id
                        WHERE uw.user_id   = $1
                        AND   uw.role      = 'user'
                        AND   uw.is_active = true
                        AND   w.is_active  = true
                        ORDER BY uw.created_at DESC
                        LIMIT 1
                        """,
                        uid
                    )
                    user_workshop = dict(user_ws_row) if user_ws_row else None

                else:
                    user_dict     = None
                    user_workshop = None

                # 4. Aktiv rollar
                active_roles = [r for r in all_roles if r["active"]]

                logger.info(
                    f"AUTH [{tg_id}]: "
                    f"all={[r['role'] for r in all_roles]} "
                    f"active={[r['role'] for r in active_roles]}"
                )

                # 5. Rolga qarab data ni to'ldirish
                if len(active_roles) == 0:
                    # Oddiy user
                    ws = None
                    if user_workshop:
                        ws = {
                            "id":                  user_workshop["id"],
                            "name":                user_workshop["name"],
                            "token":               user_workshop["token"],
                            "price_per_m2":        user_workshop["price_per_m2"],
                            "confirm_timeout_sec": user_workshop["confirm_timeout_sec"],
                        }
                    data.update(
                        role="user",
                        roles=[],
                        user=user_dict,
                        workshop=ws
                    )

                elif len(active_roles) == 1:
                    # Bitta rol — to'g'ri panel
                    r = active_roles[0]
                    data.update(
                        role=r["role"],
                        roles=active_roles,
                        user=user_dict,
                        workshop=r["workshop"]
                    )

                else:
                    # Ko'p rol — tanlash kerak
                    data.update(
                        role="multi",
                        roles=active_roles,
                        user=user_dict,
                        workshop=active_roles[0]["workshop"]
                    )

        except Exception as e:
            logger.error(f"AuthMiddleware [{tg_id}]: {e}", exc_info=True)
            data.update(
                role="user", roles=[],
                user=None, workshop=None
            )

        return await handler(event, data)