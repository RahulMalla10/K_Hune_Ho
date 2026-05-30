import os
from dotenv import load_dotenv
# Load environment variables
load_dotenv()

# configuration class for all settings.
class Config:
    LLM_MODEL_PATH = os.getenv("LLM_MODEL_PATH", "models/qwen2.5-7b-instruct-q4_K_M.gguf")
    N_GPU_LAYERS = int(os.getenv("N_GPU_LAYERS", "99"))
    N_CTX = int(os.getenv("N_CTX", "8192"))
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "512"))

    NEWS_MAX_ARTICLES = int(os.getenv("NEWS_MAX_ARTICLES", "15"))
    NEWS_TIME_RANGE = os.getenv("NEWS_TIME_RANGE", "week")
    DUCKDUCKGO_TIMEOUT = int(os.getenv("DUCKDUCKGO_TIMEOUT", "10"))

    dw_str = os.getenv("DOMAIN_WEIGHTS", "")
    DOMAIN_WEIGHTS = {}
    if dw_str:
        for item in dw_str.split(","):
            if ":" in item:
                k, v = item.split(":")
                DOMAIN_WEIGHTS[k.strip()] = float(v.strip())
    else:
        DOMAIN_WEIGHTS = {
            "financial": 1.0, "geopolitical": 0.9, "legal": 0.7,
            "sentiment": 0.6, "economic": 0.9, "technological": 0.8,
            "social": 0.5, "environmental": 0.7, "health": 0.6,
            "military": 0.8, "cultural": 0.4, "ethical": 0.6,
            "strategic": 0.9, "historical": 0.5, "predictive": 0.8
        }

    DOMAINS = list(DOMAIN_WEIGHTS.keys())
config = Config()
