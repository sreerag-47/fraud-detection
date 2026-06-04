fraud-detection-app/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app (Friend's domain)
│   │   ├── database.py          # PostgreSQL connection (Friend's domain)
│   │   ├── models.py            # DB Schema Tables (Friend's domain)
│   │   │
│   │   └── fraud_engine/        # YOUR DOMAIN (Pure Python)
│   │       ├── __init__.py
│   │       ├── contract.py      # Step 2: The Agreement File
│   │       ├── core.py          # The main run_fraud_check function
│   │       └── rules/           # Individual rule files (velocity, location, etc.)
│   │           ├── __init__.py
│   │           ├── velocity.py
│   │           └── threshold.py
│   │
│   └── requirements.txt
│
└── frontend/                    # YOUR DOMAIN (React + Tailwind)
    ├── public/
    └── src/"# fraud-dectection" 



# BankGuard — Current Database Table Structures

## 1. users

Stores authenticated platform users.

| Column        | Type            | Description                |
| ------------- | --------------- | -------------------------- |
| id            | Integer (PK)    | Unique user ID             |
| name          | String          | Full name                  |
| email         | String (Unique) | User email/login           |
| password_hash | String          | bcrypt hashed password     |
| created_at    | DateTime        | Account creation timestamp |

### Relationships

* One user → many accounts

---

# 2. accounts

Represents bank accounts linked to users.

| Column         | Type                    | Description                |
| -------------- | ----------------------- | -------------------------- |
| id             | Integer (PK)            | Unique account ID          |
| user_id        | Integer (FK → users.id) | Owner user                 |
| account_number | String                  | Bank account number        |
| balance        | Float                   | Current account balance    |
| account_type   | String                  | savings/current/etc        |
| home_city      | String                  | User’s primary city        |
| home_country   | String                  | User’s primary country     |
| created_at     | DateTime                | Account creation timestamp |

### Relationships

* Many accounts → one user
* One account → many transactions
* One account → many device logs

---

# 3. transactions

Stores all transaction activity.

| Column            | Type                       | Description           |
| ----------------- | -------------------------- | --------------------- |
| id                | Integer (PK)               | Transaction ID        |
| account_id        | Integer (FK → accounts.id) | Source account        |
| amount            | Float                      | Transaction amount    |
| merchant_name     | String                     | Merchant/business     |
| merchant_category | String                     | shopping/crypto/etc   |
| city              | String                     | Transaction city      |
| country           | String                     | Transaction country   |
| ip_address        | String                     | Client IP             |
| device_id         | String                     | Device identifier     |
| risk_score        | Float                      | Calculated fraud risk |
| decision          | String                     | ALLOW/REVIEW/BLOCK    |
| fraud_flags       | JSON                       | Triggered fraud rules |
| timestamp         | DateTime                   | Transaction timestamp |

### Relationships

* Many transactions → one account
* One transaction → many fraud events

---

# 4. fraud_events

Stores explainable fraud-analysis results.

| Column         | Type                           | Description                |
| -------------- | ------------------------------ | -------------------------- |
| id             | Integer (PK)                   | Fraud event ID             |
| transaction_id | Integer (FK → transactions.id) | Related transaction        |
| rule_triggered | String                         | Fraud rule code            |
| severity       | String                         | LOW/MEDIUM/HIGH            |
| details        | String                         | Human-readable explanation |
| created_at     | DateTime                       | Fraud event timestamp      |

### Relationships

* Many fraud events → one transaction

---

# 5. device_logs

Tracks known/trusted devices.

| Column     | Type                       | Description             |
| ---------- | -------------------------- | ----------------------- |
| id         | Integer (PK)               | Device log ID           |
| account_id | Integer (FK → accounts.id) | Linked account          |
| device_id  | String                     | Device fingerprint/ID   |
| ip_address | String                     | Last known IP           |
| last_seen  | DateTime                   | Last activity timestamp |

### Relationships

* Many device logs → one account

---

# Current Relationship Graph

```text
users
  │
  └── accounts
         │
         ├── transactions
         │       │
         │       └── fraud_events
         │
         └── device_logs
```

---

# Current Fraud Rules

| Rule Code   | Description                 |
| ----------- | --------------------------- |
| VEL-01      | High transaction frequency  |
| VEL-TEST-01 | High-value velocity trigger |
| LOC-01      | Country mismatch            |
| THR-01      | High-value threshold        |
| BEH-01      | Unusual merchant category   |
| DEV-01      | New device detection        |

---

# Planned Future Tables

Likely additions later:

| Table          | Purpose                           |
| -------------- | --------------------------------- |
| admin_users    | Fraud investigator/admin accounts |
| fraud_reviews  | Manual analyst review queue       |
| alerts         | Real-time notifications           |
| login_attempts | Auth anomaly tracking             |
| sessions       | Device-bound sessions             |
| rule_configs   | Dynamic fraud-rule tuning         |
| risk_snapshots | Historical account risk states    |
| audit_logs     | System-wide security auditing     |

---

# Current Architectural Style

The system currently follows:

```text
FastAPI
→ Service Layer
→ Fraud Engine
→ SQLAlchemy Async ORM
→ PostgreSQL
```

with modular fraud-rule execution and explainable event persistence.

---

# Important Infrastructure Note

Current schema management:

```text
Base.metadata.create_all()
```

Planned migration system:

```text
Alembic
```

before Dockerization and multi-developer scaling.
