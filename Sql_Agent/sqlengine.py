from langchain_core.prompts import ChatPromptTemplate
from run_llm import parser # Assuming your custom parser is here

# Prompts are defined here for isolation
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

def run_sql_generation(query: str, model, allowed_db_ids: list, db_cache: dict):
    """
    Isolated core logic for Routing and SQL Generation.
    """
    # 1. Dynamic Routing
    db_options = "\n".join([f"- ID: {id} (Name: {db_cache[id]['db_name']})" for id in allowed_db_ids])
    
    router_chain = ROUTER_PROMPT | model | parser
    routing = router_chain.invoke({"DATABASE_NAMES": db_options, "query": query})
    
    selected_id = routing.get("database")
    
    # 2. Safety Check
    if selected_id not in allowed_db_ids:
        return {"error": "routing_failed", "details": f"Model selected {selected_id} which is not in allowed list."}

    # 3. Just-in-Time Chain Construction
    db_meta = db_cache[selected_id]
    sql_chain = SQL_PROMPT.partial(SCHEMA_TEXT=db_meta["schema"]) | model | parser
    
    response = sql_chain.invoke({"query": query})
    
    return {
        "selected_db": selected_id,
        "db_name": db_meta["db_name"],
        "sql": response.get("sql"),
        "error": response.get("error")
    }