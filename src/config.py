import os
import shutil
import subprocess
import sys
from dotenv import load_dotenv
# load environment variables.
load_dotenv()
# configuration class to hold all settings.
class Config:
    def __init__(self):
        self.GPU_AVAILABLE, self.GPU_TYPE = self._detect_gpu_availability()

        env_low_power = os.getenv("LOW_POWER_MODE")
        if env_low_power is not None:
            self.LOW_POWER_MODE = env_low_power.lower() in ("1", "true", "yes")
        else:
            self.LOW_POWER_MODE = not self.GPU_AVAILABLE

        self.CPU_AGGRESSIVE_MODE = os.getenv("CPU_AGGRESSIVE_MODE", "").lower() in ("1", "true", "yes")
        self.CPU_AGGRESSIVE_MODE = self.CPU_AGGRESSIVE_MODE or self.LOW_POWER_MODE

        cpu_threads = max(1, (os.cpu_count() or 2) - 1)
        self.N_THREADS = int(os.getenv("N_THREADS", str(cpu_threads)))
        if os.getenv("AGENT_WORKERS") is not None:
            self.AGENT_WORKERS = int(os.getenv("AGENT_WORKERS", str(min(4, cpu_threads))))
        else:
            self.AGENT_WORKERS = 2 if self.CPU_AGGRESSIVE_MODE else min(4, cpu_threads)

        self.LLM_MODEL_PATH = os.getenv("LLM_MODEL_PATH", "models/qwen2.5-7b-instruct-q4_K_M.gguf")
        self.N_GPU_LAYERS = int(os.getenv("N_GPU_LAYERS", "0" if self.LOW_POWER_MODE else "99"))
        if not self.GPU_AVAILABLE:
            self.N_GPU_LAYERS = 0
        self.DEVICE = "gpu" if self.GPU_AVAILABLE and self.N_GPU_LAYERS > 0 else "cpu"

        self.FLASH_ATTN = os.getenv("FLASH_ATTN", "false").lower() in ("1", "true", "yes")
        self.DOMAIN_ROUTE_THRESHOLD = float(os.getenv("DOMAIN_ROUTE_THRESHOLD", "0.5"))

        if self.CPU_AGGRESSIVE_MODE:
            self.N_CTX = int(os.getenv("N_CTX", "4096"))
            self.MAX_TOKENS = int(os.getenv("MAX_TOKENS", "384"))
            self.CAUSAL_MAX_TOKENS = int(os.getenv("CAUSAL_MAX_TOKENS", "512"))
            self.ARTICLE_CONTEXT_CHARS = int(os.getenv("ARTICLE_CONTEXT_CHARS", "2500"))
            self.NEWS_MAX_ARTICLES = int(os.getenv("NEWS_MAX_ARTICLES", "10"))
            self.MAX_ACTIVE_DOMAINS = int(os.getenv("MAX_ACTIVE_DOMAINS", "5"))
            self.LLAMA_BATCH_SIZE = int(os.getenv("LLAMA_BATCH_SIZE", "256"))
            self.LLAMA_USE_F16_KV = os.getenv("LLAMA_USE_F16_KV", "false").lower() in ("1", "true", "yes")
            self.LLAMA_USE_MLOCK = os.getenv("LLAMA_USE_MLOCK", "false").lower() in ("1", "true", "yes")
        else:
            self.N_CTX = int(os.getenv("N_CTX", "8192"))
            self.MAX_TOKENS = int(os.getenv("MAX_TOKENS", "512"))
            self.CAUSAL_MAX_TOKENS = int(os.getenv("CAUSAL_MAX_TOKENS", "768"))
            self.ARTICLE_CONTEXT_CHARS = int(os.getenv("ARTICLE_CONTEXT_CHARS", "3500"))
            self.NEWS_MAX_ARTICLES = int(os.getenv("NEWS_MAX_ARTICLES", "15"))
            self.MAX_ACTIVE_DOMAINS = int(os.getenv("MAX_ACTIVE_DOMAINS", "6"))
            self.LLAMA_BATCH_SIZE = int(os.getenv("LLAMA_BATCH_SIZE", "512"))
            self.LLAMA_USE_F16_KV = os.getenv("LLAMA_USE_F16_KV", "true").lower() in ("1", "true", "yes")
            self.LLAMA_USE_MLOCK = os.getenv("LLAMA_USE_MLOCK", "false").lower() in ("1", "true", "yes")

        self.NEWS_TIME_RANGE = os.getenv("NEWS_TIME_RANGE", "week")
        self.DUCKDUCKGO_TIMEOUT = int(os.getenv("DUCKDUCKGO_TIMEOUT", "10"))
        self.MIN_ACTIVE_DOMAINS = int(os.getenv("MIN_ACTIVE_DOMAINS", "3"))
        self.ENABLE_CAUSAL_TRACE = os.getenv("ENABLE_CAUSAL_TRACE", "true").lower() in ("1", "true", "yes")

        # LLM sampling temperature (0.0 - 1.0)
        self.TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))

        dw_str = os.getenv("DOMAIN_WEIGHTS", "")
        self.DOMAIN_WEIGHTS = {}
        if dw_str:
            for item in dw_str.split(","):
                if ":" in item:
                    k, v = item.split(":")
                    self.DOMAIN_WEIGHTS[k.strip()] = float(v.strip())
        else:
            self.DOMAIN_WEIGHTS = {
                "financial": 1.0, "geopolitical": 0.9, "legal": 0.7,
                "sentiment": 0.6, "economic": 0.9, "technological": 0.8,
                "social": 0.5, "environmental": 0.7, "health": 0.6,
                "military": 0.8, "cultural": 0.4, "ethical": 0.6,
                "strategic": 0.9, "historical": 0.5, "predictive": 0.8
            }

        self.DOMAINS = list(self.DOMAIN_WEIGHTS.keys())

    def _detect_gpu_availability(self) -> tuple[bool, str]:
        if shutil.which("nvidia-smi") is not None:
            return True, "cuda"

        if sys.platform == "darwin":
            try:
                output = subprocess.check_output(
                    ["system_profiler", "SPDisplaysDataType"],
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                if any(token in output for token in ("Chipset Model", "Apple M", "Metal", "GPU")):
                    return True, "metal"
            except Exception:
                pass
        return False, "cpu"

config = Config()
