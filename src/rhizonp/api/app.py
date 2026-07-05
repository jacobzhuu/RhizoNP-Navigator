from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session, sessionmaker

from rhizonp.domain.models import CandidateLink, Compound, EvidenceItem, OmicsAssociation, Taxon
from rhizonp.literature.retrieval import (
    HybridWeights,
    SearchFilters,
    SearchResult,
    persist_retrieval_results,
    search_paper_chunks,
)
from rhizonp.storage.postgres import create_engine_from_settings, create_session_factory
from rhizonp.storage.repositories import (
    CandidateLinkRepository,
    CompoundRepository,
    DatasetRepository,
    EvidenceRepository,
    OmicsAssociationRepository,
    TaxonRepository,
)

from .schemas import (
    CandidateLinkResponse,
    CompoundResponse,
    EvidenceGradingRequest,
    EvidenceGradingResponse,
    EvidenceItemResponse,
    GroundedAnswerRequest,
    GroundedAnswerResponse,
    HealthResponse,
    NaturalProductLinkRequest,
    NaturalProductLinkResponse,
    NaturalProductLinkRowResponse,
    NormalizedTaxonResponse,
    OmicsAssociationResponse,
    OwnDataPipelineRequest,
    OwnDataPipelineResponse,
    SearchRequest,
    SearchResponse,
    SearchResultResponse,
    SearchTraceResponse,
    TaxonResponse,
    WriterClaimResponse,
)


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


SESSION_DEPENDENCY = Depends(get_session)


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


TAGS_HEALTH = "Health"
TAGS_ENTITIES = "Entities"
TAGS_LITERATURE = "Literature"
TAGS_TAXONOMY = "Taxonomy"
TAGS_NATURAL_PRODUCTS = "Natural Products"
TAGS_OWN_DATA = "Own Data"
TAGS_WRITER = "Grounded Writer"


def create_app() -> FastAPI:
    api = FastAPI(
        title="RhizoNP Navigator",
        version="0.1.0",
        description=(
            "Evidence-grounded research API for plant–microbe interactions and microbial "
            "natural products. Exposes literature retrieval, taxonomy-aware evidence grading, "
            "natural product candidate linking, own-data omics pipelines, and a grounded report "
            "writer. Entity endpoints require PostgreSQL with loaded fixtures; grading, linking, "
            "own-data, and writer endpoints are stateless. See the research workspace frontend "
            "for workflow demos."
        ),
        openapi_tags=[
            {"name": TAGS_HEALTH, "description": "Service health checks."},
            {"name": TAGS_ENTITIES, "description": "Normalized taxa, compounds, evidence, and omics associations."},
            {"name": TAGS_LITERATURE, "description": "Literature chunk retrieval with provenance traces."},
            {"name": TAGS_TAXONOMY, "description": "Taxonomy-aware evidence grading and claim limits."},
            {"name": TAGS_NATURAL_PRODUCTS, "description": "Natural product candidate linking matrix."},
            {"name": TAGS_OWN_DATA, "description": "Own-data omics CSV pipeline."},
            {"name": TAGS_WRITER, "description": "Evidence-grounded scientific report writer."},
        ],
    )

    @api.get("/api/v1/health", response_model=HealthResponse, tags=[TAGS_HEALTH])
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

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

    @api.post("/api/v1/own-data/pipeline", response_model=OwnDataPipelineResponse, tags=[TAGS_OWN_DATA])
    def run_own_data_to_literature(
        request: OwnDataPipelineRequest,
    ) -> OwnDataPipelineResponse:
        from sqlalchemy import create_engine
        from sqlalchemy.pool import StaticPool

        from rhizonp.config import PROJECT_ROOT
        from rhizonp.domain.models import Base
        from rhizonp.ingestion.literature import load_phase2_literature_fixture
        from rhizonp.omics.pipeline import OwnDataPipelineOptions, run_own_data_pipeline
        from rhizonp.storage.postgres import create_engine_from_settings, create_session_factory

        data_dir = request.data_dir or str(
            PROJECT_ROOT / "data" / "fixtures" / "own_data_demo"
        )
        literature_session = None
        if request.enable_literature_retrieval:
            try:
                engine = create_engine_from_settings()
            except RuntimeError:
                engine = create_engine(
                    "sqlite+pysqlite://",
                    connect_args={"check_same_thread": False},
                    poolclass=StaticPool,
                    future=True,
                )
            Base.metadata.create_all(engine)
            session_factory = create_session_factory(engine)
            literature_session = session_factory()
            load_phase2_literature_fixture(literature_session)
            literature_session.commit()

        try:
            result = run_own_data_pipeline(
                data_dir,
                session=literature_session,
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

    @api.post("/api/v1/writer/answer", response_model=GroundedAnswerResponse, tags=[TAGS_WRITER])
    def write_answer(request: GroundedAnswerRequest) -> GroundedAnswerResponse:
        from sqlalchemy import create_engine
        from sqlalchemy.pool import StaticPool

        from rhizonp.domain.models import Base
        from rhizonp.ingestion.literature import load_phase2_literature_fixture
        from rhizonp.storage.postgres import create_engine_from_settings, create_session_factory
        from rhizonp.writer.models import EvidenceInput, WriterRequest
        from rhizonp.writer.retrieval_service import retrieve_literature_evidence_hits
        from rhizonp.writer.retrieval_writer import write_grounded_answer_from_literature_hits
        from rhizonp.writer.service import write_grounded_answer

        citation_validation: dict[str, object] | None = None
        faithfulness_diagnostics: list[dict[str, object]] = []

        if request.retrieve_evidence:
            query = request.retrieval_query or request.question
            literature_session = None
            try:
                try:
                    engine = create_engine_from_settings()
                except RuntimeError:
                    engine = create_engine(
                        "sqlite+pysqlite://",
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool,
                        future=True,
                    )
                Base.metadata.create_all(engine)
                session_factory = create_session_factory(engine)
                literature_session = session_factory()
                load_phase2_literature_fixture(literature_session)
                literature_session.commit()
                hits = retrieve_literature_evidence_hits(
                    literature_session,
                    query,
                    query_taxon=request.query_taxon or query,
                    observation_method=request.observation_method,
                    retrieval_mode=request.retrieval_mode,
                    top_k=request.top_k,
                )
                writer_result = write_grounded_answer_from_literature_hits(
                    request.question,
                    hits,
                    limitations=request.limitations,
                    taxonomy_warnings=request.taxonomy_warnings,
                    retrieval_status="RETRIEVED" if hits else "NO_RESULTS",
                    use_llm=request.use_llm,
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
            answer = write_grounded_answer(writer_request, use_llm=request.use_llm)
        return GroundedAnswerResponse(
            status=answer.status.value,
            answer=answer.answer,
            claims=[
                WriterClaimResponse(
                    text=claim.text,
                    evidence_refs=claim.evidence_refs,
                    claim_level=claim.claim_level,
                )
                for claim in answer.claims
            ],
            evidence_refs=answer.evidence_refs,
            limitations=answer.limitations,
            suggested_validations=answer.suggested_validations,
            writer_mode=answer.writer_mode,
            provenance=answer.provenance,
            citation_validation=citation_validation,
            faithfulness_diagnostics=faithfulness_diagnostics,
        )

    @api.post("/api/v1/search", response_model=SearchResponse, tags=[TAGS_LITERATURE])
    def search_literature(
        request: SearchRequest,
        session: Session = SESSION_DEPENDENCY,
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
            results = search_paper_chunks(
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
