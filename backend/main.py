"""FastAPI application entry point for Qwen Council.

Endpoints:
  POST /api/review          — Run the council on submitted code
  POST /api/review/stream   — Stream council progress via SSE
  POST /api/chat            — Multi-agent chat (content-aware routing)
  POST /api/chat/stream     — Stream chat via SSE
  GET  /api/sessions         — List previous sessions
  GET  /api/sessions/{id}    — Session detail
  DELETE /api/sessions/{id}  — Delete a session
  GET  /api/memory/patterns  — Consolidated semantic patterns
  GET  /api/health           — Health check
  GET  /api/diagnostics      — Recent LLM/agent errors (debugging)
  POST /api/diagnostics/clear — Clear diagnostics store
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from backend.config import settings
from backend.council.orchestrator import CouncilOrchestrator
from backend.memory.episodic_memory import EpisodicMemoryManager
from backend.memory.semantic_memory import SemanticMemoryManager
from backend.models.db import (
    EpisodicMemory,
    SemanticMemory,
    async_session_factory,
    check_db_connection,
    get_session,
    init_db,
)
from backend.models.schemas import (
    AgentContribution,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    MemoryPattern,
    ReviewRequest,
    ReviewResponse,
    SessionDetail,
    SessionSummary,
)
# Core agents — Agent Society with role-based capabilities
from backend.agents.core.coordinator_agent import CoordinatorAgent
from backend.agents.core.analyst_agent import AnalystAgent
from backend.agents.core.architect_agent import ArchitectAgent
from backend.agents.core.engineer_agent import EngineerAgent
from backend.agents.core.critic_agent import CriticAgent
from backend.agents.core.researcher_agent import ResearcherAgent

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


# ──────────────────────────────────────────────
#  Lifespan
# ──────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    logger.info("Starting Qwen Council API")
    # Log API key status (safely — never log the actual key)
    key_status = "SET" if settings.llm_api_key else "NOT SET — agents will return NO_FINDINGS!"
    key_preview = (settings.llm_api_key[:8] + "..." + settings.llm_api_key[-4:]) if settings.llm_api_key else "N/A"
    logger.info("Qwen API key: %s (len=%d, preview=%s)", key_status, len(settings.llm_api_key), key_preview)
    logger.info("Qwen model: %s", settings.llm_model)
    logger.info("Qwen base URL: %s", settings.llm_base_url)
    logger.info("Database URL: %s", settings.database_url.replace(settings.database_url.split(":")[2].split("@")[0], "****") if "@" in settings.database_url else settings.database_url)
    try:
        await init_db()
        logger.info("Database tables initialised")
    except Exception:
        logger.warning(
            "Database initialisation failed — continuing without DB. "
            "Set DATABASE_URL if you need persistence."
        )
    yield
    logger.info("Shutting down Qwen Council API")


# ──────────────────────────────────────────────
#  App
# ──────────────────────────────────────────────

app = FastAPI(
    title="Qwen Council API",
    description=(
        "Multi-agent code review and collaboration system built for the "
        "[Global AI Hackathon Series with Qwen Cloud](https://qwencloud-hackathon.devpost.com/) — Track 3: Agent Society.\n\n"
        "## Features\n\n"
        "- **6 role-based core agents** (Coordinator, Analyst, Architect, Engineer, Critic, Researcher)\n"
        "- **15 specialised sub-agents** delegated by core agents for task decomposition\n"
        "- **3-round debate cycle** with Inverted Pyramid + Given-New communication protocol\n"
        "- **3-level memory architecture** (Working, Episodic, Semantic with pgvector)\n"
        "- **Real-time SSE streaming** for live agent status updates\n"
        "- **MCP server** for integration with OpenCode, Claude Desktop, and Cursor\n\n"
        "## Authentication\n\n"
        "No authentication required. All endpoints are public for hackathon demo purposes.\n\n"
        "## Token Usage\n\n"
        "Review responses include `token_usage` with per-agent breakdown and estimated cost."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
#  Structured JSON Logging Middleware
# ──────────────────────────────────────────────

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add a unique request-id to every request and log in JSON format."""

    async def dispatch(self, request: Request, call_next):
        import time
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        # Structured JSON log
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "INFO",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 1),
            "client": request.client.host if request.client else "unknown",
        }
        print(json.dumps(log_entry), flush=True)

        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestIDMiddleware)

orchestrator = CouncilOrchestrator()

# ──────────────────────────────────────────────
#  API v1 Router
# ──────────────────────────────────────────────

router = APIRouter(prefix="/api/v1")

# Routers will be registered at the end of the file after all endpoints are defined
legacy_router = APIRouter(prefix="/api")


