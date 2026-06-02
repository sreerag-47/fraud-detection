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
