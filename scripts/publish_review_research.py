"""Attach the verified research outputs to an exact Review snapshot."""

import argparse
import hashlib
import json
from pathlib import Path
import re

from publish_review_snapshot import encode, write_changed
from validate_unified_review_bundle import identity

SCHEMA = "trend-birth-review-research-v1"
REPORTS = {
    "trendBirthForward": ("trend-birth-stage-forward.json", "trend-birth-stage-forward-v2"),
    "kellForward": ("kell-forward-validation.json", "kell-forward-validation-v1"),
    "kellGoldSet": ("kell-gold-set-eval.json", "kell-gold-set-eval-v2"),
    "alerts": ("trend-birth-alerts.json", "trend-birth-alerts-v1"),
}


def research_snapshot(directory: Path, publication: dict) -> bytes:
    run, day, unified = identity(publication)
    snapshot_id = publication.get("snapshotId")
    if (not isinstance(snapshot_id, str) or
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}--[a-f0-9]{64}", snapshot_id) or
            snapshot_id != f"{run}--{publication.get('sha256')}"):
        raise ValueError("Invalid Review snapshot for research publication")
    reports = {}
    for key, (filename, schema) in REPORTS.items():
        report = json.loads((directory / filename).read_bytes())
        if report.get("schemaVersion") != schema or identity(report.get("source") or {}) != (run, day, unified):
            raise ValueError(f"Research report does not match Review publication: {filename}")
        reports[key] = report
    if (reports["trendBirthForward"].get("asOf") != day or
            reports["kellForward"]["source"].get("asOf") != day or
            reports["kellForward"]["source"].get("lastSignalDate") != day or
            reports["alerts"].get("reviewSnapshotId") != snapshot_id):
        raise ValueError("Research cutoff, latest score or alert target differs from Review publication")
    return encode({
        "schemaVersion": SCHEMA,
        "reviewSnapshotId": snapshot_id,
        "source": {"runId": run, "sessionDate": day, "unifiedManifestSha256": unified},
        "reports": reports,
    })


def research_reference(publication: dict, content: bytes) -> dict:
    digest = hashlib.sha256(content).hexdigest()
    return {"schemaVersion": SCHEMA, "sha256": digest,
            "path": f"data/research-runs/{publication['snapshotId']}--{digest}.json"}


def publish(directory: Path) -> dict:
    path = directory / "publication.json"
    publication = json.loads(path.read_bytes())
    content = research_snapshot(directory, publication)
    reference = research_reference(publication, content)
    archive = directory / reference["path"].removeprefix("data/")
    if archive.exists() and archive.read_bytes() != content:
        raise ValueError("Immutable research snapshot collision")
    write_changed(archive, content)
    publication["research"] = reference
    write_changed(path, encode(publication))
    return reference


def validate_research(directory: Path, publication: dict) -> None:
    content = research_snapshot(directory, publication)
    reference = research_reference(publication, content)
    if publication.get("research") != reference:
        raise ValueError("Research reference does not match the generated report bytes")
    archive = directory / reference["path"].removeprefix("data/")
    if not archive.is_file() or archive.read_bytes() != content:
        raise ValueError("Research snapshot missing or content digest mismatch")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("lab/data"))
    parser.add_argument("--check", action="store_true", help="Verify the current pointer and archive without writes")
    args = parser.parse_args()
    if args.check:
        publication = json.loads((args.directory / "publication.json").read_bytes())
        validate_research(args.directory, publication)
        print(json.dumps(publication["research"]))
        return
    print(json.dumps(publish(args.directory)))


if __name__ == "__main__":
    main()
