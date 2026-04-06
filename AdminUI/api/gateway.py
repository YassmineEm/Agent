from typing import Any
import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class ServiceGatewayError(Exception):
    pass


def _post(url: str, *, json: dict | None = None, data: dict | None = None, files: dict | None = None, headers: dict | None = None) -> dict[str, Any]:
    try:
        logger.info(f"[GATEWAY] POST → {url}")
        resp = requests.post(
            url,
            json=json,
            data=data,
            files=files,
            headers=headers or {},
            timeout=settings.MICROSERVICE_TIMEOUT_SECONDS,
        )
        logger.info(f"[GATEWAY] POST ← {url} | status={resp.status_code}")
        if resp.status_code >= 400:
            raise ServiceGatewayError(f"{url} -> {resp.status_code}: {resp.text}")
        return resp.json() if resp.content else {}
    except requests.ConnectionError as exc:
        logger.error(f"[GATEWAY] Connection REFUSED → {url} | {exc}")
        raise ServiceGatewayError(f"Cannot connect to {url} — service is down or wrong port: {exc}") from exc
    except requests.Timeout as exc:
        logger.error(f"[GATEWAY] Timeout → {url} | {exc}")
        raise ServiceGatewayError(f"Timeout calling {url} — increase MICROSERVICE_TIMEOUT_SECONDS: {exc}") from exc
    except requests.RequestException as exc:
        logger.error(f"[GATEWAY] Request error → {url} | {exc}")
        raise ServiceGatewayError(str(exc)) from exc
    except Exception as exc:
        logger.error(f"[GATEWAY] Unexpected error → {url} | {exc}")
        raise ServiceGatewayError(f"Unexpected error calling {url}: {exc}") from exc


def _get(url: str, *, params: dict | None = None, headers: dict | None = None) -> dict[str, Any]:
    try:
        logger.info(f"[GATEWAY] GET → {url} | params={params}")
        resp = requests.get(
            url,
            params=params,
            headers=headers or {},
            timeout=settings.MICROSERVICE_TIMEOUT_SECONDS,
        )
        logger.info(f"[GATEWAY] GET ← {url} | status={resp.status_code}")
        if resp.status_code >= 400:
            raise ServiceGatewayError(f"{url} -> {resp.status_code}: {resp.text}")
        return resp.json() if resp.content else {}
    except requests.ConnectionError as exc:
        logger.error(f"[GATEWAY] Connection REFUSED → {url} | {exc}")
        raise ServiceGatewayError(f"Cannot connect to {url} — service is down or wrong port: {exc}") from exc
    except requests.Timeout as exc:
        logger.error(f"[GATEWAY] Timeout → {url} | {exc}")
        raise ServiceGatewayError(f"Timeout calling {url} — increase MICROSERVICE_TIMEOUT_SECONDS: {exc}") from exc
    except requests.RequestException as exc:
        logger.error(f"[GATEWAY] Request error → {url} | {exc}")
        raise ServiceGatewayError(str(exc)) from exc
    except Exception as exc:
        logger.error(f"[GATEWAY] Unexpected error → {url} | {exc}")
        raise ServiceGatewayError(f"Unexpected error calling {url}: {exc}") from exc


def sync_sql_chatbot(chatbot) -> dict[str, Any]:
    active_connections = chatbot.sql_connections.filter(is_active=True)
    if not active_connections.exists():
        logger.warning(f"[GATEWAY] sync_sql_chatbot — no active connections for chatbot '{chatbot.name}'")
        return {"status": "skipped", "reason": "No active SQL connections"}

    model_name = chatbot.sql_llm or chatbot.base_model

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

    logger.info(f"[GATEWAY] sync_sql_chatbot → chatbot='{chatbot.name}' | payload={payload}")
    result = _post(f"{settings.SQL_AGENT_BASE_URL}/sync/chatbot", json=payload)
    logger.info(f"[GATEWAY] sync_sql_chatbot ← result={result}")
    return result


def upload_rag_document(*, chatbot_id: str, uploaded_file, doc_type: str, description: str = "") -> dict[str, Any]:
    headers = {
        "X-Admin-Key": "akwa_admin_secret_2025"
    }
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

    logger.info(f"[GATEWAY] upload_rag_document → chatbot_id='{chatbot_id}' | file='{uploaded_file.name}' | doc_type='{doc_type}'")
    result = _post(f"{settings.RAG_AGENT_BASE_URL}/admin/upload", data=data, files=files, headers=headers)
    logger.info(f"[GATEWAY] upload_rag_document ← result={result}")
    return result


def query_sql_agent(*, chatbot_id: str, user_question: str) -> dict[str, Any]:
    params = {
        "chatbot_id": chatbot_id,
        "user_question": user_question
    }
    logger.info(f"[GATEWAY] query_sql_agent → chatbot_id='{chatbot_id}' | question='{user_question}'")
    result = _get(f"{settings.SQL_AGENT_BASE_URL}/query", params=params)
    logger.info(f"[GATEWAY] query_sql_agent ← result={result}")
    return result


def query_rag_agent(*, chatbot_id: str, question: str) -> dict[str, Any]:
    payload = {
        "chatbot_id": chatbot_id,
        "question": question
    }
    logger.info(f"[GATEWAY] query_rag_agent → chatbot_id='{chatbot_id}' | question='{question}'")
    result = _post(f"{settings.RAG_AGENT_BASE_URL}/query", json=payload)
    logger.info(f"[GATEWAY] query_rag_agent ← result={result}")
    return result