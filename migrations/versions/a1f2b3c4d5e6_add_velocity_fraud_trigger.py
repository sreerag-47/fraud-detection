"""add_velocity_fraud_trigger

Revision ID: a1f2b3c4d5e6
Revises: 834f845b35d1
Create Date: 2026-06-04 12:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = '834f845b35d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create BEFORE INSERT function and trigger
    op.execute("""
    CREATE OR REPLACE FUNCTION process_transaction_fraud_check()
    RETURNS TRIGGER AS $$
    DECLARE
        v_transaction_count INT;
        v_home_country VARCHAR;
        v_device_exists INT;
        v_risk_score FLOAT := 0.0;
        v_triggered_rules JSONB := '[]'::jsonb;
        v_decision VARCHAR := 'ALLOW';
    BEGIN
        -- VEL-01: 5 or more transactions in the last hour
        SELECT COUNT(*)
        INTO v_transaction_count
        FROM transactions
        WHERE account_id = NEW.account_id
          AND timestamp >= NOW() - INTERVAL '1 hour';

        IF v_transaction_count >= 5 THEN
            v_triggered_rules := v_triggered_rules || '"VEL-01"'::jsonb;
            v_risk_score := v_risk_score + 0.15;
        END IF;

        -- VEL-TEST-01: High amount velocity
        IF NEW.amount > 10000 THEN
            v_triggered_rules := v_triggered_rules || '"VEL-TEST-01"'::jsonb;
            v_risk_score := v_risk_score + 0.30;
        END IF;

        -- LOC-01: Location mismatch
        SELECT home_country
        INTO v_home_country
        FROM accounts
        WHERE id = NEW.account_id;

        IF v_home_country IS NOT NULL AND v_home_country <> NEW.country THEN
            v_triggered_rules := v_triggered_rules || '"LOC-01"'::jsonb;
            v_risk_score := v_risk_score + 0.40;
        END IF;

        -- THR-01: Threshold exceeded
        IF NEW.amount > 50000 THEN
            v_triggered_rules := v_triggered_rules || '"THR-01"'::jsonb;
            v_risk_score := v_risk_score + 0.20;
        END IF;

        -- BEH-01: Behaviour anomaly
        IF LOWER(NEW.merchant_category) IN ('jewellery', 'crypto', 'luxury') THEN
            v_triggered_rules := v_triggered_rules || '"BEH-01"'::jsonb;
            v_risk_score := v_risk_score + 0.10;
        END IF;

        -- DEV-01: Device anomaly
        SELECT COUNT(*)
        INTO v_device_exists
        FROM device_logs
        WHERE account_id = NEW.account_id
          AND device_id = NEW.device_id;

        IF v_device_exists = 0 THEN
            v_triggered_rules := v_triggered_rules || '"DEV-01"'::jsonb;
            v_risk_score := v_risk_score + 0.15;
        END IF;

        -- Clamp risk score to max 1.0
        IF v_risk_score > 1.0 THEN
            v_risk_score := 1.0;
        END IF;

        -- Decision mapping
        IF v_risk_score >= 0.85 THEN
            v_decision := 'BLOCK';
        ELSIF v_risk_score >= 0.55 THEN
            v_decision := 'REVIEW';
        ELSE
            v_decision := 'ALLOW';
        END IF;

        NEW.risk_score := v_risk_score;
        NEW.decision := v_decision;
        NEW.fraud_flags := (v_triggered_rules)::json;

        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE TRIGGER trg_transactions_fraud_check
    BEFORE INSERT ON transactions
    FOR EACH ROW
    EXECUTE FUNCTION process_transaction_fraud_check();
    """)

    # 2. Create AFTER INSERT function and trigger
    op.execute("""
    CREATE OR REPLACE FUNCTION process_transaction_fraud_actions()
    RETURNS TRIGGER AS $$
    DECLARE
        v_flag TEXT;
        v_details TEXT;
        v_home_country VARCHAR;
        v_transaction_count INT;
    BEGIN
        -- 2.1 Log Fraud Events
        FOR v_flag IN SELECT json_array_elements_text(COALESCE(NEW.fraud_flags, '[]'::json)) LOOP
            v_details := '';
            
            IF v_flag = 'VEL-01' THEN
                SELECT COUNT(*) INTO v_transaction_count
                FROM transactions
                WHERE account_id = NEW.account_id
                  AND timestamp >= NEW.timestamp - INTERVAL '1 hour';
                  
                v_details := v_transaction_count || ' transactions detected within last hour';
                
            ELSIF v_flag = 'VEL-TEST-01' THEN
                v_details := 'High transaction amount velocity test triggered';
                
            ELSIF v_flag = 'LOC-01' THEN
                SELECT home_country INTO v_home_country
                FROM accounts
                WHERE id = NEW.account_id;
                
                v_details := 'Transaction country ''' || NEW.country || ''' does not match home country ''' || COALESCE(v_home_country, '') || '''';
                
            ELSIF v_flag = 'THR-01' THEN
                v_details := 'Transaction amount exceeded ₹50,000 threshold';
                
            ELSIF v_flag = 'BEH-01' THEN
                v_details := 'Unusual merchant category: ' || NEW.merchant_category;
                
            ELSIF v_flag = 'DEV-01' THEN
                v_details := 'New device detected for account';
            END IF;

            INSERT INTO fraud_events (transaction_id, rule_triggered, severity, details, created_at)
            VALUES (NEW.id, v_flag, 'MEDIUM', v_details, NOW());
        END LOOP;

        -- 2.2 Upsert Device Log
        UPDATE device_logs
        SET last_seen = NOW()
        WHERE account_id = NEW.account_id AND device_id = NEW.device_id;
        
        IF NOT FOUND THEN
            INSERT INTO device_logs (account_id, device_id, ip_address, last_seen)
            VALUES (NEW.account_id, NEW.device_id, NEW.ip_address, NOW());
        END IF;

        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE TRIGGER trg_transactions_fraud_actions
    AFTER INSERT ON transactions
    FOR EACH ROW
    EXECUTE FUNCTION process_transaction_fraud_actions();
    """)


def downgrade() -> None:
    op.execute("""
    DROP TRIGGER IF EXISTS trg_transactions_fraud_actions ON transactions;
    DROP FUNCTION IF EXISTS process_transaction_fraud_actions();
    DROP TRIGGER IF EXISTS trg_transactions_fraud_check ON transactions;
    DROP FUNCTION IF EXISTS process_transaction_fraud_check();
    """)
