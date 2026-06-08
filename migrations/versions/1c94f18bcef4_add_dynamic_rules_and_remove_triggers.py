"""add_dynamic_rules_and_remove_triggers

Revision ID: 1c94f18bcef4
Revises: b0ca3f07d894
Create Date: 2026-06-05 14:35:34.415330

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c94f18bcef4'
down_revision: Union[str, Sequence[str], None] = 'b0ca3f07d894'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop the triggers on transactions table
    op.execute("DROP TRIGGER IF EXISTS trg_transactions_fraud_actions ON transactions CASCADE;")
    op.execute("DROP TRIGGER IF EXISTS trg_transactions_fraud_check ON transactions CASCADE;")
    
    # 2. Drop the trigger functions
    op.execute("DROP FUNCTION IF EXISTS process_transaction_fraud_actions() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS process_transaction_fraud_check() CASCADE;")

    # 3. Create the fraud_rules table
    op.create_table(
        'fraud_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sql_expression', sa.Text(), nullable=False),
        sa.Column('weight', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_fraud_rules_code', 'fraud_rules', ['code'], unique=True)
    op.create_index('ix_fraud_rules_id', 'fraud_rules', ['id'], unique=False)

    # 4. Seed the initial rules
    op.execute(sa.text(r"""
    INSERT INTO fraud_rules (code, name, description, sql_expression, weight, is_active)
    VALUES
    ('VEL-01', 'High Velocity (Hour)', '5 or more transactions in the last hour', 
     'SELECT COUNT(*) >= 4 FROM transactions WHERE account_id = \:account_id AND timestamp >= NOW() - INTERVAL ''1 hour''', 0.15, true),
    ('VEL-TEST-01', 'High Amount Velocity', 'Transaction amount exceeds 10,000', 
     'SELECT \:amount > 10000', 0.30, true),
    ('LOC-01', 'Location Mismatch', 'Transaction country does not match account home country', 
     'SELECT home_country IS NOT NULL AND home_country <> \:country FROM accounts WHERE id = \:account_id', 0.40, true),
    ('THR-01', 'High Amount Threshold', 'Transaction amount exceeds 50,000', 
     'SELECT \:amount > 50000', 0.20, true),
    ('BEH-01', 'Unusual Merchant Category', 'Transaction in jewellery, crypto, or luxury category', 
     'SELECT LOWER(\:merchant_category) IN (''jewellery'', ''crypto'', ''luxury'')', 0.10, true),
    ('DEV-01', 'New Device Detected', 'Transaction from a device not registered to the account', 
     'SELECT COUNT(*) = 0 FROM device_logs WHERE account_id = \:account_id AND device_id = \:device_id', 0.15, true),
    ('VEL-HIGH-FREQ', 'High Frequency (2 minutes)', '3 or more transactions in the last 2 minutes', 
     'SELECT COUNT(*) >= 2 FROM transactions WHERE account_id = \:account_id AND timestamp >= NOW() - INTERVAL ''2 minutes''', 0.35, true),
    ('THR-NORM-EXCEED', 'Normal Threshold Exceeded', 'Transaction amount exceeds 3x the average transaction amount', 
     'SELECT COALESCE(AVG(amount), 0) > 0 AND \:amount > (COALESCE(AVG(amount), 0) * 3) FROM transactions WHERE account_id = \:account_id', 0.25, true),
    ('BEH-MICRO-TEST', 'Micro-Test Sequence', 'Transaction >= 1,000 following a micro-transaction (1-5) in the last 10 minutes', 
     'SELECT \:amount >= 1000 AND EXISTS (SELECT 1 FROM transactions WHERE account_id = \:account_id AND amount BETWEEN 1 AND 5 AND timestamp >= NOW() - INTERVAL ''10 minutes'')', 0.40, true),
    ('LOC-NEW-COUNTRY', 'New Country Visited', 'Transaction country not match home country and user has never transacted there before', 
     'SELECT \:country <> (SELECT home_country FROM accounts WHERE id = \:account_id) AND NOT EXISTS (SELECT 1 FROM transactions WHERE account_id = \:account_id AND country = \:country)', 0.45, true),
    ('DEV-MULTI-ACCOUNT', 'Multi-Account Device', 'Device linked to multiple distinct platform accounts', 
     'SELECT COUNT(DISTINCT account_id) > 0 FROM device_logs WHERE device_id = \:device_id AND account_id <> \:account_id', 0.30, true),
    ('REP-AMT', 'Repeated Transactions', 'Repeated transaction of the same amount in the last 5 minutes', 
     'SELECT EXISTS (SELECT 1 FROM transactions WHERE account_id = \:account_id AND amount = \:amount AND timestamp >= NOW() - INTERVAL ''5 minutes'')', 0.40, true);
    """))


def downgrade() -> None:
    # 1. Drop index and table fraud_rules
    op.drop_index('ix_fraud_rules_id', table_name='fraud_rules')
    op.drop_index('ix_fraud_rules_code', table_name='fraud_rules')
    op.drop_table('fraud_rules')

    # 2. Re-create the triggers and trigger functions on transactions table (from revision b2c3d4e5f6a7)
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
        -- VEL-01
        SELECT COUNT(*) INTO v_transaction_count FROM transactions WHERE account_id = NEW.account_id AND timestamp >= NOW() - INTERVAL '1 hour';
        IF v_transaction_count >= 5 THEN
            v_triggered_rules := v_triggered_rules || '"VEL-01"'::jsonb;
            v_risk_score := v_risk_score + 0.15;
        END IF;

        -- VEL-TEST-01
        IF NEW.amount > 10000 THEN
            v_triggered_rules := v_triggered_rules || '"VEL-TEST-01"'::jsonb;
            v_risk_score := v_risk_score + 0.30;
        END IF;

        -- LOC-01
        SELECT home_country INTO v_home_country FROM accounts WHERE id = NEW.account_id;
        IF v_home_country IS NOT NULL AND v_home_country <> NEW.country THEN
            v_triggered_rules := v_triggered_rules || '"LOC-01"'::jsonb;
            v_risk_score := v_risk_score + 0.40;
        END IF;

        -- THR-01
        IF NEW.amount > 50000 THEN
            v_triggered_rules := v_triggered_rules || '"THR-01"'::jsonb;
            v_risk_score := v_risk_score + 0.20;
        END IF;

        -- BEH-01
        IF LOWER(NEW.merchant_category) IN ('jewellery', 'crypto', 'luxury') THEN
            v_triggered_rules := v_triggered_rules || '"BEH-01"'::jsonb;
            v_risk_score := v_risk_score + 0.10;
        END IF;

        -- DEV-01
        SELECT COUNT(*) INTO v_device_exists FROM device_logs WHERE account_id = NEW.account_id AND device_id = NEW.device_id;
        IF v_device_exists = 0 THEN
            v_triggered_rules := v_triggered_rules || '"DEV-01"'::jsonb;
            v_risk_score := v_risk_score + 0.15;
        END IF;

        -- VEL-HIGH-FREQ
        SELECT COUNT(*) INTO v_tx_minutes_count FROM transactions WHERE account_id = NEW.account_id AND timestamp >= NOW() - INTERVAL '2 minutes';
        IF v_tx_minutes_count >= 3 THEN
            v_triggered_rules := v_triggered_rules || '"VEL-HIGH-FREQ"'::jsonb;
            v_risk_score := v_risk_score + 0.35;
        END IF;

        -- THR-NORM-EXCEED
        SELECT COALESCE(AVG(amount), 0) INTO v_avg_amount FROM transactions WHERE account_id = NEW.account_id;
        IF v_avg_amount > 0 AND NEW.amount > (v_avg_amount * 3) THEN
            v_triggered_rules := v_triggered_rules || '"THR-NORM-EXCEED"'::jsonb;
            v_risk_score := v_risk_score + 0.25;
        END IF;

        -- BEH-MICRO-TEST
        SELECT COUNT(*) INTO v_micro_test_exists FROM transactions WHERE account_id = NEW.account_id AND amount BETWEEN 1 AND 5 AND timestamp >= NOW() - INTERVAL '10 minutes';
        IF v_micro_test_exists > 0 AND NEW.amount >= 1000 THEN
            v_triggered_rules := v_triggered_rules || '"BEH-MICRO-TEST"'::jsonb;
            v_risk_score := v_risk_score + 0.40;
        END IF;

        -- LOC-NEW-COUNTRY
        SELECT COUNT(*) INTO v_past_country_txs FROM transactions WHERE account_id = NEW.account_id AND country = NEW.country;
        IF v_past_country_txs = 0 AND v_home_country <> NEW.country THEN
            v_triggered_rules := v_triggered_rules || '"LOC-NEW-COUNTRY"'::jsonb;
            v_risk_score := v_risk_score + 0.45;
        END IF;

        -- DEV-MULTI-ACCOUNT
        SELECT COUNT(DISTINCT account_id) INTO v_device_acc_count FROM device_logs WHERE device_id = NEW.device_id AND account_id <> NEW.account_id;
        IF v_device_acc_count > 0 THEN
            v_triggered_rules := v_triggered_rules || '"DEV-MULTI-ACCOUNT"'::jsonb;
            v_risk_score := v_risk_score + 0.30;
        END IF;

        IF v_risk_score > 1.0 THEN v_risk_score := 1.0; END IF;
        IF v_risk_score >= 0.85 THEN v_decision := 'BLOCK'; ELSIF v_risk_score >= 0.55 THEN v_decision := 'REVIEW'; ELSE v_decision := 'ALLOW'; END IF;

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
    BEGIN
        FOR v_flag IN SELECT json_array_elements_text(COALESCE(NEW.fraud_flags, '[]'::json)) LOOP
            v_details := '';
            IF v_flag = 'VEL-01' THEN
                SELECT COUNT(*) INTO v_transaction_count FROM transactions WHERE account_id = NEW.account_id AND timestamp >= NEW.timestamp - INTERVAL '1 hour';
                v_details := v_transaction_count || ' transactions detected within last hour';
            ELSIF v_flag = 'VEL-TEST-01' THEN
                v_details := 'High transaction amount velocity test triggered';
            ELSIF v_flag = 'LOC-01' THEN
                SELECT home_country INTO v_home_country FROM accounts WHERE id = NEW.account_id;
                v_details := 'Transaction country ''' || NEW.country || ''' does not match home country ''' || COALESCE(v_home_country, '') || '''';
            ELSIF v_flag = 'THR-01' THEN
                v_details := 'Transaction amount exceeded ₹50,000 threshold';
            ELSIF v_flag = 'BEH-01' THEN
                v_details := 'Unusual merchant category: ' || NEW.merchant_category;
            ELSIF v_flag = 'DEV-01' THEN
                v_details := 'New device detected for account';
            ELSIF v_flag = 'VEL-HIGH-FREQ' THEN
                SELECT COUNT(*) INTO v_tx_minutes_count FROM transactions WHERE account_id = NEW.account_id AND timestamp >= NEW.timestamp - INTERVAL '2 minutes';
                v_details := v_tx_minutes_count || ' high frequency transactions detected in last 2 minutes';
            ELSIF v_flag = 'THR-NORM-EXCEED' THEN
                SELECT COALESCE(AVG(amount), 0) INTO v_avg_amount FROM transactions WHERE account_id = NEW.account_id AND id <> NEW.id;
                v_details := 'Transaction amount ₹' || NEW.amount || ' exceeds account average of ₹' || ROUND(v_avg_amount::numeric, 2) || ' by over 3x';
            ELSIF v_flag = 'BEH-MICRO-TEST' THEN
                v_details := 'High-value transaction immediately following small micro-test transactions';
            ELSIF v_flag = 'LOC-NEW-COUNTRY' THEN
                v_details := 'Transaction from a country user has never accessed from: ' || NEW.country;
            ELSIF v_flag = 'DEV-MULTI-ACCOUNT' THEN
                v_details := 'Device linked to multiple distinct platform accounts';
            END IF;

            INSERT INTO fraud_events (transaction_id, rule_triggered, severity, details, created_at)
            VALUES (NEW.id, v_flag, 'MEDIUM', v_details, NOW());
        END LOOP;

        UPDATE device_logs SET last_seen = NOW() WHERE account_id = NEW.account_id AND device_id = NEW.device_id;
        IF NOT FOUND THEN
            INSERT INTO device_logs (account_id, device_id, ip_address, last_seen) VALUES (NEW.account_id, NEW.device_id, NEW.ip_address, NOW());
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

