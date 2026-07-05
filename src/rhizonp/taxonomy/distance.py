from __future__ import annotations

from rhizonp.taxonomy.models import NormalizedTaxon, TaxonomyDistance

_SPECIES_LEVEL_RANKS = frozenset({"species", "strain", "isolate"})


def _norm(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    return cleaned or None


def _resolved_species(taxon: NormalizedTaxon) -> str | None:
    """Return a species label only when the taxon is resolved at species rank or below."""
    explicit = _norm(taxon.species)
    if explicit:
        return explicit
    rank = (taxon.rank or "").lower()
    if rank in _SPECIES_LEVEL_RANKS:
        return _norm(taxon.canonical_name)
    return None


def _resolved_genus(taxon: NormalizedTaxon) -> str | None:
    explicit = _norm(taxon.genus)
    if explicit:
        return explicit
    if taxon.canonical_name:
        return _norm(taxon.canonical_name.split()[0])
    return None


def compute_taxonomy_distance(
    query_taxon: NormalizedTaxon,
    literature_taxon: NormalizedTaxon,
) -> TaxonomyDistance:
    query_strain = _norm(query_taxon.strain)
    lit_strain = _norm(literature_taxon.strain)
    query_species = _resolved_species(query_taxon)
    lit_species = _resolved_species(literature_taxon)
    query_genus = _resolved_genus(query_taxon)
    lit_genus = _resolved_genus(literature_taxon)
    query_family = _norm(query_taxon.family)
    lit_family = _norm(literature_taxon.family)
    query_taxid = query_taxon.external_ids.get("ncbi_taxid")
    lit_taxid = literature_taxon.external_ids.get("ncbi_taxid")

    if query_taxid and lit_taxid and str(query_taxid) == str(lit_taxid):
        rank = (query_taxon.rank or literature_taxon.rank or "").lower()
        if rank in {"strain", "isolate"}:
            if query_strain and lit_strain and query_strain == lit_strain:
                if query_species and lit_species and query_species == lit_species:
                    return TaxonomyDistance.SAME_STRAIN
        if rank in _SPECIES_LEVEL_RANKS or rank == "species":
            return TaxonomyDistance.SAME_SPECIES
        if rank == "genus":
            return TaxonomyDistance.SAME_GENUS

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
