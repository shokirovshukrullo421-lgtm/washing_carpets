# db/queries.py
import secrets
from typing import Optional
from asyncpg import Pool
from db.database import get_pool
from utils.logger import logger


# ============================================================
# HELPERS
# ============================================================

async def _fetch(query: str, *args) -> list[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]


async def _fetchrow(query: str, *args) -> Optional[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None


async def _execute(query: str, *args):
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(query, *args)


async def _fetchval(query: str, *args):
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)


# ============================================================
# SUPER ADMIN
# ============================================================

async def is_super_admin(tg_id: int) -> bool:
    row = await _fetchrow(
        "SELECT id FROM super_admins WHERE tg_id = $1", tg_id
    )
    return row is not None


# ============================================================
# WORKSHOPS
# ============================================================

async def get_all_workshops() -> list[dict]:
    return await _fetch(
        "SELECT * FROM workshops ORDER BY created_at DESC"
    )


async def get_workshop_by_id(workshop_id: int) -> Optional[dict]:
    return await _fetchrow(
        "SELECT * FROM workshops WHERE id = $1", workshop_id
    )


async def get_workshop_by_token(token: str) -> Optional[dict]:
    return await _fetchrow(
        "SELECT * FROM workshops WHERE token = $1 AND is_active = true",
        token
    )


async def create_workshop(name: str, password_hash: str) -> dict:
    token = secrets.token_urlsafe(16)
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO workshops (name, token, password_hash)
            VALUES ($1, $2, $3) RETURNING *
            """,
            name, token, password_hash
        )
        return dict(row)


async def update_workshop_price(
    workshop_id: int,
    price_per_m2: float,
    default_worker_price: float
):
    await _execute(
        """
        UPDATE workshops
        SET price_per_m2 = $1, default_worker_price = $2
        WHERE id = $3
        """,
        price_per_m2, default_worker_price, workshop_id
    )


async def update_workshop_client_price(workshop_id: int, price: float):
    await _execute(
        "UPDATE workshops SET price_per_m2 = $1 WHERE id = $2",
        price, workshop_id
    )


async def update_workshop_default_worker_price(workshop_id: int, price: float):
    await _execute(
        "UPDATE workshops SET default_worker_price = $1 WHERE id = $2",
        price, workshop_id
    )


async def update_workshop_password(workshop_id: int, password_hash: str):
    await _execute(
        "UPDATE workshops SET password_hash = $1 WHERE id = $2",
        password_hash, workshop_id
    )


async def toggle_workshop(workshop_id: int, is_active: bool):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE workshops SET is_active = $1 WHERE id = $2",
                is_active, workshop_id
            )
            if not is_active:
                await conn.execute(
                    """
                    UPDATE user_workshops SET is_active = false
                    WHERE workshop_id = $1
                    """,
                    workshop_id
                )


# ============================================================
# USERS
# ============================================================

async def get_user_by_tg_id(tg_id: int) -> Optional[dict]:
    return await _fetchrow(
        "SELECT * FROM users WHERE tg_id = $1", tg_id
    )


async def get_user_by_id(user_id: int) -> Optional[dict]:
    return await _fetchrow(
        "SELECT * FROM users WHERE id = $1", user_id
    )


async def create_user(tg_id: int, full_name: str) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (tg_id, full_name)
            VALUES ($1, $2)
            ON CONFLICT (tg_id) DO UPDATE SET full_name = $2
            RETURNING *
            """,
            tg_id, full_name
        )
        return dict(row)


async def update_user_phone(tg_id: int, phone: str):
    await _execute(
        "UPDATE users SET phone = $1 WHERE tg_id = $2",
        phone, tg_id
    )


# ============================================================
# USER WORKSHOPS
# ============================================================

async def get_user_workshop(user_id: int, workshop_id: int) -> Optional[dict]:
    return await _fetchrow(
        """
        SELECT * FROM user_workshops
        WHERE user_id = $1 AND workshop_id = $2
        """,
        user_id, workshop_id
    )


async def get_user_active_workshops(tg_id: int) -> list[dict]:
    """User bog'langan barcha aktiv sexlar"""
    return await _fetch(
        """
        SELECT uw.*, w.name as workshop_name, w.token,
               w.price_per_m2, w.default_worker_price,
               w.confirm_timeout_sec
        FROM user_workshops uw
        JOIN workshops w ON w.id = uw.workshop_id
        JOIN users u ON u.id = uw.user_id
        WHERE u.tg_id = $1
        AND uw.is_active = true
        AND w.is_active = true
        ORDER BY uw.created_at DESC
        """,
        tg_id
    )


