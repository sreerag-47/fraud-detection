"""add_geo_velocity_rule

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-05 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update BEFORE INSERT function to include GEO-VEL-01 rule
    op.execute("""
    CREATE OR REPLACE FUNCTION process_transaction_fraud_check()
    RETURNS TRIGGER AS $$
    DECLARE
        v_transaction_count INT;
        v_tx_minutes_count INT;
        v_avg_amount FLOAT;
        v_micro_test_exists INT;
        v_past_country_txs INT;
        v_device_acc_count INT;
        
        v_home_country VARCHAR;
        v_device_exists INT;
        v_last_transaction RECORD;
        v_time_diff_minutes INT;
        
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

        -- LOC-01: Location mismatch (home country)
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

        -- VEL-HIGH-FREQ: >=3 transactions in 2 minutes
        SELECT COUNT(*) INTO v_tx_minutes_count
        FROM transactions
        WHERE account_id = NEW.account_id
          AND timestamp >= NOW() - INTERVAL '2 minutes';

        IF v_tx_minutes_count >= 3 THEN
            v_triggered_rules := v_triggered_rules || '"VEL-HIGH-FREQ"'::jsonb;
            v_risk_score := v_risk_score + 0.35;
        END IF;

        -- THR-NORM-EXCEED: Exceeds historical average by over 3x
        SELECT COALESCE(AVG(amount), 0) INTO v_avg_amount
        FROM transactions
        WHERE account_id = NEW.account_id;

        IF v_avg_amount > 0 AND NEW.amount > (v_avg_amount * 3) THEN
            v_triggered_rules := v_triggered_rules || '"THR-NORM-EXCEED"'::jsonb;
            v_risk_score := v_risk_score + 0.25;
        END IF;

        -- BEH-MICRO-TEST: Micro-test transaction (₹1-5) followed by large one (>= ₹1000)
        SELECT COUNT(*) INTO v_micro_test_exists
        FROM transactions
        WHERE account_id = NEW.account_id
          AND amount BETWEEN 1 AND 5
          AND timestamp >= NOW() - INTERVAL '10 minutes';

        IF v_micro_test_exists > 0 AND NEW.amount >= 1000 THEN
            v_triggered_rules := v_triggered_rules || '"BEH-MICRO-TEST"'::jsonb;
            v_risk_score := v_risk_score + 0.40;
        END IF;

        -- LOC-NEW-COUNTRY: Country user has never transacted from
        SELECT COUNT(*) INTO v_past_country_txs
        FROM transactions
        WHERE account_id = NEW.account_id
          AND country = NEW.country;

        IF v_past_country_txs = 0 AND v_home_country <> NEW.country THEN
            v_triggered_rules := v_triggered_rules || '"LOC-NEW-COUNTRY"'::jsonb;
            v_risk_score := v_risk_score + 0.45;
        END IF;

        -- DEV-MULTI-ACCOUNT: Same device logged into multiple distinct accounts
        SELECT COUNT(DISTINCT account_id) INTO v_device_acc_count
        FROM device_logs
        WHERE device_id = NEW.device_id
          AND account_id <> NEW.account_id;

        IF v_device_acc_count > 0 THEN
            v_triggered_rules := v_triggered_rules || '"DEV-MULTI-ACCOUNT"'::jsonb;
            v_risk_score := v_risk_score + 0.30;
        END IF;

        -- GEO-VEL-01: Rapid Geo-Jump (different country within 15 minutes)
        SELECT id, country, timestamp
        INTO v_last_transaction
        FROM transactions
        WHERE account_id = NEW.account_id
        ORDER BY timestamp DESC
        LIMIT 1;

        IF v_last_transaction.id IS NOT NULL THEN
            v_time_diff_minutes := EXTRACT(EPOCH FROM (NEW.timestamp - v_last_transaction.timestamp)) / 60;

            IF v_last_transaction.country <> NEW.country 
               AND v_time_diff_minutes <= 15 
               AND v_time_diff_minutes >= 0 THEN
                v_triggered_rules := v_triggered_rules || '"GEO-VEL-01"'::jsonb;
                v_risk_score := v_risk_score + 0.50;
            END IF;
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

    # Update AFTER INSERT function to include explanation for GEO-VEL-01
    op.execute("""
    CREATE OR REPLACE FUNCTION process_transaction_fraud_actions()
    RETURNS TRIGGER AS $$
    DECLARE
        v_flag TEXT;
        v_details TEXT;
        v_home_country VARCHAR;
        v_transaction_count INT;
        v_tx_minutes_count INT;
        v_avg_amount FLOAT;
        v_last_transaction RECORD;
        v_time_diff_minutes INT;
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
                
            ELSIF v_flag = 'VEL-HIGH-FREQ' THEN
                SELECT COUNT(*) INTO v_tx_minutes_count
                FROM transactions
                WHERE account_id = NEW.account_id
                  AND timestamp >= NEW.timestamp - INTERVAL '2 minutes';
                  
                v_details := v_tx_minutes_count || ' high frequency transactions detected in last 2 minutes';
                
            ELSIF v_flag = 'THR-NORM-EXCEED' THEN
                SELECT COALESCE(AVG(amount), 0) INTO v_avg_amount
                FROM transactions
                WHERE account_id = NEW.account_id AND id <> NEW.id;
                
                v_details := 'Transaction amount ₹' || NEW.amount || ' exceeds account average of ₹' || ROUND(v_avg_amount::numeric, 2) || ' by over 3x';
                
            ELSIF v_flag = 'BEH-MICRO-TEST' THEN
                v_details := 'High-value transaction immediately following small micro-test transactions';
                
            ELSIF v_flag = 'LOC-NEW-COUNTRY' THEN
                v_details := 'Transaction from a country user has never accessed from: ' || NEW.country;
                
            ELSIF v_flag = 'DEV-MULTI-ACCOUNT' THEN
                v_details := 'Device linked to multiple distinct platform accounts';

            ELSIF v_flag = 'GEO-VEL-01' THEN
                SELECT country, timestamp
                INTO v_last_transaction
                FROM transactions
                WHERE account_id = NEW.account_id
                  AND id <> NEW.id
                ORDER BY timestamp DESC
                LIMIT 1;

                IF v_last_transaction.country IS NOT NULL THEN
                    v_time_diff_minutes := EXTRACT(EPOCH FROM (NEW.timestamp - v_last_transaction.timestamp)) / 60;
                    v_details := 'Rapid geographic jump detected: transaction from ' || v_last_transaction.country || ' to ' || NEW.country || ' in ' || v_time_diff_minutes || ' minutes (physically impossible)';
                ELSE
                    v_details := 'Rapid geographic jump detected from previous transaction country';
                END IF;
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


def downgrade() -> None:
    # Downgrade reverts to previous advanced rules without GEO-VEL-01
    op.execute("""
    CREATE OR REPLACE FUNCTION process_transaction_fraud_check()
    RETURNS TRIGGER AS $$
    DECLARE
        v_transaction_count INT;
        v_tx_minutes_count INT;
        v_avg_amount FLOAT;
        v_micro_test_exists INT;
        v_past_country_txs INT;
        v_device_acc_count INT;
        
        v_home_country VARCHAR;
        v_device_exists INT;
        v_risk_score FLOAT := 0.0;
        v_triggered_rules JSONB := '[]'::jsonb;
        v_decision VARCHAR := 'ALLOW';
    BEGIN
        SELECT COUNT(*) INTO v_transaction_count FROM transactions WHERE account_id = NEW.account_id AND timestamp >= NOW() - INTERVAL '1 hour';
        IF v_transaction_count >= 5 THEN v_triggered_rules := v_triggered_rules || '"VEL-01"'::jsonb; v_risk_score := v_risk_score + 0.15; END IF;

        IF NEW.amount > 10000 THEN v_triggered_rules := v_triggered_rules || '"VEL-TEST-01"'::jsonb; v_risk_score := v_risk_score + 0.30; END IF;

        SELECT home_country INTO v_home_country FROM accounts WHERE id = NEW.account_id;
        IF v_home_country IS NOT NULL AND v_home_country <> NEW.country THEN v_triggered_rules := v_triggered_rules || '"LOC-01"'::jsonb; v_risk_score := v_risk_score + 0.40; END IF;

        IF NEW.amount > 50000 THEN v_triggered_rules := v_triggered_rules || '"THR-01"'::jsonb; v_risk_score := v_risk_score + 0.20; END IF;

        IF LOWER(NEW.merchant_category) IN ('jewellery', 'crypto', 'luxury') THEN v_triggered_rules := v_triggered_rules || '"BEH-01"'::jsonb; v_risk_score := v_risk_score + 0.10; END IF;

        SELECT COUNT(*) INTO v_device_exists FROM device_logs WHERE account_id = NEW.account_id AND device_id = NEW.device_id;
        IF v_device_exists = 0 THEN v_triggered_rules := v_triggered_rules || '"DEV-01"'::jsonb; v_risk_score := v_risk_score + 0.15; END IF;

        SELECT COUNT(*) INTO v_tx_minutes_count FROM transactions WHERE account_id = NEW.account_id AND timestamp >= NOW() - INTERVAL '2 minutes';
        IF v_tx_minutes_count >= 3 THEN v_triggered_rules := v_triggered_rules || '"VEL-HIGH-FREQ"'::jsonb; v_risk_score := v_risk_score + 0.35; END IF;

        SELECT COALESCE(AVG(amount), 0) INTO v_avg_amount FROM transactions WHERE account_id = NEW.account_id;
        IF v_avg_amount > 0 AND NEW.amount > (v_avg_amount * 3) THEN v_triggered_rules := v_triggered_rules || '"THR-NORM-EXCEED"'::jsonb; v_risk_score := v_risk_score + 0.25; END IF;

        SELECT COUNT(*) INTO v_micro_test_exists FROM transactions WHERE account_id = NEW.account_id AND amount BETWEEN 1 AND 5 AND timestamp >= NOW() - INTERVAL '10 minutes';
        IF v_micro_test_exists > 0 AND NEW.amount >= 1000 THEN v_triggered_rules := v_triggered_rules || '"BEH-MICRO-TEST"'::jsonb; v_risk_score := v_risk_score + 0.40; END IF;

        SELECT COUNT(*) INTO v_past_country_txs FROM transactions WHERE account_id = NEW.account_id AND country = NEW.country;
        IF v_past_country_txs = 0 AND v_home_country <> NEW.country THEN v_triggered_rules := v_triggered_rules || '"LOC-NEW-COUNTRY"'::jsonb; v_risk_score := v_risk_score + 0.45; END IF;

        SELECT COUNT(DISTINCT account_id) INTO v_device_acc_count FROM device_logs WHERE device_id = NEW.device_id AND account_id <> NEW.account_id;
        IF v_device_acc_count > 0 THEN v_triggered_rules := v_triggered_rules || '"DEV-MULTI-ACCOUNT"'::jsonb; v_risk_score := v_risk_score + 0.30; END IF;

        IF v_risk_score > 1.0 THEN v_risk_score := 1.0; END IF;

        IF v_risk_score >= 0.85 THEN v_decision := 'BLOCK'; ELSIF v_risk_score >= 0.55 THEN v_decision := 'REVIEW'; ELSE v_decision := 'ALLOW'; END IF;

        NEW.risk_score := v_risk_score;
        NEW.decision := v_decision;
        NEW.fraud_flags := (v_triggered_rules)::json;

        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)
