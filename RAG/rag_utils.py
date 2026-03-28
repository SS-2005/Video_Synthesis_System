from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional

try:
    import PyPDF2  # type: ignore
except Exception:  # pragma: no cover
    PyPDF2 = None


DEFAULT_KB_DIRS = [
    Path("Input") / "KnowledgeBase",
    Path("Input") / "knowledge_base",
    Path("KnowledgeBase"),
]
SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".json"}
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "he", "in", "is", "it", "its", "of", "on", "that", "the", "to", "was",
    "were", "will", "with", "this", "these", "those", "or", "into", "about",
    "than", "then", "their", "there", "which", "what", "when", "where", "why",
    "how", "can", "could", "should", "would", "you", "your", "they", "them",
}


@dataclass
class RetrievedChunk:
    source: str
    chunk_id: int
    text: str
    score: float
    metadata: Dict[str, str]

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


class SimpleRAG:
    """A lightweight local retrieval helper with zero extra dependencies.

    It reads .txt, .md, .pdf, and .json files from a local knowledge-base folder,
    chunks them, scores them using token overlap + rarity weighting, and returns the
    top grounded snippets for prompt conditioning.
    """

    def __init__(self, kb_dirs: Optional[Iterable[Path]] = None, chunk_size: int = 900, overlap: int = 150):
        self.kb_dirs = list(kb_dirs) if kb_dirs is not None else DEFAULT_KB_DIRS
        self.chunk_size = chunk_size
        self.overlap = overlap
        self._chunks: List[RetrievedChunk] = []
        self._df: Counter[str] = Counter()

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.replace("\r", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [
            t for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9_\-/]+", text.lower())
            if t not in STOPWORDS and len(t) > 1
        ]

    def _read_text_file(self, path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="ignore")

    def _read_json_file(self, path: Path) -> str:
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            return json.dumps(data, indent=2, ensure_ascii=False)
        except Exception:
            return path.read_text(encoding="utf-8", errors="ignore")

    def _read_pdf_file(self, path: Path) -> str:
        if PyPDF2 is None:
            return ""
        text_parts: List[str] = []
        try:
            with path.open("rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        text_parts.append(page_text)
        except Exception:
            return ""
        return "\n\n".join(text_parts)

    def _read_file(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".txt" or suffix == ".md":
            return self._read_text_file(path)
        if suffix == ".json":
            return self._read_json_file(path)
        if suffix == ".pdf":
            return self._read_pdf_file(path)
        return ""

    def _iter_source_files(self) -> Iterable[Path]:
        seen = set()
        for kb_dir in self.kb_dirs:
            if not kb_dir.exists() or not kb_dir.is_dir():
                continue
            for path in kb_dir.rglob("*"):
                if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    resolved = str(path.resolve())
                    if resolved not in seen:
                        seen.add(resolved)
                        yield path

    def _chunk_text(self, text: str) -> List[str]:
        text = self._normalize_text(text)
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]

        chunks: List[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + self.chunk_size)
            candidate = text[start:end]
            if end < len(text):
                split_points = [candidate.rfind("\n\n"), candidate.rfind(". "), candidate.rfind("; ")]
                split_points = [p for p in split_points if p > self.chunk_size * 0.55]
                if split_points:
                    end = start + max(split_points) + 1
                    candidate = text[start:end]
            chunks.append(candidate.strip())
            if end >= len(text):
                break
            start = max(start + 1, end - self.overlap)
        return [c for c in chunks if c]

    def build_index(self) -> int:
        self._chunks = []
        self._df = Counter()
        for file_path in self._iter_source_files():
            raw_text = self._read_file(file_path)
            if not raw_text.strip():
                continue
            file_chunks = self._chunk_text(raw_text)
            for idx, chunk in enumerate(file_chunks, start=1):
                chunk_obj = RetrievedChunk(
                    source=str(file_path).replace("\\", "/"),
                    chunk_id=idx,
                    text=chunk,
                    score=0.0,
                    metadata={"filename": file_path.name, "extension": file_path.suffix.lower()},
                )
                self._chunks.append(chunk_obj)
                for token in set(self._tokenize(chunk)):
                    self._df[token] += 1
        return len(self._chunks)

    def _idf(self, token: str) -> float:
        n_docs = max(len(self._chunks), 1)
        df = self._df.get(token, 0)
        return math.log((1 + n_docs) / (1 + df)) + 1.0

    def retrieve(self, query: str, top_k: int = 4) -> List[RetrievedChunk]:
        if not self._chunks:
            self.build_index()
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        ranked: List[RetrievedChunk] = []
        q_counter = Counter(query_tokens)
        for chunk in self._chunks:
            c_tokens = self._tokenize(chunk.text)
            if not c_tokens:
                continue
            c_counter = Counter(c_tokens)
            score = 0.0
            for token, q_tf in q_counter.items():
                if token in c_counter:
                    score += min(q_tf, c_counter[token]) * self._idf(token)
            if score > 0:
                length_penalty = 1.0 + (len(c_tokens) / 240.0)
                ranked.append(
                    RetrievedChunk(
                        source=chunk.source,
                        chunk_id=chunk.chunk_id,
                        text=chunk.text,
                        score=round(score / length_penalty, 4),
                        metadata=chunk.metadata,
                    )
                )
        ranked.sort(key=lambda x: x.score, reverse=True)
        return ranked[:top_k]

    def format_context(self, chunks: List[RetrievedChunk], max_chars: int = 3000) -> str:
        if not chunks:
            return ""
        parts: List[str] = []
        current = 0
        for item in chunks:
            block = (
                f"[SOURCE: {item.metadata.get('filename', item.source)} | chunk {item.chunk_id} | score {item.score}]\n"
                f"{item.text.strip()}\n"
            )
            if current + len(block) > max_chars:
                break
            parts.append(block)
            current += len(block)
        return "\n".join(parts).strip()


def ensure_default_kb_readme(base_dir: Path | str = Path("Input") / "KnowledgeBase") -> Path:
    base_path = Path(base_dir)
    base_path.mkdir(parents=True, exist_ok=True)
    readme_path = base_path / "README_KB.txt"
    if not readme_path.exists():
        readme_path.write_text(
            "Place grounding material here for RAG. Supported formats: .txt, .md, .pdf, .json\n"
            "Examples: product specs, notes, policies, brand docs, course notes, factual references.\n"
            "The generator will retrieve from these files before writing the video script.\n",
            encoding="utf-8",
        )
    return readme_path
