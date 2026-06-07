"""Export performance report to JSON."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sino_account.performance.models import PerformanceReport


def report_to_dict(report: PerformanceReport) -> dict[str, Any]:
    return asdict(report)


def export_json(report: PerformanceReport, output_dir: str | Path) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    file_path = output_path / "report_3m.json"
    payload = report_to_dict(report)
    with file_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return file_path
