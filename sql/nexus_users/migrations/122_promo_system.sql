BEGIN;

-- Promo system: reusable creatives, time-based bookings, and metrics

-- Promos: reusable creative assets owned by users
CREATE TABLE promos (
    id          SERIAL PRIMARY KEY,
    owner_id    BIGINT NOT NULL REFERENCES users(id),
    promo_type  TEXT NOT NULL CHECK (promo_type IN ('placement', 'featured_post')),
    name        TEXT NOT NULL,
    title       TEXT,
    summary     TEXT,
    link        TEXT,
    content_html TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_promos_owner ON promos (owner_id);

-- Promo images: multiple size variants per placement promo
CREATE TABLE promo_images (
    id           SERIAL PRIMARY KEY,
    promo_id     INTEGER NOT NULL REFERENCES promos(id) ON DELETE CASCADE,
    slot_variant TEXT NOT NULL,
    image_path   TEXT NOT NULL,
    width        INTEGER NOT NULL,
    height       INTEGER NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (promo_id, slot_variant)
);

-- Promo bookings: time-based slot reservations
CREATE TABLE promo_bookings (
    id          SERIAL PRIMARY KEY,
    promo_id    INTEGER NOT NULL REFERENCES promos(id),
    user_id     BIGINT NOT NULL REFERENCES users(id),
    slot_type   TEXT NOT NULL CHECK (slot_type IN ('left', 'right', 'featured_post')),
    start_date  DATE NOT NULL,
    weeks       INTEGER NOT NULL CHECK (weeks >= 1 AND weeks <= 52),
    end_date    DATE NOT NULL,
    price       NUMERIC(10, 2) CHECK (price >= 0),
    currency    TEXT NOT NULL DEFAULT 'PED',
    status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'active', 'expired', 'cancelled')),
    admin_note  TEXT,
    approved_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_promo_bookings_active ON promo_bookings (slot_type, start_date, end_date) WHERE status = 'active';
CREATE INDEX idx_promo_bookings_promo ON promo_bookings (promo_id);
CREATE INDEX idx_promo_bookings_user ON promo_bookings (user_id);
CREATE INDEX idx_promo_bookings_status ON promo_bookings (status);

-- Promo metrics: daily aggregated views and clicks per booking
CREATE TABLE promo_metrics (
    id         SERIAL PRIMARY KEY,
    booking_id INTEGER NOT NULL REFERENCES promo_bookings(id) ON DELETE CASCADE,
    event_date DATE NOT NULL,
    views      INTEGER NOT NULL DEFAULT 0,
    clicks     INTEGER NOT NULL DEFAULT 0,
    UNIQUE (booking_id, event_date)
);

-- Permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON promos TO nexus_users;
GRANT USAGE, SELECT ON promos_id_seq TO nexus_users;

GRANT SELECT, INSERT, UPDATE, DELETE ON promo_images TO nexus_users;
GRANT USAGE, SELECT ON promo_images_id_seq TO nexus_users;

GRANT SELECT, INSERT, UPDATE, DELETE ON promo_bookings TO nexus_users;
GRANT USAGE, SELECT ON promo_bookings_id_seq TO nexus_users;

GRANT SELECT, INSERT, UPDATE, DELETE ON promo_metrics TO nexus_users;
GRANT USAGE, SELECT ON promo_metrics_id_seq TO nexus_users;

COMMIT;