async def add_user_to_workshop(
    user_id: int,
    workshop_id: int,
    role: str,
    worker_price: float = None
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO user_workshops
                (user_id, workshop_id, role, worker_price_per_m2)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id, workshop_id)
            DO UPDATE SET role = $3, is_active = true,
                          worker_price_per_m2 = $4
            RETURNING *
            """,
            user_id, workshop_id, role, worker_price
        )
        return dict(row)


async def deactivate_user_in_workshop(user_id: int, workshop_id: int):
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE user_workshops SET is_active = false
            WHERE user_id = $1 AND workshop_id = $2
            AND is_active = true
            """,
            user_id, workshop_id
        )
        logger.info(f"deactivate_user: user={user_id} ws={workshop_id} result={result}")


async def update_worker_price(
    user_id: int,
    workshop_id: int,
    price: float
):
    await _execute(
        """
        UPDATE user_workshops SET worker_price_per_m2 = $1
        WHERE user_id = $2 AND workshop_id = $3
        """,
        price, user_id, workshop_id
    )


async def get_workshop_members(
    workshop_id: int,
    role: str = None
) -> list[dict]:
    """
    MUHIM: u.id — users.id (user_workshops.user_id bilan mos)
    """
    query = """
        SELECT
            u.id,           -- bu user_workshops.user_id ga mos
            u.tg_id,
            u.full_name,
            u.phone,
            uw.role,
            uw.is_active    as uw_active,
            uw.worker_price_per_m2
        FROM users u
        JOIN user_workshops uw ON uw.user_id = u.id
        WHERE uw.workshop_id = $1
    """
    params = [workshop_id]
    if role:
        query += " AND uw.role = $2"
        params.append(role)
    query += " ORDER BY uw.created_at DESC"
    return await _fetch(query, *params)


async def get_workshop_admins(workshop_id: int) -> list[dict]:
    return await get_workshop_members(workshop_id, "admin")


async def get_workshop_workers(workshop_id: int) -> list[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT u.*, uw.role, uw.is_active as uw_active,
                   COALESCE(uw.worker_price_per_m2,
                            w.default_worker_price) as effective_price
            FROM users u
            JOIN user_workshops uw ON uw.user_id = u.id
            JOIN workshops w ON w.id = uw.workshop_id
            WHERE uw.workshop_id = $1
            AND uw.role IN ('worker', 'admin_worker')
            ORDER BY uw.created_at DESC
            """,
            workshop_id
        )
        return [dict(r) for r in rows]


async def check_user_role_exists(tg_id: int) -> Optional[dict]:
    """
    User boshqa sexda admin/worker/admin_worker ekanini tekshirish
    Agar mavjud bo'lsa, sabab bilan qaytaradi
    """
    return await _fetchrow(
        """
        SELECT uw.role, w.name as workshop_name
        FROM user_workshops uw
        JOIN users u ON u.id = uw.user_id
        JOIN workshops w ON w.id = uw.workshop_id
        WHERE u.tg_id = $1
        AND uw.role IN ('admin', 'worker', 'admin_worker',
                        'super_mini_admin_worker')
        AND uw.is_active = true
        LIMIT 1
        """,
        tg_id
    )
    
    
    


async def add_or_reactivate_member(
    tg_id: int,
    full_name: str,
    workshop_id: int,
    role: str,
    worker_price: float = None
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # User yaratish yoki olish (DB da bo'lmasa yaratamiz)
            user = await conn.fetchrow(
                """
                INSERT INTO users (tg_id, full_name)
                VALUES ($1, $2)
                ON CONFLICT (tg_id)
                DO UPDATE SET full_name = COALESCE($2, users.full_name)
                RETURNING *
                """,
                tg_id, full_name
            )

            # Yangi sexga qo'shish yoki aktivlashtirish
            row = await conn.fetchrow(
                """
                INSERT INTO user_workshops
                    (user_id, workshop_id, role, worker_price_per_m2)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id, workshop_id)
                DO UPDATE SET
                    role                = $3,
                    is_active           = true,
                    worker_price_per_m2 = COALESCE($4, user_workshops.worker_price_per_m2)
                RETURNING *
                """,
                user["id"], workshop_id, role, worker_price
            )
            return {"user": dict(user), "uw": dict(row)}
    
    
async def check_user_active_role(
    tg_id: int,
    current_workshop_id: int
) -> Optional[dict]:
    """
    Faqat BOSHQA sexda aktiv rolda ekanini tekshiradi.
    O'z sexini tekshirmaydi.
    DB da yo'q bo'lsa None qaytaradi.
    """
    return await _fetchrow(
        """
        SELECT uw.role, w.name as workshop_name, w.id as workshop_id
        FROM user_workshops uw
        JOIN users u       ON u.id  = uw.user_id
        JOIN workshops w   ON w.id  = uw.workshop_id
        WHERE u.tg_id      = $1
        AND   uw.workshop_id != $2
        AND   uw.role      IN ('admin','worker','admin_worker','super_mini_admin_worker')
        AND   uw.is_active  = true
        AND   w.is_active   = true
        LIMIT 1
        """,
        tg_id, current_workshop_id
    )

    
    
    






async def get_admin_workshop_by_tg(tg_id: int) -> Optional[dict]:
    return await _fetchrow(
        """
        SELECT w.*, uw.role, uw.worker_price_per_m2
        FROM workshops w
        JOIN user_workshops uw ON uw.workshop_id = w.id
        JOIN users u ON u.id = uw.user_id
        WHERE u.tg_id = $1
        AND uw.role IN ('admin', 'admin_worker', 'super_mini_admin_worker')
        AND uw.is_active = true
        AND w.is_active = true
        LIMIT 1
        """,
        tg_id
    )


async def get_worker_workshop_by_tg(tg_id: int) -> Optional[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT w.*,
                   uw.role,
                   COALESCE(uw.worker_price_per_m2,
                            w.default_worker_price) as worker_price_per_m2
            FROM workshops w
            JOIN user_workshops uw ON uw.workshop_id = w.id
            JOIN users u ON u.id = uw.user_id
            WHERE u.tg_id = $1
            AND uw.role IN ('worker', 'admin_worker', 'super_mini_admin_worker')
            AND uw.is_active = true
            AND w.is_active = true
            LIMIT 1
            """,
            tg_id
        )
        return dict(row) if row else None