@router.post("/review", response_model=ReviewResponse, tags=["Code Review"])
@legacy_router.post("/review", response_model=ReviewResponse, include_in_schema=False)
async def review_code(payload: ReviewRequest):
    """Execute the council on the provided source code.

    If *session_id* is provided, it resumes an existing session context.
    Otherwise a new session is created.
    """
    try:
        report, session_id, round_data = await orchestrator.run_council(
            code=payload.code or "",
            session_id=payload.session_id,
            image_files=payload.images or None,
            files=payload.files or None,
            instruction=payload.instruction,
            mode=payload.mode,
        )

        return ReviewResponse(
            session_id=session_id,
            report=report,
            rounds_raw=round_data,
        )
    except Exception:
        logger.exception("Council execution failed")
        raise HTTPException(
            status_code=500, detail="Council execution failed"
        )


@router.post("/review/stream", tags=["Code Review"])
@legacy_router.post("/review/stream", include_in_schema=False)
async def review_code_stream(payload: ReviewRequest):
    """Stream council progress via Server-Sent Events.

    Accepts the same ``ReviewRequest`` body as ``POST /api/review`` but
    returns a ``text/event-stream`` response with real-time progress events.
    """
    async def event_generator():
        """Inner async generator that formats council events as SSE lines."""
        try:
            async for event_type, data in orchestrator.stream_council(
                code=payload.code or "",
                session_id=payload.session_id,
                image_files=payload.images or None,
                files=payload.files or None,
                instruction=payload.instruction,
                mode=payload.mode,
            ):
                yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        except Exception:
            logger.exception("Stream council failed")
            yield (
                "event: error\n"
                "data: "
                + json.dumps({
                    "message": "Council execution failed",
                    "detail": "Internal server error",
                })
                + "\n\n"
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ──────────────────────────────────────────────
#  Chat synthesis helper
# ──────────────────────────────────────────────


# ──────────────────────────────────────────────
#  Question classifier & agent router
# ──────────────────────────────────────────────


def _classify_question(question: str) -> str:
    """Classify a question into a category for agent routing.

    Categories: social, science, tech, history, art, philosophy, strategy, general.
    """
    q = question.lower().strip()

    # ── Social / greeting ──
    social_keywords = [
        "hello", "hi ", "hey", "hola", "good morning", "good afternoon",
        "good evening", "what's up", "sup", "how are you", "how's it going",
        "nice to meet", "thanks", "thank you", "cool", "awesome",
        "howdy", "greetings", "salutations", "yo ",
    ]
    if any(kw in q for kw in social_keywords) and len(q.split()) < 6:
        return "social"

    # Detect if question starts with "what is / explain / define" etc
    has_question = any(kw in q for kw in ["what is ", "how does ", "why does ", "explain ", "define ", "que es ", "que son ", "como ", "por que ", "cual es ", "quien ", "donde ", "cuando ", "quien fue ", "habla", "hablame", "cuentame", "dimelo"])

    # ── Science ──
    science_keywords = [
        "quantum", "physics", "biology", "chemistry", "science",
        "scientific", "evolution", "dna", "thermodynamics",
        "particle", "atom", "molecule", "gravity",
        "black hole", "universe", "cosmos", "equation",
        "formula", "theorem", "hypothesis", "experiment",
        "laboratory", "protein", "cell",
        "organism", "species", "genetic", "chemical",
        "element", "compound", "neuron", "photosynthesis",
        "planet", "star", "galaxy", "energy", "force", "mass",
        "velocity", "wave", "electron", "proton", "neutron", "photon",
        # Spanish
        "ciencia", "cientifico", "cientifica", "fisica", "quimica",
        "biologia", "naturaleza", "planeta", "estrella", "galaxia",
        "universo", "atomo", "molecula", "energia", "fuerza",
        "velocidad", "masa", "temperatura", "experimento",
        "hipotesis", "teoria", "datos", "analisis", "investigacion",
        "descubrimiento", "explique",
    ]
    science_count = sum(1 for kw in science_keywords if kw in q)
    if science_count >= 2:
        return "science"
    # "what is a black hole" → 1 science keyword + question word
    if has_question and science_count >= 1:
        return "science"

    # ── Technology / computing ──
    tech_keywords = [
        "code", "programming", "program", "software", "algorithm", "database",
        "server", "api", "function", "variable", "class", "object",
        "python", "javascript", "java", "rust", "go ", "c++", "html",
        "css", "react", "node", "docker", "kubernetes", "linux",
        "windows", "mac", "computer", "computing", "data structure",
        "compiler", "debug", "framework", "library", "dependency",
        "microservice", "architecture", "deploy", "devops", "ci/cd",
        "git", "memory", "thread", "process", "cache", "latency",
        "bandwidth", "network", "protocol", "encryption", "hash",
        "sql", "nosql", "query", "index", "scalab", "performanc",
        "optimize", "refactor", "tech", "digital", "app ", "mobile",
        "web", "frontend", "backend", "fullstack", "ai", "machine learning",
        "neural", "deep learning", "llm", "gpt", "api key",
        "website", "browser", "internet", "http", "url",
        # Spanish
        "codigo", "programa", "programacion", "computadora",
        "ordenador", "software", "hardware", "internet", "aplicacion",
        "base de datos", "servidor", "algoritmo", "funcion",
        "variable", "clase", "python", "javascript", "java", "html",
        "css", "docker", "linux", "windows", "web", "app",
        "inteligencia artificial", "maquina", "robot", "automatizar",
        "tecnologia", "digital", "red", "datos", "sistema",
    ]
    tech_count = sum(1 for kw in tech_keywords if kw in q)
    # "what is html" → 1 tech keyword + question word
    # "write a program" → 2 tech keywords
    if tech_count >= 2 or (has_question and tech_count >= 1):
        return "tech"

    # ── History / politics / society ──
    history_keywords = [
        "history", "historical", "century", "ancient", "medieval",
        "war", "revolution", "empire", "kingdom", "civilization",
        "president", "prime minister", "king", "queen", "pharaoh",
        "battle", "treaty", "colonization", "independence",
        "renaissance", "enlightenment", "industrial", "cold war",
        "world war", "nazi", "fascism", "communism", "democracy",
        "dictator", "politic", "economy", "economic", "society",
        "societal", "culture", "cultural", "religion", "religious",
        "migration", "globalization", "capitalism", "socialism",
        "nation", "border", "geopolitic", "diplomacy", "policy",
        "roman", "greek", "egyptian", "ottoman", "byzantine",
        "french revolution", "industrial revolution",
        # Spanish
        "historia", "historico", "historica", "guerra", "imperio",
        "revolucion", "independencia", "colombia", "mexico", "peru",
        "argentina", "chile", "españa", "espanol", "cultura",
        "politica", "economia", "sociedad", "civilizacion",
        "presidente", "rey", "reina", "batalla", "tratado",
        "colonizacion", "dictadura", "comunismo", "capitalismo",
        "nacion", "frontera", "religion", "migracion",
        "bolivar", "san martin", "juarez", "peron", "castro",
        "chavez", "neruda", "garcia marquez", "borges",
        "casi nunca", "curiosidades", "secretos",
    ]
    history_count = sum(1 for kw in history_keywords if kw in q)
    if history_count >= 2:
        return "history"
    if has_question and history_count >= 1:
        return "history"

    # ── Philosophy / deep questions ──
    philosophy_keywords = [
        "philosophy", "meaning", "purpose", "existence", "truth",
        "knowledge", "consciousness", "mind", "soul", "reality",
        "ethics", "moral", "right and wrong", "good and evil",
        "free will", "determinism", "god", "religion", "faith",
        "belief", "reason", "logic", "argument", "fallacy",
        "paradox", "infinite", "mortality", "death", "life",
        "wisdom", "virtue", "justice", "equality", "freedom",
        "why are we", "nature of", "essence",
        "love", "hate", "emotion", "feeling",
        # Spanish
        "filosofia", "significado", "existencia", "verdad",
        "conocimiento", "conciencia", "mente", "alma", "realidad",
        "etica", "moral", "bien", "mal", "libre albedrio",
        "dios", "religion", "fe", "creencia", "razon", "logica",
        "paradoja", "infinito", "mortalidad", "muerte", "vida",
        "sabiduria", "virtud", "justicia", "igualdad", "libertad",
        "por que estamos", "naturaleza de",
        "amor", "odio", "emocion", "sentimiento",
    ]
    philosophy_count = sum(1 for kw in philosophy_keywords if kw in q)
    if philosophy_count >= 2:
        return "philosophy"
    if has_question and philosophy_count >= 1:
        return "philosophy"

    # ── Strategy / business / advice ──
    strategy_keywords = [
        "strategy", "strategic", "business", "career", "leadership",
        "management", "goal", "plan", "decision", "risk",
        "competition", "market", "startup", "entrepreneur",
        "negotiate", "negotiation", "win", "success", "failure",
        "advice", "should i", "tip", "recommend",
        "improve", "grow", "develop", "skill", "learn",
        "productivity", "focus", "habit", "discipline",
        "team", "organization", "project", "deadline",
        "prioritize", "efficient", "effective",
        # Spanish
        "estrategia", "negocio", "carrera", "liderazgo",
        "administracion", "meta", "objetivo", "plan", "decision",
        "riesgo", "competencia", "mercado", "emprendedor",
        "negociar", "negociacion", "ganar", "exito", "fracaso",
        "consejo", "deberia", "recomendar", "mejorar", "crecer",
        "desarrollar", "habilidad", "aprender", "productividad",
        "enfoque", "habito", "disciplina", "equipo", "organizacion",
        "proyecto", "plazo", "priorizar", "eficiente", "efectivo",
    ]
    strategy_count = sum(1 for kw in strategy_keywords if kw in q)
    if strategy_count >= 2:
        return "strategy"

    # ── Art / literature / music / film (checked last since keywords overlap) ──
    art_keywords = [
        "art", "artist", "music", "song", "painting", "film", "movie",
        "literature", "book", "novel", "poem", "poetry", "dance",
        "theatre", "theater", "sculpture", "photography", "cinema",
        "director", "composer", "musician", "writer", "author",
        "creative", "imagination", "beauty", "aesthetic",
        "fashion", "drawing", "sketch", "colour",
        "melody", "rhythm", "harmony", "canvas", "brush",
        "masterpiece", "gallery", "museum", "exhibition",
        "write a poem", "write a song", "write a story", "write a book",
        "write a novel", "paint a", "draw a", "sing a", "play music",
        # Spanish
        "arte", "musica", "cancion", "pintura", "pelicula",
        "literatura", "libro", "novela", "poema", "poesia", "baile",
        "teatro", "escultura", "fotografia", "cine", "director",
        "compositor", "musico", "escritor", "autor", "creativo",
        "imaginacion", "belleza", "estetica", "moda", "dibujo",
        "boceto", "color", "melodia", "ritmo", "armonia",
        "lienzo", "pincel", "obra maestra", "galeria", "museo",
        "exposicion", "escribir un poema", "escribir una cancion",
    ]
    art_count = sum(1 for kw in art_keywords if kw in q)
    if art_count >= 2 or (has_question and art_count >= 1):
        return "art"

    return "general"


def _route_question(category: str, has_images: bool = False) -> list[dict[str, object]]:
    """Return the list of (name, agent_instance) pairs for a given category.

    Each agent is instantiated fresh so there are no shared state issues.
    Uses the Agent Society core agents with role-based capabilities.
    """
    agents = {
        "coordinator": CoordinatorAgent(),
        "analyst": AnalystAgent(),
        "architect": ArchitectAgent(),
        "engineer": EngineerAgent(),
        "critic": CriticAgent(),
        "researcher": ResearcherAgent(),
    }

    # Route table: category → which core agents to call
    routes = {
        "social":     ["coordinator"],
        "science":    ["analyst", "researcher"],
        "tech":       ["engineer", "critic", "architect"],
        "history":    ["researcher", "analyst"],
        "art":        ["analyst", "researcher", "critic"],
        "philosophy": ["analyst", "coordinator"],
        "strategy":   ["coordinator", "architect", "analyst"],
        "general":    ["coordinator", "analyst", "architect", "engineer", "critic", "researcher"],
    }

    selected = routes.get(category, routes["general"])
    # When images are present, add agents good at visual analysis
    if has_images:
        for img_agent in ("critic", "analyst", "researcher"):
            if img_agent not in selected:
                selected.append(img_agent)
    return [(name, agents[name]) for name in selected]


async def _synthesize_chat(
    question: str,
    contributions: list[dict],
) -> str:
    """Merge agent answers into a single flowing response.

    - Social: picks the best single response (no merge).
    - Others: merges all unique insights into one flowing answer.
    """
    relevant = [
        c for c in contributions
        if c["answer"]
        and not c["answer"].startswith("[Agent")
    ]

    if not relevant:
        return "Hey! I'm here to help. What's on your mind?"
    if len(relevant) == 1:
        return relevant[0]["answer"]

    # Social — just pick the best single response
    category = _classify_question(question)
    if category == "social":
        best = min(relevant, key=lambda c: len(c["answer"]))
        return best["answer"]

    # Other categories — merge all unique insights
    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )

    answers_block = "\n\n".join(
        f"--- {c['agent'].title()} ---\n{c['answer']}"
        for c in relevant
    )

    resp = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior editor. Merge the following expert answers "
                    "into ONE flowing, non-repetitive response.\n\n"
                    "Rules:\n"
                    "- Remove duplicate information.\n"
                    "- Keep UNIQUE insights from each expert.\n"
                    "- Write in natural prose.\n"
                    "- MAXIMUM 150 WORDS.\n"
                    "- Do NOT mention the experts or agents.\n"
                    "- Just answer the question directly."
                ),
            },
            {
                "role": "user",
                "content": f"### Question:\n{question}\n\n### Expert answers:\n{answers_block}",
            },
        ],
        temperature=0.2,
        max_tokens=384,
    )
    return resp.choices[0].message.content or relevant[0]["answer"]


