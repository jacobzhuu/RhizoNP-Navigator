from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_has_phase_1_initial_revision() -> None:
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)

    assert script.get_current_head() == "0001_domain_schema"
