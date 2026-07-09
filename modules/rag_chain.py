"""Traceable RAG pipeline backed by a persistent Chroma vector store."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from modules.data_loader import IntelligenceRecord, load_project_records

INDEX_PATH = Path("data/processed/rag_index.json")
INDEX_META_PATH = Path("data/processed/rag_index_meta.json")
CHROMA_DIR = Path("chroma_db")
HF_CACHE_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "hf_cache"
COLLECTION_NAME = "competitor_intelligence"
CHUNK_SIZE = 700
CHUNK_OVERLAP = 120
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
DEFAULT_HF_ENDPOINT = "https://hf-mirror.com"
DEFAULT_EMBEDDING_BATCH_SIZE = 64
CHUNK_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]


@dataclass
class EvidenceChunk:
    chunk_id: str
    record_id: str
    title: str
    text: str
    source_url: str
    competitor: str
    dimension: str
    collected_at: str


class HuggingFaceEmbeddingFunction(EmbeddingFunction[Documents]):
    """Chroma adapter around LangChain HuggingFaceEmbeddings."""

    def __init__(
        self,
        model_name: str,
        device: str = "cpu",
        normalize_embeddings: bool = True,
        batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
    ):
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError as exc:
            raise RuntimeError(
                "Hugging Face RAG requires langchain-huggingface and sentence-transformers. "
                "Install project dependencies with `python -m pip install -r requirements.txt`."
            ) from exc

        self.embeddings = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": device},
            encode_kwargs={
                "normalize_embeddings": normalize_embeddings,
                "batch_size": batch_size,
            },
        )

    def __call__(self, input: Documents) -> Embeddings:
        return self.embeddings.embed_documents(list(input))

    @staticmethod
    def name() -> str:
        return "huggingface"

    def embed_query(self, input: Documents | str) -> Embeddings:
        texts = input if isinstance(input, list) else [input]
        return self.embeddings.embed_documents(list(texts))


def get_embedding_settings(env: dict[str, str] | None = None) -> dict[str, object]:
    env = env or os.environ
    endpoint = env.get("HF_ENDPOINT", DEFAULT_HF_ENDPOINT).strip()
    if endpoint:
        os.environ.setdefault("HF_ENDPOINT", endpoint)
    cache_dir = env.get("HF_HOME", str(HF_CACHE_DIR)).strip() or str(HF_CACHE_DIR)
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", cache_dir)
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(Path(cache_dir) / "hub"))
    os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(Path(cache_dir) / "st"))
    normalize = env.get("RAG_NORMALIZE_EMBEDDINGS", "true").strip().lower() in {"1", "true", "yes", "on"}
    return {
        "provider": "huggingface",
        "model_name": env.get("RAG_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL).strip() or DEFAULT_EMBEDDING_MODEL,
        "device": env.get("RAG_EMBEDDING_DEVICE", "cpu").strip() or "cpu",
        "normalize_embeddings": normalize,
        "batch_size": max(int(env.get("RAG_EMBEDDING_BATCH_SIZE", str(DEFAULT_EMBEDDING_BATCH_SIZE))), 1),
        "cache_dir": cache_dir,
        "hf_endpoint": endpoint,
    }


def collection_name_for(settings: dict[str, object]) -> str:
    model_slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(settings["model_name"])).strip("_").lower()
    return f"{COLLECTION_NAME}_{model_slug}"


def create_embedding_function() -> HuggingFaceEmbeddingFunction:
    settings = get_embedding_settings()
    return HuggingFaceEmbeddingFunction(
        model_name=str(settings["model_name"]),
        device=str(settings["device"]),
        normalize_embeddings=bool(settings["normalize_embeddings"]),
        batch_size=int(settings["batch_size"]),
    )


def split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be larger than overlap")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=len,
        separators=CHUNK_SEPARATORS,
    )
    return [chunk.strip() for chunk in splitter.split_text(text or "") if chunk.strip()]


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[\w\u4e00-\u9fff]+", text.lower()))


def records_to_chunks(records: Sequence[IntelligenceRecord]) -> list[EvidenceChunk]:
    chunks: list[EvidenceChunk] = []
    for record in records:
        for idx, text in enumerate(split_text(record.content)):
            chunks.append(
                EvidenceChunk(
                    chunk_id=f"{record.record_id}-{idx}",
                    record_id=record.record_id,
                    title=record.title,
                    text=text,
                    source_url=record.source_url,
                    competitor=record.competitor,
                    dimension=record.dimension,
                    collected_at=record.collected_at,
                )
            )
    return chunks


def compute_records_signature(records: Sequence[IntelligenceRecord], settings: dict[str, object]) -> str:
    payload = {
        "embedding_model": settings["model_name"],
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "records": [
            {
                "record_id": record.record_id,
                "title": record.title,
                "content": record.content,
                "source_url": record.source_url,
                "competitor": record.competitor,
                "dimension": record.dimension,
                "collected_at": record.collected_at,
            }
            for record in records
        ],
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


class ChromaRAGIndex:
    """Fixed chain: clean records -> chunks -> Chroma vectors -> evidence snippets."""

    def __init__(self, chunks: list[EvidenceChunk] | None = None):
        self.chunks = chunks or []
        self.client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self.embedding_settings = get_embedding_settings()
        self.collection = self.client.get_or_create_collection(
            name=collection_name_for(self.embedding_settings),
            embedding_function=create_embedding_function(),
            metadata={
                "description": "Traceable competitor intelligence chunks",
                "embedding_provider": str(self.embedding_settings["provider"]),
                "embedding_model": str(self.embedding_settings["model_name"]),
            },
        )

    @classmethod
    def from_records(cls, records: list[IntelligenceRecord]) -> "ChromaRAGIndex":
        return cls(records_to_chunks(records))

    @classmethod
    def load(cls, path: str | Path = INDEX_PATH) -> "ChromaRAGIndex":
        index_path = Path(path)
        if index_path.exists():
            data = json.loads(index_path.read_text(encoding="utf-8"))
            return cls([EvidenceChunk(**item) for item in data])
        return cls.from_records(load_project_records())

    def persist(self, path: str | Path = INDEX_PATH) -> Path:
        index_path = Path(path)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            json.dumps([asdict(chunk) for chunk in self.chunks], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        existing = self.collection.get(include=[])
        if existing.get("ids"):
            self.collection.delete(ids=existing["ids"])

        if self.chunks:
            batch_size = int(self.embedding_settings["batch_size"])
            for start in range(0, len(self.chunks), batch_size):
                batch = self.chunks[start : start + batch_size]
                self.collection.add(
                    ids=[chunk.chunk_id for chunk in batch],
                    documents=[chunk.text for chunk in batch],
                    metadatas=[
                        {
                            "record_id": chunk.record_id,
                            "title": chunk.title,
                            "source_url": chunk.source_url,
                            "competitor": chunk.competitor,
                            "dimension": chunk.dimension,
                            "collected_at": chunk.collected_at,
                        }
                        for chunk in batch
                    ],
                )
        return index_path

    def search(
        self,
        query: str,
        top_k: int = 5,
        dimension: str | None = None,
        competitor: str | None = None,
    ) -> list[EvidenceChunk]:
        results = self.collection.query(query_texts=[query], n_results=max(top_k * 5, top_k))
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        chunks = []
        for chunk_id, text, metadata in zip(ids, documents, metadatas):
            if dimension and metadata.get("dimension") not in {dimension, "general", ""}:
                continue
            if competitor and metadata.get("competitor") != competitor:
                continue
            chunks.append(
                EvidenceChunk(
                    chunk_id=chunk_id,
                    record_id=metadata.get("record_id", ""),
                    title=metadata.get("title", ""),
                    text=text,
                    source_url=metadata.get("source_url", ""),
                    competitor=metadata.get("competitor", ""),
                    dimension=metadata.get("dimension", ""),
                    collected_at=metadata.get("collected_at", ""),
                )
            )
        fallback = self._keyword_fallback(query=query, top_k=top_k, dimension=dimension, competitor=competitor)
        by_id = {chunk.chunk_id: chunk for chunk in chunks + fallback}
        return list(by_id.values())[:top_k]

    def _keyword_fallback(
        self,
        query: str,
        top_k: int,
        dimension: str | None,
        competitor: str | None,
    ) -> list[EvidenceChunk]:
        query_tokens = tokenize(query)
        scored = []
        for chunk in self.chunks:
            if dimension and chunk.dimension not in {dimension, "general", ""}:
                continue
            if competitor and chunk.competitor != competitor:
                continue
            chunk_tokens = tokenize(" ".join([chunk.title, chunk.text, chunk.competitor, chunk.dimension]))
            overlap = len(query_tokens & chunk_tokens)
            if overlap:
                competitor_boost = 2.0 if competitor and chunk.competitor == competitor else 0.0
                scored.append((competitor_boost + overlap / math.sqrt(max(len(chunk_tokens), 1)), chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[:top_k]]


SimpleRAGIndex = ChromaRAGIndex


def build_project_index() -> ChromaRAGIndex:
    records = load_project_records()
    settings = get_embedding_settings()
    signature = compute_records_signature(records, settings)
    if INDEX_META_PATH.exists() and INDEX_PATH.exists():
        try:
            meta = json.loads(INDEX_META_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            meta = {}
        if meta.get("signature") == signature:
            return ChromaRAGIndex.load()

    index = ChromaRAGIndex.from_records(records)
    index.persist()
    INDEX_META_PATH.write_text(
        json.dumps(
            {
                "signature": signature,
                "record_count": len(records),
                "chunk_count": len(index.chunks),
                "embedding_model": settings["model_name"],
                "batch_size": settings["batch_size"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return index
