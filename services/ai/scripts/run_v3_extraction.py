#!/usr/bin/env python3
"""Run the offline extraction v3 path for a single communication."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

from app.config import AI_DB_PATH  # noqa: E402
from app.db import managed_connection  # noqa: E402
from app.pipeline.stages.extraction_v3 import run_v3_extraction_offline  # noqa: E402


def _default_output_dir(communication_id: str) -> Path:
    return AI_SERVICE_DIR / "data" / "v3_runs" / communication_id


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


async def _run(args) -> Path:
    with managed_connection(Path(args.db_path)) as db:
        result = await run_v3_extraction_offline(
            db=db,
            communication_id=args.communication_id,
            pass1_model=args.pass1_model,
            pass2_model=args.pass2_model,
        )

    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else _default_output_dir(args.communication_id)
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_json(output_dir / "pass1.json", result["pass1"])
    _write_json(output_dir / "routing.json", result["routing"])
    _write_json(output_dir / "pass2.json", result["pass2"])
    _write_json(
        output_dir / "metadata.json",
        {
            "communication_id": result["communication_id"],
            "prompts": result["prompts"],
            "models": result["models"],
            "usage": result["usage"],
        },
    )

    return output_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("communication_id", help="Communication UUID from ai.db")
    parser.add_argument(
        "--db-path",
        default=str(AI_DB_PATH),
        help="Path to ai.db (defaults to app.config.AI_DB_PATH)",
    )
    parser.add_argument(
        "--pass1-model", default=None, help="Optional model override for pass 1"
    )
    parser.add_argument(
        "--pass2-model", default=None, help="Optional model override for pass 2"
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory. Defaults to services/ai/data/v3_runs/<communication_id>",
    )
    args = parser.parse_args()

    output_dir = asyncio.run(_run(args))
    print(f"v3 extraction artifacts written to: {output_dir}")


if __name__ == "__main__":
    main()
