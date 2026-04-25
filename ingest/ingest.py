import os
import sys

# Fix Windows path issues
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import Chroma

DOCS_DIR   = "./docs"
VECTOR_DIR = "./vector_store"
EMBED_MODEL = "nomic-embed-text"   # must match what you pulled in Ollama

def load_all_documents(directory):
    docs = []
    files = [f for f in os.listdir(directory)
             if f.endswith((".pdf", ".docx", ".txt"))]

    if not files:
        print("ERROR: No supported documents found in ./docs")
        print("Add .pdf, .docx, or .txt files and retry.")
        sys.exit(1)

    for filename in files:
        filepath = os.path.join(directory, filename)
        try:
            if filename.endswith(".pdf"):
                loader = PyPDFLoader(filepath)
            elif filename.endswith(".txt"):
                loader = TextLoader(filepath, encoding="utf-8")
            elif filename.endswith(".docx"):
                loader = Docx2txtLoader(filepath)

            pages = loader.load()
            docs.extend(pages)
            print(f"  [OK] {filename}  ({len(pages)} sections)")
        except Exception as e:
            print(f"  [SKIP] {filename} — {e}")

    return docs

def ingest():
    print("\n========================================")
    print("   ERP RAG Ingestion (Ollama + ChromaDB)")
    print("========================================\n")

    print("[1/3] Loading ERP documents from ./docs ...")
    docs = load_all_documents(DOCS_DIR)
    print(f"      Total sections loaded: {len(docs)}\n")

    print("[2/3] Splitting into chunks ...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=64,
        separators=["\n\n", "\n", ".", " "]
    )
    chunks = splitter.split_documents(docs)
    print(f"      Total chunks: {len(chunks)}\n")

    print("[3/3] Embedding with Ollama (nomic-embed-text) and storing in ChromaDB ...")
    print("      This may take a few minutes on first run...\n")

    embeddings = OllamaEmbeddings(
        model=EMBED_MODEL,
        base_url="http://localhost:11434"   # Ollama default on Windows
    )

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=VECTOR_DIR,
        collection_name="erp_docs"
    )

    count = vectorstore._collection.count()
    print(f"\n[DONE] {count} vectors stored in ChromaDB at ./vector_store")
    print("       You can now start the API server.\n")

if __name__ == "__main__":
    ingest()