from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rhizonp.config import PROJECT_ROOT
from rhizonp.domain.models import (
    CandidateLink,
    Compound,
    Dataset,
    EvidenceItem,
    NaturalProductRecord,
    OmicsAssociation,
    OmicsObservation,
    Paper,
    Taxon,
)

DEFAULT_PHASE1_FIXTURE_PATH = PROJECT_ROOT / "data" / "fixtures" / "phase1_demo.json"


@dataclass(frozen=True)
class DemoFixtureSummary:
    papers: int
    taxa: int
    compounds: int
    natural_product_records: int
    datasets: int
    omics_observations: int
    omics_associations: int
    evidence_items: int
    candidate_links: int


def _read_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _keyed(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    keyed_records: dict[str, dict[str, Any]] = {}
    for record in records:
        key = record.get("key")
        if not isinstance(key, str) or not key:
            raise ValueError(f"Fixture record is missing a non-empty key: {record}")
        keyed_records[key] = record
    return keyed_records


def _ref(mapping: dict[str, Any], key: str | None) -> Any | None:
    if key is None:
        return None
    try:
        return mapping[key]
    except KeyError as exc:
        raise ValueError(f"Unknown fixture reference: {key}") from exc


def _entity_id(entity: Any | None) -> Any | None:
    if entity is None:
        return None
    if hasattr(entity, "taxon_id"):
        return entity.taxon_id
    if hasattr(entity, "compound_id"):
        return entity.compound_id
    raise TypeError(f"Unsupported entity reference type: {type(entity)!r}")


def _source_id(source: Any) -> Any:
    if hasattr(source, "paper_id"):
        return source.paper_id
    if hasattr(source, "dataset_id"):
        return source.dataset_id
    raise TypeError(f"Unsupported source reference type: {type(source)!r}")


def _find_paper(session: Session, record: dict[str, Any]) -> Paper | None:
    for field, value in (
        (Paper.doi, record.get("doi")),
        (Paper.pmid, record.get("pmid")),
        (Paper.source_url, record.get("source_url")),
        (Paper.title, record.get("title")),
    ):
        if value:
            found = session.scalar(select(Paper).where(field == value).limit(1))
            if found is not None:
                return found
    return None


def _find_taxon(session: Session, record: dict[str, Any]) -> Taxon | None:
    canonical_name = record.get("canonical_name")
    if not canonical_name:
        return None
    return session.scalar(
        select(Taxon)
        .where(func.lower(Taxon.canonical_name) == str(canonical_name).casefold())
        .limit(1)
    )


def _find_compound(session: Session, record: dict[str, Any]) -> Compound | None:
    canonical_name = record.get("canonical_name")
    if not canonical_name:
        return None
    return session.scalar(
        select(Compound)
        .where(func.lower(Compound.canonical_name) == str(canonical_name).casefold())
        .limit(1)
    )


def _find_dataset(session: Session, record: dict[str, Any]) -> Dataset | None:
    name = record.get("name")
    if not name:
        return None
    return session.scalar(select(Dataset).where(Dataset.name == name).limit(1))


def _find_np_record(session: Session, record: dict[str, Any]) -> NaturalProductRecord | None:
    return session.scalar(
        select(NaturalProductRecord)
        .where(
            NaturalProductRecord.source_database == record["source_database"],
            NaturalProductRecord.external_record_id == record["external_record_id"],
        )
        .limit(1)
    )


def _find_observation(
    session: Session,
    *,
    dataset: Dataset,
    record: dict[str, Any],
) -> OmicsObservation | None:
    with session.no_autoflush:
        return session.scalar(
            select(OmicsObservation)
            .where(
                OmicsObservation.dataset_id == dataset.dataset_id,
                OmicsObservation.entity_type == record["entity_type"],
                OmicsObservation.raw_label == record["raw_label"],
                OmicsObservation.method == record["method"],
                OmicsObservation.treatment == record.get("treatment"),
                OmicsObservation.timepoint == record.get("timepoint"),
            )
            .limit(1)
        )


def _find_association(
    session: Session,
    *,
    dataset: Dataset,
    record: dict[str, Any],
) -> OmicsAssociation | None:
    with session.no_autoflush:
        return session.scalar(
            select(OmicsAssociation)
            .where(
                OmicsAssociation.dataset_id == dataset.dataset_id,
                OmicsAssociation.source_entity_type == record["source_entity_type"],
                OmicsAssociation.source_raw_label == record["source_raw_label"],
                OmicsAssociation.target_entity_type == record["target_entity_type"],
                OmicsAssociation.target_raw_label == record["target_raw_label"],
                OmicsAssociation.method == record["method"],
                OmicsAssociation.treatment == record.get("treatment"),
                OmicsAssociation.timepoint == record.get("timepoint"),
            )
            .limit(1)
        )


def _find_evidence_item(
    session: Session,
    *,
    subject_entity: Any,
    source: Any,
    record: dict[str, Any],
) -> EvidenceItem | None:
    return session.scalar(
        select(EvidenceItem)
        .where(
            EvidenceItem.claim_type == record["claim_type"],
            EvidenceItem.subject_entity_type == record["subject_entity_type"],
            EvidenceItem.subject_entity_id == _entity_id(subject_entity),
            EvidenceItem.predicate == record["predicate"],
            EvidenceItem.source_type == record["source_type"],
            EvidenceItem.source_id == _source_id(source),
            EvidenceItem.extraction_method == record["extraction_method"],
        )
        .limit(1)
    )


def _find_candidate_link(
    session: Session,
    *,
    source_entity: Any,
    target_entity: Any,
    record: dict[str, Any],
) -> CandidateLink | None:
    return session.scalar(
        select(CandidateLink)
        .where(
            CandidateLink.source_entity_type == record["source_entity_type"],
            CandidateLink.source_entity_id == _entity_id(source_entity),
            CandidateLink.relation == record["relation"],
            CandidateLink.target_entity_type == record["target_entity_type"],
            CandidateLink.target_entity_id == _entity_id(target_entity),
            CandidateLink.status == record["status"],
        )
        .limit(1)
    )


def load_phase1_demo_fixture(
    session: Session,
    fixture_path: str | Path = DEFAULT_PHASE1_FIXTURE_PATH,
) -> DemoFixtureSummary:
    path = Path(fixture_path)
    payload = _read_fixture(path)

    paper_records = _keyed(payload.get("papers", []))
    taxon_records = _keyed(payload.get("taxa", []))
    compound_records = _keyed(payload.get("compounds", []))
    dataset_records = _keyed(payload.get("datasets", []))

    papers: dict[str, Paper] = {}
    for key, record in paper_records.items():
        existing_paper = _find_paper(session, record)
        papers[key] = existing_paper or Paper(
            doi=record.get("doi"),
            pmid=record.get("pmid"),
            pmcid=record.get("pmcid"),
            title=record["title"],
            abstract=record.get("abstract"),
            year=record.get("year"),
            journal=record.get("journal"),
            source_url=record.get("source_url"),
            license=record.get("license"),
            provenance=record.get("provenance", {}),
        )
    session.add_all(papers.values())

    taxa: dict[str, Taxon] = {}
    for key, record in taxon_records.items():
        existing_taxon = _find_taxon(session, record)
        taxa[key] = existing_taxon or Taxon(
            canonical_name=record["canonical_name"],
            rank=record.get("rank"),
            strain=record.get("strain"),
            species=record.get("species"),
            genus=record.get("genus"),
            family=record.get("family"),
            external_ids=record.get("external_ids", {}),
            normalization_status=record.get("normalization_status", "unresolved"),
        )
    session.add_all(taxa.values())

    compounds: dict[str, Compound] = {}
    for key, record in compound_records.items():
        existing_compound = _find_compound(session, record)
        compounds[key] = existing_compound or Compound(
            canonical_name=record["canonical_name"],
            smiles=record.get("smiles"),
            inchikey=record.get("inchikey"),
            formula=record.get("formula"),
            compound_class=record.get("compound_class"),
            structure_status=record.get("structure_status", "unknown"),
            external_ids=record.get("external_ids", {}),
        )
    session.add_all(compounds.values())

    datasets: dict[str, Dataset] = {}
    for key, record in dataset_records.items():
        existing_dataset = _find_dataset(session, record)
        datasets[key] = existing_dataset or Dataset(
            name=record["name"],
            description=record.get("description"),
            owner=record.get("owner"),
            data_type=record["data_type"],
            provenance=record.get("provenance", {}),
        )
    session.add_all(datasets.values())
    session.flush()

    natural_product_records: list[NaturalProductRecord] = []
    for record in payload.get("natural_product_records", []):
        existing_np_record = _find_np_record(session, record)
        natural_product_records.append(
            existing_np_record or NaturalProductRecord(
                compound=_ref(compounds, record.get("compound_ref")),
                producer_taxon=_ref(taxa, record.get("producer_taxon_ref")),
                source_database=record["source_database"],
                external_record_id=record["external_record_id"],
                bioactivity_summary=record.get("bioactivity_summary"),
                reference_paper=_ref(papers, record.get("reference_paper_ref")),
                provenance=record.get("provenance", {}),
            )
        )
    session.add_all(natural_product_records)
    session.flush()

    observations: list[OmicsObservation] = []
    for record in payload.get("omics_observations", []):
        entity = _ref({**taxa, **compounds}, record.get("entity_ref"))
        dataset = _ref(datasets, record.get("dataset_ref"))
        assert isinstance(dataset, Dataset)
        existing_observation = _find_observation(session, dataset=dataset, record=record)
        observations.append(
            existing_observation or OmicsObservation(
                dataset=dataset,
                entity_type=record["entity_type"],
                entity_id=_entity_id(entity),
                raw_label=record["raw_label"],
                treatment=record.get("treatment"),
                timepoint=record.get("timepoint"),
                layer=record.get("layer"),
                effect_size=record.get("effect_size"),
                p_value=record.get("p_value"),
                adjusted_p=record.get("adjusted_p"),
                method=record["method"],
                observation_metadata=record.get("metadata", {}),
            )
        )
    session.add_all(observations)
    session.flush()

    associations: list[OmicsAssociation] = []
    for record in payload.get("omics_associations", []):
        source_entity = _ref({**taxa, **compounds}, record.get("source_entity_ref"))
        target_entity = _ref({**taxa, **compounds}, record.get("target_entity_ref"))
        dataset = _ref(datasets, record.get("dataset_ref"))
        assert isinstance(dataset, Dataset)
        existing_association = _find_association(session, dataset=dataset, record=record)
        associations.append(
            existing_association or OmicsAssociation(
                dataset=dataset,
                source_entity_type=record["source_entity_type"],
                source_entity_id=_entity_id(source_entity),
                source_raw_label=record["source_raw_label"],
                target_entity_type=record["target_entity_type"],
                target_entity_id=_entity_id(target_entity),
                target_raw_label=record["target_raw_label"],
                score=record["score"],
                adjusted_p=record.get("adjusted_p"),
                method=record["method"],
                direction=record.get("direction"),
                treatment=record.get("treatment"),
                timepoint=record.get("timepoint"),
                association_metadata=record.get("metadata", {}),
            )
        )
    session.add_all(associations)
    session.flush()

    evidence_items: list[EvidenceItem] = []
    entity_refs = {**taxa, **compounds}
    source_refs = {**papers, **datasets}
    for record in payload.get("evidence_items", []):
        subject_entity = _ref(entity_refs, record.get("subject_entity_ref"))
        object_entity = _ref(entity_refs, record.get("object_entity_ref"))
        source = _ref(source_refs, record.get("source_ref"))
        existing_evidence = _find_evidence_item(
            session,
            subject_entity=subject_entity,
            source=source,
            record=record,
        )
        evidence_items.append(
            existing_evidence or EvidenceItem(
                claim_type=record["claim_type"],
                subject_entity_type=record["subject_entity_type"],
                subject_entity_id=_entity_id(subject_entity),
                predicate=record["predicate"],
                object_entity_type=record.get("object_entity_type"),
                object_entity_id=_entity_id(object_entity),
                object_literal=record.get("object_literal"),
                source_type=record["source_type"],
                source_id=_source_id(source),
                evidence_tier=record["evidence_tier"],
                directness=record["directness"],
                extraction_method=record["extraction_method"],
                confidence=record["confidence"],
                supporting_span=record.get("supporting_span"),
                provenance=record.get("provenance", {}),
            )
        )

    candidate_links: list[CandidateLink] = []
    for record in payload.get("candidate_links", []):
        source_entity = _ref(entity_refs, record.get("source_entity_ref"))
        target_entity = _ref(entity_refs, record.get("target_entity_ref"))
        existing_candidate = _find_candidate_link(
            session,
            source_entity=source_entity,
            target_entity=target_entity,
            record=record,
        )
        candidate_links.append(
            existing_candidate or CandidateLink(
                source_entity_type=record["source_entity_type"],
                source_entity_id=_entity_id(source_entity),
                relation=record["relation"],
                target_entity_type=record["target_entity_type"],
                target_entity_id=_entity_id(target_entity),
                internal_evidence_score=record.get("internal_evidence_score"),
                external_evidence_score=record.get("external_evidence_score"),
                taxonomy_distance=record.get("taxonomy_distance"),
                evidence_tier=record["evidence_tier"],
                status=record["status"],
                rationale=record.get("rationale", {}),
            )
        )

    session.add_all([*evidence_items, *candidate_links])
    session.flush()

    return DemoFixtureSummary(
        papers=len(papers),
        taxa=len(taxa),
        compounds=len(compounds),
        natural_product_records=len(natural_product_records),
        datasets=len(datasets),
        omics_observations=len(observations),
        omics_associations=len(associations),
        evidence_items=len(evidence_items),
        candidate_links=len(candidate_links),
    )
