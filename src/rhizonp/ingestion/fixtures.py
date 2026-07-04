from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
        papers[key] = Paper(
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
        taxa[key] = Taxon(
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
        compounds[key] = Compound(
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
        datasets[key] = Dataset(
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
        natural_product_records.append(
            NaturalProductRecord(
                compound=_ref(compounds, record.get("compound_ref")),
                producer_taxon=_ref(taxa, record.get("producer_taxon_ref")),
                source_database=record["source_database"],
                external_record_id=record["external_record_id"],
                bioactivity_summary=record.get("bioactivity_summary"),
                reference_paper=_ref(papers, record.get("reference_paper_ref")),
                provenance=record.get("provenance", {}),
            )
        )

    observations: list[OmicsObservation] = []
    for record in payload.get("omics_observations", []):
        entity = _ref({**taxa, **compounds}, record.get("entity_ref"))
        observations.append(
            OmicsObservation(
                dataset=_ref(datasets, record.get("dataset_ref")),
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

    associations: list[OmicsAssociation] = []
    for record in payload.get("omics_associations", []):
        source_entity = _ref({**taxa, **compounds}, record.get("source_entity_ref"))
        target_entity = _ref({**taxa, **compounds}, record.get("target_entity_ref"))
        associations.append(
            OmicsAssociation(
                dataset=_ref(datasets, record.get("dataset_ref")),
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

    evidence_items: list[EvidenceItem] = []
    entity_refs = {**taxa, **compounds}
    source_refs = {**papers, **datasets}
    for record in payload.get("evidence_items", []):
        subject_entity = _ref(entity_refs, record.get("subject_entity_ref"))
        object_entity = _ref(entity_refs, record.get("object_entity_ref"))
        source = _ref(source_refs, record.get("source_ref"))
        evidence_items.append(
            EvidenceItem(
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
        candidate_links.append(
            CandidateLink(
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

    session.add_all(
        [
            *natural_product_records,
            *observations,
            *associations,
            *evidence_items,
            *candidate_links,
        ]
    )
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
