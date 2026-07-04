from pathlib import Path

from .config import get_settings

try:
    from modelscope import snapshot_download
except ImportError:  # pragma: no cover - exercised only in incomplete envs
    snapshot_download = None


def download_configured_models() -> None:
    if snapshot_download is None:
        raise RuntimeError("modelscope is required to download configured models.")

    settings = get_settings()
    for model_id in [settings.embedding_model, settings.reranker_model]:
        if Path(model_id).expanduser().exists():
            print(f"跳过本地模型路径: {model_id}")
            continue
        snapshot_download(model_id)


if __name__ == "__main__":
    download_configured_models()
