#!/usr/bin/env python3
"""Transfer a fixed, reviewed Internet Archive seed packet.

No discovery, login, borrowing, CAPTCHA handling, or access-control bypass is
implemented. Requested filenames must be explicitly listed in the manifest and
present in public item metadata. Every downloaded file is size- and hash-audited.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

USER_AGENT = "ArchiveOrgSeedBridge/0.1 (+https://github.com/yongeun22/MoMent)"
RESTRICTED_COLLECTIONS = {
    "borrowablebooks",
    "inlibrary",
    "internetarchivebooks",
    "printdisabled",
}
TRUE_VALUES = {True, 1, "1", "true", "yes", "y"}
T = TypeVar("T")


def normalise_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(entry) for entry in value]
    return [str(value)]


def is_true(value: Any) -> bool:
    if isinstance(value, str):
        value = value.strip().lower()
    return value in TRUE_VALUES


def request(url: str, *, timeout: int = 180):
    return urllib.request.urlopen(
        urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json, application/pdf, text/plain, */*",
            },
        ),
        timeout=timeout,
    )


def retry(operation: Callable[[], T], *, attempts: int = 4) -> T:
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt == attempts:
                break
            retry_after = exc.headers.get("Retry-After") if isinstance(exc, urllib.error.HTTPError) else None
            delay = int(retry_after) if retry_after and retry_after.isdigit() else min(30, 2**attempt)
            time.sleep(delay)
    assert last_error is not None
    raise last_error


def restriction_reasons(metadata: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if is_true(metadata.get("access-restricted-item")):
        reasons.append("access-restricted-item=true")
    if is_true(metadata.get("is_dark")):
        reasons.append("is_dark=true")
    collections = {entry.lower() for entry in normalise_list(metadata.get("collection"))}
    blocked = sorted(collections & RESTRICTED_COLLECTIONS)
    if blocked:
        reasons.append("restricted collections=" + ",".join(blocked))
    return reasons


def hash_file(path: Path) -> tuple[str, str]:
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha1.update(chunk)
            sha256.update(chunk)
    return sha1.hexdigest(), sha256.hexdigest()


def fetch_metadata(identifier: str) -> dict[str, Any]:
    url = f"https://archive.org/metadata/{urllib.parse.quote(identifier, safe='')}"

    def fetch() -> dict[str, Any]:
        with request(url) as response:
            return json.load(response)

    payload = retry(fetch)
    if not isinstance(payload, dict):
        raise RuntimeError(f"{identifier}: metadata response is not an object")
    return payload


def download_file(
    *,
    identifier: str,
    spec: dict[str, Any],
    source: dict[str, Any],
    destination: Path,
    max_bytes: int,
) -> dict[str, Any]:
    filename = str(spec["filename"])
    declared_size = int(source.get("size") or 0)
    if declared_size and declared_size > max_bytes:
        raise RuntimeError(f"{identifier}/{filename}: declared size exceeds cap")
    if is_true(source.get("private")):
        raise RuntimeError(f"{identifier}/{filename}: source file is private")

    url = (
        "https://archive.org/download/"
        + urllib.parse.quote(identifier, safe="")
        + "/"
        + urllib.parse.quote(filename, safe="")
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    temporary.unlink(missing_ok=True)

    def transfer() -> tuple[int, str]:
        total = 0
        with request(url) as response, temporary.open("wb") as output:
            content_type = str(response.headers.get("Content-Type") or "").lower()
            if "text/html" in content_type:
                raise RuntimeError(f"{identifier}/{filename}: unexpected HTML response")
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                raise RuntimeError(f"{identifier}/{filename}: Content-Length exceeds cap")
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise RuntimeError(f"{identifier}/{filename}: stream exceeds cap")
                output.write(chunk)
        return total, content_type

    try:
        total, content_type = retry(transfer)
        if declared_size and total != declared_size:
            raise RuntimeError(
                f"{identifier}/{filename}: size mismatch {total} != {declared_size}"
            )
        os.replace(temporary, destination)
        actual_sha1, actual_sha256 = hash_file(destination)
        source_sha1 = str(source.get("sha1") or "").lower()
        if source_sha1 and actual_sha1 != source_sha1:
            destination.unlink(missing_ok=True)
            raise RuntimeError(f"{identifier}/{filename}: source SHA-1 mismatch")
        return {
            "role": spec.get("role"),
            "filename": filename,
            "source_url": url,
            "content_type": content_type,
            "bytes": total,
            "source_sha1": source_sha1 or None,
            "verified_sha1": actual_sha1,
            "sha256": actual_sha256,
        }
    finally:
        temporary.unlink(missing_ok=True)


def process_item(item: dict[str, Any], output_root: Path, *, max_bytes: int) -> dict[str, Any]:
    identifier = str(item["identifier"])
    if item.get("rights_status") != "PUBLIC_DOMAIN":
        raise RuntimeError(f"{identifier}: manifest rights_status is not PUBLIC_DOMAIN")

    raw_metadata = fetch_metadata(identifier)
    metadata = raw_metadata.get("metadata") or {}
    restrictions = restriction_reasons(metadata)
    if restrictions:
        raise RuntimeError(f"{identifier}: restricted: {'; '.join(restrictions)}")

    source_files = {
        str(entry.get("name")): entry
        for entry in (raw_metadata.get("files") or [])
        if isinstance(entry, dict) and entry.get("name")
    }
    requested = item.get("files") or []
    missing = [spec["filename"] for spec in requested if spec["filename"] not in source_files]
    if not requested or missing:
        raise RuntimeError(f"{identifier}: reviewed files missing from metadata: {missing}")

    item_root = output_root / identifier
    item_root.mkdir(parents=True, exist_ok=True)
    metadata_path = item_root / "archive_metadata.raw.json"
    metadata_path.write_text(
        json.dumps(raw_metadata, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    metadata_sha1, metadata_sha256 = hash_file(metadata_path)

    downloaded: list[dict[str, Any]] = []
    for spec in requested:
        filename = str(spec["filename"])
        downloaded.append(
            download_file(
                identifier=identifier,
                spec=spec,
                source=source_files[filename],
                destination=item_root / filename,
                max_bytes=max_bytes,
            )
        )
        time.sleep(2)

    result = {
        "schema_version": "0.1.0",
        "identifier": identifier,
        "scope_id": item.get("scope_id"),
        "archive_item_url": f"https://archive.org/details/{identifier}",
        "rights_status": item.get("rights_status"),
        "rights_basis": item.get("rights_basis"),
        "restriction_check": "PASS",
        "downloaded_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "metadata_file": {
            "filename": metadata_path.name,
            "bytes": metadata_path.stat().st_size,
            "sha1": metadata_sha1,
            "sha256": metadata_sha256,
        },
        "files": downloaded,
    }
    (item_root / "download.manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return result


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-file-mb", type=int, default=100)
    args = parser.parse_args(list(argv) if argv is not None else None)

    packet = json.loads(args.manifest.read_text(encoding="utf-8"))
    items = packet.get("items") or []
    if not items:
        raise SystemExit("reviewed manifest contains no items")

    args.output.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for item in items:
        identifier = str(item.get("identifier") or "<missing>")
        try:
            results.append(
                process_item(
                    item,
                    args.output,
                    max_bytes=args.max_file_mb * 1024 * 1024,
                )
            )
        except Exception as exc:
            failures.append({"identifier": identifier, "error": repr(exc)})

    receipt = {
        "schema_version": "0.1.0",
        "requested": len(items),
        "succeeded": len(results),
        "failed": len(failures),
        "results": results,
        "failures": failures,
    }
    (args.output / "bootstrap.receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
