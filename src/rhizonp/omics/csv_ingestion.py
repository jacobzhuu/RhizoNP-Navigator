from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rhizonp.config import PROJECT_ROOT

DEFAULT_OWN_DATA_DIR = PROJECT_ROOT / "data" / "fixtures" / "own_data_demo"


@dataclass(frozen=True)
class TaxonObservation:
    observation_id: str
    raw_label: str
    rank: str | None = None
    method: str | None = None
    treatment: str | None = None
    timepoint: str | None = None
    layer: str | None = None
    effect_size: float | None = None
    adjusted_p: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MetaboliteObservation:
    observation_id: str
    raw_label: str
    feature_id: str | None = None
    mz: float | None = None
    rt: float | None = None
    chemical_identification_tier: str | None = None
    method: str | None = None
    treatment: str | None = None
    timepoint: str | None = None
    layer: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AssociationRecord:
    association_id: str
    source_observation_id: str
    target_observation_id: str
    source_raw_label: str
    target_raw_label: str
    score: float
    adjusted_p: float | None = None
    method: str | None = None
    direction: str | None = None
    treatment: str | None = None
    timepoint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OwnDataBundle:
    taxa: list[TaxonObservation]
    metabolites: list[MetaboliteObservation]
    associations: list[AssociationRecord]
    provenance: dict[str, Any] = field(default_factory=dict)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _optional_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def load_taxa_csv(path: str | Path) -> list[TaxonObservation]:
    records: list[TaxonObservation] = []
    for row in _read_csv(Path(path)):
        records.append(
            TaxonObservation(
                observation_id=row["observation_id"],
                raw_label=row["raw_label"],
                rank=row.get("rank") or None,
                method=row.get("method") or None,
                treatment=row.get("treatment") or None,
                timepoint=row.get("timepoint") or None,
                layer=row.get("layer") or None,
                effect_size=_optional_float(row.get("effect_size")),
                adjusted_p=_optional_float(row.get("adjusted_p")),
            )
        )
    return records


def load_metabolites_csv(path: str | Path) -> list[MetaboliteObservation]:
    records: list[MetaboliteObservation] = []
    for row in _read_csv(Path(path)):
        records.append(
            MetaboliteObservation(
                observation_id=row["observation_id"],
                raw_label=row["raw_label"],
                feature_id=row.get("feature_id") or None,
                mz=_optional_float(row.get("mz")),
                rt=_optional_float(row.get("rt")),
                chemical_identification_tier=row.get("chemical_identification_tier") or None,
                method=row.get("method") or None,
                treatment=row.get("treatment") or None,
                timepoint=row.get("timepoint") or None,
                layer=row.get("layer") or None,
            )
        )
    return records


def load_associations_csv(path: str | Path) -> list[AssociationRecord]:
    records: list[AssociationRecord] = []
    for row in _read_csv(Path(path)):
        records.append(
            AssociationRecord(
                association_id=row["association_id"],
                source_observation_id=row["source_observation_id"],
                target_observation_id=row["target_observation_id"],
                source_raw_label=row["source_raw_label"],
                target_raw_label=row["target_raw_label"],
                score=float(row["score"]),
                adjusted_p=_optional_float(row.get("adjusted_p")),
                method=row.get("method") or None,
                direction=row.get("direction") or None,
                treatment=row.get("treatment") or None,
                timepoint=row.get("timepoint") or None,
                metadata={"correlation_not_causation": True},
            )
        )
    return records


def load_own_data_bundle(data_dir: str | Path = DEFAULT_OWN_DATA_DIR) -> OwnDataBundle:
    directory = Path(data_dir)
    return OwnDataBundle(
        taxa=load_taxa_csv(directory / "taxa.csv"),
        metabolites=load_metabolites_csv(directory / "metabolites.csv"),
        associations=load_associations_csv(directory / "associations.csv"),
        provenance={
            "fixture": True,
            "data_dir": str(directory),
            "not_real_experiment": True,
        },
    )
