from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_head_includes_phase_2_literature_provenance() -> None:
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)

    assert script.get_current_head() == "0003_literature_corpus_state"