@router.post("/chat", response_model=ChatResponse, tags=["Chat"])
@legacy_router.post("/chat", response_model=ChatResponse, include_in_schema=False)
async def chat_general(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_session),
):
    """Multi-agent chat for ANY question.

    If session_id is provided with existing context, acts as follow-up
    using a single LLM call. Otherwise, routes the question to all 6
    specialised agents in parallel and synthesises a unified answer.

    Every chat interaction is persisted to episodic memory so that it
    appears in the session sidebar and is available for future reference.
    """
    from openai import AsyncOpenAI

    try:
        # ── Follow-up mode (code review context only) ────────────────
        if payload.session_id and payload.context:
            client = AsyncOpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
            )
            system_prompt = (
                "You are a code review assistant answering follow-up questions about a previous analysis. "
                "Use the provided context (findings, code, discussion) to give specific, actionable answers. "
                "Be concise but thorough. If you need more context, say so."
            )
            user_content = (
                f"### Context from code review:\n{payload.context or 'No additional context provided.'}\n\n"
                f"### Question:\n{payload.message}"
            )
            resp = await client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=1000,
                temperature=0.3,
            )
            answer = resp.choices[0].message.content or "I couldn't generate a response."
            return ChatResponse(
                response=answer,
                session_id=payload.session_id,
                agent_contributions=[],
            )

        # ── Load previous conversation if session_id exists ──────────
        conversation_history = ""  # previous Q&A pairs as context
        existing_findings: list[dict] = []

        if payload.session_id:
            try:
                from backend.memory.episodic_memory import EpisodicMemoryManager
                mgr = EpisodicMemoryManager(db)
                prev = await mgr.get(payload.session_id)
                if prev:
                    raw = prev.findings_json
                    if isinstance(raw, str):
                        raw = json.loads(raw)
                    if isinstance(raw, list):
                        existing_findings = raw
                        # Build conversation history from previous turns
                        parts = []
                        for entry in existing_findings:
                            q = entry.get("question", "")
                            r = entry.get("response", "")
                            if q:
                                parts.append(f"User: {q}")
                            if r:
                                parts.append(f"Assistant: {r}")
                        conversation_history = "\n".join(parts)
            except Exception:
                logger.warning("Could not load previous chat context — continuing fresh")

        # ── Detect content type if files are uploaded ──
        from backend.utils.content_detector import detect_content_type, get_handler_prompt

        detected_content_types: list[str] = []
        non_code_files: list[dict] = []

        if payload.files:
            for f in payload.files:
                ct = detect_content_type(f.filename, f.content)
                logger.info("File %s detected as %s", f.filename, ct)
                detected_content_types.append(ct)
                if ct != "code":
                    non_code_files.append({"filename": f.filename, "content": f.content, "type": ct})

        # ── Route to the right agents based on content type ──
        # For non-code content (math, research, text), select agents that excel
        # at general analysis instead of code review
        category = _classify_question(payload.message)

        # If files contain non-code content, override routing to use generalist agents
        if non_code_files and not payload.images:
            # Use the Analyst + Researcher + Coordinator for general content
            # Engineer + Architect for code-related questions
            primary_type = detected_content_types[0] if detected_content_types else "text"
            if primary_type in ("math", "research", "text"):
                # For non-code, use the analytical + research-oriented agents
                selected_agents = {
                    "coordinator": CoordinatorAgent(),
                    "analyst": AnalystAgent(),
                    "researcher": ResearcherAgent(),
                    "critic": CriticAgent(),
                }
            else:
                selected_agents = _route_question(category, has_images=bool(payload.images))
        else:
            selected_agents = _route_question(category, has_images=bool(payload.images))

        session_id = payload.session_id or f"chat-{uuid.uuid4().hex[:8]}"

        # Build agent context: conversation history + any explicit context
        agent_context = ""
        if conversation_history:
            agent_context += f"### Previous conversation:\n{conversation_history}\n\n"
        if payload.context:
            agent_context += f"### Additional context:\n{payload.context}\n"

        # Add file contents to context if files were uploaded
        file_context = ""
        if payload.files:
            file_parts = []
            for f in payload.files:
                file_parts.append(f"### File: {f.filename}\n```\n{f.content}\n```")
            file_context = "\n\n".join(file_parts)
            agent_context += f"\n### Uploaded files:\n{file_context}\n"

        # ── Vision pre-processing: describe images before agent analysis ──
        vision_description = ""
        if payload.images:
            from openai import AsyncOpenAI
            vision_client = AsyncOpenAI(
                api_key=settings.llm_api_key,
                base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            )
            vision_content: list[dict] = [
                {"type": "text", "text": f"Describe this image in detail. The user asked: \"{payload.message}\". Provide a thorough visual analysis covering all relevant elements, text, diagrams, charts, UI components, or code visible in the image. Be specific and detailed."}
            ]
            for img in payload.images:
                # Handle both Pydantic model objects and plain dicts
                if hasattr(img, 'mime_type'):
                    mime_type = img.mime_type
                    img_content = img.content
                else:
                    mime_type = img['mime_type']
                    img_content = img['content']
                data_url = f"data:{mime_type};base64,{img_content}"
                vision_content.append({
                    "type": "image_url",
                    "image_url": {"url": data_url},
                })
            try:
                vision_response = await vision_client.chat.completions.create(
                    model="qwen-vl-plus-latest",
                    messages=[
                        {"role": "system", "content": "You are a visual analyst. Describe images thoroughly and accurately."},
                        {"role": "user", "content": vision_content},
                    ],
                    max_tokens=2048,
                )
                vision_description = vision_response.choices[0].message.content or ""
                logger.info("Vision model returned description (%d chars)", len(vision_description))
            except Exception as e:
                logger.error("Vision pre-processing failed: %s", e)
                vision_description = f"[Image description unavailable: {e}]"

            # Inject vision description into agent context so text-only agents can analyze it
            agent_context += (
                f"\n### Image Analysis (Vision Model Description):\n"
                f"{vision_description}\n\n"
                f"Use the description above as the visual reference. "
                f"Provide your expert perspective on what the image shows.\n"
            )

        async def ask_agent(name: str, agent: object) -> dict:
            """Call a single agent's answer_question and return its contribution.

            Agents receive the vision model's text description (in agent_context)
            instead of raw image data, so all 6 agents can contribute their
            expertise regardless of vision-model support.
            """
            try:
                # Pass content_type so the agent adapts its response style
                ct = detected_content_types[0] if detected_content_types else "general"
                answer = await agent.answer_question(  # type: ignore[union-attr]
                    question=payload.message,
                    context=agent_context if agent_context else None,
                    content_type=ct,
                )
                return {
                    "agent": name,
                    "role_description": getattr(agent, "role_description", ""),
                    "answer": answer,
                }
            except Exception as e:
                logger.error("Agent '%s' chat failed: %s", name, e)
                return {
                    "agent": name,
                    "role_description": getattr(agent, "role_description", ""),
                    "answer": f"[Agent {name} unavailable]",
                }

        tasks = [ask_agent(name, agent) for name, agent in selected_agents]
        contributions_data = await asyncio.gather(*tasks)

        # Synthesise final answer — merge all agents into one flowing response
        final = await _synthesize_chat(payload.message, contributions_data)

        # ── Persist to episodic memory (append to existing) ──────────
        try:
            from backend.memory.episodic_memory import EpisodicMemoryManager

            new_entry = {
                "question": payload.message,
                "response": final,
                "agent_contributions": [
                    {
                        "agent": c["agent"],
                        "role_description": c["role_description"],
                        "answer": c["answer"],
                    }
                    for c in contributions_data
                ],
            }

            mgr = EpisodicMemoryManager(db)
            # Keep the first question as `code` for sidebar preview
            first_question = existing_findings[0]["question"] if existing_findings else payload.message
            await mgr.save(
                session_id=session_id,
                code=first_question,
                findings=[*existing_findings, new_entry],
                score=0.5,
            )
        except Exception:
            logger.warning("Failed to persist chat session to DB — continuing without persistence")

        return ChatResponse(
            response=final,
            session_id=session_id,
            agent_contributions=[
                AgentContribution(**c) for c in contributions_data
            ],
        )
    except Exception:
        logger.exception("Multi-agent chat failed")
        raise HTTPException(status_code=500, detail="Chat failed")


