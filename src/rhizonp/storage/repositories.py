from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rhizonp.domain.models import (
    CandidateLink,
    Compound,
    Dataset,
    EvidenceItem,
    NaturalProductRecord,
    OmicsAssociation,
    Paper,
    PaperChunk,
    RetrievalResult,
    RetrievalRun,
    Taxon,
)

ModelT = TypeVar("ModelT")
IdT = TypeVar("IdT")


class Repository(Generic[ModelT, IdT]):
    def __init__(self, session: Session, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        self.session.flush()
        return instance

    def get(self, identity: IdT) -> ModelT | None:
        return self.session.get(self.model, identity)

    def list(self, *, limit: int = 100) -> list[ModelT]:
        return list(self.session.scalars(select(self.model).limit(limit)))


class PaperRepository(Repository[Paper, object]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Paper)

    def find_by_doi(self, doi: str) -> Paper | None:
        return self.session.scalar(select(Paper).where(Paper.doi == doi))

    def find_by_source_url(self, source_url: str) -> Paper | None:
        return self.session.scalar(select(Paper).where(Paper.source_url == source_url))

    def find_by_pmid(self, pmid: str) -> Paper | None:
        return self.session.scalar(select(Paper).where(Paper.pmid == pmid))


class TaxonRepository(Repository[Taxon, object]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Taxon)

    def find_by_canonical_name(self, name: str) -> Taxon | None:
        return self.session.scalar(
            select(Taxon).where(func.lower(Taxon.canonical_name) == name.lower())
        )

    def list_by_rank(self, rank: str) -> list[Taxon]:
        return list(self.session.scalars(select(Taxon).where(Taxon.rank == rank)))


class CompoundRepository(Repository[Compound, object]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Compound)

    def find_by_canonical_name(self, name: str) -> Compound | None:
        return self.session.scalar(
            select(Compound).where(func.lower(Compound.canonical_name) == name.lower())
        )

    def find_by_inchikey(self, inchikey: str) -> Compound | None:
        return self.session.scalar(select(Compound).where(Compound.inchikey == inchikey))


class NaturalProductRecordRepository(Repository[NaturalProductRecord, object]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, NaturalProductRecord)

    def find_by_source_record(
        self,
        *,
        source_database: str,
        external_record_id: str,
    ) -> NaturalProductRecord | None:
        return self.session.scalar(
            select(NaturalProductRecord).where(
                NaturalProductRecord.source_database == source_database,
                NaturalProductRecord.external_record_id == external_record_id,
            )
        )


class PaperChunkRepository(Repository[PaperChunk, object]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, PaperChunk)

    def list_for_paper(self, paper_id: object) -> list[PaperChunk]:
        return list(
            self.session.scalars(
                select(PaperChunk)
                .where(PaperChunk.paper_id == paper_id)
                .order_by(PaperChunk.section, PaperChunk.paragraph_index)
            )
        )

    def find_by_source_hash(self, source_hash: str) -> PaperChunk | None:
        return self.session.scalar(select(PaperChunk).where(PaperChunk.source_hash == source_hash))


class DatasetRepository(Repository[Dataset, object]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Dataset)

    def find_by_name(self, name: str) -> Dataset | None:
        return self.session.scalar(select(Dataset).where(Dataset.name == name))


class OmicsAssociationRepository(Repository[OmicsAssociation, object]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, OmicsAssociation)

    def list_for_dataset(self, dataset_id: object) -> list[OmicsAssociation]:
        return list(
            self.session.scalars(
                select(OmicsAssociation).where(OmicsAssociation.dataset_id == dataset_id)
            )
        )


class EvidenceRepository(Repository[EvidenceItem, object]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, EvidenceItem)

    def list_for_subject(
        self,
        *,
        subject_entity_type: str,
        subject_entity_id: object,
    ) -> list[EvidenceItem]:
        return list(
            self.session.scalars(
                select(EvidenceItem).where(
                    EvidenceItem.subject_entity_type == subject_entity_type,
                    EvidenceItem.subject_entity_id == subject_entity_id,
                )
            )
        )


class CandidateLinkRepository(Repository[CandidateLink, object]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, CandidateLink)

    def list_for_source(
        self,
        *,
        source_entity_type: str,
        source_entity_id: object,
    ) -> list[CandidateLink]:
        return list(
            self.session.scalars(
                select(CandidateLink).where(
                    CandidateLink.source_entity_type == source_entity_type,
                    CandidateLink.source_entity_id == source_entity_id,
                )
            )
        )

    def list_by_status(self, status: str) -> list[CandidateLink]:
        return list(self.session.scalars(select(CandidateLink).where(CandidateLink.status == status)))


class RetrievalRunRepository(Repository[RetrievalRun, object]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, RetrievalRun)


class RetrievalResultRepository(Repository[RetrievalResult, object]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, RetrievalResult)

    def list_for_run(self, run_id: object) -> list[RetrievalResult]:
        return list(
            self.session.scalars(
                select(RetrievalResult)
                .where(RetrievalResult.run_id == run_id)
                .order_by(RetrievalResult.rank)
            )
        )
