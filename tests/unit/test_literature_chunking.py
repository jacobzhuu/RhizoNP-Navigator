from rhizonp.literature.adapters import RawLiteratureRecord, SyntheticLiteratureAdapter
from rhizonp.literature.chunking import structured_chunk_record


def test_structured_chunking_preserves_section_metadata_and_source_hash() -> None:
    raw_record = RawLiteratureRecord(
        source_id="fixture-1",
        title="Synthetic Streptomyces title",
        abstract="Synthetic abstract.",
        doi="10.0000/example",
        metadata={"taxa": ["Streptomyces"], "host": ["Synthetic plant"]},
        sections={
            "results": "First result paragraph.\n\nSecond result paragraph about Streptomyces.",
            "discussion": "Discussion paragraph.",
        },
    )
    record = SyntheticLiteratureAdapter([raw_record]).normalize(raw_record)

    chunks = structured_chunk_record(record, max_chars=80)
    repeated_chunks = structured_chunk_record(record, max_chars=80)

    assert [chunk.section for chunk in chunks][:2] == ["title", "abstract"]
    assert any(chunk.section == "results" for chunk in chunks)
    assert chunks == repeated_chunks
    assert all(chunk.source_hash for chunk in chunks)
    result_chunk = next(chunk for chunk in chunks if "Streptomyces" in chunk.text)
    assert result_chunk.metadata["doi"] == "10.0000/example"
    assert result_chunk.metadata["source_type"] == "paper"
    assert result_chunk.metadata["taxa"] == ["Streptomyces"]
