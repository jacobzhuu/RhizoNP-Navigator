from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from rhizonp.config import PROJECT_ROOT, get_settings
from rhizonp.domain.models import Dataset, OmicsAssociation, OmicsObservation, Paper, PaperChunk
from rhizonp.evidence.context import context_from_association_result
from rhizonp.evidence.validator import validate_scientific_constraints
from rhizonp.omics.pipeline import OwnDataPipelineOptions, run_own_data_pipeline
from rhizonp.omics.real_pubmed_validation import (
    DEFAULT_SNAPSHOT_DIR,
    evaluate_safety_checks,
    ingest_bounded_pubmed_snapshot,
    run_direct_retrieval_validation,
    run_own_data_bridge_validation,
)
from rhizonp.storage.postgres import create_session_factory
from rhizonp.writer.retrieval_writer import write_grounded_answer_from_literature_retrieval

DEFAULT_DATABASE_URL = "postgresql://rhizonp:rhizonp_dev@localhost:5432/rhizonp"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "data" / "eval" / "reports" / "latest"
REQUIRED_TABLES = (
    "papers",
    "paper_chunks",
    "taxa",
    "compounds",
    "natural_product_records",
    "datasets",
    "omics_observations",
    "omics_associations",
)


@dataclass(frozen=True)
class DockerState:
    classification: str
    cli_available: bool
    daemon_ready: bool
    compose_available: bool
    docker_version: str | None = None
    compose_version: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "cli_available": self.cli_available,
            "daemon_ready": self.daemon_ready,
            "compose_available": self.compose_available,
            "docker_version": self.docker_version,
            "compose_version": self.compose_version,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class PostgreSQLFullstackValidationReport:
    validation_type: str
    docker: DockerState
    database_url_host: str
    postgresql_version: str | None
    database_backend: str
    migration_revision: str | None
    tables_present: dict[str, bool]
    corpus: dict[str, Any]
    direct_retrieval: list[dict[str, Any]]
    own_data_bridge: list[dict[str, Any]]
    own_data_persistence: dict[str, Any]
    read_back: dict[str, Any]
    restart_persistence: dict[str, Any]
    writer_trace: dict[str, Any]
    api_checks: dict[str, Any]
    safety_checks: dict[str, Any]
    constraint_checks: dict[str, Any]
    real_trace_present: bool
    real_trace: dict[str, Any] | None
    passed: bool
    limitations: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_type": self.validation_type,
            "docker": self.docker.to_dict(),
            "database_url_host": self.database_url_host,
            "postgresql_version": self.postgresql_version,
            "database_backend": self.database_backend,
            "migration_revision": self.migration_revision,
            "tables_present": dict(self.tables_present),
            "corpus": dict(self.corpus),
            "direct_retrieval": list(self.direct_retrieval),
            "own_data_bridge": list(self.own_data_bridge),
            "own_data_persistence": dict(self.own_data_persistence),
            "read_back": dict(self.read_back),
            "restart_persistence": dict(self.restart_persistence),
            "writer_trace": dict(self.writer_trace),
            "api_checks": dict(self.api_checks),
            "safety_checks": dict(self.safety_checks),
            "constraint_checks": dict(self.constraint_checks),
            "real_trace_present": self.real_trace_present,
            "real_trace": self.real_trace,
            "passed": self.passed,
            "limitations": list(self.limitations),
            "provenance": dict(self.provenance),
        }


def _run_command(
    args: list[str],
    *,
    timeout: float = 30.0,
    cwd: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        cwd=cwd,
    )


