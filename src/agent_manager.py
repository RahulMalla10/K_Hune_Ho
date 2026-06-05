from __future__ import annotations
import inspect
import json
import sys
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from llama_cpp import Llama
from src.config import config
from src.utils import extract_json_array, truncate_articles

class AgentManager:
    def __init__(self):
        mode = "GPU" if config.DEVICE == "gpu" else "CPU"
        print(f"Loading LLM [{mode}] (this may take 10-20 seconds)...")
        try:
            llama_kwargs = {
                "model_path": config.LLM_MODEL_PATH,
                "n_ctx": config.N_CTX,
                "n_gpu_layers": config.N_GPU_LAYERS,
                "n_threads": config.N_THREADS,
                "verbose": False,
            }
            if getattr(config, "FLASH_ATTN", False):
                llama_kwargs["flash_attn"] = True
            if config.LLAMA_BATCH_SIZE:
                llama_kwargs["n_batch"] = config.LLAMA_BATCH_SIZE
            if config.LLAMA_USE_F16_KV:
                llama_kwargs["f16_kv"] = True
            if config.LLAMA_USE_MLOCK:
                llama_kwargs["use_mlock"] = True

            supported_params = inspect.signature(Llama.__init__).parameters
            llama_kwargs = {
                key: value for key, value in llama_kwargs.items() if key in supported_params
            }

            self.llm = Llama(**llama_kwargs)
            self._print_lock = threading.Lock()
            self._results_lock = threading.Lock()
            print("LLM loaded successfully.\n")
        except Exception as e:
            print(f"\nERROR: Failed to load model: {e}")
            print("Possible fixes:")
            print("1. Run 'python setup.py' to download the model.")
            print("2. Check that the model file exists at:", config.LLM_MODEL_PATH)
            print("3. Set LOW_POWER_MODE=true and N_GPU_LAYERS=0 for Mac CPU inference")
            sys.exit(1)
        self._domain_fields = {
            "sentiment": "affected_group",
            "financial": "affected_sector",
            "geopolitical": "affected_actor",
            "legal": "jurisdiction",
            "technological": "tech_area",
            "social": "demographic",
            "environmental": "region",
            "health": "population",
            "military": "region_or_alliance",
            "economic": "economy",
            "cultural": "cultural_region",
            "ethical": "stakeholder",
            "strategic": "entity",
            "historical": "historical_event",
            "predictive": "domain",
        }

        self.prompts = {
            "sentiment": """You are a sentiment analyst. Based on the news articles below, predict the public sentiment evolution over the next 6 months.
Output a JSON array of 5-10 predictions. Each prediction object must have:
- "prediction": string 
- "confidence": float between 0 and 1
- "timeline": string (e.g., "1 month", "3 months", "6 months")
- "affected_group": string 
No extra text outside JSON.""",

            "financial": """You are a financial analyst. Predict specific market movements, sector impacts, and investment trends for the next 12 months.
Output a JSON array of 8-10 predictions. Each prediction must have:
- "prediction": string 
- "confidence": float
- "timeline": string 
- "affected_sector": string 
No extra text outside JSON.""",

            "geopolitical": """You are a geopolitical analyst. Identify the most affected countries or regions and predict diplomatic, economic, or military outcomes.
Output a JSON array of 8-10 predictions. Each prediction:
- "prediction": string 
- "confidence": float
- "timeline": string
- "affected_actor": string 
No extra text outside JSON.""",

            "legal": """You are a legal analyst. Predict regulatory changes, litigation outcomes, or compliance requirements.
Output a JSON array of 5-8 predictions. Each prediction:
- "prediction": string 
- "confidence": float
- "timeline": string
- "jurisdiction": string 
No extra text outside JSON.""",

            "technological": """You are a technology analyst. Predict technology adoption, breakthroughs, or disruptions.
Output a JSON array of 8-10 predictions. Each prediction:
- "prediction": string
- "confidence": float
- "timeline": string
- "tech_area": string 
No extra text outside JSON.""",

            "social": """You are a social impact analyst. Predict changes in public behavior, inequality, or social movements.
Output a JSON array of 5-8 predictions. Each prediction:
- "prediction": string
- "confidence": float
- "timeline": string
- "demographic": string
No extra text outside JSON.""",

            "environmental": """You are an environmental analyst. Predict climate impacts, policy outcomes, or ecological changes.
Output a JSON array of 5-8 predictions. Each prediction:
- "prediction": string
- "confidence": float
- "timeline": string
- "region": string
No extra text outside JSON.""",

            "health": """You are a public health analyst. Predict disease trends, healthcare policy, or medical breakthroughs.
Output a JSON array of 5-8 predictions. Each prediction:
- "prediction": string
- "confidence": float
- "timeline": string
- "population": string
No extra text outside JSON.""",

            "military": """You are a defence analyst. Predict conflict risks, arms deployments, or defense spending shifts.
Output a JSON array of 5-8 predictions. Each prediction:
- "prediction": string
- "confidence": float
- "timeline": string
- "region_or_alliance": string
No extra text outside JSON.""",

            "economic": """You are an economic analyst. Predict GDP growth, inflation, employment, or trade flows for specific economies.
Output a JSON array of 8-10 predictions. Each prediction:
- "prediction": string 
- "confidence": float
- "timeline": string
- "economy": string (country or sector)
No extra text outside JSON.""",

            "cultural": """You are a cultural analyst. Predict shifts in media, values, or consumer behavior.
Output a JSON array of 5-8 predictions. Each prediction:
- "prediction": string
- "confidence": float
- "timeline": string
- "cultural_region": string
No extra text outside JSON.""",

            "ethical": """You are an ethics analyst. Predict emerging ethical debates or policy responses.
Output a JSON array of 5-8 predictions. Each prediction:
- "prediction": string
- "confidence": float
- "timeline": string
- "stakeholder": string
No extra text outside JSON.""",

            "strategic": """You are a strategic analyst. Predict which companies, industries, or countries gain or lose power.
Output a JSON array of 8-10 predictions. Each prediction:
- "prediction": string 
- "confidence": float
- "timeline": string
- "entity": string
No extra text outside JSON.""",

            "historical": """You are a historical analyst. Draw parallels to past events and predict if similar patterns repeat.
Output a JSON array of 5-8 predictions. Each prediction:
- "prediction": string 
- "confidence": float
- "timeline": string
- "historical_event": string
No extra text outside JSON.""",

            "predictive": """You are a forecasting analyst. Provide high‑level, multi‑domain future scenarios.
Output a JSON array of 6-10 predictions across short, medium, and long term. Each prediction:
- "prediction": string (overall outcome)
- "confidence": float
- "timeline": string (e.g., "short-term (0-3 months)", "medium (3-12 months)", "long (>1 year)")
- "domain": string (which domain this prediction belongs to)
No extra text outside JSON."""
        }

    def _prediction_count(self, weight: float) -> int:
        """Fewer predictions = less truncated JSON on CPU/low token limits."""
        if weight >= 0.9:
            return 6
        if weight >= 0.75:
            return 5
        return 4

    def _max_tokens_for_weight(self, weight: float) -> int:
        base = config.MAX_TOKENS
        if weight >= 0.85:
            return int(base * 2.5)
        if weight >= 0.65:
            return int(base * 2)
        return int(base * 1.5)

    def _build_domain_prompt(
        self, domain: str, topic: str, context: str, count: int, weight: float
    ) -> str:
        extra = self._domain_fields.get(domain, "detail")
        return f"""{self.prompts[domain]}

Topic: {topic}
Produce exactly {count} predictions grounded in the articles below.

Articles:
{context}

CRITICAL: Reply with ONLY a valid JSON array. No markdown, no explanation.
Example format:
[
  {{"prediction": "specific forecast", "confidence": 0.85, "timeline": "3-6 months", "{extra}": "specific entity"}}
]"""

    def _llm_complete(self, prompt: str, max_tokens: int) -> str:
        response = self.llm(
            prompt,
            max_tokens=max_tokens,
            temperature=config.TEMPERATURE,
            stop=["```", "\n\n\n"],
            echo=False,
        )
        return response["choices"][0]["text"].strip()

    def _normalize_predictions(self, parsed: list, weight: float) -> list:
        out = []
        for pred in parsed:
            if not isinstance(pred, dict):
                continue
            if "prediction" not in pred and "text" in pred:
                pred["prediction"] = pred["text"]
            if "prediction" not in pred:
                continue
            try:
                raw = float(pred.get("confidence", 0.7))
                pred["effective_confidence"] = round(min(1.0, raw * weight), 3)
            except (TypeError, ValueError):
                pred["effective_confidence"] = round(weight * 0.5, 3)
            out.append(pred)
        return out

    def analyze_domain(
        self,
        domain: str,
        articles: list,
        topic: str,
        weight: float = 1.0,
    ) -> dict:
        context = truncate_articles(articles, config.ARTICLE_CONTEXT_CHARS)
        count = self._prediction_count(weight)
        max_tokens = self._max_tokens_for_weight(weight)

        prompt = self._build_domain_prompt(domain, topic, context, count, weight)
        text = self._llm_complete(prompt, max_tokens)
        parsed = extract_json_array(text)
        if not parsed:
            retry_prompt = self._build_domain_prompt(
                domain, topic, context[:2500], max(3, count - 2), weight
            )
            retry_prompt += "\nReturn compact JSON array only. Max 4 objects."
            text = self._llm_complete(retry_prompt, max_tokens)
            parsed = extract_json_array(text)

        if parsed:
            normalized = self._normalize_predictions(parsed, weight)
            if normalized:
                return {"predictions": normalized, "routing_weight": weight}

        return {"error": "JSON parse failed", "raw": text[:500], "routing_weight": weight}

    def run_routed_agents(
        self,
        articles: list,
        topic: str,
        routed_domains: dict[str, float],
        on_domain_start: Callable[[str, int, int], None] | None = None,
    ) -> dict:
        results = {}
        sorted_domains = sorted(routed_domains.items(), key=lambda x: -x[1])
        n = len(sorted_domains)
        print(f"Running {n} routed reasoning agents (topic-weighted):")

        if config.DEVICE != "cpu" or n <= 1:
            for index, (domain, weight) in enumerate(sorted_domains, start=1):
                if on_domain_start:
                    on_domain_start(domain, index, n)
                print(f"  - {domain} (w={weight:.2f})...", end=" ", flush=True)
                try:
                    results[domain] = self.analyze_domain(domain, articles, topic, weight)
                    if "predictions" in results[domain]:
                        print(f"done ({len(results[domain]['predictions'])} predictions)")
                    else:
                        print("done (parse issue)")
                except Exception as e:
                    print(f"failed ({e})")
                    results[domain] = {"error": str(e), "routing_weight": weight}
            return results

        max_workers = min(config.AGENT_WORKERS, n)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures: dict = {}
            for index, (domain, weight) in enumerate(sorted_domains, start=1):
                if on_domain_start:
                    on_domain_start(domain, index, n)
                print(f"  - {domain} (w={weight:.2f})... queued", flush=True)
                futures[executor.submit(self.analyze_domain, domain, articles, topic, weight)] = (
                    domain,
                    weight,
                )

            for future in as_completed(futures):
                domain, weight = futures[future]
                try:
                    domain_result = future.result()
                except Exception as e:
                    domain_result = {"error": str(e), "routing_weight": weight}

                with self._results_lock:
                    results[domain] = domain_result

                with self._print_lock:
                    if "predictions" in domain_result:
                        print(f"  - {domain} done ({len(domain_result['predictions'])} predictions)")
                    else:
                        if "error" in domain_result:
                            print(f"  - {domain} failed ({domain_result['error']})")
                        else:
                            print(f"  - {domain} done (parse issue)")

        return results

    def run_all_agents(self, articles: list, topic: str = "") -> dict:
        from src.domain_router import DomainRouter
        router = DomainRouter()
        routed = router.route(topic or "general news", articles)
        return self.run_routed_agents(articles, topic or "general news", routed)
