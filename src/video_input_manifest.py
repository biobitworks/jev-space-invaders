from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_numbered_frame_inputs(directory: Path, expected_frame_count: int) -> dict:
    directory = directory.resolve()
    errors: list[str] = []
    if expected_frame_count <= 0:
        errors.append("EXPECTED_FRAME_COUNT_NON_POSITIVE")
    expected_names = {f"frame_{i:04d}.png" for i in range(expected_frame_count)}
    actual_frames = sorted(directory.glob("frame_*.*"))
    actual_names = [p.name for p in actual_frames]
    actual_set = set(actual_names)
    extras = sorted(actual_set - expected_names)
    missing = sorted(expected_names - actual_set)
    extension_mismatch = [name for name in actual_names if name.startswith("frame_") and not name.endswith(".png")]
    if extras:
        errors.append("UNEXPECTED_FRAME:" + ",".join(extras[:10]))
    if missing:
        errors.append("MISSING_FRAME:" + ",".join(missing[:10]))
    if extension_mismatch:
        errors.append("EXTENSION_MISMATCH:" + ",".join(extension_mismatch[:10]))

    ordered_paths = [directory / f"frame_{i:04d}.png" for i in range(expected_frame_count)]
    sequence_material = []
    if not errors:
        for i, path in enumerate(ordered_paths):
            if not path.is_file():
                errors.append(f"MISSING_FRAME:{path.name}")
                continue
            sequence_material.append(f"{i}:{path.name}:{sha256_file(path)}")

    sequence_hash = hashlib.sha256("\n".join(sequence_material).encode()).hexdigest()
    manifest = {
        "schema": "BOUNDED_FFMPEG_INPUT_MANIFEST_V1",
        "first_frame": "frame_0000.png" if expected_frame_count else None,
        "last_frame": f"frame_{expected_frame_count - 1:04d}.png" if expected_frame_count else None,
        "expected_frame_count": expected_frame_count,
        "actual_frame_count": len([p for p in actual_frames if p.suffix == ".png"]),
        "frame_sequence_hash": sequence_hash,
        "input_manifest_sha256": None,
        "errors": errors,
    }
    digest_payload = json.dumps(
        {k: v for k, v in manifest.items() if k != "input_manifest_sha256"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    manifest["input_manifest_sha256"] = hashlib.sha256(digest_payload).hexdigest()
    if errors:
        raise ValueError(";".join(errors))
    return manifest


def write_ffmpeg_concat_manifest(directory: Path, expected_frame_count: int, output_path: Path) -> dict:
    manifest = validate_numbered_frame_inputs(directory, expected_frame_count)
    lines = []
    for i in range(expected_frame_count):
        path = (directory.resolve() / f"frame_{i:04d}.png").as_posix()
        lines.append(f"file '{path}'")
    output_path.write_text("\n".join(lines) + "\n")
    return manifest