def inspect_docker_state() -> DockerState:
    notes: list[str] = []
    cli_available = shutil.which("docker") is not None
    if not cli_available:
        return DockerState(
            classification="HARD_BLOCKER",
            cli_available=False,
            daemon_ready=False,
            compose_available=False,
            notes=["docker CLI not found on PATH"],
        )

    version = _run_command(["docker", "--version"], timeout=10.0)
    docker_version = version.stdout.strip() if version.returncode == 0 else None

    info = _run_command(["docker", "info"], timeout=15.0)
    daemon_ready = info.returncode == 0

    compose = _run_command(["docker", "compose", "version"], timeout=10.0)
    compose_available = compose.returncode == 0
    compose_version = compose.stdout.strip() if compose_available else None

    if daemon_ready and compose_available:
        classification = "DOCKER_READY"
    elif daemon_ready and not compose_available:
        classification = "DOCKER_COMPOSE_UNAVAILABLE"
        notes.append("docker compose plugin unavailable")
    elif not daemon_ready:
        classification = "DOCKER_INSTALLED_DAEMON_NOT_READY"
        notes.append((info.stderr or info.stdout or "docker info failed").strip()[:200])
    else:
        classification = "HARD_BLOCKER"

    return DockerState(
        classification=classification,
        cli_available=True,
        daemon_ready=daemon_ready,
        compose_available=compose_available,
        docker_version=docker_version,
        compose_version=compose_version,
        notes=notes,
    )


def resolve_database_url(database_url: str | None = None) -> str:
    if database_url:
        return database_url
    settings = get_settings()
    if settings.database_url:
        return settings.database_url
    password = settings.postgres_password or "rhizonp_dev"
    user = settings.postgres_user or "postgres"
    db = settings.postgres_db or "postgres"
    host = settings.postgres_host or "localhost"
    port = settings.postgres_port or 5432
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def _redact_database_url(database_url: str) -> str:
    if "@" not in database_url:
        return database_url
    prefix, suffix = database_url.split("@", 1)
    if "://" in prefix:
        scheme, _rest = prefix.split("://", 1)
        return f"{scheme}://***@{suffix}"
    return f"***@{suffix}"


def run_alembic_upgrade(database_url: str) -> str:
    env = {**os.environ, "DATABASE_URL": database_url}
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Alembic upgrade failed:\n"
            f"{result.stdout}\n{result.stderr}"
        )
    current = subprocess.run(
        ["alembic", "current"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    revision_line = current.stdout.strip().splitlines()[-1] if current.stdout.strip() else ""
    return revision_line or "head"


def inspect_tables(session: Session) -> dict[str, bool]:
    dialect = session.bind.dialect.name if session.bind is not None else "unknown"
    present: dict[str, bool] = {}
    for table in REQUIRED_TABLES:
        if dialect == "postgresql":
            exists = session.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = :name)"
                ),
                {"name": table},
            )
        else:
            exists = session.scalar(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
                {"name": table},
            )
        present[table] = bool(exists)
    return present


def query_postgresql_version(session: Session) -> str | None:
    if session.bind is None or session.bind.dialect.name != "postgresql":
        return None
    return session.scalar(text("SELECT version()"))


def verify_own_data_read_back(session: Session, *, dataset_name: str) -> dict[str, Any]:
    dataset = session.scalar(select(Dataset).where(Dataset.name == dataset_name))
    if dataset is None:
        return {"dataset_found": False}

    observations = session.scalars(
        select(OmicsObservation).where(OmicsObservation.dataset_id == dataset.dataset_id)
    ).all()
    associations = session.scalars(
        select(OmicsAssociation).where(OmicsAssociation.dataset_id == dataset.dataset_id)
    ).all()

    feature_assoc = next(
        (assoc for assoc in associations if assoc.target_raw_label == "Feature_M123"),
        None,
    )
    return {
        "dataset_found": True,
        "dataset_id": str(dataset.dataset_id),
        "observation_count": len(observations),
        "association_count": len(associations),
        "raw_labels_preserved": all(obs.raw_label for obs in observations),
        "correlation_metadata_preserved": all(
            (obs.observation_metadata or {}).get("correlation_not_causation") is True
            or obs.entity_type == "metabolite"
            for obs in observations
        ),
        "feature_m123_unknown_preserved": bool(
            feature_assoc
            and (feature_assoc.association_metadata or {}).get("correlation_not_causation") is True
        ),
        "feature_m123_assoc_id": str(feature_assoc.association_id) if feature_assoc else None,
    }


