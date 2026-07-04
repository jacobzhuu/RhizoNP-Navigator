import uuid

from sqlalchemy import create_engine

from rhizonp.domain.models import (
    Base,
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
from rhizonp.storage.postgres import create_session_factory, session_scope
from rhizonp.storage.repositories import (
    CandidateLinkRepository,
    CompoundRepository,
    DatasetRepository,
    EvidenceRepository,
    NaturalProductRecordRepository,
    OmicsAssociationRepository,
    PaperRepository,
    Repository,
    TaxonRepository,
)


def test_repository_round_trip_with_phase_1_entities() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        paper_repo: Repository[Paper, uuid.UUID] = Repository(session, Paper)
        taxon_repo: Repository[Taxon, uuid.UUID] = Repository(session, Taxon)
        compound_repo: Repository[Compound, uuid.UUID] = Repository(session, Compound)

        paper = paper_repo.add(
            Paper(
                doi="10.0000/example",
                title="Rhizosphere Streptomyces natural products",
                year=2026,
                provenance={"source": "unit-test"},
            )
        )
        taxon = taxon_repo.add(
            Taxon(
                canonical_name="Streptomyces",
                rank="genus",
                genus="Streptomyces",
                external_ids={"ncbi_taxon": "1883"},
            )
        )
        compound = compound_repo.add(
            Compound(
                canonical_name="formicamycin",
                compound_class="polyketide",
                structure_status="confirmed",
            )
        )

        np_record = NaturalProductRecord(
            compound=compound,
            producer_taxon=taxon,
            source_database="fixture_np",
            external_record_id="NP0001",
            reference_paper=paper,
            provenance={"license": "test-only"},
        )
        dataset = Dataset(
            name="root injury demo",
            data_type="own_omics_association",
            provenance={"visibility": "fixture"},
        )
        observation = OmicsObservation(
            dataset=dataset,
            entity_type="taxon",
            raw_label="Streptomyces",
            method="16S",
            observation_metadata={"rank": "genus"},
        )
        association = OmicsAssociation(
            dataset=dataset,
            source_entity_type="taxon",
            source_entity_id=taxon.taxon_id,
            source_raw_label="Streptomyces",
            target_entity_type="metabolite",
            target_raw_label="Feature_M123",
            score=0.72,
            adjusted_p=0.003,
            method="sPLS",
            direction="positive",
            association_metadata={"treatment": "RootInjury75"},
        )
        evidence = EvidenceItem(
            claim_type="taxon_produces_compound",
            subject_entity_type="taxon",
            subject_entity_id=taxon.taxon_id,
            predicate="PRODUCES",
            object_entity_type="compound",
            object_entity_id=compound.compound_id,
            source_type="paper",
            source_id=paper.paper_id,
            evidence_tier="same_genus",
            directness="indirect",
            extraction_method="manual_fixture",
            confidence=0.4,
            provenance={"policy": "test"},
        )
        candidate = CandidateLink(
            source_entity_type="taxon",
            source_entity_id=taxon.taxon_id,
            relation="PRODUCES",
            target_entity_type="compound",
            target_entity_id=compound.compound_id,
            external_evidence_score=0.4,
            taxonomy_distance="same_genus",
            evidence_tier="Tier C",
            status="PARTIALLY_SUPPORTED",
            rationale={"limitation": "genus-level only"},
        )

        session.add_all([np_record, dataset, observation, association, evidence, candidate])

    with session_scope(session_factory) as session:
        paper_repo = Repository[Paper, uuid.UUID](session, Paper)
        taxon_repo = TaxonRepository(session)
        compound_repo = CompoundRepository(session)
        np_repo = NaturalProductRecordRepository(session)
        dataset_repo = DatasetRepository(session)
        association_repo = OmicsAssociationRepository(session)
        evidence_repo = EvidenceRepository(session)
        candidate_repo = CandidateLinkRepository(session)

        saved_paper = paper_repo.get(paper.paper_id)
        saved_taxon = taxon_repo.find_by_canonical_name("streptomyces")
        saved_compound = compound_repo.find_by_canonical_name("FORMICAMYCIN")

        assert saved_paper is not None
        assert saved_paper.title == "Rhizosphere Streptomyces natural products"
        assert saved_taxon is not None
        assert saved_taxon.normalization_status == "unresolved"
        assert saved_compound is not None
        assert saved_compound.structure_status == "confirmed"
        assert len(paper_repo.list()) == 1
        assert PaperRepository(session).find_by_doi("10.0000/example") is not None
        assert len(taxon_repo.list_by_rank("genus")) == 1
        assert np_repo.find_by_source_record(
            source_database="fixture_np",
            external_record_id="NP0001",
        ) is not None
        saved_dataset = dataset_repo.find_by_name("root injury demo")
        assert saved_dataset is not None
        assert len(association_repo.list_for_dataset(saved_dataset.dataset_id)) == 1
        assert len(
            evidence_repo.list_for_subject(
                subject_entity_type="taxon",
                subject_entity_id=saved_taxon.taxon_id,
            )
        ) == 1
        assert len(
            candidate_repo.list_for_source(
                source_entity_type="taxon",
                source_entity_id=saved_taxon.taxon_id,
            )
        ) == 1
        assert len(candidate_repo.list_by_status("PARTIALLY_SUPPORTED")) == 1
