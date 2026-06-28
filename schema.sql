-- ============================================================
-- O'CHIRISH (tozalash uchun)
-- ============================================================
DROP TABLE IF EXISTS bot_logs              CASCADE;
DROP TABLE IF EXISTS expenses              CASCADE;
DROP TABLE IF EXISTS worker_payments       CASCADE;
DROP TABLE IF EXISTS client_payment_logs   CASCADE;
DROP TABLE IF EXISTS client_payments       CASCADE;
DROP TABLE IF EXISTS carpets               CASCADE;
DROP TABLE IF EXISTS orders                CASCADE;
DROP TABLE IF EXISTS user_workshops        CASCADE;
DROP TABLE IF EXISTS users                 CASCADE;
DROP TABLE IF EXISTS workshops             CASCADE;
DROP TABLE IF EXISTS super_admins          CASCADE;

DROP TYPE IF EXISTS worker_payment_status  CASCADE;
DROP TYPE IF EXISTS payment_status         CASCADE;
DROP TYPE IF EXISTS carpet_status          CASCADE;
DROP TYPE IF EXISTS order_status           CASCADE;
DROP TYPE IF EXISTS user_role              CASCADE;


-- ============================================================
-- ENUM TURLARI
-- ============================================================

-- Foydalanuvchi rollari
CREATE TYPE user_role AS ENUM (
    'super_admin',           -- tizim egasi
    'admin',                 -- sex boshqaruvchisi
    'worker',                -- gilam yuvuvchi ishchi
    'admin_worker',          -- ham admin ham ishchi
    'super_mini_admin_worker',-- barcha roldagi maxsus foydalanuvchi
    'user'                   -- oddiy buyurtmachi
);

-- Buyurtma holatlari
CREATE TYPE order_status AS ENUM (
    'pending',    -- yuborildi, admin tasdiqlamagan
    'confirmed',  -- admin tasdiqladi
    'picked_up',  -- gilamlar olib kelinidi
    'cancelled'   -- bekor qilindi
);

-- Gilam holatlari
CREATE TYPE carpet_status AS ENUM (
    'in_progress', -- keltirildi, ishchi bron qilmagan
    'booked',      -- ishchi bron qildi
    'washed',      -- yuvildi, yetkazilmagan
    'delivered'    -- mijozga yetkazildi
);

-- Mijoz to'lov holatlari
CREATE TYPE payment_status AS ENUM (
    'unpaid',   -- umuman to'lanmagan
    'partial',  -- qisman to'langan
    'paid'      -- to'liq to'langan
);

-- Ishchi to'lov holatlari
CREATE TYPE worker_payment_status AS ENUM (
    'pending',    -- ishchi hali so'rov yubormagam
    'requested',  -- ishchi so'rov yubordi
    'approved',   -- admin tasdiqladi
    'rejected',   -- admin rad etdi
    'paid'        -- pul berildi
);


