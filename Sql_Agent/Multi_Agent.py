from run_llm import get_local_llm, parser
from get_schema import extract_schema
from langchain_core.prompts import ChatPromptTemplate

class MultiAgentSystem:
    def __init__(self, databases, cached_schemas, model_name):
        self.databases = databases
        self.llm = get_local_llm(model_name)
        self.specialized_agents = {}
        
        # --- FIX 1: Define the SQL Prompt Template ONCE outside the loop ---
        # (No need to redefine it for every agent)
        self.sql_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a senior SQL generation engine specialized ONLY in the following database.
You MUST generate SQL using ONLY the provided schema.

If the question cannot be answered using this schema, return: {{"error": "cannot_answer"}}

IMPORTANT RULES:
- Use only listed tables and columns.
- Follow foreign key relationships for joins.
- SQL must be valid SQLite.
- Do NOT include explanations.
- Output STRICT JSON only.

Output format:
{{
  "sql": "<valid_sql_query>"
}}

==========================
DATABASE SCHEMA
==========================
{SCHEMA_TEXT}"""),
            ("human", "{query}")
        ])

        # --- FIX 2: Build chains correctly inside the loop ---
        for db_name in databases.keys():
            schema = cached_schemas[db_name]
            
            # Create the chain directly here.
            # We inject the specific schema into the prompt using .partial()
            chain = self.sql_prompt.partial(SCHEMA_TEXT=schema) | self.llm | parser
            
            self.specialized_agents[db_name] = chain

        # --- FIX 3: Define the missing db_names_list variable ---
        self.db_names_list = list(databases.keys())

        # 1. Orchestrator Prompt
        self.router_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a database routing engine.
Select the MOST relevant database to answer the user query.

IMPORTANT:
- Only choose from the provided database names.
- Do NOT invent database names.
- If none are suitable, return: {{"database": "none"}}

Output STRICT JSON only:
{{
  "database": "<database_name>"
}}

AVAILABLE DATABASES
==========================
{DATABASE_NAMES}"""),
            ("human", "{query}")
        ])

        self.router_chain = self.router_prompt | self.llm | parser

    def run(self, query):
        # Step 1: Route to database
        # Note: invoke expects a dict with keys matching the prompt variables
        routing = self.router_chain.invoke({
            "DATABASE_NAMES": ", ".join(self.db_names_list), 
            "query": query
        })
        
        selected_db = routing.get("database")
        
        if selected_db == "none" or selected_db not in self.databases:
            return {"error": "no_relevant_database", "selected": selected_db}

        # Step 2: Retrieve the pre-built specialized agent
        # We no longer need to extract schema here; the chain already has it!
        agent_chain = self.specialized_agents[selected_db]
        
        sql_output = agent_chain.invoke({"query": query})
        
        return {
            "database": selected_db,
            "sql": sql_output.get("sql"),
            "error": sql_output.get("error")
        }
# from run_llm import get_local_llm, parser
# from get_schema import extract_schema
# from langchain_core.prompts import ChatPromptTemplate
# import json
# import re

# class MultiAgentSystem:
#     def __init__(self, databases, cached_schemas, model_name):
#         self.databases = databases
#         self.llm = get_local_llm(model_name)
#         self.specialized_agents = {}
        
#         # 1. SQL Prompt (Injected with Schema)
#         self.sql_prompt = ChatPromptTemplate.from_messages([
#             ("system", """You are a SQL expert.
# Generate a valid SQLite query for the schema below.
# Output STRICT JSON only: {{"sql": "SELECT ..."}}
# SCHEMA:
# {SCHEMA_TEXT}"""),
#             ("human", "{query}")
#         ])

#         # 2. Router Prompt (Constrained)
#         self.router_prompt = ChatPromptTemplate.from_messages([
#             ("system", """You are a database router.
# Select the best database for the user query.

# CRITICAL RULES:
# 1. You MUST return a valid JSON object.
# 2. The "database" value MUST be one of these exact names: {DATABASE_NAMES}
# 3. Do NOT add explanations.

# Example Output:
# {{"database": "exact_database_name"}}
# """),
#             ("human", "{query}")
#         ])

#         # Build specialized agents
#         for db_name, schema in cached_schemas.items():
#             chain = self.sql_prompt.partial(SCHEMA_TEXT=schema) | self.llm | parser
#             self.specialized_agents[db_name] = chain

#         self.db_names_list = list(databases.keys())
#         self.router_chain = self.router_prompt | self.llm | parser

#     def clean_json(self, text):
#         try:
#             if isinstance(text, dict): return text
#             text = str(text).strip()
#             if "```" in text:
#                 text = re.sub(r"```(?:json)?", "", text).replace("```", "")
#             match = re.search(r'\{.*\}', text, re.DOTALL)
#             return json.loads(match.group()) if match else {}
#         except:
#             return {}

#     def run(self, query):
#         try:
#             # --- STEP 1: ROUTING ---
#             routing_raw = self.router_chain.invoke({
#                 "DATABASE_NAMES": str(self.db_names_list), # Show it a list format
#                 "query": query
#             })
            
#             routing = self.clean_json(routing_raw)
#             selected_db = routing.get("database")

#             # --- FIX: STRICT VALIDATION ---
#             # If the LLM hallucinates a name, check similarity or force default
#             if selected_db not in self.databases:
#                 # Optional: Simple fuzzy match (check if one name contains the other)
#                 # This helps if LLM returns "company_employees" but real name is "company_employee"
#                 found_match = False
#                 for real_name in self.db_names_list:
#                     if real_name in selected_db or selected_db in real_name:
#                         selected_db = real_name
#                         found_match = True
#                         print(f"   ⚠️ Router Fuzzy Match: Corrected to '{selected_db}'")
#                         break
                
#                 if not found_match:
#                     # If really wrong, force to the first DB to avoid crash (or return error)
#                     # return {"error": f"Routing failed: Invalid DB '{selected_db}'"}
#                     # OR: Default to first DB (risky but prevents pipeline break)
#                     print(f"   ❌ Router Hallucination: '{selected_db}'. Defaulting to {self.db_names_list[0]}")
#                     selected_db = self.db_names_list[0] 

#             # --- STEP 2: SQL GENERATION ---
#             agent_chain = self.specialized_agents[selected_db]
#             sql_raw = agent_chain.invoke({"query": query})
#             sql_data = self.clean_json(sql_raw)
            
#             sql = sql_data.get("sql") or sql_data.get("query")

#             return {
#                 "database": selected_db,
#                 "sql": sql
#             }

#         except Exception as e:
#             return {"error": str(e)}