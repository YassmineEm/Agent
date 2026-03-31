import requests
import json

BASE_URL = "http://localhost:8001"

def run_system_test():
    print("🚀 Starting Multi-Agent Text2SQL System Test...\n")

    # 1. CONFIGURATION: Define Chatbot and its Databases
    # Note: Using the nested structure we implemented
    chatbot_payload = {
        "chatbot_id": "flight_support_agent",
        "model_name": "Qwen/Qwen2.5-7B-Instruct",
        "databases": [
            {
                "db_id": "flight_db_01",
                "db_name": "Global Flight Operations",
                "connection_uri": "sqlite:///database/flight_1/flight_1.sqlite"
            }
        ]
    }

    # 2. SYNC: Register Chatbot (This implicitly syncs the DBs)
    print("Step 1: Syncing Chatbot and Databases...")
    sync_resp = requests.post(f"{BASE_URL}/sync/chatbot", json=chatbot_payload)
    
    if sync_resp.status_code == 200:
        print(f"✅ Sync Successful: {sync_resp.json()}\n")
    else:
        print(f"❌ Sync Failed: {sync_resp.text}")
        return

    # 3. VERIFY: Check the /databases list
    print("Step 2: Verifying Database Cache...")
    db_list_resp = requests.get(f"{BASE_URL}/databases")
    print(f"Active Databases in Cache: {db_list_resp.json()}\n")
    print("Step 3: Verifying Chatbot Cache...")
    chatbot_list_resp = requests.get(f"{BASE_URL}/chatbots")
    print(f"Active Chatbots in Cache: {chatbot_list_resp.json()}\n)")

    # 4. QUERY: Ask the User Question
    print("Step 3: Sending User Query...")
    query_params = {
        "chatbot_id": "flight_support_agent",
        "user_question": "How many aircrafts do we have?"
    }
    
    query_resp = requests.get(f"{BASE_URL}/query", params=query_params)
    
    if query_resp.status_code == 200:
        result = query_resp.json()
        print("--- QUERY RESULT ---")
        print(f"Target DB ID:   {result.get('selected_db')}")
        print(f"Target DB Name: {result.get('db_name')}")
        print(f"Generated SQL:  \n{result.get('sql')}")
        
        if result.get("error"):
            print(f"⚠️ Agent Error: {result.get('error')}")
    else:
        print(f"❌ Query Request Failed: {query_resp.status_code} - {query_resp.text}")
    

if __name__ == "__main__":
    try:
        run_system_test()
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to the server. Is uvicorn running on port 8000?")