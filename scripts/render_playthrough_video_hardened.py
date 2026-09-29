#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.video_input_manifest import write_ffmpeg_concat_manifest


def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def main() -> int:
    d = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "evidence/competition/frames/smoke")
    verify_path = d / "PLAYTHROUGH_MMR_VERIFICATION_RECEIPT.json"
    if not verify_path.exists():
        raise SystemExit("no verification receipt; run hardened custody verifier first")
    verify = json.loads(verify_path.read_text())
    if verify["PLAYTHROUGH_VERIFY"] != "PASS":
        raise SystemExit(f"refusing to render: PLAYTHROUGH_VERIFY={verify['PLAYTHROUGH_VERIFY']}")
    frame_count = verify["frames_checked"]
    input_fps = 15
    output_fps = 15
    out_path = d / "canonical.mp4"
    concat_manifest = d / "FFMPEG_INPUT_MANIFEST.concat"
    input_manifest = write_ffmpeg_concat_manifest(d, frame_count, concat_manifest)
    cmd = [
        "ffmpeg", "-y", "-r", str(input_fps), "-f", "concat", "-safe", "0", "-i", str(concat_manifest),
        "-r", str(output_fps), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        "-g", "15", "-an", str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out_path.exists():
        raise SystemExit(f"ffmpeg failed rc={proc.returncode}\n{proc.stderr[-2000:]}")
    probe = sh(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate,nb_frames,codec_name", "-of", "json", str(out_path)])
    probe_json = json.loads(probe)["streams"][0]
    video_bytes = out_path.read_bytes()
    manifest = {
        "schema": "VIDEO_ENCODING_MANIFEST_V2_BOUNDED_INPUT",
        "ffmpeg_version": sh(["ffmpeg", "-version"]).splitlines()[0],
        "codec": probe_json.get("codec_name"),
        "resolution": f"{probe_json.get('width')}x{probe_json.get('height')}",
        "input_fps": input_fps,
        "output_fps": output_fps,
        "pixel_format": "yuv420p",
        "crf": 18,
        "gop": 15,
        "exact_command": " ".join(cmd),
        "bounded_input_manifest": input_manifest,
        "frame_count_input": frame_count,
        "frame_count_output_reported": probe_json.get("nb_frames"),
        "video_file": str(out_path.relative_to(ROOT)),
        "video_bytes": len(video_bytes),
        "video_sha256": hashlib.sha256(video_bytes).hexdigest(),
        "source_playthrough_mmr_root": verify["recomputed_mmr_root"],
        "source_verify_state": verify["PLAYTHROUGH_VERIFY"],
        "label": "SETUP_SMOKE_NON_SUBMISSION_NON_EXPERIMENTAL",
    }
    (d / "VIDEO_ENCODING_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
