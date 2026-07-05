from __future__ import annotations

import uuid
from typing import Any

from rhizonp.evidence.models import ConstraintValidationContext
from rhizonp.linking.candidate_engine import link_natural_product_candidates
from rhizonp.linking.np_adapter import NaturalProductSource
from rhizonp.omics.csv_ingestion import load_own_data_bundle
from rhizonp.omics.pipeline import OwnDataPipelineOptions, run_own_data_pipeline
from rhizonp.omics.query_builder import build_query_context
from rhizonp.taxonomy.grading import grade_evidence
from rhizonp.writer.citation_validation import validate_citation_trace
from rhizonp.writer.fallback_writer import write_fallback_answer
from rhizonp.writer.models import EvidenceInput, WriterRequest


def context_from_association_result(
    case_id: str,
    association_result: dict[str, Any],
    *,
    provenance_scope: str | None = None,
) -> ConstraintValidationContext:
    candidate_links = association_result.get("candidate_links") or {}
    rows = candidate_links.get("rows") or []
    top_row = rows[0] if rows else None
    grounded = association_result.get("grounded_writer") or {}
    return ConstraintValidationContext(
        case_id=case_id,
        taxonomy_grading=association_result.get("taxonomy_grading"),
        query_context=association_result.get("query_context"),
        candidate_row=top_row,
        literature_retrieval=association_result.get("literature_retrieval"),
        writer_request=grounded.get("writer_request"),
        grounded_answer=grounded.get("answer"),
        citation_validation=grounded.get("citation_validation"),
        limitations=list(association_result.get("limitations") or []),
        association_method=str(association_result.get("method") or ""),
        provenance_scope=provenance_scope,
        source_modules=["omics", "taxonomy", "linking", "writer"],
    )


def build_genus_rapamycin_cross_module_context(
    case_id: str = "XMOD_GENUS_RAPAMYCIN",
) -> ConstraintValidationContext:
    observation_method = "16S genus-level observation"
    grading = grade_evidence(
        "Streptomyces",
        "Streptomyces coelicolor",
        observation_method=observation_method,
    )
    matrix = link_natural_product_candidates(
        "Streptomyces",
        metabolite_name="rapamycin",
        observation_method=observation_method,
    )
    top_row = matrix.rows[0] if matrix.rows else None
    request = WriterRequest(
        question="Does this sample contain a strain producing rapamycin?",
        evidence_items=[
            EvidenceInput(
                evidence_id=uuid.uuid4(),
                claim_type="taxon_produces_compound",
                predicate="MENTIONS",
                object_literal="rapamycin",
                evidence_tier=grading.evidence_tier.value,
                taxonomy_distance=grading.taxonomy_distance.value,
                supporting_span="Literature mentions Streptomyces and rapamycin in the same passage.",
            )
        ],
        taxonomy_warnings=list(grading.warnings),
        limitations=list(grading.limitations),
    )
    answer = write_fallback_answer(request)
    validation = validate_citation_trace(request.evidence_items, answer)
    return ConstraintValidationContext(
        case_id=case_id,
        taxonomy_grading=grading.to_dict(),
        candidate_row=top_row.to_dict() if top_row is not None else None,
        writer_request=request.model_dump(mode="json"),
        grounded_answer=answer.model_dump(mode="json"),
        citation_validation=validation.to_dict(),
        limitations=list(grading.limitations),
        association_method=observation_method,
        provenance_scope="cross_module_synthetic",
        source_modules=["taxonomy", "linking", "writer"],
    )


def build_empty_evidence_abstention_context(case_id: str = "XMOD_EMPTY_EVIDENCE") -> ConstraintValidationContext:
    request = WriterRequest(question="Does organism X produce compound Y?", evidence_items=[])
    answer = write_fallback_answer(request)
    validation = validate_citation_trace([], answer)
    return ConstraintValidationContext(
        case_id=case_id,
        writer_request=request.model_dump(mode="json"),
        grounded_answer=answer.model_dump(mode="json"),
        citation_validation=validation.to_dict(),
        expected_requires_abstention=True,
        source_modules=["writer"],
    )