# ============================================================
# ORDERS
# ============================================================

async def create_order(
    workshop_id: int,
    user_id: int,
    phone: str,
    location_lat: Optional[float],
    location_lon: Optional[float],
    pickup_time_note: str,
    extra_note: Optional[str],
    expires_at
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO orders (
                workshop_id, user_id, phone,
                location_lat, location_lon,
                pickup_time_note, extra_note, expires_at
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            RETURNING *
            """,
            workshop_id, user_id, phone,
            location_lat, location_lon,
            pickup_time_note, extra_note, expires_at
        )
        return dict(row)


async def confirm_order(order_id: int):
    await _execute(
        """
        UPDATE orders SET status = 'confirmed', confirmed_at = now()
        WHERE id = $1 AND status = 'pending'
        """,
        order_id
    )


async def cancel_order(order_id: int):
    await _execute(
        "UPDATE orders SET status = 'cancelled' WHERE id = $1",
        order_id
    )


async def get_order_by_id(order_id: int) -> Optional[dict]:
    return await _fetchrow(
        """
        SELECT o.*, u.full_name as user_name, u.tg_id as user_tg_id
        FROM orders o
        JOIN users u ON u.id = o.user_id
        WHERE o.id = $1
        """,
        order_id
    )


async def get_new_orders(workshop_id: int) -> list[dict]:
    return await _fetch(
        """
        SELECT o.*, u.full_name as user_name,
               u.tg_id as user_tg_id
        FROM orders o
        JOIN users u ON u.id = o.user_id
        WHERE o.workshop_id = $1 AND o.status = 'confirmed'
        ORDER BY o.created_at DESC
        """,
        workshop_id
    )


async def pickup_order(
    order_id: int,
    carpet_count: int,
    client_note: str,
    workshop_id: int
):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            ws = await conn.fetchrow(
                "SELECT * FROM workshops WHERE id = $1", workshop_id
            )
            await conn.execute(
                """
                UPDATE orders
                SET status = 'picked_up', carpet_count = $1,
                    client_note = $2, picked_up_at = now()
                WHERE id = $3
                """,
                carpet_count, client_note, order_id
            )
            for _ in range(carpet_count):
                await conn.execute(
                    """
                    INSERT INTO carpets
                        (workshop_id, order_id, price_per_m2, status)
                    VALUES ($1, $2, $3, 'in_progress')
                    """,
                    workshop_id, order_id, ws["price_per_m2"]
                )
            await conn.execute(
                """
                INSERT INTO client_payments
                    (workshop_id, order_id, total_amount, status)
                VALUES ($1, $2, 0, 'unpaid')
                ON CONFLICT (order_id) DO NOTHING
                """,
                workshop_id, order_id
            )


# ============================================================
# CARPETS
# ============================================================

async def get_carpets_by_order(order_id: int) -> list[dict]:
    return await _fetch(
        """
        SELECT c.*, u.full_name as worker_name
        FROM carpets c
        LEFT JOIN users u ON u.id = c.worker_id
        WHERE c.order_id = $1
        ORDER BY c.id
        """,
        order_id
    )


async def get_inprogress_orders(
    workshop_id: int,
    offset: int = 0,
    limit: int = 10
) -> list[dict]:
    """Keltirilgan lekin yuvilmagan gilamlar (xonadon bo'yicha)"""
    return await _fetch(
        """
        SELECT
            o.id as order_id,
            o.phone, o.client_note,
            o.picked_up_at,
            u.full_name as user_name,
            COUNT(c.id) as carpet_count,
            COUNT(c.id) FILTER (WHERE c.worker_id IS NOT NULL) as booked_count,
            array_agg(DISTINCT uw2.full_name)
                FILTER (WHERE c.worker_id IS NOT NULL) as worker_names
        FROM orders o
        JOIN users u ON u.id = o.user_id
        JOIN carpets c ON c.order_id = o.id
        LEFT JOIN users uw2 ON uw2.id = c.worker_id
        WHERE o.workshop_id = $1
        AND c.status IN ('in_progress', 'booked')
        GROUP BY o.id, o.phone, o.client_note, o.picked_up_at, u.full_name
        ORDER BY o.created_at DESC
        LIMIT $2 OFFSET $3
        """,
        workshop_id, limit, offset
    )


async def get_inprogress_orders_count(workshop_id: int) -> int:
    return await _fetchval(
        """
        SELECT COUNT(DISTINCT o.id)
        FROM orders o
        JOIN carpets c ON c.order_id = o.id
        WHERE o.workshop_id = $1
        AND c.status IN ('in_progress', 'booked')
        """,
        workshop_id
    ) or 0


async def get_washed_orders(workshop_id: int) -> list[dict]:
    """Yetkazilishi kerak bo'lgan xonadonlar"""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                o.id as order_id,
                o.phone, o.client_note,
                o.location_lat, o.location_lon,
                u.full_name as user_name,
                COUNT(c.id) as carpet_count,
                SUM(c.total_area_m2) as total_area,
                MAX(c.price_per_m2) as price_per_m2,
                COALESCE(cp.total_amount, 0) as total_amount,
                COALESCE(cp.paid_amount, 0) as paid_amount,
                COALESCE(cp.debt_amount, 0) as debt_amount,
                cp.debt_note
            FROM orders o
            JOIN users u ON u.id = o.user_id
            JOIN carpets c ON c.order_id = o.id
            LEFT JOIN client_payments cp ON cp.order_id = o.id
            WHERE o.workshop_id = $1
            AND c.status = 'washed'
            GROUP BY o.id, o.phone, o.client_note, o.location_lat,
                     o.location_lon, u.full_name,
                     cp.total_amount, cp.paid_amount,
                     cp.debt_amount, cp.debt_note
            ORDER BY o.created_at DESC
            """,
            workshop_id
        )
        return [dict(r) for r in rows]


async def get_all_carpets_paginated(
    workshop_id: int,
    offset: int = 0,
    limit: int = 5
) -> list[dict]:
    return await _fetch(
        """
        SELECT
            c.id, c.order_id, c.status,
            c.total_area_m2, c.dimensions_raw,
            c.washed_at, c.delivered_at,
            o.client_note,
            uw.full_name as worker_name,
            cp.paid_amount, cp.debt_amount
        FROM carpets c
        JOIN orders o ON o.id = c.order_id
        LEFT JOIN users uw ON uw.id = c.worker_id
        LEFT JOIN client_payments cp ON cp.order_id = c.order_id
        WHERE c.workshop_id = $1
        ORDER BY c.created_at DESC
        LIMIT $2 OFFSET $3
        """,
        workshop_id, limit, offset
    )


async def get_all_carpets_count(workshop_id: int) -> int:
    return await _fetchval(
        "SELECT COUNT(*) FROM carpets WHERE workshop_id = $1",
        workshop_id
    ) or 0


async def get_unbooked_orders(workshop_id: int) -> list[dict]:
    """Bron qilinmagan xonadonlar (worker uchun)"""
    return await _fetch(
        """
        SELECT
            o.id as order_id,
            o.client_note,
            u.full_name as user_name,
            COUNT(c.id) as carpet_count
        FROM orders o
        JOIN users u ON u.id = o.user_id
        JOIN carpets c ON c.order_id = o.id
        WHERE o.workshop_id = $1
        AND c.status = 'in_progress'
        GROUP BY o.id, o.client_note, u.full_name
        HAVING COUNT(c.id) > 0
        ORDER BY o.created_at ASC
        """,
        workshop_id
    )


async def book_order_carpets(order_id: int, worker_id: int, worker_price: float):
    """Xonadonning barcha in_progress gilamlarini bron qilish"""
    await _execute(
        """
        UPDATE carpets
        SET status = 'booked',
            worker_id = $1,
            worker_price_per_m2 = $2,
            booked_at = now()
        WHERE order_id = $3 AND status = 'in_progress'
        """,
        worker_id, worker_price, order_id
    )


async def get_worker_booked_orders(
    worker_id: int,
    workshop_id: int
) -> list[dict]:
    return await _fetch(
        """
        SELECT
            o.id as order_id,
            o.client_note,
            u.full_name as user_name,
            COUNT(c.id) as carpet_count
        FROM orders o
        JOIN users u ON u.id = o.user_id
        JOIN carpets c ON c.order_id = o.id
        WHERE c.worker_id = $1
        AND o.workshop_id = $2
        AND c.status = 'booked'
        GROUP BY o.id, o.client_note, u.full_name
        ORDER BY o.created_at ASC
        """,
        worker_id, workshop_id
    )


async def cancel_order_booking(order_id: int, worker_id: int):
    """Xonadon bronini bekor qilish"""
    await _execute(
        """
        UPDATE carpets
        SET status = 'in_progress',
            worker_id = NULL,
            worker_price_per_m2 = NULL,
            booked_at = NULL
        WHERE order_id = $1
        AND worker_id = $2
        AND status = 'booked'
        """,
        order_id, worker_id
    )


async def finish_order_carpets(
    order_id: int,
    worker_id: int,
    dimensions_raw: str,
    total_area_m2: int,
    worker_price: float,
    client_price: float,
    workshop_id: int
):
    """
    Xonadonning barcha gilamlarini yuvilgan deb belgilash,
    worker_payment va client_payment yaratish/yangilash
    """
    from utils.helpers import calculate_discount, apply_discount

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            carpets = await conn.fetch(
                """
                SELECT * FROM carpets
                WHERE order_id = $1
                AND worker_id = $2
                AND status = 'booked'
                """,
                order_id, worker_id
            )
            if not carpets:
                return

            count = len(carpets)
            per_carpet = total_area_m2 // count
            remainder = total_area_m2 % count

            for i, carpet in enumerate(carpets):
                area = per_carpet + (1 if i < remainder else 0)
                await conn.execute(
                    """
                    UPDATE carpets
                    SET status = 'washed',
                        dimensions_raw = $1,
                        total_area_m2 = $2,
                        worker_price_per_m2 = $3,
                        washed_at = now()
                    WHERE id = $4
                    """,
                    dimensions_raw, area, worker_price, carpet["id"]
                )

            # Chegirma hisoblash
            discount = calculate_discount(total_area_m2)
            base_amount = float(client_price) * total_area_m2
            final_amount = apply_discount(base_amount, discount)

            # Client payment yangilash
            existing_total = await conn.fetchval(
                """
                SELECT COALESCE(SUM(c.total_area_m2), 0)
                FROM carpets c
                WHERE c.order_id = $1
                AND c.status IN ('washed', 'delivered')
                """,
                order_id
            )
            new_total_area = int(existing_total or 0)
            new_discount = calculate_discount(new_total_area)
            new_base = float(client_price) * new_total_area
            new_total = apply_discount(new_base, new_discount)

            await conn.execute(
                """
                UPDATE client_payments
                SET total_amount = $1,
                    discount_percent = $2
                WHERE order_id = $3
                """,
                new_total, new_discount, order_id
            ) if False else None  # discount_percent ustuni yo'q, kerak bo'lsa qo'shish

            await conn.execute(
                """
                UPDATE client_payments
                SET total_amount = $1
                WHERE order_id = $2
                """,
                new_total, order_id
            )

            # Worker payment
            await conn.execute(
                """
                INSERT INTO worker_payments
                    (workshop_id, worker_id, order_id,
                     area_m2, worker_price_per_m2, status)
                VALUES ($1, $2, $3, $4, $5, 'pending')
                ON CONFLICT (order_id, worker_id)
                DO UPDATE SET area_m2 = $4, worker_price_per_m2 = $5
                """,
                workshop_id, worker_id, order_id,
                total_area_m2, worker_price
            )


async def deliver_order_carpets(order_id: int) -> float:
    """
    Xonadon gilamlarini delivered ga o'tkazish.
    Chegirmali jami summani qaytaradi.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                UPDATE carpets SET status = 'delivered', delivered_at = now()
                WHERE order_id = $1 AND status = 'washed'
                """,
                order_id
            )
            payment = await conn.fetchrow(
                "SELECT * FROM client_payments WHERE order_id = $1",
                order_id
            )
            return float(payment["total_amount"]) if payment else 0.0


# ============================================================
# CLIENT PAYMENTS
# ============================================================

async def get_client_payment(order_id: int) -> Optional[dict]:
    return await _fetchrow(
        "SELECT * FROM client_payments WHERE order_id = $1",
        order_id
    )


async def add_client_payment(
    order_id: int,
    amount: float,
    note: str,
    created_by: int
):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            payment = await conn.fetchrow(
                "SELECT * FROM client_payments WHERE order_id = $1",
                order_id
            )
            if not payment:
                return

            await conn.execute(
                """
                INSERT INTO client_payment_logs
                    (payment_id, amount, note, created_by)
                VALUES ($1, $2, $3, $4)
                """,
                payment["id"], amount, note, created_by
            )
            new_paid = float(payment["paid_amount"]) + amount
            total = float(payment["total_amount"])

            if new_paid >= total and total > 0:
                status = "paid"
            elif new_paid > 0:
                status = "partial"
            else:
                status = "unpaid"

            await conn.execute(
                """
                UPDATE client_payments
                SET paid_amount = $1, status = $2
                WHERE order_id = $3
                """,
                new_paid, status, order_id
            )


async def set_debt_note(order_id: int, note: str):
    await _execute(
        "UPDATE client_payments SET debt_note = $1 WHERE order_id = $2",
        note, order_id
    )


async def get_debtors(
    workshop_id: int,
    offset: int = 0,
    limit: int = 10
) -> list[dict]:
    return await _fetch(
        """
        SELECT
            cp.id as payment_id,
            cp.order_id,
            cp.debt_amount,
            cp.debt_note,
            cp.created_at,
            o.picked_up_at,
            o.client_note,
            u.full_name,
            u.phone,
            wu.full_name as worker_name,
            c_delivered.delivered_at
        FROM client_payments cp
        JOIN orders o ON o.id = cp.order_id
        JOIN users u ON u.id = o.user_id
        LEFT JOIN carpets c_washed ON c_washed.order_id = o.id
            AND c_washed.status = 'delivered'
        LEFT JOIN users wu ON wu.id = c_washed.worker_id
        LEFT JOIN LATERAL (
            SELECT delivered_at FROM carpets
            WHERE order_id = o.id AND status = 'delivered'
            LIMIT 1
        ) c_delivered ON true
        WHERE cp.workshop_id = $1
        AND cp.debt_amount > 0
        GROUP BY cp.id, cp.order_id, cp.debt_amount, cp.debt_note,
                 cp.created_at, o.picked_up_at, o.client_note,
                 u.full_name, u.phone, wu.full_name,
                 c_delivered.delivered_at
        ORDER BY cp.created_at DESC
        LIMIT $2 OFFSET $3
        """,
        workshop_id, limit, offset
    )


async def get_debtors_count(workshop_id: int) -> int:
    return await _fetchval(
        """
        SELECT COUNT(*) FROM client_payments
        WHERE workshop_id = $1 AND debt_amount > 0
        """,
        workshop_id
    ) or 0


# ============================================================
# WORKER PAYMENTS
# ============================================================

async def get_worker_pending_payments(
    worker_id: int,
    workshop_id: int
) -> list[dict]:
    return await _fetch(
        """
        SELECT
            wp.id, wp.order_id, wp.area_m2,
            wp.worker_price_per_m2, wp.total_amount, wp.status,
            o.client_note
        FROM worker_payments wp
        JOIN orders o ON o.id = wp.order_id
        WHERE wp.worker_id = $1
        AND wp.workshop_id = $2
        AND wp.status = 'pending'
        ORDER BY wp.created_at DESC
        """,
        worker_id, workshop_id
    )


async def request_worker_payment(order_id: int, worker_id: int):
    await _execute(
        """
        UPDATE worker_payments
        SET status = 'requested', requested_at = now()
        WHERE order_id = $1 AND worker_id = $2 AND status = 'pending'
        """,
        order_id, worker_id
    )


async def get_requested_payments(workshop_id: int) -> list[dict]:
    return await _fetch(
        """
        SELECT
            wp.id, wp.order_id, wp.area_m2,
            wp.worker_price_per_m2, wp.total_amount,
            u.full_name as worker_name,
            o.client_note
        FROM worker_payments wp
        JOIN users u ON u.id = wp.worker_id
        JOIN orders o ON o.id = wp.order_id
        WHERE wp.workshop_id = $1 AND wp.status = 'requested'
        ORDER BY wp.requested_at DESC
        """,
        workshop_id
    )


async def approve_worker_payment(payment_id: int):
    await _execute(
        """
        UPDATE worker_payments
        SET status = 'paid', approved_at = now(), paid_at = now()
        WHERE id = $1 AND status = 'requested'
        """,
        payment_id
    )


async def reject_worker_payment(payment_id: int, reason: str):
    """
    Rad etish — gilamni qayta yuvilish uchun in_progress ga qaytarish
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            wp = await conn.fetchrow(
                "SELECT * FROM worker_payments WHERE id = $1", payment_id
            )
            if not wp:
                return

            await conn.execute(
                """
                UPDATE worker_payments
                SET status = 'rejected',
                    rejected_at = now(),
                    reject_reason = $1
                WHERE id = $2
                """,
                reason, payment_id
            )
            # Gilamlarni qayta in_progress ga qaytarish
            await conn.execute(
                """
                UPDATE carpets
                SET status = 'in_progress',
                    worker_id = NULL,
                    booked_at = NULL,
                    washed_at = NULL,
                    dimensions_raw = NULL,
                    total_area_m2 = NULL
                WHERE order_id = $1
                AND worker_id = $2
                AND status = 'washed'
                """,
                wp["order_id"], wp["worker_id"]
            )
            # Client payment ni ham tuzatish
            washed_area = await conn.fetchval(
                """
                SELECT COALESCE(SUM(total_area_m2), 0)
                FROM carpets
                WHERE order_id = $1
                AND status IN ('washed', 'delivered')
                """,
                wp["order_id"]
            )
            price = await conn.fetchval(
                "SELECT price_per_m2 FROM workshops WHERE id = $1",
                wp["workshop_id"]
            )
            from utils.helpers import calculate_discount, apply_discount
            area = int(washed_area or 0)
            discount = calculate_discount(area)
            new_total = apply_discount(float(price or 0) * area, discount)
            await conn.execute(
                "UPDATE client_payments SET total_amount = $1 WHERE order_id = $2",
                new_total, wp["order_id"]
            )


# ============================================================
# LOGS
# ============================================================

async def save_log(
    tg_id: int,
    action: str,
    details: str = None,
    workshop_id: int = None,
    is_error: bool = False
):
    try:
        await _execute(
            """
            INSERT INTO bot_logs
                (tg_id, workshop_id, action, details, is_error)
            VALUES ($1, $2, $3, $4, $5)
            """,
            tg_id, workshop_id, action, details, is_error
        )
    except Exception as e:
        logger.error(f"Log saqlashda xatolik: {e}")


async def get_logs(
    workshop_id: int = None,
    is_error: bool = None,
    limit: int = 50
) -> list[dict]:
    query = "SELECT * FROM bot_logs WHERE 1=1"
    params = []
    i = 1
    if workshop_id:
        query += f" AND workshop_id = ${i}"
        params.append(workshop_id)
        i += 1
    if is_error is not None:
        query += f" AND is_error = ${i}"
        params.append(is_error)
        i += 1
    query += f" ORDER BY created_at DESC LIMIT ${i}"
    params.append(limit)
    return await _fetch(query, *params)


# ============================================================
# EXPIRED ORDERS
# ============================================================

async def cancel_expired_orders():
    pool = get_pool()
    async with pool.acquire() as conn:
        cancelled = await conn.fetchval(
            """
            WITH updated AS (
                UPDATE orders SET status = 'cancelled'
                WHERE status = 'pending' AND expires_at < now()
                RETURNING id
            )
            SELECT COUNT(*) FROM updated
            """
        )
        if cancelled and cancelled > 0:
            logger.info(f"⏰ {cancelled} ta muddati o'tgan buyurtma bekor qilindi")
        return cancelled or 0
    
    
    
    
async def get_all_orders_by_workshop(
    workshop_id: int,
    offset: int = 0,
    limit: int = 5
) -> list[dict]:
    """
    Barcha gilamlar — XONADON bo'yicha guruhlanadi
    """
    return await _fetch(
        """
        SELECT
            o.id            as order_id,
            o.client_note,
            o.picked_up_at,
            o.extra_note,
            u.full_name     as user_name,
            COUNT(c.id)     as carpet_count,
            -- Kim bron qilgan (birinchisi)
            STRING_AGG(
                DISTINCT wu.full_name, ', '
            ) FILTER (
                WHERE c.worker_id IS NOT NULL
            )               as worker_names,
            -- Statuslar soni
            COUNT(c.id) FILTER (
                WHERE c.status = 'in_progress'
            )               as in_progress_count,
            COUNT(c.id) FILTER (
                WHERE c.status = 'booked'
            )               as booked_count,
            COUNT(c.id) FILTER (
                WHERE c.status = 'washed'
            )               as washed_count,
            COUNT(c.id) FILTER (
                WHERE c.status = 'delivered'
            )               as delivered_count
        FROM orders o
        JOIN users u ON u.id = o.user_id
        JOIN carpets c ON c.order_id = o.id
        LEFT JOIN users wu ON wu.id = c.worker_id
        WHERE o.workshop_id = $1
        AND   o.status = 'picked_up'
        GROUP BY
            o.id, o.client_note, o.picked_up_at,
            o.extra_note, u.full_name
        ORDER BY o.created_at DESC
        LIMIT $2 OFFSET $3
        """,
        workshop_id, limit, offset
    )


async def get_all_orders_count(workshop_id: int) -> int:
    return await _fetchval(
        """
        SELECT COUNT(DISTINCT o.id)
        FROM orders o
        WHERE o.workshop_id = $1
        AND   o.status = 'picked_up'
        """,
        workshop_id
    ) or 0
    
    
    
    
# ============================================================
# EXPENSES (Xarajatlar) — yangilangan
# ============================================================

async def add_expense(
    workshop_id: int,
    amount: float,
    category: str,
    note: str,
    created_by: int
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO expenses
                (workshop_id, amount, category, note, created_by)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            workshop_id, amount, category, note, created_by
        )
        return dict(row)


async def get_expenses(
    workshop_id: int,
    period: str = "day"  # day, week, month, year
) -> list[dict]:
    period_map = {
        "day":   "1 day",
        "week":  "7 days",
        "month": "30 days",
        "year":  "365 days",
    }
    interval = period_map.get(period, "1 day")
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                e.id, e.amount, e.category,
                e.note, e.created_at,
                u.full_name as created_by_name
            FROM expenses e
            LEFT JOIN users u ON u.id = e.created_by
            WHERE e.workshop_id = $1
            AND e.created_at >= now() - interval '""" + interval + """'
            ORDER BY e.created_at DESC
            """,
            workshop_id
        )
        return [dict(r) for r in rows]


async def get_income(
    workshop_id: int,
    period: str = "day"
) -> list[dict]:
    period_map = {
        "day":   "1 day",
        "week":  "7 days",
        "month": "30 days",
        "year":  "365 days",
    }
    interval = period_map.get(period, "1 day")
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                cpl.amount, cpl.note, cpl.created_at,
                u.full_name as client_name,
                o.client_note,
                o.id as order_id
            FROM client_payment_logs cpl
            JOIN client_payments cp ON cp.id = cpl.payment_id
            JOIN orders o ON o.id = cp.order_id
            JOIN users u ON u.id = o.user_id
            WHERE cp.workshop_id = $1
            AND cpl.created_at >= now() - interval '""" + interval + """'
            ORDER BY cpl.created_at DESC
            """,
            workshop_id
        )
        return [dict(r) for r in rows]


async def get_finance_summary(
    workshop_id: int,
    period: str = "day"
) -> dict:
    period_map = {
        "day":   "1 day",
        "week":  "7 days",
        "month": "30 days",
        "year":  "365 days",
    }
    interval = period_map.get(period, "1 day")
    pool = get_pool()
    async with pool.acquire() as conn:
        income = await conn.fetchval(
            """
            SELECT COALESCE(SUM(cpl.amount), 0)
            FROM client_payment_logs cpl
            JOIN client_payments cp ON cp.id = cpl.payment_id
            WHERE cp.workshop_id = $1
            AND cpl.created_at >= now() - interval '""" + interval + """'
            """,
            workshop_id
        )
        expense = await conn.fetchval(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM expenses
            WHERE workshop_id = $1
            AND created_at >= now() - interval '""" + interval + """'
            """,
            workshop_id
        )
        return {
            "income":  float(income  or 0),
            "expense": float(expense or 0),
            "profit":  float((income or 0) - (expense or 0)),
        }


# ============================================================
# REKLAMA
# ============================================================

async def get_workshop_users_tg_ids(workshop_id: int) -> list[int]:
    """Shu sexning barcha aktiv buyurtmachilarini oladi"""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT u.tg_id
            FROM user_workshops uw
            JOIN users u ON u.id = uw.user_id
            WHERE uw.workshop_id = $1
            AND uw.role = 'user'
            AND uw.is_active = true
            AND u.is_active = true
            """,
            workshop_id
        )
        return [r["tg_id"] for r in rows]


async def save_ad_log(
    workshop_id: int,
    sent_by: int,
    message: str,
    sent_count: int,
    media_type: str="text"
):
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO ad_logs
                (workshop_id, sent_by, message, sent_count, media_type)
            VALUES ($1, $2, $3, $4, $5)
            """,
            workshop_id, sent_by, message, sent_count, media_type
        )
        
        
async def set_order_urgent(order_id: int, is_urgent: bool):
    await _execute(
        "UPDATE orders SET is_urgent = $1 WHERE id = $2",
        is_urgent, order_id
    )


async def get_unbooked_orders(workshop_id: int) -> list[dict]:
    """
    Shoshilinch buyurtmalar BIRINCHI,
    keyin ketma-ketlik bo'yicha (picked_up_at ASC)
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                o.id            as order_id,
                o.client_note,
                o.is_urgent,
                u.full_name     as user_name,
                COUNT(c.id)     as carpet_count
            FROM orders o
            JOIN users u ON u.id = o.user_id
            JOIN carpets c ON c.order_id = o.id
            WHERE o.workshop_id = $1
            AND   c.status = 'in_progress'
            GROUP BY o.id, o.client_note, o.is_urgent,
                     o.picked_up_at, u.full_name
            HAVING COUNT(c.id) > 0
            ORDER BY
                o.is_urgent DESC,        -- shoshilinch birinchi
                o.picked_up_at ASC       -- keyin ketma-ketlik
            """,
            workshop_id
        )
        return [dict(r) for r in rows]