from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_mistralai import ChatMistralAI
from langchain_openai import ChatOpenAI
import httpx2
from ..config import Settings

def selected_model(s: Settings) -> str:
    return {"gemini":s.gemini_model,"groq":s.groq_model,"openrouter":s.openrouter_model,"mistral":s.mistral_model}[s.agent_provider]

def build_model(s: Settings):
    common={"temperature":s.agent_temperature,"max_retries":s.agent_max_retries,"timeout":s.agent_timeout_seconds}
    if s.agent_provider=="gemini": return ChatGoogleGenerativeAI(model=s.gemini_model,google_api_key=s.gemini_api_key.get_secret_value(),max_output_tokens=s.agent_max_output_tokens,**common)
    if s.agent_provider=="groq": return ChatGroq(model=s.groq_model,api_key=s.groq_api_key,max_tokens=s.agent_max_output_tokens,**common)
    if s.agent_provider=="openrouter":
        timeout=httpx2.Timeout(s.agent_timeout_seconds,connect=min(5,s.agent_timeout_seconds),read=s.agent_timeout_seconds,write=min(10,s.agent_timeout_seconds),pool=min(5,s.agent_timeout_seconds))
        client=httpx2.Client(timeout=timeout,limits=httpx2.Limits(max_connections=4,max_keepalive_connections=2,keepalive_expiry=10),trust_env=False)
        async_client=httpx2.AsyncClient(timeout=timeout,limits=httpx2.Limits(max_connections=4,max_keepalive_connections=2,keepalive_expiry=10),trust_env=False)
        model=ChatOpenAI(model=s.openrouter_model,api_key=s.openrouter_api_key,base_url="https://openrouter.ai/api/v1",max_tokens=s.agent_max_output_tokens,extra_body={"reasoning":{"enabled":False,"exclude":True}},http_client=client,http_async_client=async_client,streaming=False,**common)
        object.__setattr__(model,"_expense_http_clients",(client,async_client))
        return model
    if s.agent_provider=="mistral" and s.mistral_inference_enabled: return ChatMistralAI(model=s.mistral_model,api_key=s.mistral_api_key,max_tokens=s.agent_max_output_tokens,**common)
    raise RuntimeError("Provider is unavailable or disabled")

async def close_model(model) -> None:
    clients=getattr(model,"_expense_http_clients",())
    for client in clients:
        if isinstance(client,httpx2.AsyncClient): await client.aclose()
        else: client.close()
