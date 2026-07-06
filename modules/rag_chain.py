"""Traceable RAG pipeline backed by a persistent Chroma vector store."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings

from modules.data_loader import IntelligenceRecord, load_project_records

INDEX_PATH = Path("data/processed/rag_index.json")
CHROMA_DIR = Path("chroma_db")
COLLECTION_NAME = "competitor_intelligence"
CHUNK_SIZE = 700
CHUNK_OVERLAP = 120
EMBEDDING_DIMENSION = 128


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


class HashEmbeddingFunction(EmbeddingFunction[Documents]):
    """Deterministic local embedding so Chroma works without extra API calls."""

    def __call__(self, input: Documents) -> Embeddings:
        return [hash_embedding(text) for text in input]


def hash_embedding(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSION
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSION
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be larger than overlap")
    chunks = []
    start = 0
    while start < len(text):
        chunk = text[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


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


class ChromaRAGIndex:
    """Fixed chain: clean records -> chunks -> Chroma vectors -> evidence snippets."""

    def __init__(self, chunks: list[EvidenceChunk] | None = None):
        self.chunks = chunks or []
        self.client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=HashEmbeddingFunction(),
            metadata={"description": "Traceable competitor intelligence chunks"},
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
            self.collection.add(
                ids=[chunk.chunk_id for chunk in self.chunks],
                documents=[chunk.text for chunk in self.chunks],
                metadatas=[
                    {
                        "record_id": chunk.record_id,
                        "title": chunk.title,
                        "source_url": chunk.source_url,
                        "competitor": chunk.competitor,
                        "dimension": chunk.dimension,
                        "collected_at": chunk.collected_at,
                    }
                    for chunk in self.chunks
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
    index = ChromaRAGIndex.from_records(load_project_records())
    index.persist()
    return index
