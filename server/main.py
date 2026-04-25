import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# ── Config ─────────────────────────────────────────────────────────
VECTOR_DIR  = "./vector_store"
EMBED_MODEL = "nomic-embed-text"
LLM_MODEL   = "llama3.2"
OLLAMA_URL  = "http://localhost:11434"

# ── FastAPI app ─────────────────────────────────────────────────────
app = FastAPI(
    title="ERP RAG Server",
    description="Local ERP Q&A powered by Ollama + ChromaDB",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Load ChromaDB ───────────────────────────────────────────────────
print("Loading ChromaDB vector store...")
embeddings = OllamaEmbeddings(
    model=EMBED_MODEL,
    base_url=OLLAMA_URL
)

vectorstore = Chroma(
    persist_directory=VECTOR_DIR,
    embedding_function=embeddings,
    collection_name="erp_docs"
)

retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 5}
)

# ── Load Ollama LLM ─────────────────────────────────────────────────
print("Loading Ollama LLM (llama3.2)...")
llm = ChatOllama(
    model=LLM_MODEL,
    base_url=OLLAMA_URL,
    temperature=0
)

# ── ERP Prompt ──────────────────────────────────────────────────────
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

# ── LCEL Pipeline (modern approach, no RetrievalQA needed) ──────────
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

rag_chain = (
    {
        "context": retriever | format_docs,
        "question": RunnablePassthrough()
    }
    | ERP_PROMPT
    | llm
    | StrOutputParser()
)

print("Server ready.\n")

# ── Pydantic Models ─────────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str

class SourceDoc(BaseModel):
    file: str
    page: Optional[int] = None

class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceDoc]
    chunks_used: int

# ── Endpoints ───────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "status": "running",
        "description": "ERP RAG Server — Ollama + ChromaDB",
        "endpoints": {
            "health": "GET /health",
            "query":  "POST /query",
            "ui":     "GET /docs"
        }
    }

@app.get("/health")
def health():
    try:
        count = vectorstore._collection.count()
        return {
            "status": "ok",
            "vectors_indexed": count,
            "llm_model": LLM_MODEL,
            "embedding_model": EMBED_MODEL,
            "ollama_url": OLLAMA_URL,
            "vector_store": "ChromaDB (local)"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {e}")

@app.post("/query", response_model=QueryResponse)
async def query_erp(request: QueryRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        # Retrieve source docs separately so we can return them
        source_docs = retriever.invoke(request.question)

        # Run the full RAG chain for the answer
        answer = rag_chain.invoke(request.question)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

    # Deduplicate sources
    seen = set()
    sources = []
    for doc in source_docs:
        file = os.path.basename(doc.metadata.get("source", "unknown"))
        page = doc.metadata.get("page", None)
        key  = f"{file}:{page}"
        if key not in seen:
            seen.add(key)
            sources.append(SourceDoc(file=file, page=page))

    return QueryResponse(
        answer=answer,
        sources=sources,
        chunks_used=len(source_docs)
    )