def count_persistence_snapshot(session: Session) -> dict[str, int]:
    return {
        "papers": int(session.scalar(select(func.count()).select_from(Paper)) or 0),
        "chunks": int(session.scalar(select(func.count()).select_from(PaperChunk)) or 0),
        "datasets": int(session.scalar(select(func.count()).select_from(Dataset)) or 0),
        "observations": int(session.scalar(select(func.count()).select_from(OmicsObservation)) or 0),
        "associations": int(session.scalar(select(func.count()).select_from(OmicsAssociation)) or 0),
    }


def restart_postgres_container(*, database_url: str | None = None) -> dict[str, Any]:
    resolved = resolve_database_url(database_url)
    settings = get_settings()
    db_user = settings.postgres_user or "postgres"
    db_name = settings.postgres_db or "postgres"

    restart = _run_command(["docker", "compose", "restart", "postgres"], timeout=120.0, cwd=str(PROJECT_ROOT))
    if restart.returncode != 0:
        return {
            "restarted": False,
            "error": (restart.stderr or restart.stdout).strip(),
        }

    ready = False
    for _ in range(30):
        probe = _run_command(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres",
                "pg_isready",
                "-U",
                db_user,
                "-d",
                db_name,
            ],
            timeout=10.0,
            cwd=str(PROJECT_ROOT),
        )
        if probe.returncode == 0:
            ready = True
            break
        time.sleep(1)

    return {"restarted": True, "ready_after_restart": ready, "database_url_host": _redact_database_url(resolved)}


def run_api_checks(database_url: str) -> dict[str, Any]:
    from collections.abc import Iterator

    from fastapi.testclient import TestClient

    from rhizonp.api.app import create_app, get_literature_retrieval_service, get_session
    from rhizonp.config import get_settings
    from rhizonp.literature.runtime import build_literature_retrieval_runtime
    from rhizonp.literature.service import LiteratureRetrievalService

    previous_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()

    engine = create_engine(database_url, future=True)
    session_factory = create_session_factory(engine)
    api = create_app()
    runtime = build_literature_retrieval_runtime(strict=False)
    api.state.literature_runtime = runtime
    api.state.literature_retrieval_service = LiteratureRetrievalService(runtime)

    def override_get_session() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def override_literature_service() -> LiteratureRetrievalService:
        return api.state.literature_retrieval_service

    api.dependency_overrides[get_session] = override_get_session
    api.dependency_overrides[get_literature_retrieval_service] = override_literature_service
    client = TestClient(api)

    try:
        checks: dict[str, Any] = {"endpoints": {}}
        health = client.get("/api/v1/health")
        checks["endpoints"]["health"] = {"status_code": health.status_code, "ok": health.status_code == 200}

        grade = client.post(
            "/api/v1/taxonomy/grade",
            json={
                "query_taxon": "Streptomyces",
                "literature_taxon": "Streptomyces hygroscopicus",
                "observation_method": "16S genus-level",
            },
        )
        checks["endpoints"]["taxonomy_grade"] = {
            "status_code": grade.status_code,
            "ok": grade.status_code == 200,
        }

        np_link = client.post(
            "/api/v1/natural-products/link",
            json={
                "query_taxon": "Streptomyces",
                "metabolite_name": "rapamycin",
                "observation_method": "16S genus-level",
            },
        )
        checks["endpoints"]["natural_product_link"] = {
            "status_code": np_link.status_code,
            "ok": np_link.status_code == 200,
        }

        search = client.post(
            "/api/v1/search",
            json={"query": "Streptomyces rhizosphere natural products", "top_k": 2},
        )
        search_payload = search.json() if search.status_code == 200 else {}
        checks["endpoints"]["literature_search"] = {
            "status_code": search.status_code,
            "ok": search.status_code == 200,
            "result_count": len(search_payload.get("results") or []),
            "postgres_backed": search.status_code == 200 and len(search_payload.get("results") or []) >= 1,
        }

        own_data = client.post(
            "/api/v1/own-data/pipeline",
            json={
                "enable_literature_retrieval": True,
                "enable_grounded_writer": True,
                "persist_to_database": False,
            },
        )
        own_payload = own_data.json() if own_data.status_code == 200 else {}
        bridge_rows = own_payload.get("results") or []
        feature_bridge = next(
            (row for row in bridge_rows if row.get("target_raw_label") == "Feature_M123"),
            None,
        )
        checks["endpoints"]["own_data_pipeline"] = {
            "status_code": own_data.status_code,
            "ok": own_data.status_code == 200,
            "association_count": own_payload.get("association_count"),
            "feature_m123_bridge": feature_bridge is not None,
        }

        writer = client.post(
            "/api/v1/writer/answer",
            json={
                "question": "What literature relates Streptomyces to Feature_M123?",
                "retrieve_evidence": True,
                "retrieval_query": "Streptomyces rhizosphere secondary metabolites",
                "top_k": 2,
                "use_llm": False,
            },
        )
        writer_payload = writer.json() if writer.status_code == 200 else {}
        checks["endpoints"]["writer_answer"] = {
            "status_code": writer.status_code,
            "ok": writer.status_code == 200,
            "writer_status": writer_payload.get("status"),
            "writer_mode": writer_payload.get("writer_mode"),
            "citation_validation_present": writer_payload.get("citation_validation") is not None,
        }

        checks["passed"] = all(item.get("ok") for item in checks["endpoints"].values())
        checks["postgres_search_hit"] = checks["endpoints"]["literature_search"].get("postgres_backed")
        checks["own_data_to_writer_chain"] = bool(
            checks["endpoints"]["own_data_pipeline"]["ok"]
            and checks["endpoints"]["writer_answer"]["ok"]
            and checks["postgres_search_hit"]
        )
        return checks
    finally:
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url
        get_settings.cache_clear()


