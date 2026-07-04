from pathlib import Path

from scripts.check_no_secrets import find_secret_findings


def test_secret_scan_allows_placeholders(tmp_path: Path) -> None:
    config = tmp_path / ".env.example"
    config.write_text(
        "\n".join(
            [
                "DEEPSEEK_" + "API_KEY=",
                "POSTGRES_" + "PASSWORD=${POSTGRES_PASSWORD:-rhizonp}",
                "TOKEN=placeholder",
            ]
        ),
        encoding="utf-8",
    )

    assert find_secret_findings(tmp_path) == []


def test_secret_scan_flags_api_key_looking_values(tmp_path: Path) -> None:
    config = tmp_path / "Config.py"
    key_name = "DEEPSEEK_" + "API_KEY"
    fake_key = "s" + "k-" + "1234567890abcdefghijklmnop"
    config.write_text(f"{key_name}='{fake_key}'\n", encoding="utf-8")

    findings = find_secret_findings(tmp_path)

    assert len(findings) == 2
    assert {finding.kind for finding in findings} == {
        "api-key-looking-token",
        "assigned-api-key",
    }


def test_secret_scan_flags_non_placeholder_password(tmp_path: Path) -> None:
    config = tmp_path / "settings.toml"
    password_field = "pass" + "word"
    fake_password = "013" + "777"
    config.write_text(f"{password_field} = '{fake_password}'\n", encoding="utf-8")

    findings = find_secret_findings(tmp_path)

    assert len(findings) == 1
    assert findings[0].kind == "assigned-password"
