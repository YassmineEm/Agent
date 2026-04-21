import logging
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import redis 
import json 
import httpx
import asyncio
import os

from run_llm import get_local_llm, parser
from get_schema import extract_schema
from sqlengine import run_sql_generation

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=6379, db=0, decode_responses=True)
app = FastAPI(title="Text2SQL Multi-Agent Service")

# --- GLOBAL CACHE STORES ---
chatbot_cache: Dict[str, dict] = {}
db_cache: Dict[str, dict] = {}
model_registry: Dict[str, any] = {}

# URL de l'AdminUI (depuis variable d'environnement)
ADMIN_API_URL = os.getenv("ADMIN_API_URL", "http://host.docker.internal:8000")

# --- HELPER: Get/Init Model ---
def get_model(model_name: str):
    if model_name not in model_registry:
        model_registry[model_name] = get_local_llm(model_name)
    return model_registry[model_name]

def save_to_redis(key_prefix: str, item_id: str, data: dict):
    r.set(f"{key_prefix}:{item_id}", json.dumps(data))

def get_from_redis(key_prefix: str, item_id: str):
    data = r.get(f"{key_prefix}:{item_id}")
    return json.loads(data) if data else None

# --- DATA MODELS ---
class DBUpdate(BaseModel):
    db_id: str
    db_name: str
    connection_uri: str

class ChatbotUpdate(BaseModel):
    chatbot_id: str
    model_name: str
    databases: List[DBUpdate]

class QueryRequest(BaseModel):
    question: str
    chatbot_id: str
    language:   str = "fr"
    admin_rules: str = ""

# --- HEALTH CHECK ---
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "sql_agent"}

# --- SYNC ENDPOINTS ---
@app.post("/sync/database")
async def sync_database(data: DBUpdate):
    try:
        schema = extract_schema(data.connection_uri)
        db_obj = {
            "id":      data.db_id,
            "uri":     data.connection_uri,
            "db_name": data.db_name,
            "schema":  schema,
        }
        save_to_redis("db", data.db_id, db_obj)
        return {"status": "success", "message": f"Database {data.db_id} synced."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/databases")
async def get_all_databases():
    # Fetch all keys starting with 'db:'
    keys = r.keys("db:*")
    databases = []
    for k in keys:
        v = json.loads(r.get(k))
        databases.append({"db_id": v["id"], "db_name": v["db_name"]})
    return databases

@app.get("/chatbots")
async def get_all_chatbots():
    keys = r.keys("chatbot:*")
    chatbots = []
    for k in keys:
        v = json.loads(r.get(k))
        # Extract ID from key 'chatbot:ID'
        chatbot_id = k.split(":")[1]
        chatbots.append({
            "chatbot_id": chatbot_id, 
            "model_name": v["model_name"], 
            "db_ids": v["db_ids"]
        })
    return chatbots

@app.post("/sync/chatbot")
async def sync_chatbot(data: ChatbotUpdate):
    newly_synced_dbs = []
    for db_info in data.databases:
        # Check Redis instead of local dict
        if not r.exists(f"db:{db_info.db_id}"):
            schema = extract_schema(db_info.connection_uri)
            db_obj = {
                "id":      db_info.db_id,
                "db_name": db_info.db_name,
                "schema":  schema,
                "uri":     db_info.connection_uri,
            }
            r.set(f"db:{db_info.db_id}", json.dumps(db_obj))
            newly_synced_dbs.append(db_info.db_id)
            
    chatbot_obj = {
        "model_name": data.model_name,
        "db_ids":     [db.db_id for db in data.databases],
    }
    r.set(f"chatbot:{data.chatbot_id}", json.dumps(chatbot_obj))
    
    # Trigger RDB snapshot to persist changes immediately
    try:
        r.bgsave()
    except redis.exceptions.ResponseError:
        pass 

    get_model(data.model_name)
    return {
        "status": "success",
        "chatbot_id": data.chatbot_id,
        "implicitly_synced_dbs": newly_synced_dbs,
        "total_active_dbs": len(data.databases),
    }

# --- QUERY ENDPOINTS ---
@app.post("/query")
async def handle_query(req: QueryRequest):
    # 1. Fetch config from Redis (Source of Truth)
    raw_config = r.get(f"chatbot:{req.chatbot_id}")
    if not raw_config:
        raise HTTPException(status_code=404, detail="Chatbot config not found in Redis")
    
    bot_config = json.loads(raw_config)
    
    # 2. Lazy-load model if not in registry
    model = get_model(bot_config["model_name"])

    # 3. Build DB cache from Redis
    active_db_cache = {}
    for db_id in bot_config["db_ids"]:
        db_data = r.get(f"db:{db_id}")
        if db_data:
            active_db_cache[db_id] = json.loads(db_data)

    # 4. Run SQL Generation (Now returns raw data/JSON)
    result = run_sql_generation(
        query=req.question,
        model=model,
        allowed_db_ids=bot_config["db_ids"],
        db_cache=active_db_cache
    )

    return {
        "status": "success" if not result.get("error") else "error",
        "data": result.get("rows", []),
        "metadata": {
            "selected_db": result.get("selected_db"),
            "db_name": result.get("db_name"),
            "sql": result.get("sql"),
            "error": result.get("error")
        }
    }


@app.on_event("startup")
async def startup_event():
    """Restore state from Redis and initialize models."""
    logger.info("🔄 Restoring state from Redis...")
    chatbot_keys = r.keys("chatbot:*")
    
    for key in chatbot_keys:
        try:
            bot_data = json.loads(r.get(key))
            model_name = bot_data.get("model_name")
            if model_name:
                # Pre-warm the model in the registry
                get_model(model_name)
                logger.info(f"✅ Model {model_name} initialized for {key}")
        except Exception as e:
            logger.error(f"❌ Failed to restore {key}: {e}")
    
    logger.info(f"🚀 SQL Engine Ready. {len(chatbot_keys)} chatbots loaded.")

@app.delete("/sync/chatbot/{chatbot_id}")
async def delete_chatbot(chatbot_id: str):
    removed_dbs = []
    if chatbot_id in chatbot_cache:
        # Nettoyer les DBs orphelines
        db_ids = chatbot_cache[chatbot_id]["db_ids"]
        for db_id in db_ids:
            if db_id in db_cache:
                del db_cache[db_id]
                removed_dbs.append(db_id)
        del chatbot_cache[chatbot_id]
        return {"status": "deleted", "chatbot_id": chatbot_id, "removed_dbs": removed_dbs}
    raise HTTPException(status_code=404, detail="Chatbot not found")