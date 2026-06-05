from __future__ import annotations
from src.config import config
from src.utils import DOMAIN_KEYWORDS, keyword_overlap_score, clamp
# Domain routing logic to determine which expert domains to  choose for a given news topic.
TOPIC_BOOSTS: dict[str, dict[str, float]] = {
    "oil_energy": {
        "triggers": [
            "oil", "fuel", "petrol", "gasoline", "crude", "opec", "hormuz",
            "pipeline", "energy price", "diesel", "lng",
        ],
        "boosts": {
            "geopolitical": 0.18, "military": 0.15, "economic": 0.15,
            "financial": 0.12, "strategic": 0.10, "environmental": 0.08,
        },
    },
    "conflict": {
        "triggers": ["war", "conflict", "strike", "invasion", "sanction", "tension"],
        "boosts": {"military": 0.20, "geopolitical": 0.18, "strategic": 0.12},
    },
    "health_crisis": {
        "triggers": ["pandemic", "outbreak", "virus", "epidemic", "disease"],
        "boosts": {"health": 0.22, "social": 0.10, "economic": 0.08},
    },
    "tech": {
        "triggers": ["ai", "chip", "semiconductor", "cyber", "tech"],
        "boosts": {"technological": 0.20, "strategic": 0.12, "economic": 0.08},
    },
    "climate": {
        "triggers": ["climate", "carbon", "emission", "flood", "wildfire", "renewable"],
        "boosts": {"environmental": 0.22, "economic": 0.10, "social": 0.08},
    },
    "legal_policy": {
        "triggers": ["court", "lawsuit", "regulation", "ban", "antitrust", "policy"],
        "boosts": {"legal": 0.20, "economic": 0.10, "ethical": 0.08},
    },
    "markets": {
        "triggers": ["stock", "crypto", "bitcoin", "ipo", "earnings", "market"],
        "boosts": {"financial": 0.20, "economic": 0.15, "sentiment": 0.10},
    },
    "sports_culture": {
        "triggers": ["world cup", "olympics", "election", "vote", "referendum"],
        "boosts": {"social": 0.15, "cultural": 0.15, "sentiment": 0.12},
    },
}

class DomainRouter:
    def __init__(self):
        self.base_weights = config.DOMAIN_WEIGHTS
        self.threshold = config.DOMAIN_ROUTE_THRESHOLD
        self.max_domains = config.MAX_ACTIVE_DOMAINS
        self.min_domains = config.MIN_ACTIVE_DOMAINS
# scoring logic for domain selection/routing
    def score_domains(self, topic: str, articles: list | None = None) -> dict[str, float]:
        topic_lower = topic.lower()
        article_text = ""
        if articles:
            article_text = " ".join(
                f"{a.get('title', '')} {a.get('snippet', '')}" for a in articles
            ).lower()

        combined_text = f"{topic_lower} {article_text}"
        scores: dict[str, float] = {}

        for domain, base_weight in self.base_weights.items():
            score = base_weight * 0.45

            if domain in topic_lower:
                score += 0.25

            keywords = DOMAIN_KEYWORDS.get(domain, [])
            topic_kw = keyword_overlap_score(topic_lower, keywords)
            article_kw = keyword_overlap_score(combined_text, keywords) if article_text else 0.0
            score += topic_kw * 0.20 + article_kw * 0.10

            scores[domain] = clamp(score)

        for group in TOPIC_BOOSTS.values():
            if any(t in combined_text for t in group["triggers"]):
                for domain, boost in group["boosts"].items():
                    if domain in scores:
                        scores[domain] = clamp(scores[domain] + boost)

        return scores

    def route(self, topic: str, articles: list | None = None) -> dict[str, float]:
        scores = self.score_domains(topic, articles)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        active = [(d, s) for d, s in ranked if s >= self.threshold]
        if len(active) < self.min_domains:
            active = ranked[: self.min_domains]
        else:
            active = active[: self.max_domains]
        if not active:
            active = ranked[: self.min_domains]
        max_s = max(s for _, s in active) or 1.0
        return {d: clamp(0.5 + 0.5 * (s / max_s)) for d, s in active}

    def skipped_domains(self, active: dict[str, float]) -> list[str]:
        return [d for d in config.DOMAINS if d not in active]
