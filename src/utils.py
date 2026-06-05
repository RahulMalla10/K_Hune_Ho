from __future__ import annotations
import json
import re
from typing import Any

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "financial": [
        "stock", "market", "invest", "bank", "fund", "equity", "bond", "ipo",
        "earnings", "dividend", "trading", "nasdaq", "dow", "sensex", "nifty",
    ],
    "geopolitical": [
        "diplomacy", "sanction", "treaty", "embassy", "nato", "un ", "geopolitic",
        "foreign policy", "alliance", "summit", "bilateral", "multilateral",
    ],
    "legal": [
        "court", "lawsuit", "regulation", "compliance", "legislation", "bill",
        "antitrust", "patent", "copyright", "verdict", "ruling", "law ",
    ],
    "sentiment": [
        "public opinion", "poll", "approval", "protest", "backlash", "outrage",
        "support", "favorability", "trust", "sentiment", "mood",
    ],
    "economic": [
        "gdp", "inflation", "unemployment", "recession", "trade", "tariff",
        "fiscal", "monetary", "central bank", "interest rate", "economy",
        "deficit", "growth", "exports", "imports",
    ],
    "technological": [
        "ai", "tech", "software", "chip", "semiconductor", "startup", "cyber",
        "digital", "innovation", "automation", "robot", "cloud", "data",
    ],
    "social": [
        "inequality", "demographic", "migration", "housing", "education",
        "welfare", "community", "social", "labor", "workers", "union",
    ],
    "environmental": [
        "climate", "carbon", "emission", "renewable", "pollution", "green",
        "sustainability", "ecology", "wildfire", "flood", "drought",
    ],
    "health": [
        "disease", "pandemic", "vaccine", "hospital", "healthcare", "who",
        "outbreak", "virus", "medical", "pharma", "epidemic",
    ],
    "military": [
        "war", "conflict", "army", "navy", "missile", "defense", "troops",
        "invasion", "airstrike", "weapon", "military", "combat", "nuclear",
    ],
    "cultural": [
        "media", "film", "music", "culture", "entertainment", "fashion",
        "sport", "celebrity", "arts", "festival",
    ],
    "ethical": [
        "ethics", "moral", "privacy", "rights", "discrimination", "bias",
        "accountability", "transparency", "governance",
    ],
    "strategic": [
        "strategy", "competitive", "market share", "supply chain", "merger",
        "acquisition", "dominance", "power", "influence", "leverage",
    ],
    "historical": [
        "history", "historical", "precedent", "analog", "past", "legacy",
        "century", "era", "colonial", "revolution",
    ],
    "predictive": [
        "forecast", "scenario", "outlook", "trend", "future", "projection",
        "predict", "risk", "uncertainty",
    ],
}

def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))

def keyword_overlap_score(text: str, keywords: list[str]) -> float:
    text_lower = text.lower()
    hits = sum(1 for kw in keywords if kw in text_lower)
    if not keywords:
        return 0.0
    return min(1.0, hits / max(3, len(keywords) * 0.15))

def _try_parse_json(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None

def _repair_json_array(fragment: str) -> str:
    fragment = fragment.strip()
    fragment = re.sub(r",\s*]", "]", fragment)
    fragment = re.sub(r",\s*}", "}", fragment)
    if fragment.count("[") > fragment.count("]"):
        fragment += "]" * (fragment.count("[") - fragment.count("]"))
    if fragment.count("{") > fragment.count("}"):
        fragment += "}" * (fragment.count("{") - fragment.count("}"))
    return fragment

def extract_json_objects_loose(text: str) -> list:
    objects = []
    for match in re.finditer(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL):
        obj = _try_parse_json(match.group())
        if isinstance(obj, dict) and obj:
            objects.append(obj)
    return objects

def extract_json_array(text: str) -> list | None:
    if not text or not text.strip():
        return None
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()

    start = cleaned.find("[")
    end = cleaned.rfind("]") + 1
    if start != -1 and end > start:
        raw = cleaned[start:end]
        parsed = _try_parse_json(raw)
        if isinstance(parsed, list) and parsed:
            return parsed
        repaired = _try_parse_json(_repair_json_array(raw))
        if isinstance(repaired, list) and repaired:
            return repaired
    obj = extract_json_object(cleaned)
    if isinstance(obj, dict):
        if "predictions" in obj and isinstance(obj["predictions"], list):
            return obj["predictions"]
        if "ranked_causes" in obj and isinstance(obj["ranked_causes"], list):
            return obj["ranked_causes"]
        return [obj]

    loose = extract_json_objects_loose(cleaned)
    return loose if loose else None

def extract_json_object(text: str) -> dict | None:
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start:end])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None

def truncate_articles(articles: list, max_chars: int = 4000) -> str:
    texts = [
        f"Title: {a['title']}\nDate: {a.get('date', '')}\n"
        f"Source: {a.get('source', '')}\nContent: {a['snippet']}\n---\n"
        for a in articles
    ]
    combined = "".join(texts)
    return combined[:max_chars] if len(combined) > max_chars else combined

def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))