@router.post("/chat/stream", tags=["Chat"])
@legacy_router.post("/chat/stream", include_in_schema=False)
async def chat_stream(payload: ChatRequest):
    """Stream multi-agent chat responses via Server-Sent Events.

    Emits one ``agent_responding`` event per agent when they start,
    an ``agent_response`` event when each agent finishes, and a final
    ``synthesis_complete`` event with the combined answer.
    """
    async def event_generator():
        try:
            # ── Direct LLM for non-code content (math, research, text) ──
            from backend.utils.content_detector import detect_content_type, get_handler_prompt

            use_direct_llm = False
            direct_llm_system = None
            direct_llm_files = []

            if payload.files:
                for f in payload.files:
                    ct = detect_content_type(f.filename, f.content)
                    logger.info("File %s detected as %s (stream)", f.filename, ct)
                    if ct != "code":
                        use_direct_llm = True
                        direct_llm_system = get_handler_prompt(ct, f.filename)
                    direct_llm_files.append({"filename": f.filename, "content": f.content, "type": ct})

            if use_direct_llm and not payload.images:
                try:
                    from openai import AsyncOpenAI
                    client = AsyncOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
                    file_block = "\n\n".join(
                        f"### {f['filename']}\n```\n{f['content'][:6000]}\n```"
                        for f in direct_llm_files
                    )
                    prompt = f"{file_block}\n\n### Question:\n{payload.message}"
                    response = await client.chat.completions.create(
                        model=settings.llm_model,
                        messages=[
                            {"role": "system", "content": direct_llm_system},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.2,
                        max_tokens=2048,
                    )
                    final = response.choices[0].message.content or ""
                    session_id = payload.session_id or f"chat-{uuid.uuid4().hex[:8]}"
                    yield "event: synthesis_complete\ndata: " + json.dumps({
                        "final_answer": final,
                        "session_id": session_id,
                        "contributions": [],
                        "content_type": "direct_llm",
                    }) + "\n\n"
                    return
                except Exception as e:
                    logger.exception("Direct LLM stream failed, falling back to agents")
                    # Fall through to agent routing

            category = _classify_question(payload.message)
            selected_agents = _route_question(category, has_images=bool(payload.images))

            session_id = payload.session_id or f"chat-{uuid.uuid4().hex[:8]}"

            # ── Follow-up shortcut ──────────────────────────────
            if payload.session_id and payload.context:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(
                    api_key=settings.llm_api_key,
                    base_url=settings.llm_base_url,
                )
                yield "event: synthesis_complete\ndata: " + json.dumps({
                    "final_answer": "Follow-up mode — single response",
                    "session_id": session_id,
                    "contributions": [],
                }) + "\n\n"
                return

            # ── Fire all agents in parallel ─────────────────────
            async def run_agent(name: str, agent: object) -> tuple[str, str, str]:
                """Run a single agent and return (name, role, answer)."""
                role = getattr(agent, "role_description", "")
                try:
                    answer = await agent.answer_question(  # type: ignore[union-attr]
                        question=payload.message,
                        context=payload.context,
                    )
                except Exception as e:
                    logger.error("Agent '%s' stream chat failed: %s", name, e)
                    answer = f"[Agent {name} unavailable]"
                return name, role, answer

            tasks = [run_agent(name, agent) for name, agent in selected_agents]
            # Build a name→agent lookup for role descriptions
            agent_lookup = {name: agent for name, agent in selected_agents}
            for name in agent_lookup:
                role = getattr(agent_lookup[name], "role_description", "")
                yield f"event: agent_responding\ndata: {json.dumps({'agent': name, 'role': role})}\n\n"

            # Wait for all in parallel
            results_data = await asyncio.gather(*tasks)

            # Emit individual responses
            for name, role, answer in results_data:
                yield f"event: agent_response\ndata: {json.dumps({'agent': name, 'answer': answer})}\n\n"

            # Build synthesis — merge all agents into one flowing response
            contributions = [
                {"agent": name, "role_description": role, "answer": answer}
                for name, role, answer in results_data
            ]
            final = await _synthesize_chat(payload.message, contributions)

            # ── Persist to episodic memory ──────────────────────────
            try:
                from backend.memory.episodic_memory import EpisodicMemoryManager
                from backend.models.db import async_session_factory

                async with async_session_factory() as persist_db:
                    mgr = EpisodicMemoryManager(persist_db)
                    await mgr.save(
                        session_id=session_id,
                        code=payload.message,
                        findings=[{
                            "question": payload.message,
                            "response": final,
                            "agent_contributions": contributions,
                        }],
                        score=0.5,
                    )
            except Exception:
                logger.warning("Failed to persist stream chat session to DB")

            yield "event: synthesis_complete\ndata: " + json.dumps({
                "final_answer": final,
                "session_id": session_id,
                "contributions": contributions,
            }) + "\n\n"

        except Exception:
            logger.exception("Stream chat failed")
            yield "event: error\ndata: " + json.dumps({
                "message": "Chat stream failed",
                "detail": "Internal server error",
            }) + "\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/sessions", response_model=list[SessionSummary], tags=["Sessions"])
