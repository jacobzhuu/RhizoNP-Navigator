from __future__ import annotations

import logging
import uuid
from collections import Counter
from collections.abc import Iterator
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from rhizonp.api.middleware import RequestContextMiddleware
from rhizonp.api.readiness import evaluate_readiness
from rhizonp.api.runtime import create_runtime_engine, is_prod_mode
from rhizonp.domain.models import (
    CandidateLink,
    Compound,
    Dataset,
    EvidenceItem,
    NaturalProductRecord,
    OmicsAssociation,
    OmicsObservation,
    Paper,
    PaperChunk,
    Taxon,
)
from rhizonp.literature.retrieval import (
    HybridWeights,
    SearchFilters,
    SearchResult,
    persist_retrieval_results,
)
from rhizonp.literature.retrieval_settings import (
    PROFILE_OFFLINE,
    resolve_literature_retrieval_settings,
)
from rhizonp.literature.runtime import build_literature_retrieval_runtime
from rhizonp.literature.service import LiteratureRetrievalService
from rhizonp.query.llm_policy import resolve_use_llm
from rhizonp.storage.postgres import create_engine_from_settings, create_session_factory
from rhizonp.storage.repositories import (
    CandidateLinkRepository,
    CompoundRepository,
    DatasetRepository,
    EvidenceRepository,
    OmicsAssociationRepository,
    TaxonRepository,
)
from rhizonp.writer.answer_contract import enrich_grounded_answer_metadata

from .schemas import (
    AskRequest,
    AskResponse,
    CandidateLinkResponse,
    CompoundResponse,
    CorpusCountItemResponse,
    CorpusSamplePaperResponse,
    CorpusSummaryResponse,
    EvidenceGradingRequest,
    EvidenceGradingResponse,
    EvidenceItemResponse,
    GroundedAnswerRequest,
    GroundedAnswerResponse,
    HealthResponse,
    HistoryDetailResponse,
    HistoryListItemResponse,
    HistoryListResponse,
    NaturalProductLinkRequest,
    NaturalProductLinkResponse,
    NaturalProductLinkRowResponse,
    NormalizedTaxonResponse,
    OmicsAssociationResponse,
    OwnDataPipelineRequest,
    OwnDataPipelineResponse,
    ReadinessResponse,
    ResultDemoRequest,
    ResultInterpretationRequest,
    ResultsInterpretationResponse,
    SearchRequest,
    SearchResponse,
    SearchResultResponse,
    SearchTraceResponse,
    TaxonResponse,
    WriterClaimResponse,
)

logger = logging.getLogger(__name__)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    engine = create_engine_from_settings()
    return create_session_factory(engine)


def get_session() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def get_optional_session() -> Iterator[Session | None]:
    try:
        session = get_session_factory()()
    except RuntimeError:
        yield None
        return
    try:
        yield session
    finally:
        session.close()


SESSION_DEPENDENCY = Depends(get_session)
OPTIONAL_SESSION_DEPENDENCY = Depends(get_optional_session)


def get_literature_retrieval_service(request: Request) -> LiteratureRetrievalService:
    service = getattr(request.app.state, "literature_retrieval_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="Literature retrieval runtime is unavailable. Check readiness and FAISS index build.",
        )
    return service


LITERATURE_SERVICE_DEPENDENCY = Depends(get_literature_retrieval_service)


def _grounded_answer_response(
    answer_payload: dict[str, object],
    *,
    llm_requested: bool,
    citation_validation: dict[str, object] | None = None,
    faithfulness_diagnostics: list[dict[str, object]] | None = None,
) -> GroundedAnswerResponse:
    from rhizonp.writer.models import GroundedAnswer

    grounded = GroundedAnswer.model_validate(answer_payload)
    contract = enrich_grounded_answer_metadata(grounded, llm_requested=llm_requested)
    return GroundedAnswerResponse(
        status=grounded.status,
        answer=grounded.answer,
        claims=[
            WriterClaimResponse(
                text=claim.text,
                evidence_refs=claim.evidence_refs,
                claim_level=claim.claim_level,
            )
            for claim in grounded.claims
        ],
        evidence_refs=grounded.evidence_refs,
        limitations=grounded.limitations,
        suggested_validations=grounded.suggested_validations,
        writer_mode=grounded.writer_mode,
        provenance=grounded.provenance,
        citation_validation=citation_validation,
        faithfulness_diagnostics=list(faithfulness_diagnostics or []),
        answer_mode=contract["answer_mode"],
        evidence_status=contract["evidence_status"],
        llm_status=contract["llm_status"],
    )


