from langchain_core.prompts import ChatPromptTemplate
from run_llm import parser, get_local_llm_text
from sqlalchemy import create_engine, text
import logging


logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# PROMPTS
# ──────────────────────────────────────────────────────────────────────────────

SQL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a senior SQL generation engine.
You MUST generate SQL using ONLY the provided schema.
If the question cannot be answered using this schema, return: {{"error": "cannot_answer"}}

Output STRICT JSON only:
{{
  "sql": "<valid_sql_query>"
}}

DATABASE SCHEMA
==========================
{SCHEMA_TEXT}

ADMIN RULES (PRIORITY — follow these exactly)
==========================
{ADMIN_RULES}

Output STRICT JSON only: {{"sql": "<valid_sql_query>"}}"""),
    ("human", "{query}")
])

ROUTER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a database routing engine. Select the MOST relevant database for the question.
Analyse the table names and column names to decide which database contains the answer.
Output STRICT JSON only:
{{
  "database": "<database_id>"
}}

AVAILABLE DATABASES WITH THEIR SCHEMAS
==========================
{DATABASE_NAMES}"""),
    ("human", "{query}")
])

NATURAL_LANGUAGE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful data analyst for AKWA, a fuel company in Morocco.
Your job is to convert raw SQL query results into a natural, concise answer.

RULES:
- Respond ONLY in this language: {language}
- Currency is always Moroccan Dirham (DH or MAD)
- Be concise: 2-4 sentences maximum unless listing items
- Do NOT mention SQL, databases, or technical terms
- If the result is a list of stations, format each station on its own line
- If no data found, say so clearly in the target language"""),
    ("human", """User question: {question}

Raw data result:
{raw_result}

