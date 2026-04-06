from langchain_groq import ChatGroq
from langchain_core.output_parsers import JsonOutputParser

GROQ_API_KEY = "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"

def get_local_llm(model_name="llama-3.3-70b-versatile"):
    """
    Groq — rapide, gratuit, fiable pour Text-to-SQL.
    Modèles disponibles :
    - llama-3.3-70b-versatile   ← meilleur pour SQL
    - llama-3.1-8b-instant      ← plus rapide, moins précis
    - mixtral-8x7b-32768        ← bon pour JSON structuré
    """
    return ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name=model_name,
        temperature=0,
        model_kwargs={"response_format": {"type": "json_object"}}
    )

parser = JsonOutputParser()

def get_local_llm_text(model_name="llama-3.3-70b-versatile"):
    return ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name=model_name,
        temperature=0.3,
        # Pas de response_format JSON
    )