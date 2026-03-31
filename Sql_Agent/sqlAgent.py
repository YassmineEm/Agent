import logging
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel

from run_llm import get_local_llm, parser
from get_schema import extract_schema
from langchain_core.prompts import ChatPromptTemplate
from sqlengine import run_sql_generation

app = FastAPI(title="Text2SQL Multi-Agent Service")

# --- GLOBAL CACHE STORES ---
chatbot_cache: Dict[str, dict] = {}
db_cache: Dict[str, dict] = {}
model_registry: Dict[str, any] = {}


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

# ← NOUVEAU : modèle pour recevoir les requêtes POST de l'orchestrateur
class QueryRequest(BaseModel):
    question:   str
    chatbot_id: str


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
    return [
        {"db_id": k, "db_name": v["db_name"]}
        for k, v in db_cache.items()
    ]
@app.get("/chatbots")
async def get_all_chatbots():
    """Returns a list of all chatbots currently in the microservice cache."""
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
        "status":               "success",
        "chatbot_id":           data.chatbot_id,
        "implicitly_synced_dbs": newly_synced_dbs,
        "total_active_dbs":     len(data.databases),
    }


# --- QUERY ENDPOINT ---

# ← Ancien endpoint GET — gardé pour les tests Postman directs
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
    )

    # result contient déjà "answer" et "confidence" depuis sqlengine
    return {
        "answer":     result.get("answer", "Aucune réponse disponible."),
        "confidence": result.get("confidence", 0.0),
        "agent":      "sql",
        "metadata": {
            "selected_db": result.get("selected_db"),
            "db_name":     result.get("db_name"),
            "sql":         result.get("sql"),
            "error":       result.get("error"),
        }
    }