@asynccontextmanager
async def _app_lifespan(app: FastAPI):
    settings = resolve_literature_retrieval_settings()
    strict = settings.profile != PROFILE_OFFLINE
    runtime = build_literature_retrieval_runtime(strict=strict)
    app.state.literature_runtime = runtime
    app.state.literature_retrieval_service = LiteratureRetrievalService(runtime)
    yield


def _error_payload(*, code: str, message: str, detail: str | None = None) -> dict[str, object]:
    resolved_detail = detail or message
    return {
        "error": {
            "code": code,
            "message": message,
            "detail": resolved_detail,
        },
        "detail": resolved_detail,
    }


def _taxon_or_404(session: Session, canonical_name: str) -> Taxon:
    taxon = TaxonRepository(session).find_by_canonical_name(canonical_name)
    if taxon is None:
        raise HTTPException(status_code=404, detail=f"Taxon not found: {canonical_name}")
    return taxon


def _compound_or_404(session: Session, canonical_name: str) -> Compound:
    compound = CompoundRepository(session).find_by_canonical_name(canonical_name)
    if compound is None:
        raise HTTPException(status_code=404, detail=f"Compound not found: {canonical_name}")
    return compound


def _taxon_response(taxon: Taxon) -> TaxonResponse:
    return TaxonResponse(
        taxon_id=taxon.taxon_id,
        canonical_name=taxon.canonical_name,
        rank=taxon.rank,
        strain=taxon.strain,
        species=taxon.species,
        genus=taxon.genus,
        family=taxon.family,
        external_ids=taxon.external_ids,
        normalization_status=taxon.normalization_status,
    )


def _compound_response(compound: Compound) -> CompoundResponse:
    return CompoundResponse(
        compound_id=compound.compound_id,
        canonical_name=compound.canonical_name,
        smiles=compound.smiles,
        inchikey=compound.inchikey,
        formula=compound.formula,
        compound_class=compound.compound_class,
        structure_status=compound.structure_status,
        external_ids=compound.external_ids,
    )


def _evidence_response(evidence: EvidenceItem) -> EvidenceItemResponse:
    return EvidenceItemResponse(
        evidence_id=evidence.evidence_id,
        claim_type=evidence.claim_type,
        subject_entity_type=evidence.subject_entity_type,
        subject_entity_id=evidence.subject_entity_id,
        predicate=evidence.predicate,
        object_entity_type=evidence.object_entity_type,
        object_entity_id=evidence.object_entity_id,
        object_literal=evidence.object_literal,
        source_type=evidence.source_type,
        source_id=evidence.source_id,
        evidence_tier=evidence.evidence_tier,
        directness=evidence.directness,
        extraction_method=evidence.extraction_method,
        confidence=evidence.confidence,
        supporting_span=evidence.supporting_span,
        provenance=evidence.provenance,
    )


def _candidate_link_response(candidate: CandidateLink) -> CandidateLinkResponse:
    return CandidateLinkResponse(
        candidate_id=candidate.candidate_id,
        source_entity_type=candidate.source_entity_type,
        source_entity_id=candidate.source_entity_id,
        relation=candidate.relation,
        target_entity_type=candidate.target_entity_type,
        target_entity_id=candidate.target_entity_id,
        internal_evidence_score=candidate.internal_evidence_score,
        external_evidence_score=candidate.external_evidence_score,
        taxonomy_distance=candidate.taxonomy_distance,
        evidence_tier=candidate.evidence_tier,
        status=candidate.status,
        rationale=candidate.rationale,
    )


def _omics_association_response(association: OmicsAssociation) -> OmicsAssociationResponse:
    return OmicsAssociationResponse(
        association_id=association.association_id,
        dataset_id=association.dataset_id,
        source_entity_type=association.source_entity_type,
        source_entity_id=association.source_entity_id,
        source_raw_label=association.source_raw_label,
        target_entity_type=association.target_entity_type,
        target_entity_id=association.target_entity_id,
        target_raw_label=association.target_raw_label,
        score=association.score,
        adjusted_p=association.adjusted_p,
        method=association.method,
        direction=association.direction,
        treatment=association.treatment,
        timepoint=association.timepoint,
        metadata=association.association_metadata,
    )


