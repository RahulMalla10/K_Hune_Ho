from __future__ import annotations
import asyncio
import json
import threading
from collections.abc import AsyncIterator, Iterator
from typing import Any
from src.agent_manager import AgentManager
from src.config import config
from src.domain_router import DomainRouter
from src.news_retriever import NewsRetriever
from src.news_tracer import NewsTracer
from src.pipeline_log import log_banner, log_detail, log_done, log_failed, log_step
from src.synthesizer import Synthesizer

def _evt(step: int, status: str, message: str = "", **extra: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"type": "progress", "step": step, "status": status, "message": message}
    out.update(extra)
    return out


def _emit_step(step: int, status: str, message: str, **extra: Any) -> dict[str, Any]:
    log_step(step, status, message)
    return _evt(step, status, message, **extra)


def analyze_event_generator(
    topic: str,
    enable_causal_trace: bool,
    *,
    retriever: NewsRetriever,
    router: DomainRouter,
    agent_manager: AgentManager,
    tracer: NewsTracer,
    synthesizer: Synthesizer,
) -> Iterator[dict[str, Any]]:
    log_banner(topic, causal_trace=enable_causal_trace)

    yield _emit_step(1, "active", "Fetching articles from news sources…")

    articles = retriever.search(topic)
    if not articles:
        msg = "No articles were found for that topic."
        log_step(1, "error", msg)
        for line in retriever.last_search_status:
            log_detail(line)
        log_failed(1, msg)
        yield {
            "type": "error",
            "step": 1,
            "message": msg,
            "status": retriever.last_search_status,
        }
        return

    done_msg = f"Found {len(articles)} articles."
    log_step(1, "completed", done_msg)
    for line in retriever.last_search_status[-4:]:
        log_detail(line)
    yield _evt(1, "completed", done_msg, article_count=len(articles))

    yield _emit_step(2, "active", "Routing topic to expert domains…")
    routed_domains = router.route(topic, articles)
    skipped_domains = router.skipped_domains(routed_domains)
    domain_list = ", ".join(routed_domains.keys())
    done_msg = f"Active domains: {domain_list}."
    log_step(2, "completed", done_msg)
    if skipped_domains:
        log_detail(f"Skipped ({len(skipped_domains)}): {', '.join(skipped_domains)}")
    yield _evt(
        2,
        "completed",
        done_msg,
        routed_domains=routed_domains,
        skipped_domains=skipped_domains,
    )

    causal_report = ""
    causal_chains: list = []

    if enable_causal_trace:
        yield _emit_step(3, "active", "Extracting entities from articles…")
        log_detail("Extracting metadata from articles…")
        metadata = tracer.extract_metadata(topic, articles)
        yield _evt(3, "active", "Tracing ranked causal chains…")
        log_detail("Tracing ranked causal chains…")
        causal_chains = tracer.trace_causal_chains(topic, articles, metadata)
        causal_report = tracer.format_report(topic, causal_chains)
        done_msg = f"Identified {len(causal_chains)} causal chain(s)."
        yield _emit_step(3, "completed", done_msg, causal_chain_count=len(causal_chains))
    else:
        yield _emit_step(3, "skipped", "Causal trace disabled — skipped.")

    n_domains = len(routed_domains)
    sorted_domains = sorted(routed_domains.items(), key=lambda x: -x[1])

    yield _emit_step(4, "active", f"Starting {n_domains} domain agent(s)…", domain_total=n_domains)

    agent_results: dict = {}

    for index, (domain, weight) in enumerate(sorted_domains, start=1):
        running_msg = f"Running {domain} agent ({index}/{n_domains})…"
        log_step(4, "active", running_msg)
        log_detail(f"weight={weight:.2f}")
        yield _evt(
            4,
            "active",
            running_msg,
            domain=domain,
            domain_index=index,
            domain_total=n_domains,
        )
        try:
            agent_results[domain] = agent_manager.analyze_domain(domain, articles, topic, weight)
            n_preds = len(agent_results[domain].get("predictions", []))
            if "error" in agent_results[domain]:
                log_detail(f"{domain}: {agent_results[domain]['error']}")
            else:
                log_detail(f"{domain}: {n_preds} prediction(s)")
        except Exception as e:
            agent_results[domain] = {"error": str(e), "routing_weight": weight}
            log_step(4, "error", f"{domain} agent failed: {e}")
        completed_msg = f"Completed {domain} ({index}/{n_domains})."
        log_detail(completed_msg)
        yield _evt(
            4,
            "active",
            completed_msg,
            domain=domain,
            domain_index=index,
            domain_total=n_domains,
        )

    yield _emit_step(4, "completed", f"Finished all {n_domains} domain agent(s).")

    yield _emit_step(5, "active", "Building timeline and final report…")
    report_text = synthesizer.final_report(
        topic,
        articles,
        agent_results,
        routed_domains=routed_domains,
        causal_report=causal_report,
        skipped=skipped_domains,
    )
    timeline = synthesizer.build_timeline(articles)
    yield _emit_step(5, "completed", "Report ready.")

    log_done(topic)

    yield {
        "type": "done",
        "result": {
            "topic": topic,
            "model_mode": "low-power" if config.LOW_POWER_MODE else "standard",
            "articles": articles,
            "article_count": len(articles),
            "routed_domains": routed_domains,
            "skipped_domains": skipped_domains,
            "causal_chains": causal_chains,
            "causal_report": causal_report,
            "agent_results": agent_results,
            "timeline": timeline,
            "report_text": report_text,
        },
    }


def stream_analysis_ndjson(
    topic: str,
    enable_causal_trace: bool,
    *,
    retriever: NewsRetriever,
    router: DomainRouter,
    agent_manager: AgentManager,
    tracer: NewsTracer,
    synthesizer: Synthesizer,
) -> Iterator[str]:
    try:
        for event in analyze_event_generator(
            topic,
            enable_causal_trace,
            retriever=retriever,
            router=router,
            agent_manager=agent_manager,
            tracer=tracer,
            synthesizer=synthesizer,
        ):
            yield json.dumps(event) + "\n"
    except Exception as e:
        log_failed(0, str(e))
        yield json.dumps({"type": "error", "step": 0, "message": str(e)}) + "\n"


async def stream_analysis_ndjson_async(
    topic: str,
    enable_causal_trace: bool,
    *,
    retriever: NewsRetriever,
    router: DomainRouter,
    agent_manager: AgentManager,
    tracer: NewsTracer,
    synthesizer: Synthesizer,
) -> AsyncIterator[str]:
    """Run the blocking pipeline in a thread so each progress line flushes before long LLM work."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def produce() -> None:
        try:
            for event in analyze_event_generator(
                topic,
                enable_causal_trace,
                retriever=retriever,
                router=router,
                agent_manager=agent_manager,
                tracer=tracer,
                synthesizer=synthesizer,
            ):
                future = asyncio.run_coroutine_threadsafe(queue.put(event), loop)
                future.result()
        except Exception as e:
            asyncio.run_coroutine_threadsafe(queue.put(e), loop).result()
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()

    threading.Thread(target=produce, daemon=True).start()

    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                log_failed(0, str(item))
                yield json.dumps({"type": "error", "step": 0, "message": str(item)}) + "\n"
                break
            yield json.dumps(item) + "\n"
            await asyncio.sleep(0)
    except Exception as e:
        log_failed(0, str(e))
        yield json.dumps({"type": "error", "step": 0, "message": str(e)}) + "\n"