@legacy_router.get("/sessions", response_model=list[SessionSummary], include_in_schema=False)
async def list_sessions(
    limit: int = 20,
    db: AsyncSession = Depends(get_session),
):
    """List recent sessions from episodic memory."""
    try:
        mgr = EpisodicMemoryManager(db)
        sessions = await mgr.list_recent(limit=limit)
        summaries: list[SessionSummary] = []
        for ses in sessions:
            try:
                findings = ses.get_findings()
                finding_count = len(findings) if isinstance(findings, list) else 0
            except Exception:
                finding_count = 0
            summaries.append(
                SessionSummary(
                    id=ses.session_id,
                    code_preview=ses.code[:120] if ses.code else "",
                    score=round(ses.score, 2),
                    created_at=ses.created_at.isoformat()
                    if ses.created_at
                    else "",
                    finding_count=finding_count,
                )
            )
        return summaries
    except Exception:
        logger.exception("Failed to list sessions")
        raise HTTPException(status_code=500, detail="Failed to list sessions")


@router.get("/sessions/{session_id}", response_model=SessionDetail, tags=["Sessions"])
@legacy_router.get("/sessions/{session_id}", response_model=SessionDetail, include_in_schema=False)
async def get_session_detail(
    session_id: str,
    db: AsyncSession = Depends(get_session),
):
    """Get detailed information about a specific session."""
    try:
        mgr = EpisodicMemoryManager(db)
        record = await mgr.get(session_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return SessionDetail(
            id=record.session_id,
            code=record.code,
            findings_json=record.get_findings(),
            score=round(record.score, 2),
            created_at=record.created_at.isoformat()
            if record.created_at
            else "",
            last_referenced_at=record.last_referenced_at.isoformat()
            if record.last_referenced_at
            else None,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get session detail")
        raise HTTPException(
            status_code=500, detail="Failed to get session detail"
        )


@router.delete("/sessions/{session_id}", tags=["Sessions"])
@legacy_router.delete("/sessions/{session_id}", include_in_schema=False)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_session),
):
    """Delete a session from memory."""
    try:
        mgr = EpisodicMemoryManager(db)
        deleted = await mgr.delete_session(session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"status": "deleted", "session_id": session_id}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete session %s", session_id)
        raise HTTPException(status_code=500, detail="Failed to delete session")


