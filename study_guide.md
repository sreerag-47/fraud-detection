# BankGuard Project Study Guide & Fraud Testing Mock Data

This guide is designed for developers studying the BankGuard database-driven fraud engine. It details the system architecture, trigger dynamics, and provides a SQL test suite to validate the rules.

---

## 1. Project Architecture Overview

BankGuard uses a **hybrid database-logic architecture**:

```
[ FastAPI App ] ──(Raw Transaction details)──> [ PostgreSQL Table ]
                                                        │
                                           (BEFORE INSERT Trigger Fired)
                                                        │
                                            Calculates Risk/Decision
                                                        │
                                           (AFTER INSERT Trigger Fired)
                                                        │
                                            Logs Events & Upserts Devices
```

1. **FastAPI Client (API Layer):** Receives the HTTP payload, validates the token, checks account ownership, and commits a raw transaction.
2. **`BEFORE INSERT` SQL Trigger (`process_transaction_fraud_check`):** Automatically evaluates all rules and sets `risk_score`, `decision` (`ALLOW`/`REVIEW`/`BLOCK`), and `fraud_flags` inside the database before committing the row.
3. **`AFTER INSERT` SQL Trigger (`process_transaction_fraud_actions`):** Automatically splits the JSON array `fraud_flags` to insert explanatory event logs into `fraud_events` and registers or updates device details in `device_logs`.

---

## 2. Guide to Files

