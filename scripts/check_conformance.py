"""Check authority revision and matrix coverage, not behavioral conformance.

Run from any directory: python scripts/check_conformance.py
The source documents are read only. No Office or third-party dependency is needed.
"""

import hashlib
import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
STATUSES = {
    "IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "DESIGNED_NOT_IMPLEMENTED",
    "MISSING", "CONFLICTING", "DEFERRED",
}
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def check(root: Path = ROOT) -> list[str]:
    """Return traceability errors; an empty list is not a release approval."""
    errors: list[str] = []
    folder = root / "docs/conformance"
    matrix = (folder / "authority-matrix.md").read_text(encoding="utf-8")
    manifest = json.loads((folder / "authority-sources.json").read_text(encoding="utf-8"))
    evidence = set(re.findall(r"^\| ([A-Z]\d{2}) \|", matrix, re.MULTILINE))
    seen: set[str] = set()
    for line in matrix.splitlines():
        if not line.startswith("| AUTH-"):
            continue
        columns = [value.strip() for value in line.split("|")[1:-1]]
        if len(columns) != 5:
            errors.append(f"Malformed matrix row: {line}")
            continue
        identity, _, status, references, gap = columns
        if identity in seen:
            errors.append(f"Duplicate requirement group: {identity}")
        seen.add(identity)
        if status not in STATUSES:
            errors.append(f"Unknown classification: {identity}: {status}")
        if not gap or not references:
            errors.append(f"Missing evidence/gap explanation: {identity}")
        for reference in references.split(","):
            if reference.strip() not in evidence:
                errors.append(f"Unknown evidence reference: {identity}: {reference}")
    expected: set[str] = set()
    documents: set[str] = set()
    for entry in manifest:
        number = entry["document"]
        if number in documents:
            errors.append(f"Duplicate authority source: {number}")
        documents.add(number)
        path = (root / entry["path"]).resolve()
        if not path.is_relative_to((root / "docs").resolve()):
            errors.append(f"Authority source outside docs: {number}")
            continue
        if not path.is_file():
            errors.append(f"Missing authority source: {entry['path']}")
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            errors.append(f"Authority revision changed; review before repinning: {number}")
        with ZipFile(path) as document:
            tree = ElementTree.fromstring(document.read("word/document.xml"))
        paragraphs = tree.findall(".//w:p", NS)
        text = "\n".join(
            "".join(node.text or "" for node in p.findall(".//w:t", NS))
            for p in paragraphs
        )
        metadata = re.search(r"Document Number:\s*(\d+)", text)
        if metadata is None or int(metadata.group(1)) != int(number):
            errors.append(f"Document identity mismatch: {number}")
        if int(number) > 7:
            continue
        for paragraph in paragraphs:
            style = paragraph.find("w:pPr/w:pStyle", NS)
            if style is None or "heading" not in style.get(f"{{{NS['w']}}}val", "").lower():
                continue
            heading = "".join(node.text or "" for node in paragraph.findall(".//w:t", NS))
            match = re.match(r"^(\d+)\. ", heading)
            if match:
                expected.add(f"AUTH-{int(number):02}-{int(match.group(1)):02}")
    if documents != {f"{number:02}" for number in range(1, 11)}:
        errors.append("Source manifest must identify Documents 01–10 exactly once")
    errors.extend(f"Unmapped authority section: {item}" for item in sorted(expected - seen))
    errors.extend(f"Unknown authority section: {item}" for item in sorted(seen - expected))
    if not expected:
        errors.append("No authority sections discovered")
    return errors


def main() -> int:
    try:
        errors = check()
    except (OSError, ValueError, KeyError, ElementTree.ParseError) as exc:
        print(f"Conformance inventory could not be read: {exc}", file=sys.stderr)
        return 1
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Authority hashes, Documents 01–07 section coverage and evidence references pass.")
    print("Traceability only: behavioral/release conformance is not established.")
    print("Documents 08–10 are pinned in the source manifest for supplemental review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
