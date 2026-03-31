from langchain_core.prompts import ChatPromptTemplate
from run_llm import parser
from sqlalchemy import create_engine, text

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
{SCHEMA_TEXT}"""),
    ("human", "{query}")
])

ROUTER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a database routing engine. Select the MOST relevant database.
Output STRICT JSON only:
{{
  "database": "<database_id>"
}}

AVAILABLE DATABASES
==========================
{DATABASE_NAMES}"""),
    ("human", "{query}")
])


def execute_sql(connection_uri: str, sql: str) -> str:
    """Exécute le SQL et retourne le résultat en texte lisible."""
    try:
        engine = create_engine(connection_uri)
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows    = result.fetchall()
            columns = list(result.keys())

            if not rows:
                return "Aucun résultat trouvé."

            # Formatage en tableau texte
            lines = [" | ".join(str(c) for c in columns)]
            lines.append("-" * 50)
            for row in rows[:20]:
                lines.append(" | ".join(str(v) for v in row))

            if len(rows) > 20:
                lines.append(f"... et {len(rows) - 20} lignes supplémentaires.")

            return "\n".join(lines)

    except Exception as e:
        return f"Erreur d'exécution SQL : {str(e)}"


def run_sql_generation(query: str, model, allowed_db_ids: list, db_cache: dict):
    # 1. Routing vers la bonne base
    db_options = "\n".join([
        f"- ID: {id} (Name: {db_cache[id]['db_name']})"
        for id in allowed_db_ids
    ])
    router_chain = ROUTER_PROMPT | model | parser
    routing      = router_chain.invoke({"DATABASE_NAMES": db_options, "query": query})
    selected_id  = routing.get("database")

    if selected_id not in allowed_db_ids:
        return {
            "answer":     "Je ne peux pas répondre à cette question.",
            "confidence": 0.0,
            "error":      "routing_failed",
            "sql":        None,
        }

    # 2. Génération SQL
    db_meta   = db_cache[selected_id]
    sql_chain = SQL_PROMPT.partial(SCHEMA_TEXT=db_meta["schema"]) | model | parser
    response  = sql_chain.invoke({"query": query})

    sql   = response.get("sql")
    error = response.get("error")

    # 3. Hors périmètre
    if error == "cannot_answer" or not sql:
        return {
            "answer":     "Je ne peux pas répondre à cette question avec les données disponibles.",
            "confidence": 0.0,
            "error":      error or "no_sql_generated",
            "sql":        None,
        }

    # 4. Exécution du SQL → résultat lisible
    result_text = execute_sql(db_meta["uri"], sql)

    return {
        "answer":      result_text,   # ← résultat réel en texte
        "confidence":  0.85,
        "selected_db": selected_id,
        "db_name":     db_meta["db_name"],
        "sql":         sql,           # gardé pour debug
        "error":       None,
    }