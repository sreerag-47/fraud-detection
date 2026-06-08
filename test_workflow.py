import time
import asyncio
import httpx
from main import app

def safe_print(*args):
    message = " ".join(str(arg) for arg in args)
    clean_msg = message.encode('ascii', errors='replace').decode('ascii')
    print(clean_msg)

async def run_tests():
    # Use AsyncClient with ASGI transport to run the FastAPI app directly in the current event loop
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Generate unique user email to prevent collisions
        unique_id = int(time.time())
        email = f"user_{unique_id}@example.com"
        password = "SecurePassword123!"
        
        safe_print("\n--- [STEP 1] Registering User ---")
        reg_payload = {
            "name": "Integration Test User",
            "email": email,
            "password": password,
            "home_city": "Kozhikode",
            "home_country": "India",
            "account_type": "savings",
            "balance": 150000.0
        }
        reg_response = await client.post("/auth/register", json=reg_payload)
        assert reg_response.status_code == 200, f"Registration failed: {reg_response.text}"
        reg_data = reg_response.json()
        safe_print("Registration Response:", reg_data)
        
        user_id = reg_data["user_id"]
        account_id = reg_data["account_id"]
        account_number = reg_data["account_number"]
        assert user_id is not None
        assert account_id is not None
        assert account_number is not None

        # 2. Promote user to Admin via Developer Playground API
        safe_print("\n--- [STEP 2] Promoting User to Admin ---")
        promote_payload = {
            "data": {
                "is_admin": True
            }
        }
        promote_response = await client.put(f"/dev/db/tables/users/{user_id}", json=promote_payload)
        assert promote_response.status_code == 200, f"Promotion failed: {promote_response.text}"
        safe_print("Promotion Response:", promote_response.json())

        # 3. Login User (as Admin)
        safe_print("\n--- [STEP 3] Logging In ---")
        login_payload = {
            "username": email,
            "password": password
        }
        # FastAPI OAuth2PasswordRequestForm expects form data
        login_response = await client.post("/auth/login", data=login_payload)
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        login_data = login_response.json()
        token = login_data["access_token"]
        assert token is not None
        assert login_data["is_admin"] is True
        headers = {"Authorization": f"Bearer {token}"}

        # 4. Get Account Info & Clear Webhook Queue
        safe_print("\n--- [STEP 4] Verifying Account & Clearing Webhooks ---")
        acc_response = await client.get("/accounts/me", headers=headers)
        assert acc_response.status_code == 200, f"Get accounts failed: {acc_response.text}"
        accounts = acc_response.json()
        assert len(accounts) > 0
        account = accounts[0]
        initial_balance = account["balance"]
        assert initial_balance == 150000.0
        safe_print(f"Initial balance: INR {initial_balance:.2f}")

        # Clear mock receiver logs
        clear_res = await client.delete("/dev/webhook-received", headers=headers)
        assert clear_res.status_code == 200

        # 5. Configure Dynamic Webhook URL
        safe_print("\n--- [STEP 5] Setting Webhook Target URL ---")
        webhook_settings_payload = {
            "webhook_url": "http://test/dev/webhook-receiver"
        }
        set_settings_res = await client.post("/admin/webhook-settings", json=webhook_settings_payload, headers=headers)
        assert set_settings_res.status_code == 200
        safe_print("Webhook Settings Response:", set_settings_res.json())

        # Check GET /admin/webhook-settings
        get_settings_res = await client.get("/admin/webhook-settings", headers=headers)
        assert get_settings_res.status_code == 200
        assert get_settings_res.json()["webhook_url"] == "http://test/dev/webhook-receiver"

        # 6. Deposit Funds
        safe_print("\n--- [STEP 6] Depositing INR 10,000 ---")
        deposit_payload = {"amount": 10000.0}
        dep_response = await client.post(f"/accounts/{account_id}/deposit", json=deposit_payload, headers=headers)
        assert dep_response.status_code == 200, f"Deposit failed: {dep_response.text}"
        dep_data = dep_response.json()
        safe_print("Deposit Response:", dep_data)
        assert dep_data["new_balance"] == 160000.0

        # 7. Make a Normal Transaction (ALLOW) and Verify Webhook
        safe_print("\n--- [STEP 7] Processing ALLOW Transaction (INR 2,500) ---")
        tx_payload = {
            "account_id": account_id,
            "amount": 2500.0,
            "merchant_name": "Kozhikode Cafe",
            "merchant_category": "food",
            "city": "Kozhikode",
            "country": "India",
            "ip_address": "192.168.1.15",
            "device_id": "test_device_1"
        }
        tx_response = await client.post("/transactions/", json=tx_payload, headers=headers)
        assert tx_response.status_code == 200, f"Transaction failed: {tx_response.text}"
        tx_data = tx_response.json()
        safe_print("Normal Transaction Response:", tx_data)
        assert tx_data["decision"] == "ALLOW"
        
        # Verify balance was deducted (160,000 - 2,500 = 157,500)
        acc_response = await client.get("/accounts/me", headers=headers)
        balance_after_allow = acc_response.json()[0]["balance"]
        safe_print(f"Balance after ALLOW: INR {balance_after_allow:.2f}")
        assert balance_after_allow == 157500.0

        # Wait briefly for FastAPI BackgroundTasks to process and send the Webhook
        await asyncio.sleep(1)

        # Retrieve received webhooks
        webhooks_res = await client.get("/dev/webhook-received", headers=headers)
        assert webhooks_res.status_code == 200
        webhook_events = webhooks_res.json()
        safe_print("Received Webhook Events:", webhook_events)
        assert len(webhook_events) == 1
        
        event1 = webhook_events[0]["payload"]
        assert event1["event"] == "transaction.allow"
        assert event1["data"]["amount"] == 2500.0
        assert event1["data"]["decision"] == "ALLOW"
        safe_print("✓ Successfully verified ALLOW event webhook dispatch!")

        # 8. Make a Transaction with Insufficient Funds (Rejected immediately - no webhook should fire)
        safe_print("\n--- [STEP 8] Processing Insufficient Funds Transaction (INR 200,000) ---")
        insufficient_tx_payload = {
            "account_id": account_id,
            "amount": 200000.0,
            "merchant_name": "Luxury Yacht Shop",
            "merchant_category": "luxury",
            "city": "Mumbai",
            "country": "India",
            "ip_address": "192.168.1.15",
            "device_id": "test_device_1"
        }
        inf_response = await client.post("/transactions/", json=insufficient_tx_payload, headers=headers)
        assert inf_response.status_code == 400
        inf_data = inf_response.json()
        safe_print("Insufficient Funds Response (Expected Error):", inf_data)
        assert "Insufficient funds" in inf_data["detail"]

        await asyncio.sleep(1)
        # Verify no new webhooks were logged
        webhooks_res = await client.get("/dev/webhook-received", headers=headers)
        assert len(webhooks_res.json()) == 1

        # 9. Make a Suspicious Transaction that gets BLOCKED (Verify webhook fires with BLOCK status)
        safe_print("\n--- [STEP 9] Processing High-Risk Blocked Transaction (INR 75,000 from Dubai) ---")
        suspicious_tx_payload = {
            "account_id": account_id,
            "amount": 75000.0,
            "merchant_name": "Dubai Crypto Exchange",
            "merchant_category": "crypto",
            "city": "Dubai",
            "country": "UAE",
            "ip_address": "185.12.5.4",
            "device_id": "unknown_phone_99"
        }
        blocked_response = await client.post("/transactions/", json=suspicious_tx_payload, headers=headers)
        assert blocked_response.status_code == 200
        blocked_data = blocked_response.json()
        safe_print("Blocked Transaction Response:", blocked_data)
        assert blocked_data["decision"] == "BLOCK"
        assert blocked_data["risk_score"] == 1.0
        
        # Verify balance was NOT deducted (should still be 157,500)
        acc_response = await client.get("/accounts/me", headers=headers)
        balance_after_block = acc_response.json()[0]["balance"]
        safe_print(f"Balance after BLOCK: INR {balance_after_block:.2f}")
        assert balance_after_block == 157500.0

        await asyncio.sleep(1)
        # Verify BLOCK event webhook was dispatched
        webhooks_res = await client.get("/dev/webhook-received", headers=headers)
        webhook_events = webhooks_res.json()
        safe_print("Received Webhook Events (Updated):", webhook_events)
        assert len(webhook_events) == 2
        
        event2 = webhook_events[1]["payload"]
        assert event2["event"] == "transaction.block"
        assert event2["data"]["amount"] == 75000.0
        assert event2["data"]["decision"] == "BLOCK"
        assert "VEL-TEST-01" in event2["data"]["triggered_rules"]
        safe_print("✓ Successfully verified BLOCK event webhook dispatch!")

        # 10. Make a rapid geographic jump to trigger GEO-VEL-01
        safe_print("\n--- [STEP 10] Processing Geo-Jump Transaction (INR 100 in Germany) ---")
        geo_tx_payload = {
            "account_id": account_id,
            "amount": 100.0,
            "merchant_name": "Berlin Cafe",
            "merchant_category": "food",
            "city": "Berlin",
            "country": "Germany",
            "ip_address": "46.100.12.1",
            "device_id": "test_device_1"
        }
        geo_response = await client.post("/transactions/", json=geo_tx_payload, headers=headers)
        assert geo_response.status_code == 200
        geo_data = geo_response.json()
        safe_print("Geo-Jump Transaction Response:", geo_data)
        assert "GEO-VEL-01" in geo_data["triggered_rules"]
        safe_print("✓ Successfully verified GEO-VEL-01 dynamic geo-velocity rule!")

        safe_print("\n✓ Integration, dynamic webhook, and geo-velocity tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_tests())
