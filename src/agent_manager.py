import json
import sys
from llama_cpp import Llama
from src.config import config


class AgentManager:
    def __init__(self):
        print("Loading LLM (this may take 10-20 seconds)...")
        try:
            self.llm = Llama(
                model_path=config.LLM_MODEL_PATH,
                n_ctx=config.N_CTX,
                n_gpu_layers=config.N_GPU_LAYERS,
                verbose=False,
                flash_attn=True
            )
            print("LLM loaded successfully.\n")
        except Exception as e:
            print(f"\nERROR: Failed to load model: {e}")
            print("Possible fixes:")
            print("1. Run 'python setup.py' to download the model.")
            print("2. Check that the model file exists at:", config.LLM_MODEL_PATH)
            print("3. Reinstall llama-cpp-python with: CMAKE_ARGS='-DLLAMA_CUBLAS=on' pip install llama-cpp-python")
            sys.exit(1)

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
- "prediction": string (
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

    def _truncate_articles(self, articles, max_chars=6000):
        texts = [f"Title: {a['title']}\nDate: {a.get('date','')}\nContent: {a['snippet']}\n---\n" for a in articles]
        combined = "".join(texts)
        return combined[:max_chars] if len(combined) > max_chars else combined

    def analyze_domain(self, domain: str, articles: list) -> dict:
        context = self._truncate_articles(articles)
        prompt = f"""{self.prompts[domain]}

Articles:
{context}

Output only valid JSON array. Example:
[
  {{"prediction": "...", "confidence": 0.85, "timeline": "...", "affected_group": "..."}},
  ...
]"""

        response = self.llm(
            prompt,
            max_tokens=config.MAX_TOKENS * 2,
            temperature=config.TEMPERATURE,
            stop=["```"],
            echo=False
        )
        text = response["choices"][0]["text"].strip()
        try:
            start = text.find("[")
            end = text.rfind("]") + 1
            if start != -1 and end > start:
                parsed = json.loads(text[start:end])
                if isinstance(parsed, list):
                    return {"predictions": parsed}
                else:
                    return {"error": "Not an array", "raw": text}
            return {"error": "No JSON array found", "raw": text}
        except Exception as e:
            return {"error": f"JSON parse failed: {e}", "raw": text}

    def run_all_agents(self, articles: list) -> dict:
        results = {}
        print("Running 15 reasoning agents (each will produce 5-10 detailed predictions):")
        for domain in config.DOMAINS:
            print(f"  - {domain}...", end=" ", flush=True)
            try:
                results[domain] = self.analyze_domain(domain, articles)
                if "predictions" in results[domain]:
                    print(f"done ({len(results[domain]['predictions'])} predictions)")
                else:
                    print("done (no predictions)")
            except Exception as e:
                print(f"failed ({e})")
                results[domain] = {"error": str(e)}
        return results
