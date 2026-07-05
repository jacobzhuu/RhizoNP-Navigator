#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def main() -> None:
    from rhizonp.writer.llm_writer import check_llm_configuration

    report = check_llm_configuration()
    print("DeepSeek / LLM configuration self-check")
    print(f"  provider configured: {'YES' if report['provider_configured'] else 'NO'}")
    print(f"  provider: {report['provider']}")
    print(f"  API key present: {'YES' if report['api_key_present'] else 'NO'}")
    print(f"  base URL configured: {'YES' if report['base_url_configured'] else 'NO'}")
    print(f"  model configured: {'YES' if report['model_configured'] else 'NO'}")
    print(f"  live evaluation ready: {'YES' if report['live_evaluation_ready'] else 'NO'}")
    print(f"  status: {report['status']}")

    if not report["live_evaluation_ready"]:
        print("\nBLOCKED_BY_EXTERNAL_INPUT: DEEPSEEK_API_KEY_REQUIRED")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
