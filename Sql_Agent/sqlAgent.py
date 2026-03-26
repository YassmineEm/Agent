import logging
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel

# LangChain & Logic Imports
from run_llm import get_local_llm, parser  # Assuming these are in your local files
from get_schema import extract_schema
from langchain_core.prompts import ChatPromptTemplate

from sqlengine import run_sql_generation

app = FastAPI(title="Text2SQL Multi-Agent Service")

# --- 1. GLOBAL CACHE STORES (O(1) Access) ---
# chatbot_cache: { "bot_id": {"model_name": "phi4", "db_ids": ["db1", "db2"]} }
chatbot_cache: Dict[str, dict] = {}

# db_cache: { "db_id": {"schema": "...", "name": "sales_db"} }
db_cache: Dict[str, dict] = {}

# model_registry: Cache for LLM instances so we don't re-init them
model_registry: Dict[str, any] = {}


# --- 3. HELPER: Get/Init Model ---
def get_model(model_name: str):
    if model_name not in model_registry:
        # get_local_llm should point to your Ollama server/instance
        model_registry[model_name] = get_local_llm(model_name)
    return model_registry[model_name]

# --- 4. DATA MODELS FOR POST REQUESTS ---
class DBUpdate(BaseModel):
    db_id: str
    db_name: str
    connection_uri: str 

class ChatbotUpdate(BaseModel):
    chatbot_id: str
    model_name: str
    databases: List[DBUpdate]

# --- 5. ENDPOINTS: CACHE UPDATES ---

@app.post("/sync/database")
async def sync_database(data: DBUpdate):
    """Admin calls this when a DB is added or schema is refreshed."""
    try:
        schema = extract_schema(data.connection_uri)
        db_cache[data.db_id] = {
            "id": data.db_id,
            "uri": data.connection_uri,
            "db_name": data.db_name,
            "schema": schema,
        }
        return {"status": "success", "message": f"Database {data.db_id} synced."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/databases")
async def get_all_databases():
    """Returns a list of all databases currently in the microservice cache."""
    # We return the IDs and Names, but hide the raw schemas/URIs for cleanliness
    return [
        {"db_id": k, "db_name": v["db_name"]} 
        for k, v in db_cache.items()
    ]

# --- ENDPOINT: SYNC CHATBOT (With Implicit DB Sync) ---
@app.post("/sync/chatbot")
async def sync_chatbot(data: ChatbotUpdate):
    """
    Admin calls this to create/edit a chatbot.
    Implicitly syncs any databases that aren't already in the cache.
    """
    newly_synced_dbs = []
    
    for db_info in data.databases:
        # Check if the DB is already in cache
        if db_info.db_id not in db_cache:
            # Trigger implicit sync logic
            schema = extract_schema(db_info.connection_uri)
            db_cache[db_info.db_id] = {
                "db_name": db_info.db_name,
                "schema": schema,
                "uri": db_info.connection_uri
            }
            newly_synced_dbs.append(db_info.db_id)

    # Update chatbot configuration
    chatbot_cache[data.chatbot_id] = {
        "model_name": data.model_name,
        "db_ids": [db.db_id for db in data.databases]
    }
    
    # Pre-warm the model
    get_model(data.model_name)
    
    return {
        "status": "success", 
        "chatbot_id": data.chatbot_id,
        "implicitly_synced_dbs": newly_synced_dbs,
        "total_active_dbs": len(data.databases)
    }
# --- 6. ENDPOINT: THE EXECUTION QUERY ---

@app.get("/query")
async def handle_query(chatbot_id: str, user_question: str):
    # 1. Context Retrieval (O(1))
    bot_config = chatbot_cache.get(chatbot_id)
    if not bot_config: raise HTTPException(status_code=404, detail="Bot not found")
    
    model = model_registry[bot_config["model_name"]]
    
    # 2. Call the isolated Engine
    result = run_sql_generation(
        query=user_question,
        model=model,
        allowed_db_ids=bot_config["db_ids"],
        db_cache=db_cache
    )
    
    return result
