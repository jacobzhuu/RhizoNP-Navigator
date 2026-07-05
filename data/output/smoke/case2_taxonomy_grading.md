# Demo Case 2: Taxonomy-aware Evidence Grading

Query taxon: Streptomyces (genus-level 16S observation)
Literature taxon: Streptomyces hygroscopicus OS-2 (strain-level record)

- Taxonomy distance: SAME_GENUS
- Evidence tier: C
- Max supported claim: genus_level_candidate

## Warnings

- Genus-level or unresolved observation cannot support strain-level production claims.
- 16S genus-level observation must not be promoted to strain-level production based on literature from a different strain.
- Same-genus evidence is candidate-level only; it does not prove this sample produces the compound.