import os
import sys
import time
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ── Library Imports ──────────────────────────────────────────────────────────
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Literal

import httpx
from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

# ════════════════════════════════════════════════════════════════════════════
# LOGGING SETUP
# ════════════════════════════════════════════════════════════════════════════
# Format: [2025-01-15 14:23:01.452]  INFO  server.py:42  — message
LOG_FORMAT = "[%(asctime)s]  %(levelname)-8s  %(filename)s:%(lineno)d  — %(message)s"
logging.basicConfig(
    level=logging.DEBUG,
    format=LOG_FORMAT,
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout)   # Console output
        # Add logging.FileHandler("erp_rag.log") here to also write to a file
    ]
)
log = logging.getLogger("erp_rag")

# Silence noisy third-party loggers so our logs stay readable
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("chromadb").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

def elapsed(start: float) -> str:
    """Returns a human-readable elapsed time string since `start`."""
    ms = (time.perf_counter() - start) * 1000
    return f"{ms:.1f}ms" if ms < 1000 else f"{ms / 1000:.2f}s"

# ── Config ───────────────────────────────────────────────────────────────────
EMBED_MODEL = "nomic-embed-text"
OLLAMA_URL  = "http://localhost:11434"
VECTOR_DIR  = "./vector_store"

LLM_BACKEND: Literal["ollama", "openrouter"] = "openrouter"

OLLAMA_LLM_MODEL    = "llama3.2"
OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "YOUR_API_KEY_HERE")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL    = "z-ai/glm-5.1"

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="ERP RAG Server",
    description="Local ERP Q&A — ChromaDB + Ollama embeddings + switchable LLM",
    version="4.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ════════════════════════════════════════════════════════════════════════════
# EMBEDDINGS — Ollama HTTP (always local)
# ════════════════════════════════════════════════════════════════════════════

class OllamaHTTPEmbeddings(Embeddings):

    def _embed(self, text: str) -> list[float]:
        t0 = time.perf_counter()
        log.debug(f"[EMBED] Calling Ollama /api/embeddings | model={EMBED_MODEL} | input_length={len(text)} chars")
        try:
            response = httpx.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": EMBED_MODEL, "prompt": text},
                timeout=60.0
            )
            response.raise_for_status()
            vector = response.json()["embedding"]
            log.debug(f"[EMBED] Vector received | dimensions={len(vector)} | took {elapsed(t0)}")
            return vector
        except httpx.HTTPStatusError as e:
            log.error(f"[EMBED] Ollama HTTP error {e.response.status_code}: {e.response.text} | took {elapsed(t0)}")
            raise
        except httpx.ConnectError:
            log.error(f"[EMBED] Cannot reach Ollama at {OLLAMA_URL} — is it running? | took {elapsed(t0)}")
            raise

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        log.debug(f"[EMBED] embed_documents called for {len(texts)} document(s)")
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        log.debug(f"[EMBED] embed_query called | preview='{text[:80]}{'...' if len(text) > 80 else ''}'")
        return self._embed(text)


# ════════════════════════════════════════════════════════════════════════════
# LLM BACKEND 1 — Ollama
# ════════════════════════════════════════════════════════════════════════════

def ollama_chat(prompt_text: str) -> str:
    t0 = time.perf_counter()
    log.info(f"[LLM:OLLAMA] Sending prompt to Ollama | model={OLLAMA_LLM_MODEL} | prompt_length={len(prompt_text)} chars")
    try:
        response = httpx.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_LLM_MODEL,
                "messages": [{"role": "user", "content": prompt_text}],
                "stream": False,
                "options": {"temperature": 0}
            },
            timeout=120.0
        )
        response.raise_for_status()
        answer = response.json()["message"]["content"]
        log.info(f"[LLM:OLLAMA] Response received | answer_length={len(answer)} chars | took {elapsed(t0)}")
        return answer
    except httpx.HTTPStatusError as e:
        log.error(f"[LLM:OLLAMA] HTTP error {e.response.status_code}: {e.response.text} | took {elapsed(t0)}")
        raise
    except httpx.ConnectError:
        log.error(f"[LLM:OLLAMA] Cannot reach Ollama at {OLLAMA_URL} | took {elapsed(t0)}")
        raise
    except Exception as e:
        log.error(f"[LLM:OLLAMA] Unexpected error: {type(e).__name__}: {e} | took {elapsed(t0)}")
        raise