def _search_result_response(result: SearchResult) -> SearchResultResponse:
    return SearchResultResponse(
        rank=result.rank,
        score=result.score,
        text=result.text,
        matched_terms=result.matched_terms,
        score_components=result.score_components,
        trace=SearchTraceResponse(
            chunk_id=result.chunk_id,
            paper_id=result.paper_id,
            doi=result.doi,
            source_url=result.source_url,
            section=result.section,
            char_start=result.char_start,
            char_end=result.char_end,
        ),
    )


def _top_count_items(counter: Counter[str], *, limit: int = 8) -> list[CorpusCountItemResponse]:
    return [
        CorpusCountItemResponse(value=value, count=count)
        for value, count in counter.most_common(limit)
    ]


TAGS_HEALTH = "Health"
TAGS_ENTITIES = "Entities"
TAGS_LITERATURE = "Literature"
TAGS_TAXONOMY = "Taxonomy"
TAGS_NATURAL_PRODUCTS = "Natural Products"
TAGS_OWN_DATA = "Own Data"
TAGS_WRITER = "Grounded Writer"
TAGS_ASK = "Unified Ask"
TAGS_RESULTS = "Results Interpretation"
TAGS_HISTORY = "History"


def create_app() -> FastAPI:
    api = FastAPI(
        title="RhizoNP Navigator",
        version="0.1.0",
        lifespan=_app_lifespan,
        description=(
            "Evidence-grounded research API for plant–microbe interactions and microbial "
            "natural products. Exposes literature retrieval, taxonomy-aware evidence grading, "
            "natural product candidate linking, own-data omics pipelines, and a grounded report "
            "writer. Entity endpoints require PostgreSQL with loaded corpus data."
        ),
        openapi_tags=[
            {"name": TAGS_HEALTH, "description": "Service health checks."},
            {"name": TAGS_ENTITIES, "description": "Normalized taxa, compounds, evidence, and omics associations."},
            {"name": TAGS_LITERATURE, "description": "Literature chunk retrieval with provenance traces."},
            {"name": TAGS_TAXONOMY, "description": "Taxonomy-aware evidence grading and claim limits."},
            {"name": TAGS_NATURAL_PRODUCTS, "description": "Natural product candidate linking matrix."},
            {"name": TAGS_OWN_DATA, "description": "Own-data omics CSV pipeline."},
            {"name": TAGS_WRITER, "description": "Evidence-grounded scientific report writer."},
            {"name": TAGS_ASK, "description": "Single-question RAG workflow: plan, expand, retrieve, and answer."},
            {"name": TAGS_RESULTS, "description": "Task-oriented interpretation of omics findings."},
        ],
    )

    api.add_middleware(RequestContextMiddleware)

    @api.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        message = str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(code=f"http_{exc.status_code}", message=message, detail=message),
        )

    @api.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        message = "Request validation failed"
        detail = str(exc.errors())
        return JSONResponse(
            status_code=422,
            content=_error_payload(code="validation_error", message=message, detail=detail),
        )

    @api.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled API error")
        message = "Internal server error"
        return JSONResponse(
            status_code=500,
            content=_error_payload(code="internal_error", message=message, detail=str(exc)),
        )

    @api.get("/api/v1/health", response_model=HealthResponse, tags=[TAGS_HEALTH])
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @api.get("/api/v1/readiness", response_model=ReadinessResponse, tags=[TAGS_HEALTH])
    def readiness(session: Session | None = OPTIONAL_SESSION_DEPENDENCY) -> ReadinessResponse:
        payload = evaluate_readiness(session)
        return ReadinessResponse.model_validate(payload)

    @api.post("/api/v1/ask", response_model=AskResponse, tags=[TAGS_ASK])
    def ask_question(
        request: AskRequest,
        session: Session = SESSION_DEPENDENCY,
        retrieval_service: LiteratureRetrievalService = LITERATURE_SERVICE_DEPENDENCY,
    ) -> AskResponse:
        from rhizonp.config import get_settings
        from rhizonp.query.assistant import run_ask_pipeline

        resolved_use_llm = resolve_use_llm(request.use_llm, get_settings())
        try:
            result = run_ask_pipeline(
                session,
                request.question,
                retrieval_mode=request.retrieval_mode,
                top_k=request.top_k,
                max_queries=request.max_queries,
                use_llm=resolved_use_llm,
                retrieval_service=retrieval_service,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        payload = result.to_dict()
        answer = payload["answer"]
        grounded = _grounded_answer_response(
            answer,
            llm_requested=resolved_use_llm,
            citation_validation=payload["citation_validation"],
            faithfulness_diagnostics=payload["faithfulness_diagnostics"],
        )
        ask_response = AskResponse(
            question_plan=payload["question_plan"],
            retrieval_mode=payload["retrieval_mode"],
            retrieval_hits=payload["retrieval_hits"],
            answer=grounded,
            evidence_items=payload["evidence_items"],
            citation_validation=payload["citation_validation"],
            faithfulness_diagnostics=payload["faithfulness_diagnostics"],
            provenance=payload["provenance"],
        )
        from rhizonp.history.persistence import persist_ask_history

        history_id = persist_ask_history(session, request, ask_response)
        session.commit()
        return ask_response.model_copy(update={"history_id": history_id})

    @api.get("/api/v1/corpus/summary", response_model=CorpusSummaryResponse, tags=[TAGS_LITERATURE])
    def corpus_summary(session: Session = SESSION_DEPENDENCY) -> CorpusSummaryResponse:
        chunks = list(session.scalars(select(PaperChunk).join(Paper).order_by(PaperChunk.created_at)))
        section_counts: Counter[str] = Counter()
        source_type_counts: Counter[str] = Counter()
        taxa_counts: Counter[str] = Counter()
        compound_counts: Counter[str] = Counter()
        host_counts: Counter[str] = Counter()
        fixture_chunk_count = 0
        real_chunk_count = 0
        for chunk in chunks:
            section_counts[chunk.section] += 1
            metadata = chunk.chunk_metadata or {}
            source_type_counts[str(metadata.get("source_type") or "unknown")] += 1
            if metadata.get("fixture") is True:
                fixture_chunk_count += 1
            else:
                real_chunk_count += 1
            for item in metadata.get("taxa") or []:
                taxa_counts[str(item)] += 1
            for item in metadata.get("compounds") or []:
                compound_counts[str(item)] += 1
            for item in metadata.get("host") or []:
                host_counts[str(item)] += 1

        sample_papers = [
            CorpusSamplePaperResponse(
                title=paper.title,
                year=paper.year,
                journal=paper.journal,
                doi=paper.doi,
                pmid=paper.pmid,
                source_url=paper.source_url,
            )
            for paper in session.scalars(
                select(Paper).order_by(Paper.year.desc().nullslast(), Paper.title).limit(6)
            )
        ]
        structured_counts = {
            "taxa": session.scalar(select(func.count()).select_from(Taxon)) or 0,
            "compounds": session.scalar(select(func.count()).select_from(Compound)) or 0,
            "natural_product_records": session.scalar(select(func.count()).select_from(NaturalProductRecord)) or 0,
            "datasets": session.scalar(select(func.count()).select_from(Dataset)) or 0,
            "omics_observations": session.scalar(select(func.count()).select_from(OmicsObservation)) or 0,
            "omics_associations": session.scalar(select(func.count()).select_from(OmicsAssociation)) or 0,
            "evidence_items": session.scalar(select(func.count()).select_from(EvidenceItem)) or 0,
            "candidate_links": session.scalar(select(func.count()).select_from(CandidateLink)) or 0,
        }
        return CorpusSummaryResponse(
            paper_count=session.scalar(select(func.count()).select_from(Paper)) or 0,
            paper_chunk_count=len(chunks),
            retrievable_tables=["paper_chunks"],
            retrieval_modes=["bm25", "dense", "hybrid", "hybrid_rerank"],
            section_counts=dict(section_counts),
            source_type_counts=dict(source_type_counts),
            real_chunk_count=real_chunk_count,
            fixture_chunk_count=fixture_chunk_count,
            structured_counts=structured_counts,
            top_taxa=_top_count_items(taxa_counts),
            top_compounds=_top_count_items(compound_counts),
            top_hosts=_top_count_items(host_counts),
            sample_papers=sample_papers,
        )

    @api.get("/api/v1/taxa/{canonical_name}", response_model=TaxonResponse, tags=[TAGS_ENTITIES])
    def get_taxon(canonical_name: str, session: Session = SESSION_DEPENDENCY) -> TaxonResponse:
        return _taxon_response(_taxon_or_404(session, canonical_name))

    @api.get("/api/v1/compounds/{canonical_name}", response_model=CompoundResponse, tags=[TAGS_ENTITIES])
    def get_compound(
        canonical_name: str,
        session: Session = SESSION_DEPENDENCY,
    ) -> CompoundResponse:
        return _compound_response(_compound_or_404(session, canonical_name))

    @api.get("/api/v1/taxa/{canonical_name}/evidence", response_model=list[EvidenceItemResponse], tags=[TAGS_ENTITIES])
    def list_taxon_evidence(
        canonical_name: str,
        session: Session = SESSION_DEPENDENCY,
    ) -> list[EvidenceItemResponse]:
        taxon = _taxon_or_404(session, canonical_name)
        evidence_items = EvidenceRepository(session).list_for_subject(
            subject_entity_type="taxon",
            subject_entity_id=taxon.taxon_id,
        )
        return [_evidence_response(evidence) for evidence in evidence_items]

    @api.get(
        "/api/v1/taxa/{canonical_name}/candidate-links",
        response_model=list[CandidateLinkResponse],
        tags=[TAGS_ENTITIES],
    )
    def list_taxon_candidate_links(
        canonical_name: str,
        session: Session = SESSION_DEPENDENCY,
    ) -> list[CandidateLinkResponse]:
        taxon = _taxon_or_404(session, canonical_name)
        candidates = CandidateLinkRepository(session).list_for_source(
            source_entity_type="taxon",
            source_entity_id=taxon.taxon_id,
        )
        return [_candidate_link_response(candidate) for candidate in candidates]

    @api.get(
        "/api/v1/datasets/{dataset_name}/omics-associations",
        response_model=list[OmicsAssociationResponse],
        tags=[TAGS_ENTITIES],
    )
    def list_dataset_omics_associations(
        dataset_name: str,
        session: Session = SESSION_DEPENDENCY,
    ) -> list[OmicsAssociationResponse]:
        dataset = DatasetRepository(session).find_by_name(dataset_name)
        if dataset is None:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_name}")
        associations = OmicsAssociationRepository(session).list_for_dataset(dataset.dataset_id)
        return [_omics_association_response(association) for association in associations]

    @api.post("/api/v1/taxonomy/grade", response_model=EvidenceGradingResponse, tags=[TAGS_TAXONOMY])
    def grade_taxonomy_evidence(request: EvidenceGradingRequest) -> EvidenceGradingResponse:
        from rhizonp.taxonomy.grading import grade_evidence

        result = grade_evidence(
            request.query_taxon,
            request.literature_taxon,
            observation_method=request.observation_method,
            taxonomy_source=request.taxonomy_source,
        )

        def _normalized_response(taxon: object) -> NormalizedTaxonResponse:
            from rhizonp.taxonomy.models import NormalizedTaxon

            assert isinstance(taxon, NormalizedTaxon)
            return NormalizedTaxonResponse(
                canonical_name=taxon.canonical_name,
                rank=taxon.rank,
                strain=taxon.strain,
                species=taxon.species,
                genus=taxon.genus,
                normalization_status=taxon.normalization_status,
                confidence=taxon.confidence,
            )

        return EvidenceGradingResponse(
            query_taxon=_normalized_response(result.query_taxon),
            literature_taxon=_normalized_response(result.literature_taxon),
            taxonomy_distance=result.taxonomy_distance.value,
            evidence_tier=result.evidence_tier.value,
            warnings=result.warnings,
            limitations=result.limitations,
            max_supported_claim=result.max_supported_claim,
            provenance=result.provenance,
        )

    @api.post("/api/v1/natural-products/link", response_model=NaturalProductLinkResponse, tags=[TAGS_NATURAL_PRODUCTS])
    def link_natural_products(request: NaturalProductLinkRequest) -> NaturalProductLinkResponse:
        from rhizonp.linking.candidate_engine import link_natural_product_candidates

        matrix = link_natural_product_candidates(
            request.query_taxon,
            metabolite_name=request.metabolite_name,
            observation_method=request.observation_method,
            record_source=request.natural_product_source,
        )
        return NaturalProductLinkResponse(
            query_taxon=matrix.query_taxon,
            metabolite_name=matrix.metabolite_name,
            natural_product_source=matrix.natural_product_source,
            rows=[
                NaturalProductLinkRowResponse(**row.to_dict()) for row in matrix.rows
            ],
        )

    def _open_interpretation_literature_session() -> Session:
        from rhizonp.domain.models import Base
        from rhizonp.ingestion.literature import load_phase2_literature_fixture
        from rhizonp.storage.postgres import create_session_factory

        try:
            engine = create_runtime_engine(allow_sqlite_fallback=not is_prod_mode())
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        Base.metadata.create_all(engine)
        session_factory = create_session_factory(engine)
        session = session_factory()
        chunk_count = int(session.scalar(select(func.count()).select_from(PaperChunk)) or 0)
        if not is_prod_mode() and chunk_count == 0:
            load_phase2_literature_fixture(session)
            session.commit()
        return session

    def _interpretation_literature_retriever(
        session: Session,
        http_request: Request,
        *,
        retrieval_mode: str,
        top_k: int,
        max_queries: int,
    ):
        from rhizonp.omics.literature_bridge import DbBackedLiteratureRetriever

        return DbBackedLiteratureRetriever(
            session=session,
            retrieval_mode=retrieval_mode,
            top_k=top_k,
            max_queries=max_queries,
            runtime=getattr(http_request.app.state, "literature_runtime", None),
        )

    @api.post("/api/v1/own-data/pipeline", response_model=OwnDataPipelineResponse, tags=[TAGS_OWN_DATA])
    def run_own_data_to_literature(
        request: OwnDataPipelineRequest,
        http_request: Request,
    ) -> OwnDataPipelineResponse:
        from rhizonp.config import PROJECT_ROOT
        from rhizonp.domain.models import Base
        from rhizonp.ingestion.literature import load_phase2_literature_fixture
        from rhizonp.omics.pipeline import OwnDataPipelineOptions, run_own_data_pipeline
        from rhizonp.storage.postgres import create_session_factory

        if is_prod_mode() and not request.data_dir:
            raise HTTPException(
                status_code=400,
                detail="data_dir is required when RHIZONP_RUNTIME_MODE=prod",
            )

        data_dir = request.data_dir or str(
            PROJECT_ROOT / "data" / "fixtures" / "own_data_demo"
        )
        literature_session = None
        if request.enable_literature_retrieval:
            try:
                engine = create_runtime_engine(allow_sqlite_fallback=not is_prod_mode())
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            Base.metadata.create_all(engine)
            session_factory = create_session_factory(engine)
            literature_session = session_factory()
            chunk_count = int(
                literature_session.scalar(select(func.count()).select_from(PaperChunk)) or 0
            )
            if not is_prod_mode() and chunk_count == 0:
                load_phase2_literature_fixture(literature_session)
                literature_session.commit()

        try:
            literature_retriever = (
                _interpretation_literature_retriever(
                    literature_session,
                    http_request,
                    retrieval_mode=request.retrieval_mode,
                    top_k=request.top_k,
                    max_queries=request.max_queries,
                )
                if literature_session is not None and request.enable_literature_retrieval
                else None
            )
            result = run_own_data_pipeline(
                data_dir,
                session=literature_session,
                literature_retriever=literature_retriever,
                options=OwnDataPipelineOptions(
                    enable_literature_retrieval=request.enable_literature_retrieval,
                    retrieval_mode=request.retrieval_mode,
                    top_k=request.top_k,
                    max_queries=request.max_queries,
                    natural_product_source=request.natural_product_source,
                    taxonomy_source=request.taxonomy_source,
                    enable_grounded_writer=request.enable_grounded_writer,
                ),
            )
        finally:
            if literature_session is not None:
                literature_session.close()

        payload = result.to_dict()
        return OwnDataPipelineResponse(
            association_count=len(result.association_results),
            results=payload["association_results"],
            provenance={
                **payload["bundle_provenance"],
                **payload["pipeline_provenance"],
            },
        )

    @api.post(
        "/api/v1/results/interpret",
        response_model=ResultsInterpretationResponse,
        tags=[TAGS_RESULTS],
    )
    def interpret_single_result(
        request: ResultInterpretationRequest,
        http_request: Request,
        history_session: Session | None = OPTIONAL_SESSION_DEPENDENCY,
    ) -> ResultsInterpretationResponse:
        from rhizonp.config import get_settings
        from rhizonp.omics.interpretation import ResultFindingInput, interpret_single_finding

        resolved_use_llm = resolve_use_llm(request.use_llm, get_settings())
        session = _open_interpretation_literature_session()
        try:
            literature_retriever = _interpretation_literature_retriever(
                session,
                http_request,
                retrieval_mode=request.retrieval_mode,
                top_k=request.top_k,
                max_queries=request.max_queries,
            )
            payload = interpret_single_finding(
                ResultFindingInput(
                    taxon=request.taxon,
                    metabolite=request.metabolite,
                    association_direction=request.association_direction,
                    effect_size=request.effect_size,
                    p_value=request.p_value,
                    observation_method=request.observation_method,
                    use_llm=resolved_use_llm,
                    retrieval_mode=request.retrieval_mode,
                    top_k=request.top_k,
                    max_queries=request.max_queries,
                ),
                session=session,
                natural_product_source=request.natural_product_source,
                taxonomy_source=request.taxonomy_source,
                literature_retriever=literature_retriever,
            )
        finally:
            session.close()
        response = ResultsInterpretationResponse(**payload)
        history_id = None
        if history_session is not None:
            from rhizonp.history.persistence import persist_results_history

            history_id = persist_results_history(history_session, request, response)
            history_session.commit()
        return response.model_copy(update={"history_id": history_id})

    @api.post(
        "/api/v1/results/demo",
        response_model=ResultsInterpretationResponse,
        tags=[TAGS_RESULTS],
    )
    def interpret_demo_results_endpoint(
        http_request: Request,
        request: ResultDemoRequest | None = None,
    ) -> ResultsInterpretationResponse:
        from rhizonp.config import get_settings
        from rhizonp.omics.interpretation import interpret_demo_results

        resolved_request = request or ResultDemoRequest()
        resolved_use_llm = resolve_use_llm(resolved_request.use_llm, get_settings())
        session = _open_interpretation_literature_session()
        try:
            literature_retriever = _interpretation_literature_retriever(
                session,
                http_request,
                retrieval_mode=resolved_request.retrieval_mode,
                top_k=resolved_request.top_k,
                max_queries=resolved_request.max_queries,
            )
            payload = interpret_demo_results(
                session=session,
                use_llm=resolved_use_llm,
                retrieval_mode=resolved_request.retrieval_mode,
                top_k=resolved_request.top_k,
                max_queries=resolved_request.max_queries,
                natural_product_source=resolved_request.natural_product_source,
                taxonomy_source=resolved_request.taxonomy_source,
                literature_retriever=literature_retriever,
            )
        finally:
            session.close()
        return ResultsInterpretationResponse(**payload)

    @api.get("/api/v1/history", response_model=HistoryListResponse, tags=[TAGS_HISTORY])
    def list_history(
        session: Session = SESSION_DEPENDENCY,
        kind: str | None = Query(default=None, pattern="^(ask|results)$"),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> HistoryListResponse:
        from rhizonp.history.persistence import list_interaction_history

        items, total = list_interaction_history(session, kind=kind, limit=limit, offset=offset)
        return HistoryListResponse(
            items=[
                HistoryListItemResponse(
                    history_id=item.history_id,
                    kind=item.kind,  # type: ignore[arg-type]
                    title=item.title,
                    status=item.status,
                    summary=item.summary,
                    created_at=item.created_at.isoformat(),
                )
                for item in items
            ],
            total=total,
            limit=limit,
            offset=offset,
        )

    @api.get("/api/v1/history/{history_id}", response_model=HistoryDetailResponse, tags=[TAGS_HISTORY])
    def get_history(
        history_id: uuid.UUID,
        session: Session = SESSION_DEPENDENCY,
    ) -> HistoryDetailResponse:
        from rhizonp.history.persistence import get_interaction_history

        record = get_interaction_history(session, history_id)
        if record is None:
            raise HTTPException(status_code=404, detail="History record not found")
        return HistoryDetailResponse(
            history_id=record.history_id,
            kind=record.kind,  # type: ignore[arg-type]
            created_at=record.created_at.isoformat(),
            request=record.request_payload,
            response=record.response_payload,
        )

    @api.post("/api/v1/writer/answer", response_model=GroundedAnswerResponse, tags=[TAGS_WRITER])
    def write_answer(
        request: GroundedAnswerRequest,
        http_request: Request,
    ) -> GroundedAnswerResponse:
        from rhizonp.config import get_settings
        from rhizonp.domain.models import Base
        from rhizonp.ingestion.literature import load_phase2_literature_fixture
        from rhizonp.storage.postgres import create_session_factory
        from rhizonp.writer.models import EvidenceInput, WriterRequest
        from rhizonp.writer.retrieval_service import retrieve_literature_evidence_hits
        from rhizonp.writer.retrieval_writer import write_grounded_answer_from_literature_hits
        from rhizonp.writer.service import write_grounded_answer

        resolved_use_llm = resolve_use_llm(request.use_llm, get_settings())
        citation_validation: dict[str, object] | None = None
        faithfulness_diagnostics: list[dict[str, object]] = []
        retrieval_service = getattr(http_request.app.state, "literature_retrieval_service", None)

        if request.retrieve_evidence:
            query = request.retrieval_query or request.question
            literature_session = None
            try:
                try:
                    engine = create_runtime_engine(allow_sqlite_fallback=not is_prod_mode())
                except RuntimeError as exc:
                    raise HTTPException(status_code=503, detail=str(exc)) from exc
                Base.metadata.create_all(engine)
                session_factory = create_session_factory(engine)
                literature_session = session_factory()
                if not is_prod_mode():
                    load_phase2_literature_fixture(literature_session)
                    literature_session.commit()
                hits = retrieve_literature_evidence_hits(
                    literature_session,
                    query,
                    query_taxon=request.query_taxon or query,
                    observation_method=request.observation_method,
                    retrieval_mode=request.retrieval_mode,
                    top_k=request.top_k,
                    retrieval_service=retrieval_service,
                )
                writer_result = write_grounded_answer_from_literature_hits(
                    request.question,
                    hits,
                    limitations=request.limitations,
                    taxonomy_warnings=request.taxonomy_warnings,
                    retrieval_status="RETRIEVED" if hits else "NO_RESULTS",
                    use_llm=resolved_use_llm,
                )
                answer = writer_result.answer
                citation_validation = writer_result.citation_validation.to_dict()
                faithfulness_diagnostics = list(writer_result.faithfulness_diagnostics)
            finally:
                if literature_session is not None:
                    literature_session.close()
        else:
            writer_request = WriterRequest(
                question=request.question,
                evidence_items=[EvidenceInput(**item.model_dump()) for item in request.evidence_items],
                taxonomy_warnings=request.taxonomy_warnings,
                limitations=request.limitations,
            )
            answer = write_grounded_answer(writer_request, use_llm=resolved_use_llm)
        return _grounded_answer_response(
            answer.model_dump(mode="json"),
            llm_requested=resolved_use_llm,
            citation_validation=citation_validation,
            faithfulness_diagnostics=faithfulness_diagnostics,
        )

    @api.post("/api/v1/search", response_model=SearchResponse, tags=[TAGS_LITERATURE])
    def search_literature(
        request: SearchRequest,
        session: Session = SESSION_DEPENDENCY,
        retrieval_service: LiteratureRetrievalService = LITERATURE_SERVICE_DEPENDENCY,
    ) -> SearchResponse:
        filters = SearchFilters(
            year_from=request.filters.year_from,
            year_to=request.filters.year_to,
            sections=tuple(request.filters.sections),
            source_types=tuple(request.filters.source_types),
            dois=tuple(request.filters.dois),
            source_urls=tuple(request.filters.source_urls),
            journals=tuple(request.filters.journals),
            taxa=tuple(request.filters.taxa),
            compounds=tuple(request.filters.compounds),
            host=tuple(request.filters.host),
        )
        try:
            results = retrieval_service.search(
                session,
                request.query,
                top_k=request.top_k,
                filters=filters,
                retrieval_mode=request.retrieval_mode,
                hybrid_weights=HybridWeights(
                    bm25=request.bm25_weight,
                    dense=request.dense_weight,
                ),
                reranker_weight=request.reranker_weight,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        run = persist_retrieval_results(
            session,
            query=request.query,
            results=results,
            filters=filters,
            retrieval_mode=request.retrieval_mode,
            parameters={
                "top_k": request.top_k,
                "bm25_weight": request.bm25_weight,
                "dense_weight": request.dense_weight,
                "reranker_weight": request.reranker_weight,
            },
        )
        session.commit()
        return SearchResponse(
            run_id=run.run_id,
            retrieval_mode=run.retrieval_mode,
            results=[_search_result_response(result) for result in results],
        )

    return api


app = create_app()