Please provide a natural language answer in {language}:""")
])


# ──────────────────────────────────────────────────────────────────────────────
# UTILS
# ──────────────────────────────────────────────────────────────────────────────

def execute_sql(connection_uri: str, sql: str) -> tuple[str, list]:
    """
    Exécute le SQL et retourne (texte_lisible, rows_json).
    - texte_lisible : pour le validator et l'affichage
    - rows_json     : liste de dicts pour injection dans le location agent
    """
    try:
        engine = create_engine(connection_uri)
        with engine.connect() as conn:
            result  = conn.execute(text(sql))
            rows    = result.fetchall()
            columns = list(result.keys())

            if not rows:
                return "Aucun résultat trouvé.", []

            # Texte lisible
            lines = [" | ".join(str(c) for c in columns)]
            lines.append("-" * 50)
            for row in rows[:20]:
                lines.append(" | ".join(str(v) for v in row))
            if len(rows) > 20:
                lines.append(f"... et {len(rows) - 20} lignes supplémentaires.")
            text_result = "\n".join(lines)

            # JSON structuré — liste de dicts {colonne: valeur}
            rows_json = [
                {columns[i]: row[i] for i in range(len(columns))}
                for row in rows
            ]

            return text_result, rows_json

    except Exception as e:
        return f"Erreur d'exécution SQL : {str(e)}", []


def _parse_rows_as_list(connection_uri: str, sql: str) -> list[dict]:
    """
    Retourne les résultats SQL sous forme de liste de dicts (pour location agent).
    Utilisé pour renvoyer les lignes brutes dans la réponse.
    """
    try:
        engine = create_engine(connection_uri)
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows = result.fetchall()
            return [dict(zip(columns, row)) for row in rows[:50]]
    except Exception:
        return []


def _format_as_natural_response(query, raw_result, model, language="fr"):
    if not raw_result or "Aucun résultat" in raw_result or "Erreur" in raw_result:
        if language in ("ar", "arabe", "arabic"):
            return "لا توجد نتائج متاحة."
        elif language in ("en", "anglais", "english"):
            return "No results found."
        return "Aucun résultat disponible."
    try:
        model_name = getattr(model, 'model_name', 'llama-3.3-70b-versatile')
        text_llm = get_local_llm_text(model_name)
        chain = NATURAL_LANGUAGE_PROMPT | text_llm
        response = chain.invoke({
            "question": query,
            "raw_result": raw_result[:1000],
            "language": language,
        })
        return response.content.strip()
    except Exception as e:
        logger.error(f"Erreur reformulation: {type(e).__name__}: {e}")
        logger.error(f"Modèle utilisé: {getattr(model, 'model_name', 'inconnu')}")
        return raw_result


# ──────────────────────────────────────────────────────────────────────────────
# MAIN FUNCTION
# ──────────────────────────────────────────────────────────────────────────────

def run_sql_generation(
    query:          str,
    model,
    allowed_db_ids: list,
    db_cache:       dict,
    language:       str = "fr",      
    admin_rules=""
) -> dict:
    """
    Pipeline complet : routing → SQL generation → execution → natural answer.
    """
    # ── 1. Routing ────────────────────────────────────────────────────────────
    db_options = "\n\n".join([
        f"- ID: {id}\n  Name: {db_cache[id]['db_name']}\n  Schema: {db_cache[id]['schema']}"
        for id in allowed_db_ids
        if id in db_cache
    ])

    router_chain = ROUTER_PROMPT | model | parser
    routing = router_chain.invoke({
        "DATABASE_NAMES": db_options,
        "query": query,
    })
    selected_id = routing.get("database")

    # ── Garde-fou routing (fuzzy fallback) ───────────────────────────────────
    if selected_id not in allowed_db_ids:
        query_lower = query.lower()
        for db_id in allowed_db_ids:
            schema_lower = db_cache[db_id].get("schema", "").lower()
            for word in query_lower.split():
                if len(word) > 3 and word in schema_lower:
                    selected_id = db_id
                    break
            if selected_id in allowed_db_ids:
                break

    if selected_id not in allowed_db_ids:
        # Message d'erreur dans la langue demandée
        if language in ("ar", "arabe", "arabic"):
            error_msg = "لا يمكنني تحديد قاعدة البيانات المناسبة."
        elif language in ("en", "anglais", "english"):
            error_msg = "I cannot determine which database to use."
        else:
            error_msg = "Je ne peux pas déterminer quelle base de données utiliser."
        return {
            "answer":     error_msg,
            "rows":       [],
            "confidence": 0.0,
            "error":      "routing_failed",
            "sql":        None,
        }

    # ── 2. Génération SQL ─────────────────────────────────────────────────────
    db_meta = db_cache[selected_id]
    sql_chain = SQL_PROMPT.partial(SCHEMA_TEXT=db_meta["schema"], ADMIN_RULES=admin_rules if admin_rules else "Aucune règle spécifique.") | model | parser
    response = sql_chain.invoke({"query": query})

    sql = response.get("sql")
    error = response.get("error")

    # ── 3. Hors périmètre ────────────────────────────────────────────────────
    if error == "cannot_answer" or not sql:
        if language in ("ar", "arabe", "arabic"):
            no_answer = "لا يمكنني الإجابة على هذا السؤال بالبيانات المتاحة."
        elif language in ("en", "anglais", "english"):
            no_answer = "I cannot answer this question with the available data."
        else:
            no_answer = "Je ne peux pas répondre à cette question avec les données disponibles."
        return {
            "answer":     no_answer,
            "rows":       [],
            "confidence": 0.0,
            "error":      error or "no_sql_generated",
            "sql":        None,
        }

    # ── 4. Exécution du SQL (résultat brut + rows_json) ──────────────────────
    raw_result, rows_json = execute_sql(db_meta["uri"], sql)

    # ── 5. Génération d'une réponse naturelle dans la langue cible ───────────
    natural_answer = _format_as_natural_response(
        query=query,
        raw_result=raw_result,
        model=model,
        language=language,
    )

    # ── 6. Retour final (avec rows pour le location agent) ───────────────────
    return {
        "answer":      natural_answer,          # ← réponse naturelle, pas tableau brut
        "rows":        rows_json,               # ← liste de dicts pour location agent
        "confidence":  0.85,
        "selected_db": selected_id,
        "db_name":     db_meta["db_name"],
        "sql":         sql,
        "error":       None,
    }