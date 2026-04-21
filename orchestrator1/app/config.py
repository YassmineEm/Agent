import os
from dotenv import load_dotenv
load_dotenv()

OLLAMA_URL     = os.getenv("OLLAMA_URL", "https://ollama.mydigiapps.com")
LLM_SUPERVISOR = os.getenv("LLM_SUPERVISOR", "qwen3:8b")
LLM_VALIDATOR  = os.getenv("LLM_VALIDATOR",  "phi4")

CF_ACCESS_CLIENT_ID     = os.getenv("CF_ACCESS_CLIENT_ID", "")
CF_ACCESS_CLIENT_SECRET = os.getenv("CF_ACCESS_CLIENT_SECRET", "")

SQL_AGENT_URL      = os.getenv("SQL_AGENT_URL",      "http://akwa_sql_agent:8006/query")
RAG_AGENT_URL      = os.getenv("RAG_AGENT_URL",      "http://akwa_rag_agent:8005/query")
LOCATION_AGENT_URL = os.getenv("LOCATION_AGENT_URL", "http://location_agent:8007/query")
WEATHER_AGENT_URL  = os.getenv("WEATHER_AGENT_URL",  "http://weather_agent:8008/query")
AGENT_ADAPTER_URL = os.getenv("AGENT_ADAPTER_URL", "http://akwa_agent_adapter:8009/query")

REDIS_HOST = os.getenv("REDIS_HOST", "akwa_redis_orch")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

ROUTING_CONFIDENCE_MIN = float(os.getenv("ROUTING_CONFIDENCE_MIN", "0.65"))
FUSION_CONFIDENCE_MIN  = float(os.getenv("FUSION_CONFIDENCE_MIN",  "0.40"))
FUSION_STRONG_CONFIDENCE    = float(os.getenv("FUSION_STRONG_CONFIDENCE", "0.60"))
AGENT_TIMEOUT          = int(os.getenv("AGENT_TIMEOUT", "90"))
MAX_RETRIES            = int(os.getenv("MAX_RETRIES",   "1"))
REDIS_TTL              = int(os.getenv("REDIS_TTL",     "3600"))

AGENT_URLS = {
    "sql":      SQL_AGENT_URL,
    "rag":      RAG_AGENT_URL,
    "location": LOCATION_AGENT_URL,
    "weather":  WEATHER_AGENT_URL,
    "dynamic":  AGENT_ADAPTER_URL,
}