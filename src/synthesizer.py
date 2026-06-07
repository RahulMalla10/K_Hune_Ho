from __future__ import annotations
from src.config import config
from datetime import datetime

class Synthesizer:
    def __init__(self):
        self.weights = config.DOMAIN_WEIGHTS

    def compute_weights(self, topic: str, routed: dict[str, float] | None = None) -> dict:
        if routed:
            return routed
        topic_lower = topic.lower()
        boosted = self.weights.copy()
        for d in boosted:
            if d in topic_lower:
                boosted[d] = min(1.0, boosted[d] + 0.1)
        return boosted

    def build_timeline(self, articles):
        timeline = []
        for a in articles:
            if a.get("date"):
                timeline.append({"date": a["date"], "title": a["title"]})
        timeline.sort(key=lambda x: x["date"])
        return timeline

    def _rank_predictions(self, data: dict, domain_weight: float) -> list:
        preds = data.get("predictions", [])
        if not preds:
            return []

        def sort_key(p):
            eff = p.get("effective_confidence")
            if eff is not None:
                return float(eff)
            conf = p.get("confidence", 0.5)
            try:
                return float(conf) * domain_weight
            except (TypeError, ValueError):
                return domain_weight * 0.5

        return sorted(preds, key=sort_key, reverse=True)

    def format_predictions(self, domain, data, domain_weight: float = 1.0):
        ranked = self._rank_predictions(data, domain_weight)
        if not ranked:
            return "  No predictions generated.\n"
        lines = []
        for i, pred in enumerate(ranked, 1):
            lines.append(f"    {i}. {pred.get('prediction', 'N/A')}")
            conf = pred.get("confidence", "N/A")
            eff = pred.get("effective_confidence")
            conf_line = f"       Confidence: {conf}"
            if eff is not None:
                conf_line += f" | Weighted: {eff}"
            conf_line += f" | Timeline: {pred.get('timeline', 'N/A')}"
            lines.append(conf_line)
            extra_fields = [
                k for k in pred.keys()
                if k not in ("prediction", "confidence", "timeline", "effective_confidence")
            ]
            for field in extra_fields:
                lines.append(f"       {field.replace('_', ' ').title()}: {pred[field]}")
            lines.append("")
        return "\n".join(lines)

    def final_report(
        self,
        topic,
        articles,
        agent_results,
        routed_domains: dict[str, float] | None = None,
        causal_report: str = "",
        skipped: list[str] | None = None,
    ):
        weights = self.compute_weights(topic, routed_domains)
        timeline = self.build_timeline(articles)
        active = list(agent_results.keys())

        report = f"""
------ IN-DEPTH PREDICTIONS REPORT ------

Topic: {topic}
Generated from {len(articles)} news articles
Timestamp: {datetime.now().isoformat()}
"""
        # Causal trace first — primary output
        report += causal_report if causal_report else (
            "\n=== CAUSAL TRACE ===\n  (not run — set ENABLE_CAUSAL_TRACE=true)\n"
        )

        if routed_domains:
            report += "\n=== DOMAIN ROUTING ===\n"
            for d, w in sorted(routed_domains.items(), key=lambda x: -x[1]):
                report += f"  • {d}: weight {w:.2f}\n"
            if skipped:
                report += f"\n  Skipped (low relevance): {', '.join(skipped)}\n"
            report += f"  Active domains analyzed: {len(active)}\n"

        report += "\n=== DOMAIN-WISE PREDICTIONS (ranked by weighted confidence) ===\n"
        for domain in sorted(active, key=lambda d: weights.get(d, 0), reverse=True):
            weight = weights.get(domain, 0.5)
            report += f"\n## {domain.upper()} (routing weight {weight:.2f})\n"
            if domain in agent_results and "predictions" in agent_results[domain]:
                report += self.format_predictions(
                    domain, agent_results[domain], weight
                )
            else:
                err = agent_results[domain].get("error", "parse failed")
                report += f"  Failed to generate predictions ({err}).\n"

        if timeline:
            report += "\n=== TIMELINE OF SOURCES ===\n"
            for t in timeline:
                report += f"  {t['date']}: {t['title']}\n"

        report += "\n=== FULL NEWS SOURCES ===\n"
        for i, a in enumerate(articles, 1):
            report += (
                f"{i}. {a['title']}\n   {a['url']}\n"
                f"   Date: {a.get('date', 'unknown')}\n\n"
            )
        return report
