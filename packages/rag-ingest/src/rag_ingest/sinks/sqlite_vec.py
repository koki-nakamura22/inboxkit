from __future__ import annotations

import json
import sqlite3
import struct

import sqlite_vec

from rag_ingest._upstream import Item
from rag_ingest.exceptions import SqliteVecLoadError
from rag_ingest.types import Chunk, IngestContext, Vector


class SQLiteVecSink:
    def __init__(
        self,
        db_path: str,
        table: str = "documents",
        dim: int | None = None,
    ) -> None:
        self._db_path = db_path
        self._table = table
        self._dim = dim
        self._table_ready = False
        self._conn = sqlite3.connect(db_path)
        self._load_extension()

    def _load_extension(self) -> None:
        self._conn.enable_load_extension(True)
        try:
            sqlite_vec.load(self._conn)
        except Exception as exc:
            raise SqliteVecLoadError(str(exc)) from exc
        finally:
            self._conn.enable_load_extension(False)

    def _ensure_table(self, dim: int) -> None:
        if self._table_ready:
            return
        self._conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {self._table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                vector float[{dim}],
                source_uri TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                metadata TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_uri, chunk_index)
            )"""
        )
        self._conn.commit()
        self._dim = dim
        self._table_ready = True

    def _commit(self) -> None:
        self._conn.commit()

    def write(
        self,
        chunks: list[Chunk],
        vectors: list[Vector],
        item: Item,
        ingest_context: IngestContext,
    ) -> None:
        """Source 1 件 = 1 transaction で N 行を upsert."""
        if not chunks:
            return
        dim = self._dim if self._dim is not None else len(vectors[0])
        self._ensure_table(dim)
        source_uri = item.id
        try:
            for chunk, vector in zip(chunks, vectors):
                metadata: dict[str, object] = {
                    "source_type": ingest_context.source_type,
                    "extracted_at": ingest_context.extracted_at.isoformat(),
                    "extractor_version": ingest_context.extractor_version,
                    "embedder_provider": ingest_context.embedder_provider,
                    "embedder_model": ingest_context.embedder_model,
                    "chunker_config": ingest_context.chunker_config,
                    **chunk.metadata,
                }
                vec_bytes = struct.pack(f"{dim}f", *vector)
                self._conn.execute(
                    f"""INSERT INTO {self._table}
                        (content, vector, source_uri, chunk_index, metadata)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(source_uri, chunk_index) DO UPDATE SET
                          content=excluded.content,
                          vector=excluded.vector,
                          metadata=excluded.metadata""",
                    (chunk.text, vec_bytes, source_uri, chunk.chunk_index, json.dumps(metadata)),
                )
            self._commit()
        except Exception:
            self._conn.rollback()
            raise

    def existing_source_uris(self) -> set[str]:
        try:
            rows = self._conn.execute(
                f"SELECT DISTINCT source_uri FROM {self._table}"
            ).fetchall()
            return {row[0] for row in rows}
        except sqlite3.OperationalError:
            return set()
