import logging
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import asyncio
import os

from run_llm import get_local_llm, parser
from get_schema import extract_schema
from sqlengine import run_sql_generation

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# --- HEALTH CHECK ---
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "sql_agent"}

# --- SYNC ENDPOINTS ---
@app.post("/sync/database")
async def sync_database(data: DBUpdate):
    try:
        schema = extract_schema(data.connection_uri)
        db_cache[data.db_id] = {
            "id":      data.db_id,
            "uri":     data.connection_uri,
            "db_name": data.db_name,
            "schema":  schema,
        }
        return {"status": "success", "message": f"Database {data.db_id} synced."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/databases")
async def get_all_databases():
    return [{"db_id": k, "db_name": v["db_name"]} for k, v in db_cache.items()]

@app.get("/chatbots")
async def get_all_chatbots():
    return [
        {"chatbot_id": k, "model_name": v["model_name"], "db_ids": v["db_ids"]}
        for k, v in chatbot_cache.items()
    ]

@app.post("/sync/chatbot")
async def sync_chatbot(data: ChatbotUpdate):
    newly_synced_dbs = []
    for db_info in data.databases:
        if db_info.db_id not in db_cache:
            schema = extract_schema(db_info.connection_uri)
            db_cache[db_info.db_id] = {
                "db_name": db_info.db_name,
                "schema":  schema,
                "uri":     db_info.connection_uri,
            }
            newly_synced_dbs.append(db_info.db_id)
    chatbot_cache[data.chatbot_id] = {
        "model_name": data.model_name,
        "db_ids":     [db.db_id for db in data.databases],
    }
    get_model(data.model_name)
    return {
        "status": "success",
        "chatbot_id": data.chatbot_id,
        "implicitly_synced_dbs": newly_synced_dbs,
        "total_active_dbs": len(data.databases),
    }

# --- QUERY ENDPOINTS ---
@app.get("/query")
async def handle_query_get(chatbot_id: str, user_question: str):
    bot_config = chatbot_cache.get(chatbot_id)
    if not bot_config:
        raise HTTPException(status_code=404, detail="Bot not found")
    model = model_registry.get(bot_config["model_name"])
    if not model:
        raise HTTPException(status_code=404, detail="Model not initialized")
    result = run_sql_generation(
        query=user_question,
        model=model,
        allowed_db_ids=bot_config["db_ids"],
        db_cache=db_cache,
    )
    return result

@app.post("/query")
async def handle_query_post(req: QueryRequest):
    bot_config = chatbot_cache.get(req.chatbot_id)
    if not bot_config:
        raise HTTPException(status_code=404, detail="Bot not found")

    model = model_registry.get(bot_config["model_name"])
    if not model:
        raise HTTPException(status_code=404, detail="Model not initialized")

    result = run_sql_generation(
        query          = req.question,
        model          = model,
        allowed_db_ids = bot_config["db_ids"],
        db_cache       = db_cache,
        language       = req.language,      # ← NOUVEAU
    )

    return {
        "answer":     result.get("answer", "Aucune réponse disponible."),
        "confidence": result.get("confidence", 0.0),
        "agent":      "sql",
        "metadata": {
            "selected_db": result.get("selected_db"),
            "db_name":     result.get("db_name"),
            "sql":         result.get("sql"),
            "rows":        result.get("rows", []),
            "error":       result.get("error"),
        }
    }

# --- SYNCHRONISATION INITIALE AVEC L'ADMINUI ---
async def fetch_and_sync_all_chatbots():
    """
    Interroge l'AdminUI et synchronise uniquement les chatbots
    avec sql_enabled=True et au moins une DB active.
    """
    url = f"{ADMIN_API_URL}/api/chatbots/sql/"
    
    for attempt in range(1, 6):  # 5 tentatives
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"[Tentative {attempt}/5] Chargement depuis {url}")
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

            chatbots_list = data.get("chatbots", [])
            logger.info(f"✅ {len(chatbots_list)} chatbot(s) SQL trouvés dans AdminUI")

            for bot in chatbots_list:
                try:
                    payload = ChatbotUpdate(
                        chatbot_id=bot["chatbot_id"],
                        model_name=bot["model_name"],
                        databases=[
                            DBUpdate(
                                db_id=db["db_id"],
                                db_name=db["db_name"],
                                connection_uri=db["connection_uri"],
                            )
                            for db in bot["databases"]
                        ]
                    )
                    await sync_chatbot(payload)
                    logger.info(f"  ✔ Chatbot '{bot['chatbot_name']}' synchronisé ({len(bot['databases'])} DB)")
                except Exception as e:
                    logger.error(f"  ✘ Erreur sync chatbot '{bot.get('chatbot_name')}': {e}")

            return  # succès → on sort

        except Exception as e:
            logger.warning(f"[Tentative {attempt}/5] AdminUI inaccessible: {e}")
            if attempt < 5:
                await asyncio.sleep(5)

    logger.error("❌ AdminUI inaccessible après 5 tentatives. Démarrage sans chatbots.")

@app.on_event("startup")
async def startup_event():
    """Au démarrage, tente de synchroniser tous les chatbots depuis l'AdminUI."""
    # Laisser un peu de temps au réseau pour démarrer
    await asyncio.sleep(5)
    await fetch_and_sync_all_chatbots()

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