def build_conflict_context(case_id: str = "XMOD_CONFLICT") -> ConstraintValidationContext:
    evidence_id = uuid.uuid4()
    request = WriterRequest(
        question="Does the taxon produce rapamycin?",
        evidence_items=[
            EvidenceInput(
                evidence_id=evidence_id,
                claim_type="taxon_produces_compound",
                predicate="PRODUCES",
                object_literal="rapamycin",
                evidence_tier="B",
            ),
            EvidenceInput(
                evidence_id=uuid.uuid4(),
                claim_type="taxon_produces_compound",
                predicate="DOES_NOT_PRODUCE",
                object_literal="rapamycin",
                evidence_tier="B",
            ),
        ],
    )
    answer = write_fallback_answer(request)
    validation = validate_citation_trace(request.evidence_items, answer)
    return ConstraintValidationContext(
        case_id=case_id,
        writer_request=request.model_dump(mode="json"),
        grounded_answer=answer.model_dump(mode="json"),
        citation_validation=validation.to_dict(),
        expected_requires_conflict=True,
        source_modules=["writer"],
    )


def build_no_false_conflict_context(case_id: str = "XMOD_NO_FALSE_CONFLICT") -> ConstraintValidationContext:
    request = WriterRequest(
        question="Does the taxon produce two different compounds?",
        evidence_items=[
            EvidenceInput(
                evidence_id=uuid.uuid4(),
                claim_type="taxon_produces_compound",
                predicate="PRODUCES",
                object_literal="rapamycin",
                evidence_tier="B",
            ),
            EvidenceInput(
                evidence_id=uuid.uuid4(),
                claim_type="taxon_produces_compound",
                predicate="DOES_NOT_PRODUCE",
                object_literal="actinomycin",
                evidence_tier="B",
            ),
        ],
    )
    answer = write_fallback_answer(request)
    validation = validate_citation_trace(request.evidence_items, answer)
    return ConstraintValidationContext(
        case_id=case_id,
        writer_request=request.model_dump(mode="json"),
        grounded_answer=answer.model_dump(mode="json"),
        citation_validation=validation.to_dict(),
        expected_requires_conflict=False,
        source_modules=["writer"],
    )


def build_npatlas_candidate_context(case_id: str = "XMOD_NPATLAS_CANDIDATE") -> ConstraintValidationContext:
    observation_method = "16S genus-level observation"
    grading = grade_evidence(
        "Streptomyces",
        "Streptomyces nodosus (NPS007994)",
        observation_method=observation_method,
    )
    matrix = link_natural_product_candidates(
        "Streptomyces",
        observation_method=observation_method,
        record_source=NaturalProductSource.NPATLAS_BOUNDED,
    )
    top_row = matrix.rows[0] if matrix.rows else None
    return ConstraintValidationContext(
        case_id=case_id,
        taxonomy_grading=grading.to_dict(),
        candidate_row=top_row.to_dict() if top_row is not None else None,
        limitations=list(grading.limitations),
        association_method=observation_method,
        provenance_scope="real_bounded_npatlas",
        source_modules=["taxonomy", "linking"],
    )


def build_ncbi_taxonomy_bounded_context(case_id: str = "XMOD_NCBI_TAXONOMY") -> ConstraintValidationContext:
    grading = grade_evidence(
        "Streptomyces",
        "Streptomyces hygroscopicus",
        taxonomy_source="ncbi_cached",
    )
    matrix = link_natural_product_candidates(
        "Streptomyces",
        metabolite_name="rapamycin",
        taxonomy_source="ncbi_cached",
    )
    top_row = matrix.rows[0] if matrix.rows else None
    return ConstraintValidationContext(
        case_id=case_id,
        taxonomy_grading=grading.to_dict(),
        candidate_row=top_row.to_dict() if top_row is not None else None,
        provenance_scope="real_bounded_ncbi_taxonomy",
        source_modules=["taxonomy", "linking"],
    )


