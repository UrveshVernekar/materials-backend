from sqlalchemy import text
from app.core.database import engine
from app.core.security import hash_password

def init_db():
    INIT_SQL = """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        first_name VARCHAR(100) NOT NULL,
        last_name VARCHAR(100) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        role VARCHAR(50) NOT NULL DEFAULT 'user',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );

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
        lead_time_qty NUMERIC(12,2) DEFAULT 0,
        delta INT DEFAULT 0,
        cov_in_days NUMERIC,
        branch_pend NUMERIC,
        pending_reorders NUMERIC DEFAULT 0,
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
        month1_prediction_days NUMERIC(12,2),
        month1_po NUMERIC(12,2),
        month1_po_days NUMERIC(12,2),
        month1_mes NUMERIC(12,2),
        month1_mes_days NUMERIC(12,2),
        month2_date DATE,
        month2_prediction NUMERIC(12,2),
        month2_prediction_days NUMERIC(12,2),
        month2_po NUMERIC(12,2),
        month2_po_days NUMERIC(12,2),
        month2_mes NUMERIC(12,2),
        month2_mes_days NUMERIC(12,2),
        month3_date DATE,
        month3_prediction NUMERIC(12,2),
        month3_prediction_days NUMERIC(12,2),
        month3_po NUMERIC(12,2),
        month3_po_days NUMERIC(12,2),
        month3_mes NUMERIC(12,2),
        month3_mes_days NUMERIC(12,2),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );


    CREATE TABLE IF NOT EXISTS purchase_orders (
        id              INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        material_code   VARCHAR(50) NOT NULL,
        po_number       VARCHAR(255) NOT NULL UNIQUE,
        order_qty       NUMERIC DEFAULT 0,
        receive_qty     NUMERIC DEFAULT 0,
        year            INT NOT NULL,
        month           INT NOT NULL CHECK (month BETWEEN 1 AND 12),
        period_date     DATE GENERATED ALWAYS AS (MAKE_DATE(year, month, 1)) STORED,
        user_id         INT REFERENCES users(id) ON DELETE SET NULL,
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

    CREATE TABLE IF NOT EXISTS material_checks (
        id SERIAL PRIMARY KEY,
        material_code VARCHAR(50) NOT NULL REFERENCES materials(material_code) ON DELETE CASCADE,
        user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        is_checked BOOLEAN NOT NULL DEFAULT TRUE,
        checked_at TIMESTAMPTZ DEFAULT NOW(),
        unchecked_at TIMESTAMPTZ DEFAULT NULL,
        UNIQUE(material_code, user_id)
    );

    CREATE INDEX IF NOT EXISTS idx_material_checks_code ON material_checks(material_code);
    CREATE INDEX IF NOT EXISTS idx_material_checks_user ON material_checks(user_id);

    CREATE TABLE IF NOT EXISTS ALTERNATIVE_PARTS (
        id                  INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        master_code         VARCHAR(50) NOT NULL,
        master_mat_desc     VARCHAR(255) NOT NULL,
        substitute          VARCHAR(255) NOT NULL UNIQUE,
        substitute_mat_desc VARCHAR(255) NOT NULL,
        created_at      TIMESTAMPTZ DEFAULT NOW(),
        updated_at      TIMESTAMPTZ DEFAULT NOW()
    );

    /* CREATE OR REPLACE FUNCTION trigger_set_timestamp()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    */
    
    DROP TRIGGER IF EXISTS set_substitute_master_updated_at ON alternative_parts;
    CREATE TRIGGER set_substitute_master_updated_at
        BEFORE UPDATE ON alternative_parts
        FOR EACH ROW
        EXECUTE FUNCTION trigger_set_timestamp();

    CREATE INDEX IF NOT EXISTS idx_alternative_material ON alternative_parts (substitute);
    -- CREATE INDEX IF NOT EXISTS idx_po_period   ON purchase_orders (year, month, material_code);
    -- CREATE INDEX IF NOT EXISTS idx_po_date     ON purchase_orders (period_date);


    -- Ensure all columns exist for existing deployments
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS product_category VARCHAR(200) DEFAULT NULL;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS product_status VARCHAR(100) DEFAULT NULL;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS vendor VARCHAR(200);
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS machine_population BIGINT;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS last_production_year INT;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS serv_per_left INT;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS inh NUMERIC;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS inh_s_obslte VARCHAR(50);
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS alt_token VARCHAR(50);
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS alt VARCHAR(50);
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS price NUMERIC(12,2);
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS moq INT;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS lead_time INT DEFAULT 0;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS lead_time_qty NUMERIC(12,2) DEFAULT 0;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS delta INT DEFAULT 0;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS cov_in_days NUMERIC;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS branch_pend NUMERIC;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS pending_reorders NUMERIC DEFAULT 0;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS no_trace_damage NUMERIC;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS po_balance NUMERIC;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS gpc_stk NUMERIC;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS gpc_free_stk NUMERIC;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS branch_stk NUMERIC;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS for_1_day_req NUMERIC;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS stk_in_alt_part NUMERIC;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS req_on_12m_avg NUMERIC;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS req_on_03m_avg NUMERIC;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS average NUMERIC;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS aging_more_than_120_days NUMERIC;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS blocked_code_in_aging VARCHAR(50);
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS remarks TEXT;
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
    ALTER TABLE materials ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

    ALTER TABLE material_monthly_data ADD COLUMN IF NOT EXISTS value_type VARCHAR(50) DEFAULT 'consumption';

    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS month1_date DATE;
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS month1_prediction NUMERIC(12,2);
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS month1_prediction_days NUMERIC(12,2);
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS month1_po NUMERIC(12,2);
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS month1_po_days NUMERIC(12,2);
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS month1_mes NUMERIC(12,2);
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS month1_mes_days NUMERIC(12,2);
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS month2_date DATE;
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS month2_prediction NUMERIC(12,2);
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS month2_prediction_days NUMERIC(12,2);
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS month2_po NUMERIC(12,2);
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS month2_po_days NUMERIC(12,2);
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS month2_mes NUMERIC(12,2);
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS month2_mes_days NUMERIC(12,2);
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS month3_date DATE;
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS month3_prediction NUMERIC(12,2);
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS month3_prediction_days NUMERIC(12,2);
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS month3_po NUMERIC(12,2);
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS month3_po_days NUMERIC(12,2);
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS month3_mes NUMERIC(12,2);
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS month3_mes_days NUMERIC(12,2);
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
    ALTER TABLE consumption_prediction ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

    ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS user_id INT REFERENCES users(id) ON DELETE SET NULL;
    """

    
    with engine.begin() as conn:
        conn.execute(text(INIT_SQL))
        
        # Seed default admin user if not exists
        admin_email = "spares_admin@ifbglobal.com"
        result = conn.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": admin_email}
        ).fetchone()
        
        if not result:
            hashed = hash_password("admin1234$#")
            conn.execute(
                text("INSERT INTO users (first_name, last_name, email, password_hash, role) VALUES (:first_name, :last_name, :email, :password_hash, :role)"),
                {
                    "first_name": "Spares",
                    "last_name": "Admin",
                    "email": admin_email,
                    "password_hash": hashed,
                    "role": "admin"
                }
            )
