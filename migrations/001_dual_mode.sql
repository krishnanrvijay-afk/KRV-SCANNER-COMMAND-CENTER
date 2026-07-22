-- ============================================================
-- Dual-mode regime: Supabase schema additions
-- Run this in your Supabase SQL editor (or via psql)
-- Safe to run multiple times (IF NOT EXISTS throughout)
-- ============================================================

-- ─── 1. venue_live_state ─────────────────────────────────────
-- Written every 30s by each scanner when it processes BTC.
-- Primary key is venue (HL / MEXC / BYBIT).
CREATE TABLE IF NOT EXISTS venue_live_state (
    venue                TEXT        PRIMARY KEY,       -- 'HL', 'MEXC', 'BYBIT'
    regime               TEXT        NOT NULL DEFAULT 'RANGING',  -- BULL_TREND | BEAR_TREND | RANGING
    regime_confidence    TEXT        NOT NULL DEFAULT 'HIGH',     -- HIGH | MEDIUM | LOW
    btc_j1h              NUMERIC(7,2) NOT NULL DEFAULT 50.0,
    btc_momentum_5c      NUMERIC(10,2) NOT NULL DEFAULT 0.0,      -- sum of last 5 closed BTC 1m candle bodies
    btc_candle_velocity  NUMERIC(10,2) NOT NULL DEFAULT 0.0,      -- current 1m candle body (close-open)
    open_longs           INT         NOT NULL DEFAULT 0,
    open_shorts          INT         NOT NULL DEFAULT 0,
    daily_pnl_usd        NUMERIC(12,4) NOT NULL DEFAULT 0.0,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed rows so upserts always land on an existing row
INSERT INTO venue_live_state (venue) VALUES ('HL'), ('MEXC'), ('BYBIT')
ON CONFLICT (venue) DO NOTHING;

-- ─── 2. venue_settings ───────────────────────────────────────
-- Per-venue configurable scanner parameters.
-- Scanners read these at startup and every 60s thereafter.
CREATE TABLE IF NOT EXISTS venue_settings (
    venue                TEXT        PRIMARY KEY,
    paper_mode           BOOLEAN     NOT NULL DEFAULT TRUE,
    leverage             INT         NOT NULL DEFAULT 5,
    margin_per_trade_usd NUMERIC(10,2) NOT NULL DEFAULT 250.0,
    max_open_positions   INT         NOT NULL DEFAULT 5,
    -- Regime-aware entry thresholds
    j15m_trend_long_max  NUMERIC(5,1) NOT NULL DEFAULT 35.0,   -- BULL_TREND LONG: j15m < this
    j15m_trend_short_min NUMERIC(5,1) NOT NULL DEFAULT 65.0,   -- BEAR_TREND SHORT: j15m > this
    j15m_bounce_long_max NUMERIC(5,1) NOT NULL DEFAULT 20.0,   -- RANGING LONG: j15m < this
    j15m_bounce_short_min NUMERIC(5,1) NOT NULL DEFAULT 80.0,  -- RANGING SHORT: j15m > this
    -- Regime classifier thresholds
    regime_j1h_bull_min  NUMERIC(5,1) NOT NULL DEFAULT 60.0,   -- J1H floor for BULL_TREND
    regime_j1h_bear_max  NUMERIC(5,1) NOT NULL DEFAULT 40.0,   -- J1H ceiling for BEAR_TREND
    regime_mom5c_bull    NUMERIC(8,1) NOT NULL DEFAULT 100.0,  -- 5c momentum floor for BULL
    regime_mom5c_bear    NUMERIC(8,1) NOT NULL DEFAULT -100.0, -- 5c momentum ceiling for BEAR
    -- Kill switches
    halt_long            BOOLEAN     NOT NULL DEFAULT FALSE,
    halt_short           BOOLEAN     NOT NULL DEFAULT FALSE,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO venue_settings (venue) VALUES ('HL'), ('MEXC'), ('BYBIT')
ON CONFLICT (venue) DO NOTHING;

-- ─── 3. platform_settings ────────────────────────────────────
-- Global key-value store for command center settings.
CREATE TABLE IF NOT EXISTS platform_settings (
    key          TEXT        PRIMARY KEY,
    value        TEXT        NOT NULL,
    description  TEXT,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO platform_settings (key, value, description) VALUES
    ('telegram_alerts',   'true',   'Global Telegram alert toggle'),
    ('emergency_halt',    'false',  'Hard stop all venues when true'),
    ('paper_mode_global', 'true',   'Force paper mode on all venues regardless of venue_settings'),
    ('live_go_date',      '',       'ISO date when paper→live switch is planned (display only)')
ON CONFLICT (key) DO NOTHING;

-- ─── 4. Add trade_mode + regime columns to trade tables ──────
-- Only adds if columns don't exist (safe on re-run).
DO $$
BEGIN
    -- hl_trades
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'hl_trades') THEN
        IF NOT EXISTS (SELECT FROM information_schema.columns
                       WHERE table_name = 'hl_trades' AND column_name = 'trade_mode') THEN
            ALTER TABLE hl_trades ADD COLUMN trade_mode TEXT DEFAULT 'bounce';
        END IF;
        IF NOT EXISTS (SELECT FROM information_schema.columns
                       WHERE table_name = 'hl_trades' AND column_name = 'regime') THEN
            ALTER TABLE hl_trades ADD COLUMN regime TEXT DEFAULT 'RANGING';
        END IF;
    END IF;

    -- mexc_trades (or whatever your MEXC trade table is named)
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'mexc_trades') THEN
        IF NOT EXISTS (SELECT FROM information_schema.columns
                       WHERE table_name = 'mexc_trades' AND column_name = 'trade_mode') THEN
            ALTER TABLE mexc_trades ADD COLUMN trade_mode TEXT DEFAULT 'bounce';
        END IF;
        IF NOT EXISTS (SELECT FROM information_schema.columns
                       WHERE table_name = 'mexc_trades' AND column_name = 'regime') THEN
            ALTER TABLE mexc_trades ADD COLUMN regime TEXT DEFAULT 'RANGING';
        END IF;
    END IF;
END $$;

-- Done.
