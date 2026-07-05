#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def main() -> None:
    from rhizonp.taxonomy.grading import grade_evidence
    from rhizonp.taxonomy.models import TaxonomyDistance
    from rhizonp.taxonomy.ncbi_resolver import (
        DEFAULT_NCBI_TAXONOMY_CACHE_PATH,
        load_ncbi_taxonomy_cache,
    )
    from rhizonp.taxonomy.resolvers import TaxonomyResolverMode

    cache_path = DEFAULT_NCBI_TAXONOMY_CACHE_PATH
    if not cache_path.is_file():
        raise SystemExit(f"Missing NCBI taxonomy cache: {cache_path}")

    cache = load_ncbi_taxonomy_cache(cache_path)
    report = {
        "cache_id": "ncbi_bounded_v1",
        "cache_path": str(cache_path),
        "entry_count": len(cache),
        "backend": "offline_bounded_cache",
        "checks": [],
    }

    streptomyces = grade_evidence(
        "Streptomyces",
        "Streptomyces hygroscopicus",
        resolver_mode=TaxonomyResolverMode.NCBI_CACHED.value,
    )
    check = {
        "name": "genus_to_species_ncbi_cached",
        "query_taxid": streptomyces.query_taxon.external_ids.get("ncbi_taxid"),
        "literature_taxid": streptomyces.literature_taxon.external_ids.get("ncbi_taxid"),
        "taxonomy_distance": streptomyces.taxonomy_distance.value,
        "normalization_status_query": streptomyces.query_taxon.normalization_status,
        "normalization_status_literature": streptomyces.literature_taxon.normalization_status,
    }
    report["checks"].append(check)

    passed = (
        check["query_taxid"] == "1883"
        and check["literature_taxid"] == "1912"
        and check["taxonomy_distance"] == TaxonomyDistance.SAME_GENUS.value
        and check["normalization_status_query"] == "resolved_ncbi"
    )
    report["passed"] = passed

    output_dir = PROJECT_ROOT / "data" / "eval" / "reports" / "latest"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "ncbi_taxonomy_resolver_validation.json"
    md_path = output_dir / "ncbi_taxonomy_resolver_validation.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# NCBI Taxonomy Resolver Validation",
                "",
                f"Cache entries: {len(cache)}",
                f"Passed: {passed}",
                "",
                "## genus → species check",
                "",
                f"- query taxid: {check['query_taxid']}",
                f"- literature taxid: {check['literature_taxid']}",
                f"- distance: {check['taxonomy_distance']}",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
