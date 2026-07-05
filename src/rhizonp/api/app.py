from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session, sessionmaker

from rhizonp.domain.models import CandidateLink, Compound, EvidenceItem, OmicsAssociation, Taxon
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
    EvidenceItemResponse,
    HealthResponse,
    OmicsAssociationResponse,
    TaxonResponse,
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


def create_app() -> FastAPI:
    api = FastAPI(
        title="RhizoNP Navigator",
        version="0.1.0",
        description="Read-only Phase 1 API for synthetic fixture and domain entity queries.",
    )

    @api.get("/api/v1/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @api.get("/api/v1/taxa/{canonical_name}", response_model=TaxonResponse)
    def get_taxon(canonical_name: str, session: Session = SESSION_DEPENDENCY) -> TaxonResponse:
        return _taxon_response(_taxon_or_404(session, canonical_name))

    @api.get("/api/v1/compounds/{canonical_name}", response_model=CompoundResponse)
    def get_compound(
        canonical_name: str,
        session: Session = SESSION_DEPENDENCY,
    ) -> CompoundResponse:
        return _compound_response(_compound_or_404(session, canonical_name))

    @api.get("/api/v1/taxa/{canonical_name}/evidence", response_model=list[EvidenceItemResponse])
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

    return api


app = create_app()
