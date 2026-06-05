from __future__ import annotations
import re
from src.config import config
from src.utils import extract_json_array, extract_json_object, truncate_articles, tokenize
# news tracer uses llm to extract causal chains or linkage
_GENERIC_CAUSAL_PATTERNS = [
    (r"war|conflict|invasion|military|strike|hostilit|tension|sanction", "Geopolitical conflict or sanctions", "regional instability and market uncertainty"),
    (r"election|vote|parliament|government|policy|regulation|law|bill", "Policy or political decision", "regulatory and market shifts"),
    (r"rate hike|interest rate|central bank|fed |inflation|recession|gdp|unemployment", "Macroeconomic pressure (rates, inflation, growth)", "economic spillover effects"),
    (r"supply chain|shortage|disruption|strike|shutdown", "Supply chain or production disruption", "higher costs and delayed deliveries"),
    (r"climate|flood|drought|wildfire|storm|hurricane|heat", "Climate or natural disaster event", "damage, displacement, and recovery costs"),
    (r"pandemic|outbreak|virus|disease|health crisis|who", "Public health event", "healthcare strain and behavior change"),
    (r"ai |artificial intelligence|chip|semiconductor|cyber|data breach|tech", "Technology shift or disruption", "industry restructuring and investment flows"),
    (r"merger|acquisition|bankruptcy|earnings|ipo|stock|market crash", "Corporate or financial market event", "investor sentiment and sector repricing"),
    (r"oil|energy|fuel|gas |opec|power grid|renewable", "Energy market movement", "energy cost pass-through to consumers and industry"),
    (r"trade|tariff|export|import|wto|deal", "Trade policy or agreement", "cross-border commerce effects"),
    (r"protest|riot|strike|unrest|referendum", "Social unrest or mass movement", "policy response and instability"),
]
def _to_str(item) -> str:
    if item is None:
        return ""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for key in ("name", "title", "entity", "event", "text", "label", "value", "description"):
            if key in item and item[key]:
                return str(item[key]).strip()
        return " ".join(str(v) for v in item.values() if v and isinstance(v, (str, int, float))).strip()
    return str(item).strip()


def _join_items(items: list, sep: str = ", ", limit: int = 12) -> str:
    parts = [_to_str(x) for x in (items or [])[:limit]]
    parts = [p for p in parts if p]
    return sep.join(parts)
