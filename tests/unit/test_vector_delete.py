from pathlib import Path
from types import SimpleNamespace

from rhizonp import make_vector_db
from rhizonp.make_vector_db import find_document_ids_by_source


def _doc(source: Path | str) -> SimpleNamespace:
    return SimpleNamespace(metadata={"source": str(source)}, page_content="chunk")


def test_find_document_ids_single_chunk(tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    docstore = {"doc-1": _doc(source)}

    assert find_document_ids_by_source(docstore, source) == ["doc-1"]


def test_find_document_ids_multiple_chunks(tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    docstore = {
        "doc-1": _doc(source),
        "doc-2": _doc(source),
        "doc-3": _doc(tmp_path / "other.csv"),
    }

    assert find_document_ids_by_source(docstore, source) == ["doc-1", "doc-2"]


def test_find_document_ids_missing_source(tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    docstore = {"doc-1": _doc(tmp_path / "other.csv")}

    assert find_document_ids_by_source(docstore, source) == []


def test_find_document_ids_same_name_different_path(tmp_path: Path) -> None:
    source = tmp_path / "a" / "input.csv"
    same_name_other_path = tmp_path / "b" / "input.csv"
    docstore = {
        "doc-1": _doc(source),
        "doc-2": _doc(same_name_other_path),
    }

    assert find_document_ids_by_source(docstore, source) == ["doc-1"]


def test_delete_file_removes_all_matching_chunks(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "data" / "input.csv"
    source.parent.mkdir()
    source.write_text("id,text\n1,hello\n", encoding="utf-8")

    db_path = tmp_path / "faiss"
    files_path = db_path / "files"
    files_path.mkdir(parents=True)
    (files_path / "input.csv").write_text("id,text\n1,hello\n", encoding="utf-8")

    class FakeVectorDB:
        def __init__(self) -> None:
            self.docstore = SimpleNamespace(
                _dict={
                    "doc-1": _doc(source),
                    "doc-2": _doc(source),
                    "doc-3": _doc(tmp_path / "other.csv"),
                }
            )
            self.deleted: list[str] = []
            self.saved_path: str | None = None

        def delete(self, ids: list[str]) -> None:
            self.deleted.extend(ids)
            for doc_id in ids:
                self.docstore._dict.pop(doc_id)

        def save_local(self, path: str) -> None:
            self.saved_path = path

    fake_vector_db = FakeVectorDB()
    fake_faiss = SimpleNamespace(
        load_local=lambda **_kwargs: fake_vector_db,
    )

    monkeypatch.setattr(make_vector_db, "_FAISS", fake_faiss)
    monkeypatch.setattr(make_vector_db, "_CSVLoader", object())
    monkeypatch.setattr(make_vector_db, "_RecursiveCharacterTextSplitter", object())
    monkeypatch.setattr(make_vector_db, "get_embeddings", lambda: object())

    make_vector_db.delete_file_from_knowledge_vector_db(db_path, source)

    assert fake_vector_db.deleted == ["doc-1", "doc-2"]
    assert "doc-1" not in fake_vector_db.docstore._dict
    assert "doc-2" not in fake_vector_db.docstore._dict
    assert "doc-3" in fake_vector_db.docstore._dict
    assert fake_vector_db.saved_path == str(db_path.resolve())
    assert not (files_path / "input.csv").exists()