# ════════════════════════════════════════════════════════════════════════════
# LLM BACKEND 2 — OpenRouter
# ════════════════════════════════════════════════════════════════════════════

def openrouter_chat(prompt_text: str) -> str:
    t0 = time.perf_counter()
    log.info(f"[LLM:OPENROUTER] Sending prompt to OpenRouter | model={OPENROUTER_MODEL} | prompt_length={len(prompt_text)} chars")
    try:
        response = httpx.post(
            OPENROUTER_BASE_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "ERP RAG Server",
                "Content-Type": "application/json"
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": [{"role": "user", "content": prompt_text}],
                "temperature": 0,
                "max_tokens": 1024
            },
            timeout=60.0
        )
        response.raise_for_status()
        answer = response.json()["choices"][0]["message"]["content"]
        log.info(f"[LLM:OPENROUTER] Response received | answer_length={len(answer)} chars | took {elapsed(t0)}")
        return answer
    except httpx.HTTPStatusError as e:
        log.error(f"[LLM:OPENROUTER] HTTP error {e.response.status_code}: {e.response.text} | took {elapsed(t0)}")
        raise
    except httpx.ConnectError:
        log.error(f"[LLM:OPENROUTER] Cannot reach OpenRouter — check internet connection | took {elapsed(t0)}")
        raise
    except Exception as e:
        log.error(f"[LLM:OPENROUTER] Unexpected error: {type(e).__name__}: {e} | took {elapsed(t0)}")
        raise


# ════════════════════════════════════════════════════════════════════════════
# UNIFIED LLM ROUTER
# ════════════════════════════════════════════════════════════════════════════

def llm_chat(prompt_text: str) -> str:
    log.debug(f"[LLM:ROUTER] Dispatching to backend='{LLM_BACKEND}'")
    if LLM_BACKEND == "ollama":
        return ollama_chat(prompt_text)
    elif LLM_BACKEND == "openrouter":
        return openrouter_chat(prompt_text)
    else:
        log.error(f"[LLM:ROUTER] Unknown LLM_BACKEND value: '{LLM_BACKEND}'")
        raise ValueError(f"Unknown LLM_BACKEND: '{LLM_BACKEND}'. Must be 'ollama' or 'openrouter'.")


# ── Load ChromaDB ─────────────────────────────────────────────────────────────
log.info("[STARTUP] Loading ChromaDB vector store from disk...")
t_chroma = time.perf_counter()
embeddings = OllamaHTTPEmbeddings()
vectorstore = Chroma(
    persist_directory=VECTOR_DIR,
    embedding_function=embeddings,
    collection_name="erp_docs"
)
retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 5}
)
log.info(f"[STARTUP] ChromaDB loaded | vectors={vectorstore._collection.count()} | took {elapsed(t_chroma)}")
log.info(f"[STARTUP] LLM backend  : {LLM_BACKEND.upper()}")
if LLM_BACKEND == "ollama":
    log.info(f"[STARTUP] LLM model    : {OLLAMA_LLM_MODEL} via {OLLAMA_URL}")
else:
    log.info(f"[STARTUP] LLM model    : {OPENROUTER_MODEL} via OpenRouter")

# ── ERP Prompt ────────────────────────────────────────────────────────────────
ERP_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template="""You are an ERP support assistant for the company.
Answer the question using ONLY the context provided below from the ERP documentation.
If the answer is not in the context, say: "I could not find this in the ERP documentation."
Do not guess or make up information. Be clear and concise.

Context:
{context}

Question: {question}

Answer:"""
)

# ── LCEL Pipeline ─────────────────────────────────────────────────────────────
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

rag_chain = (
    {
        "context": retriever | format_docs,
        "question": RunnablePassthrough()
    }
    | ERP_PROMPT
    | RunnableLambda(lambda prompt_value: llm_chat(prompt_value.text))
    | StrOutputParser()
)

log.info("[STARTUP] RAG chain assembled. Server ready to accept requests.\n")

# ── Pydantic Models ────────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str

class SourceDoc(BaseModel):
    file: str
    page: Optional[int] = None

class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceDoc]
    chunks_used: int
    llm_backend: str
    time_taken_ms: float   # Total time for the full request in milliseconds

