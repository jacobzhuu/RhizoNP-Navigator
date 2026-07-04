import Config
import DownloadModel
import Embedding
import GetAnswer
import MakeVectorDB
from rhizonp import config, download_model, embedding, get_answer, make_vector_db


def test_legacy_wrappers_re_export_package_api() -> None:
    assert Config.get_settings is config.get_settings
    assert Embedding.get_embeddings is embedding.get_embeddings
    assert GetAnswer.BGEReranker is get_answer.BGEReranker
    assert MakeVectorDB.find_document_ids_by_source is make_vector_db.find_document_ids_by_source
    assert DownloadModel.download_configured_models is download_model.download_configured_models