* [database.py](file:///e:/fraud-detection-app/database.py) — Engine setup using `SQLAlchemy` async wrapper.
* [models/](file:///e:/fraud-detection-app/models) — SQLAlchemy Python classes representing the database tables.
* [routers/transactions.py](file:///e:/fraud-detection-app/routers/transactions.py) — Transaction router showing how the backend delegates work to DB triggers and fetches details back.
* [migrations/versions/b2c3d4e5f6a7_add_advanced_fraud_rules.py](file:///e:/fraud-detection-app/migrations/versions/b2c3d4e5f6a7_add_advanced_fraud_rules.py) — Contains the exact PL/pgSQL trigger code.

---

## 3. Mock Data & Rule Validation Script

You can run the following SQL script inside your database manager (e.g. pgAdmin, DBeaver, or psql terminal) to seed the database and test each of the 11 rules.

### Setup Base Users & Accounts
```sql
-- 1. Clear existing data
TRUNCATE users, accounts, transactions, fraud_events, device_logs RESTART IDENTITY CASCADE;

-- 2. Seed Users
INSERT INTO users (id, name, email, password_hash, created_at) VALUES
(1, 'Alice Smith', 'alice@test.com', 'hashed_pass_123', NOW()),
(2, 'Bob Johnson', 'bob@test.com', 'hashed_pass_456', NOW());

-- 3. Seed Accounts
INSERT INTO accounts (id, user_id, account_number, balance, account_type, home_city, home_country, created_at) VALUES
(101, 1, 'BG1101', 150000.0, 'savings', 'Mumbai', 'India', NOW()),
(102, 2, 'BG1102', 8000.0, 'current', 'Kozhikode', 'India', NOW());

-- 4. Seed a trusted device log for Alice
INSERT INTO device_logs (account_id, device_id, ip_address, last_seen) VALUES
(101, 'alices_macbook_pro', '192.168.1.5', NOW() - INTERVAL '1 day');
```

---

### Seeding Scenarios to Test the 11 Rules

Execute each of the insert scripts below and inspect the `transactions` and `fraud_events` tables to watch the triggers work automatically.

#### Test DEV-01: New Device Detection (Weight: 0.15)
Since `unknown_phone_123` is not registered in `device_logs` for Alice (Account 101), this rule triggers.
```sql
INSERT INTO transactions (account_id, amount, merchant_name, merchant_category, city, country, ip_address, device_id)
VALUES (101, 200.0, 'Starbucks', 'coffee', 'Mumbai', 'India', '192.168.1.10', 'unknown_phone_123');

-- Verification
SELECT * FROM transactions ORDER BY id DESC LIMIT 1; -- Check fraud_flags contains DEV-01
SELECT * FROM fraud_events ORDER BY id DESC LIMIT 1; -- Check corresponding event details
SELECT * FROM device_logs WHERE device_id = 'unknown_phone_123'; -- Device is now added automatically!
```

#### Test VEL-TEST-01: High amount velocity (Weight: 0.30)
Transacting ₹15,000 triggers `VEL-TEST-01` because it is greater than ₹10,000.
```sql
INSERT INTO transactions (account_id, amount, merchant_name, merchant_category, city, country, ip_address, device_id)
VALUES (101, 15000.0, 'Electronics Store', 'electronics', 'Mumbai', 'India', '192.168.1.5', 'alices_macbook_pro');
```

#### Test LOC-01: Country Mismatch (Weight: 0.40)
Transaction from Dubai (UAE) does not match Alice's home country (India).
```sql
INSERT INTO transactions (account_id, amount, merchant_name, merchant_category, city, country, ip_address, device_id)
VALUES (101, 800.0, 'Dubai Cafe', 'food', 'Dubai', 'UAE', '185.12.5.4', 'alices_macbook_pro');
```

#### Test THR-01: Large Transaction Threshold (Weight: 0.20)
Amount is ₹75,000 which exceeds the ₹50,000 threshold.
```sql
INSERT INTO transactions (account_id, amount, merchant_name, merchant_category, city, country, ip_address, device_id)
VALUES (101, 75000.0, 'Gold Jewellery Store', 'jewelry', 'Mumbai', 'India', '192.168.1.5', 'alices_macbook_pro');
```

#### Test BEH-01: Behavioural Anomaly (Weight: 0.10)
Transaction category `crypto` triggers `BEH-01`.
```sql
INSERT INTO transactions (account_id, amount, merchant_name, merchant_category, city, country, ip_address, device_id)
VALUES (101, 500.0, 'Binance', 'crypto', 'Mumbai', 'India', '192.168.1.5', 'alices_macbook_pro');
```

#### Test VEL-HIGH-FREQ: Burst Rate Limit (Weight: 0.35)
Insert 3 transactions in a row within 10 seconds for Bob (Account 102).
```sql
INSERT INTO transactions (account_id, amount, merchant_name, merchant_category, city, country, ip_address, device_id) VALUES
(102, 100.0, 'App Store', 'digital', 'Kozhikode', 'India', '192.168.1.15', 'bobs_android_phone'),
(102, 120.0, 'App Store', 'digital', 'Kozhikode', 'India', '192.168.1.15', 'bobs_android_phone'),
(102, 150.0, 'App Store', 'digital', 'Kozhikode', 'India', '192.168.1.15', 'bobs_android_phone'); -- Third one triggers VEL-HIGH-FREQ
```

#### Test THR-NORM-EXCEED: Exceeding Norms (Weight: 0.25)
Bob's account average is around ₹120. An insert of ₹2,500 exceeds 3x the average.
```sql
INSERT INTO transactions (account_id, amount, merchant_name, merchant_category, city, country, ip_address, device_id)
VALUES (102, 2500.0, 'Luxury Shoes', 'luxury', 'Kozhikode', 'India', '192.168.1.15', 'bobs_android_phone');
```

#### Test BEH-MICRO-TEST: Card Testing Behavior (Weight: 0.40)
Insert a small test transaction (₹3), then immediately follow it with a large transfer (₹12,000).
```sql
-- Alice does micro-test
INSERT INTO transactions (account_id, amount, merchant_name, merchant_category, city, country, ip_address, device_id)
VALUES (101, 3.0, 'Gateway Test', 'services', 'Mumbai', 'India', '192.168.1.5', 'alices_macbook_pro');

-- Followed immediately by large transaction
INSERT INTO transactions (account_id, amount, merchant_name, merchant_category, city, country, ip_address, device_id)
VALUES (101, 12000.0, 'High Value Retailer', 'shopping', 'Mumbai', 'India', '192.168.1.5', 'alices_macbook_pro');
```

#### Test LOC-NEW-COUNTRY: Unseen Location (Weight: 0.45)
Transaction from Germany where Alice has never transacted before.
```sql
INSERT INTO transactions (account_id, amount, merchant_name, merchant_category, city, country, ip_address, device_id)
VALUES (101, 400.0, 'Berlin Taxi', 'transport', 'Berlin', 'Germany', '46.100.12.1', 'alices_macbook_pro');
```

#### Test DEV-MULTI-ACCOUNT: Device Spoofing (Weight: 0.30)
Bob's phone (`bobs_android_phone`) tries to transact from Alice's account (`101`).
```sql
INSERT INTO transactions (account_id, amount, merchant_name, merchant_category, city, country, ip_address, device_id)
VALUES (101, 600.0, 'Local Shop', 'shopping', 'Mumbai', 'India', '192.168.1.5', 'bobs_android_phone');
```

#### Test VEL-01: Frequency Limit (Weight: 0.15)
Perform 5 transactions within an hour to check velocity triggers.
```sql
INSERT INTO transactions (account_id, amount, merchant_name, merchant_category, city, country, ip_address, device_id) VALUES
(101, 100.0, 'Shop A', 'retail', 'Mumbai', 'India', '192.168.1.5', 'alices_macbook_pro'),
(101, 100.0, 'Shop B', 'retail', 'Mumbai', 'India', '192.168.1.5', 'alices_macbook_pro'),
(101, 100.0, 'Shop C', 'retail', 'Mumbai', 'India', '192.168.1.5', 'alices_macbook_pro'),
(101, 100.0, 'Shop D', 'retail', 'Mumbai', 'India', '192.168.1.5', 'alices_macbook_pro'),
(101, 100.0, 'Shop E', 'retail', 'Mumbai', 'India', '192.168.1.5', 'alices_macbook_pro'); -- Triggers VEL-01
```