# class to trace causal chains for a news topic provided.
class NewsTracer:

    CAUSAL_PROMPT = """You are an expert causal news analyst. Explain WHY the topic outcome is happening, using ONLY the articles below.

TOPIC (outcome to explain): {topic}

ARTICLES:
{context}
{meta_block}

Return JSON only (no markdown):
{{
  "outcome": "<one-line restatement of topic>",
  "ranked_causes": [
    {{
      "rank": 1,
      "chain": "Root cause → intermediate step(s) → outcome related to topic",
      "confidence": 0.85,
      "evidence": "brief fact from articles"
    }}
  ]
}}

RULES (apply to ANY subject — politics, tech, sports, health, finance, etc.):
- rank 1 = most DIRECT cause of the topic; higher rank = more indirect
- Each chain is ONE line with " → " between steps
- Provide 4–7 parallel ranked_causes when multiple drivers exist
- NO graph node IDs (no 0->1)
- Every chain must end at or clearly connect to: {topic}
- Use only facts supported by the articles; mark uncertainty with "(reported)"
Output ONLY the JSON object."""

    PLAIN_TEXT_PROMPT = """Topic to explain: {topic}

News headlines and snippets:
{headlines}

Write exactly 5 numbered causal chains explaining this topic.
Format each line as:
N. Root cause → intermediate step → ... → link to topic

Rules:
- Most direct cause is rank 1
- Use → between steps
- Base chains on the headlines above only
- Works for any domain (not only oil or war)

Output plain text only, no JSON."""

    def __init__(self, llm):
        self.llm = llm

    def _call_llm(self, prompt: str, max_tokens: int | None = None) -> str:
        response = self.llm(
            prompt,
            max_tokens=max_tokens or config.CAUSAL_MAX_TOKENS,
            temperature=min(config.TEMPERATURE, 0.15),
            stop=["```", "\n\n\n"],
            echo=False,
        )
        return response["choices"][0]["text"].strip()

    def extract_metadata(self, topic: str, articles: list) -> dict:
        context = truncate_articles(articles, config.ARTICLE_CONTEXT_CHARS)
        prompt = f"""For topic "{topic}", extract from these articles:

{context}

JSON only: {{"entities": [], "events": [], "regions": []}}"""

        text = self._call_llm(prompt, max_tokens=400)
        obj = extract_json_object(text)
        if obj:
            return {
                "entities": [_to_str(x) for x in obj.get("entities", [])[:20] if _to_str(x)],
                "events": [_to_str(x) for x in obj.get("events", [])[:12] if _to_str(x)],
                "regions": [_to_str(x) for x in obj.get("regions", [])[:10] if _to_str(x)],
            }
        return {"entities": [], "events": [], "regions": []}

    def _parse_numbered_chains(self, text: str, topic: str) -> list[dict]:
        chains = []
        for line in text.splitlines():
            line = line.strip()
            m = re.match(r"^(\d+)[.)]\s*(.+)$", line)
            if not m:
                continue
            body = m.group(2).strip()
            if len(body) < 12:
                continue
            body = re.sub(r"\s*->\s*", " → ", body)
            body = re.sub(r"\s*—>\s*", " → ", body)
            if "→" not in body:
                body = f"{body} → {topic}"
            elif topic.lower() not in body.lower():
                body = f"{body} → {topic}"

            chains.append({
                "rank": int(m.group(1)),
                "chain": body,
                "confidence": 0.68,
                "sources": [],
                "evidence": "",
                "fallback": True,
            })
        return chains

    def _pattern_fallback(self, blob: str, topic: str, articles: list) -> list[dict]:
        chains = []
        rank = 1
        seen: set[str] = set()
        for pattern, root, intermediate in _GENERIC_CAUSAL_PATTERNS:
            if re.search(pattern, blob, re.I) and root not in seen:
                seen.add(root)
                chains.append({
                    "rank": rank,
                    "chain": f"{root} → {intermediate} → {topic}",
                    "confidence": 0.65,
                    "sources": [a.get("title", "")[:55] for a in articles[:2]],
                    "evidence": "Matched theme in article text",
                    "fallback": True,
                })
                rank += 1
        return chains[:5]

    def _headline_fallback(self, topic: str, articles: list) -> list[dict]:
        topic_tokens = tokenize(topic)
        chains = []
        rank = 1

        for article in articles[:6]:
            title = (article.get("title") or "").strip()
            if len(title) < 12:
                continue
            title_lower = title.lower()
            overlap = sum(1 for t in topic_tokens if len(t) > 3 and t in title_lower)
            if overlap == 0 and len(topic_tokens) > 2:
                if rank > 4:
                    continue

            snippet = (article.get("snippet") or "")[:120].strip()
            mid = snippet if snippet else "developments reported in coverage"
            chain = f"{title} → {mid} → {topic}"
            if len(chain) > 220:
                chain = f"{title[:100]} → contributes to → {topic}"

            chains.append({
                "rank": rank,
                "chain": chain,
                "confidence": 0.6,
                "sources": [title[:60]],
                "evidence": "Built from news headline",
                "fallback": True,
            })
            rank += 1

        return chains[:5]

    def _fallback_from_articles(self, topic: str, articles: list) -> list[dict]:
        blob = " ".join(
            f"{a.get('title', '')} {a.get('snippet', '')}" for a in articles
        ).lower()

        chains = self._pattern_fallback(blob, topic, articles)
        if len(chains) < 2:
            chains.extend(self._headline_fallback(topic, articles))
        return chains[:7]

    def trace_causal_chains(self, topic: str, articles: list, metadata: dict | None = None) -> list[dict]:
        if not articles:
            return []

        context = truncate_articles(articles, config.ARTICLE_CONTEXT_CHARS)
        meta_block = ""
        if metadata:
            ents = _join_items(metadata.get("entities", []), ", ", 12)
            evts = _join_items(metadata.get("events", []), "; ", 6)
            if ents:
                meta_block += f"\nKey entities: {ents}"
            if evts:
                meta_block += f"\nKey events: {evts}"
        prompt = self.CAUSAL_PROMPT.format(
            topic=topic, context=context, meta_block=meta_block
        )
        text = self._call_llm(prompt, max_tokens=config.CAUSAL_MAX_TOKENS)
        chains = self._parse_causal_response(text, topic)
        if not chains:
            retry = f"""Topic: {topic}

Articles:
{context[:2200]}

JSON: {{"outcome":"{topic}","ranked_causes":[{{"rank":1,"chain":"cause → step → {topic}","confidence":0.8}}]}}
Give 5 causes for THIS topic. JSON only."""
            text = self._call_llm(retry, max_tokens=config.CAUSAL_MAX_TOKENS)
            chains = self._parse_causal_response(text, topic)
        if not chains:
            headlines = "\n".join(
                f"{i}. {a.get('title', '')} — {(a.get('snippet') or '')[:150]}"
                for i, a in enumerate(articles[:8], 1)
            )
            plain = self.PLAIN_TEXT_PROMPT.format(topic=topic, headlines=headlines)
            text = self._call_llm(plain, max_tokens=config.CAUSAL_MAX_TOKENS)
            chains = self._parse_numbered_chains(text, topic)
        if not chains:
            chains = self._fallback_from_articles(topic, articles)

        chains.sort(key=lambda x: (x["rank"], -x["confidence"]))
        for i, c in enumerate(chains, 1):
            c["display_rank"] = i
        return chains

    def _parse_causal_response(self, text: str, topic: str) -> list[dict]:
        obj = extract_json_object(text)
        if obj:
            items = obj.get("ranked_causes") or obj.get("chains") or obj.get("causes")
            if isinstance(items, list):
                return self._normalize_items(items, topic)
            if obj.get("chain"):
                return self._normalize_items([obj], topic)

        arr = extract_json_array(text)
        if arr:
            return self._normalize_items(arr, topic)
        return []

    def _normalize_items(self, items: list, topic: str) -> list[dict]:
        valid = []
        for item in items:
            if not isinstance(item, dict):
                if isinstance(item, str) and item.strip():
                    valid.append({
                        "rank": len(valid) + 1,
                        "chain": item.strip(),
                        "confidence": 0.7,
                        "sources": [],
                    })
                continue

            chain = (
                item.get("chain")
                or item.get("description")
                or item.get("cause")
                or ""
            )
            if not chain and item.get("leads_to"):
                parts = [p for p in [item.get("cause"), item.get("leads_to"), item.get("effect"), topic] if p]
                chain = " → ".join(parts)

            if not chain:
                continue

            chain = re.sub(r"\s*->\s*", " → ", str(chain))
            if "→" not in chain and topic.lower() not in chain.lower():
                chain = f"{chain} → {topic}"

            try:
                rank = int(item.get("rank", len(valid) + 1))
            except (TypeError, ValueError):
                rank = len(valid) + 1

            try:
                conf = float(item.get("confidence", 0.75))
            except (TypeError, ValueError):
                conf = 0.75

            sources = item.get("sources") or []
            if isinstance(sources, list):
                sources = [_to_str(s) for s in sources if _to_str(s)]
            else:
                sources = [_to_str(sources)] if _to_str(sources) else []

            evidence = _to_str(item.get("evidence", ""))
            if evidence and not sources:
                sources = [evidence]

            valid.append({
                "rank": rank,
                "chain": chain.strip(),
                "confidence": conf,
                "sources": sources[:3],
                "evidence": evidence,
            })
        return valid

    def format_report(self, topic: str, chains: list[dict]) -> str:
        lines = [
            "\n" + "=" * 50,
            "=== CAUSAL TRACE (ranked causes → effect) ===",
            "=" * 50,
            f"\nOutcome: {topic}\n",
            "Ranked by directness (1 = most direct cause of the outcome):\n",
        ]

        if not chains:
            lines.append("  Unable to build causal chains (no articles or no parseable causes).\n")
            return "\n".join(lines)

        for c in chains:
            n = c.get("display_rank", c.get("rank", "?"))
            conf = c.get("confidence", 0)
            fb = " [article-derived]" if c.get("fallback") else ""
            lines.append(f"  {n}. {c['chain']}{fb}")
            lines.append(f"     Confidence: {conf:.2f}")
            ev = _to_str(c.get("evidence", ""))
            if ev and not c.get("fallback") and len(ev) < 120:
                lines.append(f"     Evidence: {ev}")
            if c.get("sources"):
                src = [_to_str(s) for s in c["sources"] if _to_str(s)]
                if src:
                    lines.append(f"     Sources: {'; '.join(src[:2])}")
            lines.append("")

        lines.append("=" * 50 + "\n")
        return "\n".join(lines)