@router.get("/memory/patterns", response_model=list[MemoryPattern], tags=["Memory"])
@legacy_router.get("/memory/patterns", response_model=list[MemoryPattern], include_in_schema=False)
async def list_memory_patterns(
    category: str | None = None,
    db: AsyncSession = Depends(get_session),
):
    """List consolidated semantic memory patterns."""
    try:
        mgr = SemanticMemoryManager(db)
        if category:
            patterns = await mgr.get_by_category(category)
        else:
            patterns = await mgr.get_all()
        return [
            MemoryPattern(
                id=p.id,
                pattern_text=p.pattern_text,
                category=p.category,
                strength=p.strength,
                created_at=p.created_at.isoformat() if p.created_at else "",
            )
            for p in patterns
        ]
    except Exception:
        logger.exception("Failed to list memory patterns")
        raise HTTPException(
            status_code=500, detail="Failed to list memory patterns"
        )


@router.get("/health", response_model=HealthResponse, tags=["Health"])
@legacy_router.get("/health", response_model=HealthResponse, include_in_schema=False)
async def health_check():
    """Health check endpoint."""
    db_ok = False
    try:
        db_ok = await check_db_connection()
    except Exception:
        pass
    return HealthResponse(status="ok", version="1.0.0", db_connected=db_ok)


@router.get("/diagnostics", tags=["Health"])
@legacy_router.get("/diagnostics", include_in_schema=False)
async def get_diagnostics(limit: int = 20):
    """Return the most recent LLM/agent errors.

    Useful for debugging why a review returned zero findings — the
    diagnostics store captures every exception from ``BaseAgent._call_llm``
    and other LLM call sites, so the failure mode is visible here
    instead of being silently swallowed.
    """
    from backend.utils.diagnostics import diagnostics as _diag
    return {
        "count": len(_diag.latest(limit)),
        "entries": _diag.latest(limit),
    }


@router.post("/diagnostics/clear", tags=["Health"])
@legacy_router.post("/diagnostics/clear", include_in_schema=False)
async def clear_diagnostics():
    """Clear the diagnostics store."""
    from backend.utils.diagnostics import diagnostics as _diag
    _diag.clear()
    return {"status": "cleared"}


# Register routers with the app after all endpoints are defined
app.include_router(router)
app.include_router(legacy_router)
