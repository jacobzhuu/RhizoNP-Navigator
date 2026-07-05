#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".env",
    ".example",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

IGNORED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "data",
    "env",
    "node_modules",
    "venv",
}

IGNORED_FILES = {
    ".DS_Store",
    ".env",
}

PLACEHOLDER_VALUES = {
    "",
    "changeme",
    "example",
    "none",
    "placeholder",
    "postgres",
    "rhizonp",
    "rhizonp_dev",
    "test",
}

SECRET_PATTERNS = [
    ("api-key-looking-token", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
]

SENSITIVE_FIELD_PATTERN = re.compile(r"(?i)\b[\w-]*(api[_-]?key|token|password|passwd|pwd)\b")
PASSWORD_FIELD_PATTERN = re.compile(r"(?i)\b[\w-]*(password|passwd|pwd)\b")
KEY_NAME_PATTERN = re.compile(r"^[A-Za-z_][\w-]*$")


@dataclass(frozen=True)
class SecretFinding:
    path: Path
    line_number: int
    kind: str
    excerpt: str


def _is_ignored(path: Path) -> bool:
    if path.name in IGNORED_FILES:
        return True
    return any(part in IGNORED_DIRS for part in path.parts)


def _is_text_candidate(path: Path) -> bool:
    if path.name in {"Dockerfile", "Makefile"}:
        return True
    return path.suffix in TEXT_SUFFIXES or path.name.endswith(".example")


def iter_candidate_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and not _is_ignored(path.relative_to(root)) and _is_text_candidate(path)
    )


def _is_placeholder(value: str) -> bool:
    normalized = value.strip().strip(",").strip("'\"").strip().lower()
    if normalized.startswith("${"):
        return True
    if normalized.startswith(("settings.", "os.environ", "getenv(")):
        return True
    if any(operator in normalized for operator in ("+", "(", ")")):
        return True
    return normalized in PLACEHOLDER_VALUES


def _assigned_secret_kind(line: str) -> tuple[str, str] | None:
    content = line.split("#", 1)[0].strip()
    if "=" in content:
        key = content.split("=", 1)[0].split(":", 1)[0].strip()
        value = content.rsplit("=", 1)[1]
    elif ":" in content:
        key = content.split(":", 1)[0].strip()
        value = content.split(":", 1)[1]
    else:
        return None

    if not KEY_NAME_PATTERN.match(key):
        return None
    if not SENSITIVE_FIELD_PATTERN.search(key):
        return None

    if _is_placeholder(value):
        return None

    kind = "assigned-password" if PASSWORD_FIELD_PATTERN.search(key) else "assigned-api-key"
    return kind, value.strip()


def find_secret_findings(root: Path = PROJECT_ROOT) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for path in iter_candidate_files(root):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue

        for line_number, line in enumerate(lines, start=1):
            for kind, pattern in SECRET_PATTERNS:
                for _match in pattern.finditer(line):
                    findings.append(
                        SecretFinding(
                            path=path.relative_to(root),
                            line_number=line_number,
                            kind=kind,
                            excerpt=line.strip(),
                        )
                    )
            assigned_secret = _assigned_secret_kind(line)
            if assigned_secret is not None:
                kind, _value = assigned_secret
                findings.append(
                    SecretFinding(
                        path=path.relative_to(root),
                        line_number=line_number,
                        kind=kind,
                        excerpt=line.strip(),
                    )
                )
    return findings


def main() -> int:
    findings = find_secret_findings(PROJECT_ROOT)
    if not findings:
        print("No committed secret-looking values found.")
        return 0

    print("Secret-looking values found:")
    for finding in findings:
        print(f"{finding.path}:{finding.line_number}: {finding.kind}: {finding.excerpt}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
