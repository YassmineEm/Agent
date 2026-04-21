from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.messages import HumanMessage

# Configuration for your Ollama Server
OLLAMA_BASE_URL = "https://ollama.mydigiapps.com/v1" # Note the /v1 for OpenAI compatibility
HEADERS = {
    "CF-Access-Client-Id": "2c8ae98fc22cfe99e9fcc87fc7fab058.access",
    "CF-Access-Client-Secret": "4093f9711287f919fd0855a4f9d383bcdceda22599751fe1e32de33df1a207a7"
}

def get_local_llm(model_name="qwen3:8b"):
    """
    Switched to Ollama via OpenAI-compatible endpoint.
    Keeps the JSON structure requirement.
    """
    return ChatOpenAI(
        base_url=OLLAMA_BASE_URL,
        api_key="ollama",
        model=model_name,
        temperature=0,
        default_headers=HEADERS,
        model_kwargs={"response_format": {"type": "json_object"}}
    )

parser = JsonOutputParser()

def get_local_llm_text(model_name="qwen3:8b"):
    """
    Switched to Ollama for general text generation.
    """
    return ChatOpenAI(
        base_url=OLLAMA_BASE_URL,
        api_key="ollama",
        model=model_name,
        temperature=0.3,
        default_headers=HEADERS
    )