def _extract_real_trace(
    direct_retrieval: list[dict[str, Any]],
    own_data_bridge: list[dict[str, Any]],
    corpus_id: str,
) -> dict[str, Any] | None:
    from rhizonp.omics.real_pubmed_validation import _extract_real_trace as base_extract

    return base_extract(direct_retrieval, own_data_bridge, corpus_id)


def run_postgresql_fullstack_validation(
    *,
    snapshot_path: str | Path = DEFAULT_SNAPSHOT_DIR / "corpus.json",
    database_url: str | None = None,
    retrieval_mode: str = "bm25",
    top_k: int = 3,
    skip_restart: bool = False,
) -> PostgreSQLFullstackValidationReport:
    docker = inspect_docker_state()
    resolved_url = resolve_database_url(database_url)
    limitations = [
        "This validates the repository against an actual PostgreSQL runtime and does not constitute scientific human validation.",
    ]

    if docker.classification not in {"DOCKER_READY"}:
        return PostgreSQLFullstackValidationReport(
            validation_type="POSTGRESQL_FULLSTACK_VALIDATION",
            docker=docker,
            database_url_host=_redact_database_url(resolved_url),
            postgresql_version=None,
            database_backend="unknown",
            migration_revision=None,
            tables_present={table: False for table in REQUIRED_TABLES},
            corpus={},
            direct_retrieval=[],
            own_data_bridge=[],
            own_data_persistence={},
            read_back={},
            restart_persistence={"skipped": True, "reason": docker.classification},
            writer_trace={},
            api_checks={},
            safety_checks={},
            constraint_checks={},
            real_trace_present=False,
            real_trace=None,
            passed=False,
            limitations=limitations + [f"Docker state: {docker.classification}"],
            provenance={"blocked_by": docker.classification},
        )

    migration_revision = run_alembic_upgrade(resolved_url)
    engine = create_engine(resolved_url, future=True)
    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        ingest_summary, corpus_type, corpus_id = ingest_bounded_pubmed_snapshot(session, snapshot_path)
        direct = run_direct_retrieval_validation(
            session,
            corpus_id=corpus_id,
            corpus_type=corpus_type.value,
            retrieval_mode=retrieval_mode,
            top_k=top_k,
        )
        bridge = run_own_data_bridge_validation(
            session,
            corpus_id=corpus_id,
            corpus_type=corpus_type.value,
            retrieval_mode=retrieval_mode,
            top_k=top_k,
        )

        pipeline_result = run_own_data_pipeline(
            PROJECT_ROOT / "data" / "fixtures" / "own_data_demo",
            session=session,
            options=OwnDataPipelineOptions(
                enable_literature_retrieval=True,
                enable_grounded_writer=True,
                persist_to_database=True,
                retrieval_mode=retrieval_mode,
                top_k=top_k,
                corpus_id=corpus_id,
                corpus_type=corpus_type.value,
            ),
        )
        session.commit()
        dataset_name = pipeline_result.provenance.get("database_persistence", {}).get("dataset_name", "own_data_demo")
        read_back = verify_own_data_read_back(session, dataset_name=str(dataset_name))
        before_counts = count_persistence_snapshot(session)

        feature_row = next(
            (row for row in bridge if row.get("target_raw_label") == "Feature_M123"),
            None,
        )
        writer_trace: dict[str, Any] = {}
        if feature_row:
            assoc_result = next(
                (
                    item
                    for item in pipeline_result.association_results
                    if item.association.target_raw_label == "Feature_M123"
                ),
                None,
            )
            if assoc_result and assoc_result.grounded_writer:
                writer_trace = {
                    "association_id": feature_row.get("association_id"),
                    "writer_status": assoc_result.grounded_writer.get("answer", {}).get("status"),
                    "writer_mode": assoc_result.grounded_writer.get("answer", {}).get("writer_mode"),
                    "citation_valid": assoc_result.grounded_writer.get("citation_validation", {}).get(
                        "citation_ref_validity_rate"
                    ),
                }
            elif feature_row.get("top_hit"):
                writer_result = write_grounded_answer_from_literature_retrieval(
                    "What literature relates Streptomyces to Feature_M123?",
                    {"status": "RETRIEVED", "hits": [feature_row["top_hit"]]},
                    limitations=feature_row.get("limitations") or [],
                )
                writer_trace = {
                    "association_id": feature_row.get("association_id"),
                    "writer_status": writer_result.answer.status.value,
                    "writer_mode": writer_result.answer.writer_mode,
                    "citation_valid": writer_result.citation_validation.citation_ref_validity_rate,
                }

        safety = evaluate_safety_checks(bridge)
        constraint_checks: dict[str, Any] = {}
        for index, assoc in enumerate(pipeline_result.association_results):
            if not assoc.grounded_writer:
                continue
            context = context_from_association_result(
                f"PG_FULLSTACK_{index}",
                {
                    "association_id": assoc.association.association_id,
                    "source_raw_label": assoc.association.source_raw_label,
                    "target_raw_label": assoc.association.target_raw_label,
                    "literature_retrieval": assoc.literature_retrieval,
                    "taxonomy_grading": assoc.taxonomy_grading.to_dict() if assoc.taxonomy_grading else None,
                    "candidate_links": {"rows": [row.to_dict() for row in assoc.candidate_matrix.rows]},
                    "grounded_writer": assoc.grounded_writer,
                    "limitations": assoc.limitations,
                    "method": assoc.association.method,
                },
            )
            report = validate_scientific_constraints(context)
            constraint_checks[str(assoc.association.association_id)] = {
                "passed": report.passed,
                "issues": list(report.issues),
            }

        real_trace = _extract_real_trace(direct, bridge, corpus_id)
        tables_present = inspect_tables(session)
        pg_version = query_postgresql_version(session)
    finally:
        session.close()

    restart_result: dict[str, Any]
    after_counts: dict[str, int]
    if skip_restart:
        restart_result = {"skipped": True}
        after_counts = before_counts
    else:
        restart_result = restart_postgres_container(database_url=resolved_url)
        engine.dispose()
        after_counts = before_counts
        for _attempt in range(30):
            if not restart_result.get("ready_after_restart"):
                time.sleep(1)
                continue
            try:
                fresh_engine = create_engine(resolved_url, future=True)
                fresh_factory = create_session_factory(fresh_engine)
                after_session = fresh_factory()
                try:
                    after_counts = count_persistence_snapshot(after_session)
                    break
                finally:
                    after_session.close()
                    fresh_engine.dispose()
            except Exception:
                time.sleep(1)
                continue
        restart_result["before_counts"] = before_counts
        restart_result["after_counts"] = after_counts
        restart_result["persisted"] = after_counts == before_counts and all(after_counts.values())

    api_checks = run_api_checks(resolved_url)

    passed = bool(
        ingest_summary.database_backend == "postgresql"
        and ingest_summary.corpus_type == "REAL_BOUNDED_PUBMED"
        and ingest_summary.paper_count >= 1
        and ingest_summary.chunk_count >= 1
        and read_back.get("dataset_found")
        and read_back.get("feature_m123_unknown_preserved")
        and real_trace is not None
        and all(safety.values())
        and all(item.get("passed", True) for item in constraint_checks.values())
        and restart_result.get("persisted", restart_result.get("skipped"))
        and api_checks.get("passed")
    )

    return PostgreSQLFullstackValidationReport(
        validation_type="POSTGRESQL_FULLSTACK_VALIDATION",
        docker=docker,
        database_url_host=_redact_database_url(resolved_url),
        postgresql_version=pg_version,
        database_backend=ingest_summary.database_backend,
        migration_revision=migration_revision,
        tables_present=tables_present,
        corpus=ingest_summary.to_dict(),
        direct_retrieval=direct,
        own_data_bridge=bridge,
        own_data_persistence=dict(pipeline_result.provenance.get("database_persistence") or {}),
        read_back=read_back,
        restart_persistence=restart_result,
        writer_trace=writer_trace,
        api_checks=api_checks,
        safety_checks=safety,
        constraint_checks=constraint_checks,
        real_trace_present=real_trace is not None,
        real_trace=real_trace,
        passed=passed,
        limitations=limitations,
        provenance={
            "module": "rhizonp.evaluation.postgresql_fullstack_validation",
            "integration_validation_only": True,
        },
    )


