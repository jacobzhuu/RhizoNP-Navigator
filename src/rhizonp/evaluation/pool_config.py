from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PoolSystemSpec:
    system_name: str
    retrieval_mode: str


DEFAULT_POOL_SYSTEMS: tuple[PoolSystemSpec, ...] = (
    PoolSystemSpec(system_name="bm25", retrieval_mode="bm25"),
    PoolSystemSpec(system_name="dense_hash", retrieval_mode="dense"),
    PoolSystemSpec(system_name="hybrid_hash", retrieval_mode="hybrid"),
    PoolSystemSpec(system_name="hybrid_rerank_lexical", retrieval_mode="hybrid_rerank"),
)

DEFAULT_POOL_DEPTH = 20
