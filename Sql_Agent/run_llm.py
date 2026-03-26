# import sqlite3
# import json
# import requests
# from langchain_openai import ChatOpenAI
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.output_parsers import JsonOutputParser

# # Configuration for Local LLM
# LOCAL_URL = "https://rugs-end-units-walnut.trycloudflare.com/v1" # Adjusted to standard base path


# def get_local_llm(model_name):
#     return ChatOpenAI(
#         base_url=LOCAL_URL,
#         api_key="ollama", # Local servers usually don't check this
#         model=model_name,
#         temperature=0,
#         #model_kwargs={"response_format": {"type": "json_object"}} # Forces JSON mode if backend supports it
#     )

# # llm = get_local_llm()
# parser = JsonOutputParser()

#####################

# import os
# from langchain_groq import ChatGroq
# from langchain_core.output_parsers import JsonOutputParser

# # Configuration for Groq API
# GROQ_API_KEY = "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"

# def get_local_llm(model_name="llama-3.1-8b-instant"):
#     """
#     Returns a Groq LLM instance configured for LangChain.
#     Common models: 
#     - "llama-3.1-8b-instant"
#     - "llama-3.3-70b-versatile"
#     - "mixtral-8x7b-32768"
#     """
#     return ChatGroq(
#         groq_api_key=GROQ_API_KEY,
#         model_name=model_name,
#         temperature=0,
#         # Groq supports JSON mode for specific models
#         model_kwargs={"response_format": {"type": "json_object"}} 
#     )

# # Standard JSON parser used by all agents
# parser = JsonOutputParser()

#############
# import os
# from langchain_mistralai import ChatMistralAI
# from langchain_core.output_parsers import JsonOutputParser

# # Configuration for Mistral API
# MISTRAL_API_KEY = "q42xME2SsNoBIYVJKmGGQVPOsdfdPbAD"

# def get_local_llm(model_name="mistral-large-latest"):
#     """
#     Returns a Mistral LLM instance configured for LangChain.

#     Common models:
#     - "mistral-small-latest"
#     - "mistral-medium-latest"
#     - "mistral-large-latest"
#     - "open-mistral-7b"
#     """

#     return ChatMistralAI(
#         api_key=MISTRAL_API_KEY,
#         model=model_name,
#         temperature=0
#     )

# # Standard JSON parser used by all agents
# parser = JsonOutputParser()


#######
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
# Get your free token from hf.co/settings/tokens
HF_TOKEN = "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"

def get_local_llm(model_name="Qwen/Qwen3-Coder-32B-Instruct"):
    """
    Uses Hugging Face's 2026 Router API for SOTA Text-to-SQL.
    This configuration supports 'provider' routing (e.g., :novita).
    """
    return ChatOpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=HF_TOKEN,
        model=model_name,
        temperature=0,
        # Note: Ensure the specific model selected supports JSON mode.
        # Most modern instruction-tuned models on HF Inference do.
        model_kwargs={"response_format": {"type": "json_object"}} 
    )
# # Standard JSON parser used by all agents
parser = JsonOutputParser()