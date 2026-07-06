import re

from rhizonp.config import PROJECT_ROOT, get_settings


def test_default_settings_do_not_contain_runtime_secrets() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    serialized = "\n".join(
        [
            settings.deepseek_api_key,
            settings.qwen_api_key,
            settings.postgres_password,
        ]
    )

    leaked_key_prefix = "s" + "k-"
    leaked_password = "013" + "777"

    assert not re.search(leaked_key_prefix + r"[A-Za-z0-9]+", serialized)
    assert leaked_password not in serialized


def test_default_model_settings_are_cross_platform_identifiers() -> None:
    get_settings.cache_clear()
    settings = get_settings()

    assert ":\\" not in settings.embedding_model
    assert ":\\" not in settings.reranker_model
    assert settings.embedding_model == "aspire/acge_text_embedding"
    assert settings.reranker_model == "BAAI/bge-reranker-v2-m3"


def test_project_root_points_to_repository_root() -> None:
    assert (PROJECT_ROOT / "pyproject.toml").exists()
    assert (PROJECT_ROOT / "src" / "rhizonp").exists()
