# BankGuard

BankGuard is a modular fraud-detection backend platform built using FastAPI, PostgreSQL, SQLAlchemy Async ORM, and JWT authentication.

The system analyzes financial transactions using rule-based behavioral fraud detection and maintains explainable fraud audit trails.

---

# Current Features

## Authentication

* User registration
* JWT login authentication
* Protected API routes
* Password hashing using bcrypt

## Banking System

* Auto-created bank accounts during registration
* Account ownership enforcement
* Transaction processing pipeline

## Fraud Detection Engine

Implemented fraud modules:

* Velocity analysis
* Location mismatch detection
* Threshold analysis
* Behaviour anomaly detection
* Device anomaly detection

## Risk Engine

* Multi-rule correlation
* Weighted fraud scoring
* Automatic ALLOW / REVIEW / BLOCK decisions

## Fraud Audit Logging

* Fraud events persisted separately
* Explainable fraud reasoning
* Transaction-to-event linkage

## Device Intelligence

* Trusted device learning
* Device tracking persistence
* Device anomaly detection

---

# Tech Stack

## Backend

* FastAPI
* SQLAlchemy Async ORM
* AsyncPG
* JWT Authentication
* Passlib / bcrypt

## Database

* PostgreSQL
* Supabase

## Planned Frontend

* React
* Vite
* Axios

---

# Project Structure

```text
backend/
│
├── routers/
├── models/
├── schemas/
├── fraud/
├── utils.py
├── dependencies.py
├── database.py
├── config.py
├── main.py
```

---

# Setup Instructions

## 1. Clone Repository

```powershell
git clone https://github.com/sreerag-47/fraud-detection.git

cd fraud-detection
cd backend
```

---

## 2. Create Virtual Environment

```powershell
python -m venv env
```

Activate:

```powershell
env\Scripts\activate
```

---

## 3. Install Dependencies

```powershell
pip install -r requirements.txt
```

---

## 4. Create `.env`

Create a `.env` file inside backend:

```env
DATABASE_URL=YOUR_DATABASE_URL

SECRET_KEY=YOUR_SECRET_KEY
```

---

## 5. Run Backend

```powershell
uvicorn main:app --reload
```

Backend:

```text
http://127.0.0.1:8000
```

Swagger Docs:

```text
http://127.0.0.1:8000/docs
```

---

# Testing Flow

## Register User

`POST /auth/register`

Example:

```json
{
  "name": "Test User",
  "email": "test@example.com",
  "password": "StrongPassword123"
}
```

---

## Login

Use Swagger Authorize button:

```text
username = test@example.com
password = StrongPassword123
```

---

## Get Accounts

`GET /accounts/me`

---

## Create Transaction

`POST /transactions/`

Example:

```json
{
  "account_id": 1,
  "amount": 75000,
  "merchant_name": "Crypto Exchange",
  "merchant_category": "crypto",
  "city": "Dubai",
  "country": "UAE",
  "ip_address": "192.168.1.1",
  "device_id": "unknown_device_999"
}
```

Expected:

* fraud rules triggered
* risk score returned
* fraud events persisted

---

# Current Development Status

Current backend MVP is operational.

Completed:

* async backend infrastructure
* fraud detection engine
* JWT authentication
* protected APIs
* transaction analytics
* fraud audit logging

Planned next:

* React frontend
* Alembic migrations
* Dockerization
* advanced fraud heuristics
* admin investigator dashboard

---

# Collaboration Workflow

## Branch Strategy

Never push directly to `main`.

Create feature branches:

```powershell
git checkout -b feature-name
```

Push:

```powershell
git push -u origin feature-name
```

Then create Pull Requests.

---

# Security Notes

Never commit:

* `.env`
* database credentials
* JWT secrets
* virtual environments

Rotate credentials immediately if exposed.