-- ============================================================
-- SUPER ADMIN
-- Bot: /start bosqanda super_admin ekanligini tekshiradi
-- Dashboard: super_admin login uchun ishlatilmaydi
--            (.env da login/parol saqlanadi)
-- ============================================================
CREATE TABLE super_admins (
    id         BIGSERIAL    PRIMARY KEY,
    tg_id      BIGINT       UNIQUE NOT NULL,  -- Telegram ID
    full_name  VARCHAR(255),
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Birinchi super admin
INSERT INTO super_admins (tg_id, full_name)
VALUES (6563817580, 'Bosh Admin');


-- ============================================================
-- WORKSHOPS (Sexlar)
-- Bot: token orqali foydalanuvchini sexga bog'laydi
--      admin panel uchun workshop_id ishlatiladi
-- Dashboard: admin login qilganda workshop_id va parol tekshiriladi
--            narxlarni o'zgartirish, token ko'rish
-- ============================================================
CREATE TABLE workshops (
    id                   BIGSERIAL     PRIMARY KEY,
    name                 VARCHAR(255)  NOT NULL,
    token                VARCHAR(100)  UNIQUE NOT NULL, -- havola uchun
    password_hash        VARCHAR(255)  NOT NULL,        -- bcrypt hash
    is_active            BOOLEAN       NOT NULL DEFAULT true,
    price_per_m2         NUMERIC(10,2) NOT NULL DEFAULT 8000,  -- mijozdan olinadigan narx
    default_worker_price NUMERIC(10,2) NOT NULL DEFAULT 1500,  -- ishchiga beriladigan narx
    confirm_timeout_sec  INTEGER       NOT NULL DEFAULT 300,   -- buyurtma muddati (sekund)
    created_at           TIMESTAMPTZ   NOT NULL DEFAULT now()
);


-- ============================================================
-- USERS (Foydalanuvchilar)
-- Bot: /start bosqanda yaratiladi yoki topiladi
--      is_active=false bo'lsa botda bloklangan
-- Dashboard: mijozlar, ishchilar ro'yxatida ko'rinadi
-- ============================================================
CREATE TABLE users (
    id         BIGSERIAL    PRIMARY KEY,
    tg_id      BIGINT       UNIQUE NOT NULL,  -- Telegram ID
    full_name  VARCHAR(255),
    phone      VARCHAR(20),                   -- kontakt ulashganda saqlanadi
    is_active  BOOLEAN      NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);


-- ============================================================
-- USER_WORKSHOPS (Kim qaysi sexda)
-- Bot: middleware da user roli va sexi aniqlanadi
--      is_active=false bo'lsa o'sha sexda bloklangan
-- Dashboard: ishchilarni bloklash, admin/ishchi qo'shish/o'chirish
--            individual ishchi narxini o'zgartirish
-- ============================================================
CREATE TABLE user_workshops (
    id                  BIGSERIAL     PRIMARY KEY,
    user_id             BIGINT        NOT NULL REFERENCES users(id)     ON DELETE CASCADE,
    workshop_id         BIGINT        NOT NULL REFERENCES workshops(id)  ON DELETE CASCADE,
    role                user_role     NOT NULL DEFAULT 'user',
    worker_price_per_m2 NUMERIC(10,2),        -- NULL bo'lsa default_worker_price ishlatiladi
    is_active           BOOLEAN       NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE(user_id, workshop_id)
);


-- ============================================================
-- ORDERS (Buyurtmalar)
-- Bot: user buyurtma beradi -> pending
--      admin tasdiqlaydi -> confirmed
--      admin olib kelindi bosadi -> picked_up
-- Dashboard: buyurtmalar ro'yxati, filter, tahrirlash, o'chirish
-- ============================================================
CREATE TABLE orders (
    id               BIGSERIAL     PRIMARY KEY,
    workshop_id      BIGINT        NOT NULL REFERENCES workshops(id),
    user_id          BIGINT        NOT NULL REFERENCES users(id),
    phone            VARCHAR(20)   NOT NULL,
    location_lat     NUMERIC(10,7),           -- xarita uchun
    location_lon     NUMERIC(10,7),
    address_text     TEXT,
    pickup_time_note TEXT          NOT NULL,   -- qachon borish
    extra_note       TEXT,                     -- qo'shimcha izoh
    carpet_count     SMALLINT      CHECK(carpet_count > 0),
    client_note      TEXT,                     -- mijoz laqabi/xususiyati
    status           order_status  NOT NULL DEFAULT 'pending',
    confirmed_at     TIMESTAMPTZ,
    picked_up_at     TIMESTAMPTZ,
    expires_at       TIMESTAMPTZ   NOT NULL,   -- bu vaqtgacha admin tasdiqlamasa bekor
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT now()
);


-- ============================================================
-- CARPETS (Gilamlar)
-- Bot: pickup_order -> gilamlar yaratiladi (in_progress)
--      ishchi bron qiladi -> booked
--      ishchi yuvildi bosadi -> washed (o'lchamlar saqlanadi)
--      admin yetkazildi bosadi -> delivered
-- Dashboard: gilamlar ro'yxati, status, kim yuvdi
-- ============================================================
CREATE TABLE carpets (
    id                  BIGSERIAL     PRIMARY KEY,
    workshop_id         BIGINT        NOT NULL REFERENCES workshops(id),
    order_id            BIGINT        NOT NULL REFERENCES orders(id),
    worker_id           BIGINT        REFERENCES users(id) ON DELETE SET NULL,
    dimensions_raw      TEXT,                     -- "2*3, 3.5*4" xom matn
    total_area_m2       INTEGER       CHECK(total_area_m2 > 0),
    price_per_m2        NUMERIC(10,2),             -- yuvilgan paytdagi snapshot
    worker_price_per_m2 NUMERIC(10,2),             -- ishchi narxi snapshot
    discount_percent    NUMERIC(5,2)  DEFAULT 0,   -- chegirma foizi
    status              carpet_status NOT NULL DEFAULT 'in_progress',
    booked_at           TIMESTAMPTZ,
    washed_at           TIMESTAMPTZ,
    delivered_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT now()
);


-- ============================================================
-- CLIENT_PAYMENTS (Mijoz to'lovlari)
-- Bot: pickup_order da yaratiladi (total_amount=0)
--      ishchi yuvildi bosanda total_amount yangilanadi
--      admin yetkazildi bosanda to'lov kiritiladi
-- Dashboard: to'lovlar ro'yxati, to'lov kiritish, qarz muddati
-- ============================================================
CREATE TABLE client_payments (
    id           BIGSERIAL      PRIMARY KEY,
    workshop_id  BIGINT         NOT NULL REFERENCES workshops(id),
    order_id     BIGINT         NOT NULL REFERENCES orders(id) UNIQUE,
    total_amount NUMERIC(12,2)  NOT NULL DEFAULT 0,  -- chegirmadan keyin
    paid_amount  NUMERIC(12,2)  NOT NULL DEFAULT 0,
    debt_amount  NUMERIC(12,2)  GENERATED ALWAYS AS (total_amount - paid_amount) STORED,
    status       payment_status NOT NULL DEFAULT 'unpaid',
    debt_note    TEXT,          -- qarz muddati (masalan "3 kun ichida")
    paid_at      TIMESTAMPTZ,
    created_at   TIMESTAMPTZ    NOT NULL DEFAULT now()
);


-- ============================================================
-- CLIENT_PAYMENT_LOGS (To'lov logi)
-- Bot: to'lov qo'shilganda yoziladi
-- Dashboard: kirim ro'yxatida ko'rinadi
-- ============================================================
CREATE TABLE client_payment_logs (
    id         BIGSERIAL     PRIMARY KEY,
    payment_id BIGINT        NOT NULL REFERENCES client_payments(id),
    amount     NUMERIC(12,2) NOT NULL CHECK(amount > 0),
    note       TEXT,
    created_by BIGINT        REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ   NOT NULL DEFAULT now()
);


-- ============================================================
-- WORKER_PAYMENTS (Ishchi to'lovlari)
-- Bot: ishchi yuvildi bosanda yaratiladi
--      ishchi "adminga so'rov" bosanda -> requested
--      admin tasdiqlasa -> paid
--      admin rad etsa -> rejected, gilam qayta in_progress
-- Dashboard: ish haqi so'rovlari, tasdiqlash, rad etish
-- ============================================================
CREATE TABLE worker_payments (
    id                  BIGSERIAL             PRIMARY KEY,
    workshop_id         BIGINT                NOT NULL REFERENCES workshops(id),
    worker_id           BIGINT                NOT NULL REFERENCES users(id),
    order_id            BIGINT                NOT NULL REFERENCES orders(id),
    area_m2             INTEGER               NOT NULL CHECK(area_m2 > 0),
    worker_price_per_m2 NUMERIC(10,2)         NOT NULL,
    total_amount        NUMERIC(12,2)         GENERATED ALWAYS AS
                        (area_m2 * worker_price_per_m2) STORED,
    status              worker_payment_status NOT NULL DEFAULT 'pending',
    reject_reason       TEXT,                 -- rad etilgan sabab
    requested_at        TIMESTAMPTZ,
    approved_at         TIMESTAMPTZ,
    rejected_at         TIMESTAMPTZ,
    paid_at             TIMESTAMPTZ,
    created_at          TIMESTAMPTZ           NOT NULL DEFAULT now(),
    UNIQUE(order_id, worker_id)
);


-- ============================================================
-- EXPENSES (Xarajatlar)
-- Bot: ishlatilmaydi
-- Dashboard: admin xarajat qo'shadi, kirim-chiqim sahifasida
--            chiqim tabida ko'rinadi, sof foyda hisoblanadi
-- ============================================================
CREATE TABLE expenses (
    id          BIGSERIAL     PRIMARY KEY,
    workshop_id BIGINT        NOT NULL REFERENCES workshops(id),
    amount      NUMERIC(12,2) NOT NULL CHECK(amount > 0),
    category    VARCHAR(100)  NOT NULL,  -- yoqilg'i, ta'mirlash va h.k.
    note        TEXT,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now()
);


-- ============================================================
-- BOT_LOGS (Bot logi)
-- Bot: muhim harakatlar loglanadi
-- Dashboard: hozircha ko'rsatilmaydi, debug uchun
-- ============================================================
CREATE TABLE bot_logs (
    id          BIGSERIAL   PRIMARY KEY,
    tg_id       BIGINT,
    workshop_id BIGINT      REFERENCES workshops(id),
    action      VARCHAR(100) NOT NULL,
    details     TEXT,
    is_error    BOOLEAN      NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);


-- ============================================================
-- INDEXLAR (Tezlashtirish uchun)
-- ============================================================
CREATE INDEX idx_users_tg_id              ON users(tg_id);
CREATE INDEX idx_uw_user                  ON user_workshops(user_id);
CREATE INDEX idx_uw_workshop              ON user_workshops(workshop_id);
CREATE INDEX idx_uw_role                  ON user_workshops(role);
CREATE INDEX idx_uw_active                ON user_workshops(is_active);
CREATE INDEX idx_orders_workshop          ON orders(workshop_id);
CREATE INDEX idx_orders_user              ON orders(user_id);
CREATE INDEX idx_orders_status            ON orders(status);
CREATE INDEX idx_orders_expires           ON orders(expires_at) WHERE status = 'pending';
CREATE INDEX idx_carpets_order            ON carpets(order_id);
CREATE INDEX idx_carpets_workshop         ON carpets(workshop_id);
CREATE INDEX idx_carpets_worker           ON carpets(worker_id);
CREATE INDEX idx_carpets_status           ON carpets(status);
CREATE INDEX idx_client_payments_order    ON client_payments(order_id);
CREATE INDEX idx_client_payments_workshop ON client_payments(workshop_id);
CREATE INDEX idx_client_payments_debt     ON client_payments(workshop_id) WHERE debt_amount > 0;
CREATE INDEX idx_worker_payments_order    ON worker_payments(order_id);
CREATE INDEX idx_worker_payments_worker   ON worker_payments(worker_id);
CREATE INDEX idx_worker_payments_status   ON worker_payments(status);
CREATE INDEX idx_workshops_token          ON workshops(token);
CREATE INDEX idx_bot_logs_tg              ON bot_logs(tg_id);
CREATE INDEX idx_bot_logs_created         ON bot_logs(created_at);
CREATE INDEX idx_expenses_workshop        ON expenses(workshop_id);
CREATE INDEX idx_cpl_payment              ON client_payment_logs(payment_id);


-- ============================================================
-- TRIGGERLAR
-- ============================================================

-- Order status vaqtlari
CREATE OR REPLACE FUNCTION trg_order_timestamps()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status = 'confirmed' AND OLD.status = 'pending' THEN
        NEW.confirmed_at = now();
    END IF;
    IF NEW.status = 'picked_up' AND OLD.status = 'confirmed' THEN
        NEW.picked_up_at = now();
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_order_ts
    BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION trg_order_timestamps();

-- Carpet status vaqtlari
CREATE OR REPLACE FUNCTION trg_carpet_timestamps()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status = 'booked'    AND OLD.status = 'in_progress' THEN NEW.booked_at    = now(); END IF;
    IF NEW.status = 'washed'    AND OLD.status = 'booked'      THEN NEW.washed_at    = now(); END IF;
    IF NEW.status = 'delivered' AND OLD.status = 'washed'      THEN NEW.delivered_at = now(); END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_carpet_ts
    BEFORE UPDATE ON carpets
    FOR EACH ROW EXECUTE FUNCTION trg_carpet_timestamps();

-- Worker payment status vaqtlari
CREATE OR REPLACE FUNCTION trg_wp_timestamps()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status = 'requested' AND OLD.status = 'pending'   THEN NEW.requested_at = now(); END IF;
    IF NEW.status = 'approved'  AND OLD.status = 'requested' THEN NEW.approved_at  = now(); END IF;
    IF NEW.status = 'rejected'  AND OLD.status = 'requested' THEN NEW.rejected_at  = now(); END IF;
    IF NEW.status = 'paid'      AND OLD.status IN ('approved','requested') THEN NEW.paid_at = now(); END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_wp_ts
    BEFORE UPDATE ON worker_payments
    FOR EACH ROW EXECUTE FUNCTION trg_wp_timestamps();

-- Client payment status avtomatik yangilash
-- Dashboard to'lov kiritganda va bot to'lov kiritganda ikkalasida ishlaydi
CREATE OR REPLACE FUNCTION trg_client_payment_status()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.total_amount > 0 AND NEW.paid_amount >= NEW.total_amount THEN
        NEW.status  = 'paid';
        NEW.paid_at = now();
    ELSIF NEW.paid_amount > 0 THEN
        NEW.status = 'partial';
    ELSE
        NEW.status = 'unpaid';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_client_payment_st
    BEFORE UPDATE ON client_payments
    FOR EACH ROW EXECUTE FUNCTION trg_client_payment_status();

-- Muddati o'tgan buyurtmalarni bekor qilish funksiyasi
-- pg_cron yoki botdan har daqiqa chaqiriladi
CREATE OR REPLACE FUNCTION cancel_expired_orders()
RETURNS INTEGER LANGUAGE plpgsql AS $$
DECLARE
    cnt INTEGER;
BEGIN
    WITH updated AS (
        UPDATE orders SET status = 'cancelled'
        WHERE status = 'pending' AND expires_at < now()
        RETURNING id
    )
    SELECT COUNT(*) INTO cnt FROM updated;
    RETURN cnt;
END;
$$;