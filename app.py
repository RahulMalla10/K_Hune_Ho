import os
import subprocess
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import logging

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
try:
    import psutil
except ImportError:
    psutil = None

from src.agent_manager import AgentManager
from src.analyze_pipeline import analyze_event_generator, stream_analysis_ndjson_async
from src.config import config
from src.domain_router import DomainRouter
from src.news_retriever import NewsRetriever
from src.news_tracer import NewsTracer
from src.synthesizer import Synthesizer

logging.getLogger("duckduckgo_search").setLevel(logging.ERROR)
logging.getLogger("primp").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

class _IgnoreStatusAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            return "/api/status" not in msg
        except Exception:
            return True

logging.getLogger("uvicorn.access").addFilter(_IgnoreStatusAccessFilter())

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(
    title="KHUNEHO UI",
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

retriever = NewsRetriever(max_articles=config.NEWS_MAX_ARTICLES, time_range=config.NEWS_TIME_RANGE)
agent_manager = AgentManager()
router = DomainRouter()
synthesizer = Synthesizer()
tracer = NewsTracer(agent_manager.llm)

class AnalyzeRequest(BaseModel):
    topic: str
    enable_causal_trace: bool | None = None

def _causal_enabled(request: AnalyzeRequest) -> bool:
    if request.enable_causal_trace is not None:
        return request.enable_causal_trace
    return config.ENABLE_CAUSAL_TRACE

@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    html_path = BASE_DIR / "templates" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))

@app.get("/favicon.ico")
async def favicon() -> Response:
    return Response(status_code=204)

@app.post("/api/analyze/stream")
async def analyze_stream(request: AnalyzeRequest) -> StreamingResponse:
    topic = request.topic.strip()
    if not topic:
        return StreamingResponse(
            iter(['{"type":"error","step":0,"message":"Please provide a non-empty topic."}\n']),
            media_type="application/x-ndjson",
        )
    enable_causal = _causal_enabled(request)
    return StreamingResponse(
        stream_analysis_ndjson_async(
            topic,
            enable_causal,
            retriever=retriever,
            router=router,
            agent_manager=agent_manager,
            tracer=tracer,
            synthesizer=synthesizer,
        ),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@app.get("/api/status")
async def status() -> JSONResponse:
    def _query_nvidia_smi() -> dict | None:
        try:
            output = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,memory.used,memory.total,name",
                    "--format=csv,noheader,nounits",
                ],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=2,
            )
            line = output.strip().splitlines()[0]
            gpu_util, mem_used, mem_total, name = [item.strip() for item in line.split(",")]
            return {
                "name": name,
                "utilization_percent": float(gpu_util),
                "memory_used_mb": float(mem_used),
                "memory_total_mb": float(mem_total),
            }
        except Exception:
            return None
    cpu_status = {}
    if psutil is not None:
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count_logical = psutil.cpu_count(logical=True)
            cpu_count_physical = psutil.cpu_count(logical=False) or cpu_count_logical
            mem = psutil.virtual_memory()
            process_cpu = round(psutil.Process().cpu_percent(interval=None) / max(1, cpu_count_logical), 1)
            cpu_status = {
                "cpu_percent": cpu_percent,
                "cpu_count_logical": cpu_count_logical,
                "cpu_count_physical": cpu_count_physical,
                "memory_total_mb": round(mem.total / 1024 / 1024, 1),
                "memory_used_mb": round(mem.used / 1024 / 1024, 1),
                "memory_available_mb": round(mem.available / 1024 / 1024, 1),
                "memory_percent": mem.percent,
                "process_cpu_percent": process_cpu,
            }
        except Exception:
            cpu_status = {}

    gpu_info = {"gpu_available": config.GPU_AVAILABLE, "gpu_type": config.GPU_TYPE}
    if config.GPU_AVAILABLE and config.GPU_TYPE == "cuda":
        nvidia = _query_nvidia_smi()
        if nvidia:
            gpu_info.update(nvidia)

    resp = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "model_mode": "low-power" if config.LOW_POWER_MODE else "standard",
        "device": config.DEVICE,
        "n_threads": config.N_THREADS,
        "agent_workers": config.AGENT_WORKERS,
    }
    resp.update(cpu_status)
    resp.update({k: v for k, v in gpu_info.items() if v is not None and v != {}})
    return JSONResponse(resp)

@app.post("/api/analyze")
async def analyze(request: AnalyzeRequest) -> JSONResponse:
    topic = request.topic.strip()
    if not topic:
        return JSONResponse({"error": "Please provide a non-empty topic."}, status_code=400)

    enable_causal = _causal_enabled(request)
    result = None
    for event in analyze_event_generator(
        topic,
        enable_causal,
        retriever=retriever,
        router=router,
        agent_manager=agent_manager,
        tracer=tracer,
        synthesizer=synthesizer,
    ):
        if event.get("type") == "error":
            status = 404 if event.get("step") == 1 else 500
            return JSONResponse(event, status_code=status)
        if event.get("type") == "done":
            result = event.get("result")
    if result is None:
        return JSONResponse({"error": "Analysis produced no result."}, status_code=500)
    return JSONResponse(result)
