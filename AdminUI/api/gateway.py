from typing import Any
import requests
from django.conf import settings


class ServiceGatewayError(Exception):
    pass


def _post(url: str, *, json: dict | None = None, data: dict | None = None, files: dict | None = None, headers: dict | None = None) -> dict[str, Any]:
    try:
        resp = requests.post(
            url,
            json=json,
            data=data,
            files=files,
            headers=headers or {},
            timeout=settings.MICROSERVICE_TIMEOUT_SECONDS,
        )
        if resp.status_code >= 400:
            raise ServiceGatewayError(f"{url} -> {resp.status_code}: {resp.text}")
        return resp.json() if resp.content else {}
    except requests.RequestException as exc:
        raise ServiceGatewayError(str(exc)) from exc


def sync_sql_chatbot(chatbot) -> dict[str, Any]:
    active_connections = chatbot.sql_connections.filter(is_active=True)
    if not active_connections.exists():
        return {"status": "skipped", "reason": "No active SQL connections"}

    model_name = next((c.llm for c in active_connections if c.llm), chatbot.base_model)

    payload = {
        "chatbot_id": chatbot.name,
        "model_name": model_name,
        "databases": [
            {
                "db_id": conn.db_id,
                "db_name": conn.db_name,
                "connection_uri": conn.connection_uri,
            }
            for conn in active_connections
        ],
    }
    return _post(f"{settings.SQL_AGENT_BASE_URL}/sync/chatbot", json=payload)


def upload_rag_document(*, chatbot_id: str, uploaded_file, doc_type: str, description: str = "") -> dict[str, Any]:
    headers = {}
    
    headers["X-Admin-Key"] = "akwa_admin_secret_2025"

    files = {
        "file": (
            uploaded_file.name,
            uploaded_file,
            uploaded_file.content_type or "application/octet-stream",
        )
    }
    data = {
        "chatbot_id": chatbot_id,
        "doc_type": doc_type,
        "description": description,
    }
    return _post(f"{settings.RAG_AGENT_BASE_URL}/admin/upload", data=data, files=files, headers=headers)