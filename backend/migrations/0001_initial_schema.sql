-- Schema inicial Postgres do Prime Encontros (migrado do MongoDB em 2026-07-12).
-- Ver .ai/context/ARCHITECTURE.md e .ai/context/CONTRACTS.md pro racional.
-- Design aprovado em revisão — não alterar sem repetir o processo de design.

CREATE TABLE users (
    user_id     TEXT PRIMARY KEY,
    email       TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    picture     TEXT NOT NULL DEFAULT '',
    is_admin    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_sessions (
    session_token TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    expires_at    TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id);

CREATE TABLE massagistas (
    id                          TEXT PRIMARY KEY,
    owner_user_id               TEXT UNIQUE REFERENCES users(user_id) ON DELETE SET NULL,
    name                        TEXT NOT NULL,
    bairro                      TEXT NOT NULL,
    bairro_slug                 TEXT NOT NULL,
    lat                         DOUBLE PRECISION NOT NULL,
    lng                         DOUBLE PRECISION NOT NULL,
    rating                      DOUBLE PRECISION NOT NULL DEFAULT 0,
    reviews                     INTEGER NOT NULL DEFAULT 0,
    bio                         TEXT NOT NULL DEFAULT '',
    specialties                 TEXT[] NOT NULL DEFAULT '{}',
    hourly_rate                 NUMERIC(10,2) NOT NULL,
    price_60                    NUMERIC(10,2) NOT NULL,
    price_90                    NUMERIC(10,2) NOT NULL,
    price_120                   NUMERIC(10,2) NOT NULL,
    main_image                  TEXT NOT NULL DEFAULT '',
    gallery                     TEXT[] NOT NULL DEFAULT '{}',
    video_url                   TEXT NOT NULL DEFAULT '',
    video_thumb                 TEXT NOT NULL DEFAULT '',
    experience_years            INTEGER NOT NULL DEFAULT 0,
    languages                   TEXT[] NOT NULL DEFAULT '{}',
    ddd                         TEXT NOT NULL DEFAULT '',
    phone                       TEXT NOT NULL DEFAULT '',
    verified                    BOOLEAN NOT NULL DEFAULT FALSE,
    verification_status         TEXT NOT NULL DEFAULT 'pending'
                                 CHECK (verification_status IN ('pending','verified','rejected')),
    verification_id_check       BOOLEAN NOT NULL DEFAULT FALSE,
    verification_photo_check    BOOLEAN NOT NULL DEFAULT FALSE,
    verification_address_check  BOOLEAN NOT NULL DEFAULT FALSE,
    verification_verified_at    TIMESTAMPTZ,
    verification_verified_by    TEXT,
    verification_notes          TEXT,
    is_deleted                  BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_by                  TEXT,
    deleted_at                  TIMESTAMPTZ,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_massagistas_bairro_slug ON massagistas(bairro_slug);
CREATE INDEX idx_massagistas_verified    ON massagistas(verified);
CREATE INDEX idx_massagistas_is_deleted  ON massagistas(is_deleted);

-- Sem FK de payment_session_id ainda (payment_transactions só existe depois) —
-- fechada no fim deste arquivo via ALTER TABLE.
CREATE TABLE bookings (
    id                    TEXT PRIMARY KEY,
    user_id               TEXT NOT NULL REFERENCES users(user_id),
    user_email            TEXT NOT NULL,
    massagista_id         TEXT NOT NULL REFERENCES massagistas(id) ON DELETE RESTRICT,
    massagista_name       TEXT NOT NULL,
    massagista_image      TEXT NOT NULL DEFAULT '',
    bairro                TEXT NOT NULL,
    date                  DATE NOT NULL,
    time                  TIME NOT NULL,
    duration              INTEGER NOT NULL CHECK (duration IN (60, 90, 120)),
    location_type         TEXT NOT NULL CHECK (location_type IN ('studio','home')),
    address               TEXT,
    notes                 TEXT,
    amount                NUMERIC(10,2) NOT NULL,
    currency              TEXT NOT NULL DEFAULT 'brl',
    status                TEXT NOT NULL DEFAULT 'pending_payment'
                          CHECK (status IN ('pending_payment','confirmed','cancelled','completed')),
    payment_session_id    TEXT,
    payment_method        TEXT CHECK (payment_method IN ('whatsapp','pix','cash','manual') OR payment_method IS NULL),
    manual_confirmed_by   TEXT,
    manual_confirmed_at   TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_bookings_user_id            ON bookings(user_id);
CREATE INDEX idx_bookings_massagista_id      ON bookings(massagista_id);
CREATE INDEX idx_bookings_status             ON bookings(status);
CREATE INDEX idx_bookings_payment_session_id ON bookings(payment_session_id);

CREATE TABLE payment_transactions (
    session_id      TEXT PRIMARY KEY,
    booking_id      TEXT NOT NULL REFERENCES bookings(id) ON DELETE RESTRICT,
    user_id         TEXT NOT NULL REFERENCES users(user_id),
    user_email      TEXT NOT NULL,
    amount          NUMERIC(10,2) NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'brl',
    status          TEXT NOT NULL DEFAULT 'initiated',
    payment_status  TEXT NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_payment_transactions_booking_id ON payment_transactions(booking_id);

ALTER TABLE bookings
    ADD CONSTRAINT fk_bookings_payment_session
    FOREIGN KEY (payment_session_id)
    REFERENCES payment_transactions(session_id)
    ON DELETE SET NULL;

CREATE TABLE reviews (
    id             TEXT PRIMARY KEY,
    booking_id     TEXT NOT NULL UNIQUE REFERENCES bookings(id),
    massagista_id  TEXT NOT NULL REFERENCES massagistas(id) ON DELETE RESTRICT,
    user_id        TEXT NOT NULL REFERENCES users(user_id),
    user_name      TEXT NOT NULL,
    user_picture   TEXT NOT NULL DEFAULT '',
    rating         INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment        TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_reviews_massagista_id ON reviews(massagista_id);

CREATE TABLE whatsapp_clicks (
    id              TEXT PRIMARY KEY,
    massagista_id   TEXT NOT NULL REFERENCES massagistas(id) ON DELETE RESTRICT,
    massagista_name TEXT NOT NULL,
    user_id         TEXT REFERENCES users(user_id),
    user_email      TEXT,
    user_name       TEXT,
    source          TEXT NOT NULL DEFAULT 'detail',
    user_agent      TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_whatsapp_clicks_massagista_id ON whatsapp_clicks(massagista_id);
CREATE INDEX idx_whatsapp_clicks_created_at    ON whatsapp_clicks(created_at);

CREATE TABLE profile_views (
    id             TEXT PRIMARY KEY,
    massagista_id  TEXT NOT NULL REFERENCES massagistas(id) ON DELETE RESTRICT,
    user_id        TEXT REFERENCES users(user_id),
    user_agent     TEXT NOT NULL DEFAULT '',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_profile_views_massagista_id ON profile_views(massagista_id);
CREATE INDEX idx_profile_views_created_at    ON profile_views(created_at);

CREATE TABLE files (
    id                 TEXT PRIMARY KEY,
    massagista_id      TEXT NOT NULL REFERENCES massagistas(id) ON DELETE RESTRICT,
    kind               TEXT NOT NULL CHECK (kind IN ('image','video')),
    storage_path       TEXT NOT NULL UNIQUE,
    content_type       TEXT NOT NULL,
    size               INTEGER NOT NULL,
    original_filename  TEXT,
    uploaded_by        TEXT NOT NULL,
    is_deleted         BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_by         TEXT,
    deleted_at         TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_files_massagista_id ON files(massagista_id);
