import re
import shutil
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Any, cast

from .config import PROJECT_ROOT
from .embedding import get_embeddings

_RecursiveCharacterTextSplitter: Any = None
_CSVLoader: Any = None
_FAISS: Any = None
try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter as _ImportedTextSplitter
    from langchain_community.document_loaders import CSVLoader as _ImportedCSVLoader
    from langchain_community.vectorstores import FAISS as _ImportedFAISS

    _RecursiveCharacterTextSplitter = _ImportedTextSplitter
    _CSVLoader = _ImportedCSVLoader
    _FAISS = _ImportedFAISS
except ImportError:  # pragma: no cover - exercised only in incomplete envs
    pass


DATA_DIR = PROJECT_ROOT / "data"


def _looks_like_windows_path(path_value: str) -> bool:
    return "\\" in path_value or re.match(r"^[A-Za-z]:", path_value) is not None


def canonical_source(source: str | Path) -> str:
    """Return a stable comparable source path across platforms."""

    source_value = str(source)
    if _looks_like_windows_path(source_value):
        return str(PureWindowsPath(source_value)).replace("\\", "/").casefold()
    return Path(source_value).expanduser().resolve().as_posix().casefold()


def resolve_data_file_path(filepath: str | Path) -> Path:
    candidate = Path(filepath).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    if candidate.exists():
        return candidate.resolve()
    return (DATA_DIR / candidate).resolve()


def find_document_ids_by_source(
    docstore_dict: dict[str, Any],
    source_path: str | Path,
) -> list[str]:
    expected_source = canonical_source(source_path)
    matching_ids: list[str] = []
    for doc_id, document in docstore_dict.items():
        source = getattr(document, "metadata", {}).get("source")
        if source is None:
            continue
        if canonical_source(source) == expected_source:
            matching_ids.append(doc_id)
    return matching_ids


def _require_vector_dependencies() -> None:
    missing = [
        name
        for name, dependency in {
            "langchain": _RecursiveCharacterTextSplitter,
            "langchain-community": _CSVLoader,
            "FAISS": _FAISS,
        }.items()
        if dependency is None
    ]
    if missing:
        raise RuntimeError(
            "Missing vector database dependencies: "
            + ", ".join(missing)
            + ". Install project dependencies before using FAISS workflows."
        )


def load_file(filepath: str | Path) -> list[Any]:
    _require_vector_dependencies()
    abs_filepath = resolve_data_file_path(filepath)

    loader = _CSVLoader(file_path=str(abs_filepath), encoding="gbk")
    textsplitter = _RecursiveCharacterTextSplitter(
        chunk_size=1024,
        chunk_overlap=100,
        length_function=len,
        is_separator_regex=False,
    )
    return loader.load_and_split(text_splitter=textsplitter)


def init_knowledge_vector_db(
    init_file_path: str | Path,
    save_path: str | Path | None = None,
    overwrite: bool = False,
) -> Any | None:
    _require_vector_dependencies()
    source_file = resolve_data_file_path(init_file_path)
    if save_path is None:
        current_time = datetime.now().strftime("%Y%m%d%H%M%S")
        target_path = PROJECT_ROOT / "data" / f"faiss_{current_time}"
    else:
        target_path = Path(save_path).expanduser().resolve()

    try:
        if target_path.exists():
            if overwrite:
                shutil.rmtree(target_path)
                print(f"覆盖已存在的路径: {target_path}")
            else:
                raise FileExistsError(f"保存路径 {target_path} 已经存在")

        files_path = target_path / "files"
        files_path.mkdir(parents=True)
        shutil.copy(source_file, files_path / source_file.name)
    except Exception as exc:
        print(f"初始化时发生错误: {exc}")
        return None

    try:
        docs = load_file(source_file)
        vector_db = _FAISS.from_documents(docs, get_embeddings())
        vector_db.save_local(str(target_path))
        return vector_db
    except Exception as exc:
        print(f"创建 FAISS 数据库失败: {exc}")
        return None


def add_to_knowledge_vector_db(vector_db_path: str | Path, file_path: str | Path) -> None:
    _require_vector_dependencies()
    db_path = Path(vector_db_path).expanduser().resolve()
    source_file = resolve_data_file_path(file_path)

    try:
        files_folder = db_path / "files"
        target_file_path = files_folder / source_file.name
        if target_file_path.exists():
            raise FileExistsError(f"文件 {source_file} 已经存在于 {files_folder} 中")

        docs = load_file(source_file)
        vector_db = _FAISS.load_local(
            folder_path=str(db_path),
            embeddings=get_embeddings(),
            allow_dangerous_deserialization=True,
        )
        vector_db.add_documents(docs)
        vector_db.save_local(str(db_path))
        shutil.copy(source_file, target_file_path)

    except FileExistsError as exc:
        print(exc)
    except Exception as exc:
        print(f"处理文件 {source_file} 时发生错误: {exc}")


def delete_file_from_knowledge_vector_db(
    vector_db_path: str | Path,
    file_path: str | Path,
) -> None:
    _require_vector_dependencies()
    db_path = Path(vector_db_path).expanduser().resolve()
    source_file = resolve_data_file_path(file_path)
    file_name = source_file.name

    try:
        files_folder = db_path / "files"
        target_file_path = files_folder / file_name
        if not target_file_path.exists():
            raise FileNotFoundError(f"文件 {file_name} 未存在于 {files_folder} 中")

        vector_db = _FAISS.load_local(
            folder_path=str(db_path),
            embeddings=get_embeddings(),
            allow_dangerous_deserialization=True,
        )
        docstore_dict = cast(Any, vector_db.docstore)._dict
        matching_ids = find_document_ids_by_source(docstore_dict, source_file)

        if not matching_ids:
            raise ValueError(f"文件 {source_file} 不存在于 vector_db 中")

        vector_db.delete(matching_ids)
        vector_db.save_local(str(db_path))
        target_file_path.unlink()
        print(f"成功删除 {file_name} 的 {len(matching_ids)} 个文档 chunk")

    except (FileNotFoundError, ValueError) as exc:
        print(exc)
    except Exception as exc:
        print(f"处理文件 {source_file} 时发生错误: {exc}")


if __name__ == "__main__":
    init_file_path = DATA_DIR / "input.csv"
    save_path = DATA_DIR / "faiss_all_acge"

    vector_db = init_knowledge_vector_db(
        init_file_path=init_file_path,
        save_path=save_path,
        overwrite=True,
    )
    if vector_db:
        print("成功初始化知识向量数据库")
    else:
        print("初始化失败")
