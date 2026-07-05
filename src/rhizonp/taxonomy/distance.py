from __future__ import annotations

from rhizonp.taxonomy.models import NormalizedTaxon, TaxonomyDistance


def _norm(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    return cleaned or None


def compute_taxonomy_distance(
    query_taxon: NormalizedTaxon,
    literature_taxon: NormalizedTaxon,
) -> TaxonomyDistance:
    query_strain = _norm(query_taxon.strain)
    lit_strain = _norm(literature_taxon.strain)
    query_species = _norm(query_taxon.species) or _norm(query_taxon.canonical_name)
    lit_species = _norm(literature_taxon.species) or _norm(literature_taxon.canonical_name)
    query_genus = _norm(query_taxon.genus) or (
        _norm(query_taxon.canonical_name.split()[0]) if query_taxon.canonical_name else None
    )
    lit_genus = _norm(literature_taxon.genus) or (
        _norm(literature_taxon.canonical_name.split()[0])
        if literature_taxon.canonical_name
        else None
    )
    query_family = _norm(query_taxon.family)
    lit_family = _norm(literature_taxon.family)

    if query_strain and lit_strain and query_strain == lit_strain:
        if query_species and lit_species and query_species == lit_species:
            return TaxonomyDistance.SAME_STRAIN
    if query_species and lit_species and query_species == lit_species:
        return TaxonomyDistance.SAME_SPECIES
    if query_genus and lit_genus and query_genus == lit_genus:
        return TaxonomyDistance.SAME_GENUS
    if query_family and lit_family and query_family == lit_family:
        return TaxonomyDistance.HIGHER_TAXON
    return TaxonomyDistance.UNKNOWN


def distance_to_evidence_tier(distance: TaxonomyDistance) -> str:
    mapping = {
        TaxonomyDistance.SAME_STRAIN: "A",
        TaxonomyDistance.SAME_SPECIES: "B",
        TaxonomyDistance.SAME_GENUS: "C",
        TaxonomyDistance.HIGHER_TAXON: "D",
        TaxonomyDistance.UNKNOWN: "D",
    }
    return mapping[distance]
