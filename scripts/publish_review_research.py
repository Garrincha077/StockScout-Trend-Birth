"""Attach the verified research outputs to an exact Review snapshot."""

import argparse
import hashlib
import json
from pathlib import Path
import re

from publish_review_snapshot import encode, write_changed
from validate_unified_review_bundle import identity

SCHEMA = "trend-birth-review-research-v1"
CASE_SCHEMA = "weekly-base-cases-v1"
CASE_FILE = "weekly-base-cases.json"
REPORTS = {
    "trendBirthForward": ("trend-birth-stage-forward.json", "trend-birth-stage-forward-v2"),
    "kellForward": ("kell-forward-validation.json", "kell-forward-validation-v1"),
    "kellGoldSet": ("kell-gold-set-eval.json", "kell-gold-set-eval-v2"),
    "alerts": ("trend-birth-alerts.json", "trend-birth-alerts-v1"),
}


def _case_reference(publication: dict, content: bytes) -> dict:
    digest = hashlib.sha256(content).hexdigest()
    snapshot_id = publication["snapshotId"]
    return {"schemaVersion": CASE_SCHEMA, "snapshotId": snapshot_id, "sha256": digest,
            "path": f"data/research-runs/{snapshot_id}--weekly-cases--{digest}.json"}


def _validate_cases(report: dict, cases: dict, publication: dict) -> None:
    count = report.get("caseCount")
    days = cases.get("days")
    if (cases.get("schemaVersion") != CASE_SCHEMA or cases.get("asOf") != report.get("asOf") or
            identity(cases.get("source") or {}) != identity(publication) or type(count) is not int or count < 0 or
            cases.get("caseCount") != count or report.get("groups", {}).get("all", {}).get("entries") != count or
            not isinstance(days, list) or any(not isinstance(day, dict) or not isinstance(day.get("cases"), list) for day in days) or
            sum(len(day["cases"]) for day in days) != count):
        raise ValueError("Weekly Base case history differs from the Review publication")


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
    swing = reports["kellForward"].get("swingStatistics")
    if swing is not None and (swing.get("schemaVersion") != "kell-swing-statistics-v1" or swing.get("asOf") != day):
        raise ValueError("Kell swing statistics differ from the Review publication")
    execution_cohorts = (swing or {}).get("executionCohorts")
    if execution_cohorts is not None and (
        execution_cohorts.get("schemaVersion") != "kell-swing-execution-cohorts-v1"
        or execution_cohorts.get("asOf") != day
    ):
        raise ValueError("Kell execution cohorts differ from the Review publication")
    matched = (reports["trendBirthForward"].get("earlyTrend") or {}).get("matched")
    if matched is not None and (matched.get("schemaVersion") != "trend-birth-matched-cohorts-v1" or
                                matched.get("asOf") != day):
        raise ValueError("Matched Trend Birth cohorts differ from the Review publication")
    weekly = reports["trendBirthForward"].get("weeklyBase")
    if weekly is not None and (weekly.get("schemaVersion") != "weekly-base-outcomes-v1" or weekly.get("asOf") != day):
        raise ValueError("Weekly Base outcomes differ from the Review publication")
    if weekly is not None and "caseCount" in weekly:
        ref = publication.get("weeklyBaseCases")
        if not ref or ref.get("schemaVersion") != CASE_SCHEMA or ref.get("snapshotId") != snapshot_id:
            raise ValueError("Weekly Base case reference differs from the Review publication")
        weekly["caseReference"] = ref
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
    forward = json.loads((directory / REPORTS["trendBirthForward"][0]).read_bytes())
    weekly = forward.get("weeklyBase") or {}
    case_file = None
    if "caseCount" in weekly:
        cases = json.loads((directory / CASE_FILE).read_bytes())
        _validate_cases(weekly, cases, publication)
        case_file = encode({**cases, "reviewSnapshotId": publication["snapshotId"]})
        publication["weeklyBaseCases"] = _case_reference(publication, case_file)
    else:
        publication.pop("weeklyBaseCases", None)
    content = research_snapshot(directory, publication)
    reference = research_reference(publication, content)
    if case_file is not None:
        case_archive = directory / publication["weeklyBaseCases"]["path"].removeprefix("data/")
        if case_archive.exists() and case_archive.read_bytes() != case_file:
            raise ValueError("Immutable Weekly Base case snapshot collision")
        write_changed(case_archive, case_file)
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
    case_ref = publication.get("weeklyBaseCases")
    if case_ref is not None:
        digest = case_ref.get("sha256")
        snapshot_id = publication["snapshotId"]
        if (not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest) or
                case_ref.get("path") != f"data/research-runs/{snapshot_id}--weekly-cases--{digest}.json"):
            raise ValueError("Invalid Weekly Base case history reference")
        case_archive = directory / case_ref["path"].removeprefix("data/")
        case_file = case_archive.read_bytes() if case_archive.is_file() else None
        if case_file is None or _case_reference(publication, case_file) != case_ref:
            raise ValueError("Weekly Base case history digest mismatch")
        cases = json.loads(case_file)
        if cases.get("reviewSnapshotId") != snapshot_id:
            raise ValueError("Weekly Base case history points to another snapshot")
        weekly = json.loads(content)["reports"]["trendBirthForward"]["weeklyBase"]
        _validate_cases(weekly, cases, publication)


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
