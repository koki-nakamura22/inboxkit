from __future__ import annotations

import json
import sqlite3
import struct
from datetime import datetime, timezone
from pathlib import Path

import pytest

from rag_ingest._upstream import Item
from rag_ingest.sinks import SQLiteVecSink
from rag_ingest.types import Chunk, IngestContext, Vector


def make_item(source_uri: str) -> Item:
    return Item(id=source_uri, payload="")


def make_ctx() -> IngestContext:
    return IngestContext(
        embedder_provider="stub",
        embedder_model="stub-model",
        chunker_config={"chunk_size": 512, "overlap": 64, "unit": "token"},
        extractor_version="0.1.0",
        source_type="pdf",
        extracted_at=datetime(2026, 5, 17, 0, 0, 0, tzinfo=timezone.utc),
    )


def make_chunks(n: int) -> list[Chunk]:
    return [Chunk(text=f"chunk_{i}", chunk_index=i, metadata={}) for i in range(n)]


def make_vectors(n: int, dim: int = 4) -> list[Vector]:
    return [[0.1 * (i + 1)] * dim for i in range(n)]


@pytest.mark.needs_sqlite_vec
def test_sink_upsert(tmp_path: Path) -> None:
    """AC-005: upsert keeps row count unchanged on second write for same source."""
    db = tmp_path / "rag.db"
    sink = SQLiteVecSink(str(db), dim=4)
    chunks = make_chunks(3)
    vectors = make_vectors(3, dim=4)
    ctx = make_ctx()
    item = make_item("file:///a.pdf")

    sink.write(chunks, vectors, item, ctx)
    sink.write(chunks, vectors, item, ctx)  # 2nd write: upsert

    conn = sqlite3.connect(str(db))
    count = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE source_uri='file:///a.pdf'"
    ).fetchone()[0]
    conn.close()
    assert count == 3


@pytest.mark.needs_sqlite_vec
def test_metadata_has_required_keys(tmp_path: Path) -> None:
    """AC-005: metadata JSON contains the minimum 6 required keys."""
    db = tmp_path / "rag.db"
    sink = SQLiteVecSink(str(db), dim=4)
    sink.write(make_chunks(1), make_vectors(1), make_item("file:///a.pdf"), make_ctx())

    conn = sqlite3.connect(str(db))
    meta_str = conn.execute("SELECT metadata FROM documents LIMIT 1").fetchone()[0]
    conn.close()
    meta = json.loads(meta_str)
    required = {
        "source_type",
        "extracted_at",
        "extractor_version",
        "embedder_provider",
        "embedder_model",
        "chunker_config",
    }
    assert required.issubset(meta.keys())


@pytest.mark.needs_sqlite_vec
def test_schema_and_sqlite_vec_loaded(tmp_path: Path) -> None:
    """AC-005b: table schema + UNIQUE constraint + sqlite-vec loaded on write."""
    db = tmp_path / "rag.db"
    sink = SQLiteVecSink(str(db), dim=4)
    sink.write(make_chunks(1), make_vectors(1), make_item("file:///b.pdf"), make_ctx())

    # sqlite-vec is loaded on sink's connection — vec_version() must be callable
    version = sink._conn.execute("SELECT vec_version()").fetchone()[0]
    assert version.startswith("v")

    conn = sqlite3.connect(str(db))
    cols = {row[1] for row in conn.execute("PRAGMA table_info(documents)").fetchall()}
    assert {"id", "content", "vector", "source_uri", "chunk_index", "metadata", "created_at"}.issubset(
        cols
    )
    # index_list: idx[2] == 1 means UNIQUE
    indices = conn.execute("PRAGMA index_list(documents)").fetchall()
    assert any(idx[2] == 1 for idx in indices)
    conn.close()


@pytest.mark.needs_sqlite_vec
def test_inheritance_search(tmp_path: Path) -> None:
    """AC-006: SQLiteVecSink can be subclassed to add a search method."""

    class TestSearchSink(SQLiteVecSink):
        def search(self, query_vec: Vector, top_k: int = 5) -> list[tuple[int, str, float]]:
            dim = len(query_vec)
            query_bytes = struct.pack(f"{dim}f", *query_vec)
            rows = self._conn.execute(
                f"""SELECT id, content, vec_distance_cosine(vector, ?) as dist
                    FROM {self._table}
                    ORDER BY dist ASC
                    LIMIT ?""",
                (query_bytes, top_k),
            ).fetchall()
            return [(int(row[0]), str(row[1]), float(row[2])) for row in rows]

    db = tmp_path / "rag.db"
    sink = TestSearchSink(str(db), dim=4)
    # Use vectors with varying cosine distances from query [1, 0, 0, 0]
    vectors: list[Vector] = [[1.0, float(i), 0.0, 0.0] for i in range(10)]
    chunks = make_chunks(10)
    sink.write(chunks, vectors, make_item("file:///test.pdf"), make_ctx())

    results = sink.search([1.0, 0.0, 0.0, 0.0], top_k=5)
    assert len(results) == 5
    distances = [r[2] for r in results]
    assert distances == sorted(distances)

    # Write still works after subclassing
    sink.write(make_chunks(2), make_vectors(2), make_item("file:///test2.pdf"), make_ctx())
    conn = sqlite3.connect(str(db))
    count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    conn.close()
    assert count == 12  # 10 + 2


@pytest.mark.needs_sqlite_vec
def test_rollback_on_commit_failure(tmp_path: Path) -> None:
    """AC-R-002: commit failure rolls back the entire Source transaction."""
    db = tmp_path / "rag.db"
    sink = SQLiteVecSink(str(db), dim=4)
    ctx = make_ctx()

    # 1st write: succeeds
    sink.write(make_chunks(3), make_vectors(3), make_item("file:///first.pdf"), ctx)

    # Force the next _commit() to fail
    def failing_commit() -> None:
        raise RuntimeError("simulated commit failure")

    sink._commit = failing_commit  # type: ignore[method-assign]

    # 2nd write: commit fails → rollback
    with pytest.raises(RuntimeError, match="simulated commit failure"):
        sink.write(make_chunks(2), make_vectors(2), make_item("file:///second.pdf"), ctx)

    # Reopen DB to verify committed vs rolled-back state
    conn = sqlite3.connect(str(db))
    first_count = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE source_uri='file:///first.pdf'"
    ).fetchone()[0]
    second_count = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE source_uri='file:///second.pdf'"
    ).fetchone()[0]
    conn.close()
    assert first_count == 3
    assert second_count == 0


@pytest.mark.needs_sqlite_vec
def test_existing_source_uris(tmp_path: Path) -> None:
    """existing_source_uris() returns the set of committed source URIs."""
    db = tmp_path / "rag.db"
    sink = SQLiteVecSink(str(db), dim=4)
    ctx = make_ctx()

    assert sink.existing_source_uris() == set()

    sink.write(make_chunks(2), make_vectors(2), make_item("file:///a.pdf"), ctx)
    sink.write(make_chunks(1), make_vectors(1), make_item("file:///b.pdf"), ctx)

    assert sink.existing_source_uris() == {"file:///a.pdf", "file:///b.pdf"}
