#!/usr/bin/env python3
"""Deterministic frame-corpus -> canonical MP4 render via ffmpeg. Requires the
frame corpus to already carry a PASS PLAYTHROUGH_MMR_VERIFICATION_RECEIPT.json;
refuses to render an unverified corpus.
"""
from __future__ import annotations
import hashlib, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def main() -> int:
    d = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "evidence/competition/frames/smoke")
    if not d.is_absolute():
        d = ROOT / d
    verify_path = d / "PLAYTHROUGH_MMR_VERIFICATION_RECEIPT.json"
    if not verify_path.exists():
        raise SystemExit("no verification receipt; run verify_playthrough_custody.py first")
    verify = json.loads(verify_path.read_text())
    if verify["PLAYTHROUGH_VERIFY"] != "PASS":
        raise SystemExit(f"refusing to render: PLAYTHROUGH_VERIFY={verify['PLAYTHROUGH_VERIFY']}")
    construction = json.loads((d / "PLAYTHROUGH_MMR_CONSTRUCTION_RECEIPT.json").read_text())

    frame_count = verify["frames_checked"]
    capture_mode = construction.get("capture_mode", "decision")
    input_fps = 60 if capture_mode == "actual-ale" else 15
    output_fps = input_fps
    out_path = d / "canonical.mp4"
    cmd = ["ffmpeg", "-y", "-framerate", str(input_fps), "-i", str(d / "frame_%04d.png"),
           "-r", str(output_fps), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
           "-g", "15", "-an", str(out_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out_path.exists():
        raise SystemExit(f"ffmpeg failed rc={proc.returncode}\n{proc.stderr[-2000:]}")

    probe = sh(["ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,r_frame_rate,nb_frames,codec_name",
                "-of", "json", str(out_path)])
    probe_json = json.loads(probe)["streams"][0]
    video_bytes = out_path.read_bytes()
    manifest = {
        "schema": "VIDEO_ENCODING_MANIFEST_V1",
        "ffmpeg_version": sh(["ffmpeg", "-version"]).splitlines()[0],
        "codec": probe_json.get("codec_name"),
        "resolution": f"{probe_json.get('width')}x{probe_json.get('height')}",
        "input_fps": input_fps,
        "output_fps": output_fps,
        "pixel_format": "yuv420p",
        "crf": 18,
        "gop": 15,
        "exact_command": " ".join(cmd),
        "frame_count_input": frame_count,
        "frame_count_output_reported": probe_json.get("nb_frames"),
        "video_file": str(out_path.relative_to(ROOT)),
        "video_bytes": len(video_bytes),
        "video_sha256": hashlib.sha256(video_bytes).hexdigest(),
        "source_playthrough_mmr_root": verify["recomputed_mmr_root"],
        "source_verify_state": verify["PLAYTHROUGH_VERIFY"],
        "label": construction.get("label", "UNSPECIFIED"),
    }
    (d / "VIDEO_ENCODING_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
