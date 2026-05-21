from sqlalchemy import text
from app.core.database import engine

def init_db():
    INIT_SQL = """
    CREATE TABLE IF NOT EXISTS materials (
        material_id SERIAL PRIMARY KEY,
        material_code VARCHAR(50) UNIQUE NOT NULL,
        material_description TEXT,
        product_category VARCHAR(200) DEFAULT NULL,
        product_status VARCHAR(100) DEFAULT NULL,
        vendor VARCHAR(200),
        machine_population BIGINT,
        last_production_year INT,
        serv_per_left INT,
        inh NUMERIC,
        inh_s_obslte VARCHAR(50),
        alt_token VARCHAR(50),
        alt VARCHAR(50),
        price NUMERIC(12,2),
        moq INT,
        lead_time INT DEFAULT 0,
        delta INT DEFAULT 0,
        cov_in_days NUMERIC,
        branch_pend NUMERIC,
        no_trace_damage NUMERIC,
        po_balance NUMERIC,
        gpc_stk NUMERIC,
        gpc_free_stk NUMERIC,
        branch_stk NUMERIC,
        for_1_day_req NUMERIC,
        stk_in_alt_part NUMERIC,
        req_on_12m_avg NUMERIC,
        req_on_03m_avg NUMERIC,
        average NUMERIC,
        aging_more_than_120_days NUMERIC,
        blocked_code_in_aging VARCHAR(50),
        remarks TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_materials_code ON materials(material_code);

    CREATE TABLE IF NOT EXISTS material_monthly_data (
        id SERIAL PRIMARY KEY,
        material_code VARCHAR(50) NOT NULL REFERENCES materials(material_code) ON DELETE CASCADE,
        year INT NOT NULL,                    -- e.g. 2025
        month INT NOT NULL CHECK (month BETWEEN 1 AND 12),  -- 1=Jan, 4=Apr, etc.
        period_date DATE GENERATED ALWAYS AS (MAKE_DATE(year, month, 1)) STORED,  -- for easy querying
        consumption NUMERIC,                  -- Apr-25, May-25, ... values
        value_type VARCHAR(50) DEFAULT 'consumption',  -- 'consumption', 'stock', 'po', etc. if you want to store more
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(material_code, year, month, value_type)
    );

    CREATE INDEX IF NOT EXISTS idx_monthly_material ON material_monthly_data(material_code);
    CREATE INDEX IF NOT EXISTS idx_monthly_date ON material_monthly_data(year, month);

    CREATE TABLE IF NOT EXISTS consumption_prediction (
        material_code VARCHAR(50) PRIMARY KEY REFERENCES materials(material_code) ON DELETE CASCADE,
        month1_date DATE,
        month1_prediction NUMERIC(12,2),
        month2_date DATE,
        month2_prediction NUMERIC(12,2),
        month3_date DATE,
        month3_prediction NUMERIC(12,2),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );


    CREATE TABLE IF NOT EXISTS purchase_orders (
        id              INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        material_code   VARCHAR(50) NOT NULL REFERENCES materials(material_code),
        po_number       VARCHAR(255) NOT NULL UNIQUE,
        order_qty       NUMERIC DEFAULT 0,
        receive_qty     NUMERIC DEFAULT 0,
        year            INT NOT NULL,
        month           INT NOT NULL CHECK (month BETWEEN 1 AND 12),
        period_date     DATE GENERATED ALWAYS AS (MAKE_DATE(year, month, 1)) STORED,
        created_at      TIMESTAMPTZ DEFAULT NOW(),
        updated_at      TIMESTAMPTZ DEFAULT NOW(),

        CHECK (receive_qty <= order_qty)
    );

    CREATE OR REPLACE FUNCTION trigger_set_timestamp()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS set_purchase_orders_updated_at ON purchase_orders;
    CREATE TRIGGER set_purchase_orders_updated_at
        BEFORE UPDATE ON purchase_orders
        FOR EACH ROW
        EXECUTE FUNCTION trigger_set_timestamp();

    CREATE INDEX IF NOT EXISTS idx_po_material ON purchase_orders (material_code);
    CREATE INDEX IF NOT EXISTS idx_po_period   ON purchase_orders (year, month, material_code);
    CREATE INDEX IF NOT EXISTS idx_po_date     ON purchase_orders (period_date);

    """
    
    with engine.begin() as conn:
        conn.execute(text(INIT_SQL))
