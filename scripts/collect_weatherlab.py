"""Collect validated Weather Lab ensemble-mean ATCF cycles without losing archives."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://deepmind.google.com/science/weatherlab/download/cyclones"


@dataclass(frozen=True)
class Model:
    aid: str
    label: str
    variants: tuple[str, ...]


MODELS = (
    Model("GENC", "GenCast", ("GENC",)),
    Model("FNV3", "WeatherNext2 Cyclones", ("FNV3P2", "FNV3")),
    Model("WNV3", "WeatherNext3 Cyclones", ("WNV3",)),
)


def parse_cycle(value: str) -> datetime:
    if not re.fullmatch(r"\d{10}", value):
        raise ValueError("Cycle must use YYYYMMDDHH.")
    cycle = datetime.strptime(value, "%Y%m%d%H").replace(tzinfo=timezone.utc)
    if cycle.hour % 6:
        raise ValueError("Cycle hour must be 00, 06, 12 or 18 UTC.")
    return cycle


def cycles_to_check(now: datetime, lookback_hours: int = 48,
                    start: str = "", end: str = "") -> list[datetime]:
    now = now.astimezone(timezone.utc)
    latest = now.replace(hour=now.hour // 6 * 6, minute=0, second=0, microsecond=0)
    if bool(start) != bool(end):
        raise ValueError("Provide both --start and --end.")
    if start:
        first, last = parse_cycle(start), parse_cycle(end)
        if first > last or last > latest or last - first > timedelta(days=31):
            raise ValueError("Range must be ordered, not future-dated, and at most 31 days.")
    else:
        if not 6 <= lookback_hours <= 168:
            raise ValueError("--lookback-hours must be between 6 and 168.")
        last, first = latest, latest - timedelta(hours=lookback_hours)
    return [last - timedelta(hours=6 * step)
            for step in range(int((last - first).total_seconds() // 21600) + 1)]


def source_url(model: str, cycle: datetime) -> str:
    stamp = cycle.strftime("%Y_%m_%dT%H_00")
    return f"{BASE_URL}/{model}/ensemble_mean/paired/atcf/{model}_{stamp}_atcf_a_deck.txt"


def forecast_path(root: Path, model: Model, cycle: datetime) -> Path:
    filename = f"{model.aid}_{cycle.strftime('%Y_%m_%dT%H_00')}_atcf_a_deck.txt"
    return root / "forecast_files" / cycle.strftime("%Y/%m/%d") / filename


def migrate_legacy_paths(root: Path) -> int:
    archive = (root / "forecast_files").resolve()
    moves, directories = [], []
    for directory in sorted(archive.glob("????_??_??")):
        if not directory.is_dir() or directory.is_symlink():
            continue
        try:
            date = datetime.strptime(directory.name, "%Y_%m_%d")
        except ValueError:
            continue
        directories.append(directory)
        for source in directory.glob("*.txt"):
            target = archive / date.strftime("%Y/%m/%d") / source.name
            if source.is_symlink() or not target.resolve().is_relative_to(archive):
                raise ValueError(f"Unsafe archive path: {source}")
            if target.exists() and source.read_bytes() != target.read_bytes():
                raise ValueError(f"Archive migration collision: {target}")
            moves.append((source, target))
    # Validate the entire move set before changing any paths; preserve every byte.
    for source, target in moves:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            source.unlink()
        else:
            source.replace(target)
    for directory in directories:
        if not any(directory.iterdir()):
            directory.rmdir()
    return len(moves)


def validate_atcf(body: bytes, model: Model, cycle: datetime) -> dict:
    text = body.decode("utf-8-sig")
    rows, storms, leads = 0, set(), []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = [field.strip() for field in next(csv.reader([line]))]
        if len(fields) < 10:
            raise ValueError("Not an ATCF row.")
        if not re.fullmatch(r"[A-Z]{2}", fields[0]) or not fields[1].isdigit():
            raise ValueError("Invalid ATCF storm identifier.")
        if not 1 <= int(fields[1]) <= 99:
            raise ValueError("Invalid ATCF storm number.")
        if fields[2] != cycle.strftime("%Y%m%d%H") or fields[4] != model.aid:
            raise ValueError("ATCF cycle or model does not match the requested file.")
        lead = int(fields[5])
        if not 0 <= lead <= 720:
            raise ValueError("Invalid ATCF lead time.")
        for value, pattern, maximum in ((fields[6], r"\d+[NS]", 900),
                                         (fields[7], r"\d+[EW]", 1800)):
            if not re.fullmatch(pattern, value) or int(value[:-1]) > maximum:
                raise ValueError("Invalid ATCF coordinate.")
        for value in fields[8:10]:
            if value and not math.isfinite(float(value)):
                raise ValueError("Non-finite ATCF intensity.")
        rows += 1
        storms.add(f"{fields[0]}{int(fields[1]):02d}")
        leads.append(lead)
    if not rows:
        raise ValueError("No ATCF data rows; existing files will be retained.")
    return {"row_count": rows, "storms": sorted(storms), "max_lead_hour": max(leads)}


def write_if_changed(path: Path, body: bytes) -> bool:
    if path.exists() and path.read_bytes() == body:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(body)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = "SSalKim-GDM-WeatherLab-Collector/2"
    retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["GET"], respect_retry_after_header=False)
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def collect_cycle(model: Model, cycle: datetime, root: Path, session=None) -> dict:
    cycle_text = cycle.strftime("%Y%m%d%H")
    path = forecast_path(root, model, cycle)
    metadata_path = path.with_suffix(".json")
    previous = read_json(metadata_path)
    own_session = session is None
    session = session or make_session()
    try:
        for variant in model.variants:
            # Never replace a newer checkpoint with an older fallback for the same cycle.
            old_variant = previous.get("upstream_model")
            if old_variant in model.variants and model.variants.index(variant) > model.variants.index(old_variant):
                continue
            url = source_url(variant, cycle)
            response = session.get(url, timeout=(10, 30))
            if response.status_code in (404, 410):
                continue
            response.raise_for_status()
            body = response.content
            details = validate_atcf(body, model, cycle)
            metadata = {
                "model": model.aid, "display_name": model.label,
                "upstream_model": variant, "source_url": url,
                "cycle_utc": cycle_text, "path": path.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(body).hexdigest(), **details,
            }
            changed = write_if_changed(path, body)
            changed |= write_if_changed(metadata_path, json_bytes(metadata))
            return {"status": "updated" if changed else "unchanged", **metadata}
        return {"status": "not_ready", "model": model.aid, "cycle_utc": cycle_text}
    finally:
        if own_session:
            session.close()


def collect_safely(job: tuple[Model, datetime], root: Path) -> dict:
    model, cycle = job
    try:
        return collect_cycle(model, cycle, root)
    except (requests.RequestException, ValueError, OSError) as exc:
        return {"status": "error", "model": model.aid,
                "cycle_utc": cycle.strftime("%Y%m%d%H"), "error": str(exc)}


def update_latest(root: Path, results: list[dict]) -> None:
    path = root / "data" / "latest.json"
    latest = read_json(path)
    for result in results:
        if result["status"] not in {"updated", "unchanged"}:
            continue
        previous = latest.get(result["model"], {})
        if result["cycle_utc"] >= previous.get("cycle_utc", ""):
            latest[result["model"]] = {key: value for key, value in result.items() if key != "status"}
    if latest:
        write_if_changed(path, json_bytes(latest))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="")
    parser.add_argument("--end", default="")
    parser.add_argument("--lookback-hours", type=int, default=48)
    parser.add_argument("--workers", type=int, choices=range(1, 7), default=4)
    parser.add_argument("--models", nargs="+", choices=[model.aid for model in MODELS])
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        cycles = cycles_to_check(datetime.now(timezone.utc), args.lookback_hours, args.start, args.end)
    except ValueError as exc:
        parser.error(str(exc))
    models = [model for model in MODELS if not args.models or model.aid in args.models]
    if moved := migrate_legacy_paths(args.root):
        print(f"Migrated {moved} archive files into YYYY/MM/DD directories.")
    jobs = [(model, cycle) for cycle in cycles for model in models]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda job: collect_safely(job, args.root), jobs))
    update_latest(args.root, results)
    for result in results:
        print(f"[{result['model']} {result['cycle_utc']}] {result['status']} {result.get('error', '')}")
    counts = {state: sum(result["status"] == state for result in results)
              for state in ("updated", "unchanged", "not_ready", "error")}
    print(json.dumps(counts, sort_keys=True))
    return int(counts["error"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