def build_own_data_feature_m123_context(case_id: str = "XMOD_OWN_DATA_M123") -> ConstraintValidationContext:
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from rhizonp.domain.models import Base
    from rhizonp.ingestion.literature import load_phase2_literature_fixture
    from rhizonp.storage.postgres import create_session_factory

    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        load_phase2_literature_fixture(session)
        session.commit()
        pipeline = run_own_data_pipeline(
            session=session,
            options=OwnDataPipelineOptions(
                enable_literature_retrieval=True,
                enable_grounded_writer=True,
                natural_product_source="fixture",
                taxonomy_source="auto",
            ),
        )
        association = next(
            result
            for result in pipeline.association_results
            if result.metabolite.raw_label == "Feature_M123"
        )
        bundle = load_own_data_bundle()
        taxon = next(item for item in bundle.taxa if item.raw_label == "Streptomyces")
        metabolite = next(item for item in bundle.metabolites if item.raw_label == "Feature_M123")
        query_context = build_query_context(
            taxon,
            metabolite,
            association_score=association.association.score,
        )
        payload = association.to_dict()
        payload["query_context"] = {
            "taxon_name": query_context.taxon_name,
            "metabolite_raw_label": query_context.metabolite_raw_label,
            "normalized_compound_name": query_context.normalized_compound_name,
            "compound_identity_known": query_context.compound_identity_known,
            "chemical_identification_tier": query_context.chemical_identification_tier,
            "observation_method": query_context.observation_method,
            "association_score": query_context.association_score,
        }
        payload["method"] = association.association.method
        return context_from_association_result(
            case_id,
            payload,
            provenance_scope="own_data_fixture",
        )
    finally:
        session.close()


def build_real_bounded_pubmed_context(case_id: str = "XMOD_REAL_PUBMED") -> ConstraintValidationContext:
    from sqlalchemy.orm import Session

    from rhizonp.domain.models import Base
    from rhizonp.omics.real_pubmed_validation import (
        DEFAULT_SNAPSHOT_DIR,
        create_validation_engine,
        ingest_bounded_pubmed_snapshot,
    )
    from rhizonp.storage.postgres import create_session_factory
    from rhizonp.writer.retrieval_service import retrieve_literature_evidence_hits
    from rhizonp.writer.retrieval_writer import write_grounded_answer_from_literature_hits

    snapshot_path = DEFAULT_SNAPSHOT_DIR / "corpus.json"
    if not snapshot_path.is_file():
        raise FileNotFoundError(f"Missing bounded PubMed snapshot: {snapshot_path}")

    engine = create_validation_engine()
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    session: Session = session_factory()
    try:
        ingest_bounded_pubmed_snapshot(session, snapshot_path)
        query = "Streptomyces microbial natural products"
        hits = retrieve_literature_evidence_hits(
            session,
            query,
            query_taxon="Streptomyces",
            observation_method="16S genus-level observation",
            retrieval_mode="bm25",
            top_k=2,
        )
        hit_dicts = [hit.to_dict() for hit in hits]
        grading = (hits[0].taxonomy_grading or {}).get("grading") if hits else None
        writer_result = write_grounded_answer_from_literature_hits(
            f"What literature mentions: {query}?",
            hits,
            limitations=["Real bounded PubMed mention does not imply production or causation."],
            taxonomy_warnings=(grading or {}).get("warnings", []),
            retrieval_status="RETRIEVED" if hits else "NO_RESULTS",
        )
        writer_payload = writer_result.to_dict()
        return ConstraintValidationContext(
            case_id=case_id,
            taxonomy_grading=grading,
            literature_retrieval={
                "status": "RETRIEVED" if hits else "NO_RESULTS",
                "hits": hit_dicts,
                "queries": [{"query_text": query}],
            },
            writer_request={
                "question": f"What literature mentions: {query}?",
                "evidence_items": writer_payload.get("evidence_items") or [],
            },
            grounded_answer=writer_payload.get("answer"),
            citation_validation=writer_payload.get("citation_validation"),
            limitations=["Real bounded PubMed mention does not imply production or causation."],
            provenance_scope="real_bounded_pubmed",
            source_modules=["literature", "taxonomy", "writer"],
        )
    finally:
        session.close()