# ── Endpoints ──────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "status": "running",
        "active_llm_backend": LLM_BACKEND,
        "endpoints": {"health": "GET /health", "query": "POST /query", "ui": "GET /docs"}
    }

@app.get("/health")
def health():
    try:
        count = vectorstore._collection.count()
        backend_info = {}
        if LLM_BACKEND == "ollama":
            r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
            r.raise_for_status()
            backend_info = {"status": "reachable", "available_models": [m["name"] for m in r.json().get("models", [])]}
        else:
            backend_info = {"status": "configured", "model": OPENROUTER_MODEL, "api_key_set": OPENROUTER_API_KEY != "YOUR_API_KEY_HERE"}
        return {"status": "ok", "vectors_indexed": count, "llm_backend": LLM_BACKEND, "llm_backend_info": backend_info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {e}")


@app.post("/query", response_model=QueryResponse)
async def query_erp(request: QueryRequest):

    t_request = time.perf_counter()
    question  = request.question.strip()

    # ── Step 1: Request received ─────────────────────────────────────────────
    log.info(f"[REQUEST] {'─' * 60}")
    log.info(f"[REQUEST] Received POST /query")
    log.info(f"[REQUEST] Question : '{question[:120]}{'...' if len(question) > 120 else ''}'")

    if not question:
        log.warning("[REQUEST] Rejected — empty question")
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # ── Step 2: Fetch relevant vectors from ChromaDB ─────────────────────────
    try:
        log.info(f"[RETRIEVAL] Embedding question and searching ChromaDB for top-5 similar chunks...")
        t_retrieval = time.perf_counter()

        source_docs = retriever.invoke(question)

        log.info(f"[RETRIEVAL] ChromaDB returned {len(source_docs)} chunk(s) | took {elapsed(t_retrieval)}")
        for i, doc in enumerate(source_docs):
            src  = os.path.basename(doc.metadata.get("source", "unknown"))
            page = doc.metadata.get("page", "?")
            log.debug(f"[RETRIEVAL] Chunk {i+1}: file={src} | page={page} | preview='{doc.page_content[:80].strip()}...'")

    except Exception as e:
        log.error(f"[RETRIEVAL] Failed to retrieve vectors: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Vector retrieval failed: {str(e)}")

    # ── Step 3: Build prompt and call LLM ────────────────────────────────────
    try:
        log.info(f"[LLM] Building prompt from {len(source_docs)} chunks and invoking LLM (backend={LLM_BACKEND})...")
        t_llm = time.perf_counter()

        answer = rag_chain.invoke(question)

        log.info(f"[LLM] Answer received | length={len(answer)} chars | took {elapsed(t_llm)}")

    except httpx.HTTPStatusError as e:
        log.error(f"[LLM] HTTP error from {LLM_BACKEND}: status={e.response.status_code} body={e.response.text}")
        raise HTTPException(status_code=502, detail=f"{LLM_BACKEND} returned HTTP {e.response.status_code}: {e.response.text}")

    except httpx.ConnectError:
        msg = f"Cannot reach Ollama at {OLLAMA_URL}" if LLM_BACKEND == "ollama" else "Cannot reach OpenRouter — check internet"
        log.error(f"[LLM] Connection failed: {msg}")
        raise HTTPException(status_code=503, detail=msg)

    except Exception as e:
        log.error(f"[LLM] Unexpected error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"LLM call failed: {str(e)}")

    # ── Step 4: Deduplicate and format sources ────────────────────────────────
    log.debug("[RESPONSE] Deduplicating source documents...")
    seen, sources = set(), []
    for doc in source_docs:
        file = os.path.basename(doc.metadata.get("source", "unknown"))
        page = doc.metadata.get("page", None)
        key  = f"{file}:{page}"
        if key not in seen:
            seen.add(key)
            sources.append(SourceDoc(file=file, page=page))

    # ── Step 5: Done ──────────────────────────────────────────────────────────
    total_ms = (time.perf_counter() - t_request) * 1000
    log.info(f"[RESPONSE] Sending response | sources={len(sources)} | total_time={total_ms:.1f}ms")
    log.info(f"[REQUEST] {'─' * 60}\n")

    return QueryResponse(
        answer=answer,
        sources=sources,
        chunks_used=len(source_docs),
        llm_backend=LLM_BACKEND,
        time_taken_ms=round(total_ms, 1)
    )