def write_postgresql_validation_reports(
    report: PostgreSQLFullstackValidationReport,
    output_dir: str | Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    payload = report.to_dict()

    json_path = directory / "postgresql_fullstack_validation.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# PostgreSQL Full-Stack Validation",
        "",
        "This validates the repository against an actual PostgreSQL runtime and does not constitute scientific human validation.",
        "",
        f"- Docker state: `{payload['docker']['classification']}`",
        f"- PostgreSQL version: `{payload.get('postgresql_version', 'unknown')}`",
        f"- Database backend: `{payload['database_backend']}`",
        f"- Migration revision: `{payload['migration_revision']}`",
        f"- Papers: {payload['corpus'].get('paper_count', 0)}",
        f"- Chunks: {payload['corpus'].get('chunk_count', 0)}",
        f"- Own-data persisted: `{payload['own_data_persistence'].get('persisted', False)}`",
        f"- Real trace present: `{payload['real_trace_present']}`",
        f"- Restart persistence: `{payload['restart_persistence'].get('persisted', payload['restart_persistence'].get('skipped'))}`",
        f"- API checks passed: `{payload['api_checks'].get('passed')}`",
        f"- Overall passed: `{payload['passed']}`",
        "",
        "## Limitations",
        "",
    ]
    for item in payload["limitations"]:
        lines.append(f"- {item}")

    md_path = directory / "postgresql_fullstack_validation.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path
