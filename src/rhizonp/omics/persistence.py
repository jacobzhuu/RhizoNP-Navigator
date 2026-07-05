from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from rhizonp.domain.models import Dataset, OmicsAssociation, OmicsObservation
from rhizonp.omics.csv_ingestion import AssociationRecord, OwnDataBundle
from rhizonp.storage.repositories import DatasetRepository

RHIZONP_OMICS_NAMESPACE = uuid.UUID("6f2f4a58-9b1e-4f3a-9c2d-010000000001")


@dataclass(frozen=True)
class OwnDataPersistenceResult:
    dataset_id: uuid.UUID
    dataset_name: str
    observation_count: int
    association_count: int
    persisted: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": str(self.dataset_id),
            "dataset_name": self.dataset_name,
            "observation_count": self.observation_count,
            "association_count": self.association_count,
            "persisted": self.persisted,
        }


def _stable_uuid(kind: str, label: str) -> uuid.UUID:
    return uuid.uuid5(RHIZONP_OMICS_NAMESPACE, f"{kind}:{label}")


def _dataset_name_for_bundle(bundle: OwnDataBundle, data_dir: str | Path) -> str:
    explicit = bundle.provenance.get("dataset_name")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    return Path(data_dir).name


def persist_own_data_bundle(
    session: Session,
    bundle: OwnDataBundle,
    *,
    data_dir: str | Path,
    replace_existing: bool = True,
) -> OwnDataPersistenceResult:
    """Persist CSV bundle rows into datasets / omics_observations / omics_associations."""

    dataset_name = _dataset_name_for_bundle(bundle, data_dir)
    dataset_repo = DatasetRepository(session)
    dataset = dataset_repo.find_by_name(dataset_name)
    if dataset is None:
        dataset = Dataset(
            dataset_id=_stable_uuid("dataset", dataset_name),
            name=dataset_name,
            description="Own-data CSV import via rhizonp.omics.persistence",
            owner=None,
            data_type="own_omics_csv",
            provenance={
                **dict(bundle.provenance),
                "data_dir": str(data_dir),
                "import_module": "rhizonp.omics.persistence",
            },
        )
        session.add(dataset)
        session.flush()
    elif replace_existing:
        for association in list(dataset.associations):
            session.delete(association)
        for observation in list(dataset.observations):
            session.delete(observation)
        session.flush()

    observation_ids: dict[str, uuid.UUID] = {}

    for taxon in bundle.taxa:
        observation_id = _stable_uuid("observation", taxon.observation_id)
        observation_ids[taxon.observation_id] = observation_id
        session.merge(
            OmicsObservation(
                observation_id=observation_id,
                dataset_id=dataset.dataset_id,
                entity_type="taxon",
                entity_id=None,
                raw_label=taxon.raw_label,
                treatment=taxon.treatment,
                timepoint=taxon.timepoint,
                layer=taxon.layer,
                effect_size=taxon.effect_size,
                adjusted_p=taxon.adjusted_p,
                method=taxon.method or "unknown",
                observation_metadata={
                    **dict(taxon.metadata),
                    "rank": taxon.rank,
                    "source_observation_id": taxon.observation_id,
                    "correlation_not_causation": True,
                },
            )
        )

    for metabolite in bundle.metabolites:
        observation_id = _stable_uuid("observation", metabolite.observation_id)
        observation_ids[metabolite.observation_id] = observation_id
        session.merge(
            OmicsObservation(
                observation_id=observation_id,
                dataset_id=dataset.dataset_id,
                entity_type="metabolite",
                entity_id=None,
                raw_label=metabolite.raw_label,
                treatment=metabolite.treatment,
                timepoint=metabolite.timepoint,
                layer=metabolite.layer,
                effect_size=None,
                adjusted_p=None,
                method=metabolite.method or "unknown",
                observation_metadata={
                    **dict(metabolite.metadata),
                    "feature_id": metabolite.feature_id,
                    "mz": metabolite.mz,
                    "rt": metabolite.rt,
                    "chemical_identification_tier": metabolite.chemical_identification_tier,
                    "source_observation_id": metabolite.observation_id,
                    "unknown_feature_not_confirmed_compound": bool(
                        metabolite.chemical_identification_tier
                        and metabolite.chemical_identification_tier.startswith("C4")
                    ),
                },
            )
        )

    association_count = 0
    for assoc_record in bundle.associations:
        association_count += 1
        session.merge(
            _association_model(
                assoc_record,
                dataset_id=dataset.dataset_id,
                observation_ids=observation_ids,
            )
        )

    session.flush()
    return OwnDataPersistenceResult(
        dataset_id=dataset.dataset_id,
        dataset_name=dataset_name,
        observation_count=len(observation_ids),
        association_count=association_count,
        persisted=True,
    )


def _association_model(
    association: AssociationRecord,
    *,
    dataset_id: uuid.UUID,
    observation_ids: dict[str, uuid.UUID],
) -> OmicsAssociation:
    return OmicsAssociation(
        association_id=_stable_uuid("association", association.association_id),
        dataset_id=dataset_id,
        source_entity_type="taxon",
        source_entity_id=observation_ids.get(association.source_observation_id),
        source_raw_label=association.source_raw_label,
        target_entity_type="metabolite",
        target_entity_id=observation_ids.get(association.target_observation_id),
        target_raw_label=association.target_raw_label,
        score=association.score,
        adjusted_p=association.adjusted_p,
        method=association.method or "unknown",
        direction=association.direction,
        treatment=association.treatment,
        timepoint=association.timepoint,
        association_metadata={
            **dict(association.metadata),
            "source_association_id": association.association_id,
            "correlation_not_causation": True,
        },
    )
