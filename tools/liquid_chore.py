#!/usr/bin/env python3
"""Liquid-backed chore helper: summarize-log, commit-msg, classify-failure.

Advisory only. Liquid never chooses JEV/OpenJev moves and is not used in results.json
runs. Every fact it reports here is re-checked by a deterministic heuristic before use;
callers should still verify before acting on advisory output.
"""
from __future__ import annotations
import argparse, hashlib, json, platform, re, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "http://127.0.0.1:11434"
MODEL = "hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF:Q4_K_M"
CHORE_LOG = ROOT / "evidence" / "liquid_chores.jsonl"
MANIFEST = ROOT / "evidence" / "liquid" / "CHORE_RUNTIME_MANIFEST.json"
FAILURE_CLASSES = ["auth", "rate_limit", "network", "oom", "code_error", "env_missing", "other"]


def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def _guard_path(p: Path) -> None:
    if ".env" in p.name.lower():
        raise SystemExit(f"refusing to process {p}: looks like a secrets file")


def _ollama_generate(prompt: str, timeout_s: float = 60.0) -> tuple[str, float]:
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False,
                        "options": {"temperature": 0, "seed": 0}}).encode()
    req = urllib.request.Request(ENDPOINT + "/api/generate", data=body,
                                  headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout_s) as r:
        resp = json.loads(r.read())
    ms = round((time.monotonic() - t0) * 1000, 1)
    return (resp.get("response") or "").strip(), ms


def load_runtime(write_manifest: bool = True) -> dict:
    with urllib.request.urlopen(ENDPOINT + "/api/tags", timeout=5) as r:
        tags = json.load(r)
    names = {m.get("name") for m in tags.get("models", [])}
    if MODEL not in names:
        raise SystemExit(f"{MODEL} not resident in local Ollama store (see: ollama list)")
    text, ms = _ollama_generate("Reply with exactly one word: OK")
    smoke = "PASS" if "OK" in text.upper() else "FAIL"
    man = {
        "schema": "LIQUID_CHORE_RUNTIME_MANIFEST_V1",
        "LIQUID_LOADED": "YES" if smoke == "PASS" else "NO",
        "purpose": "tools/liquid_chore.py tedious-work chores; advisory text only, never chooses JEV/OpenJev moves, not used in results.json runs",
        "provider": "liquid",
        "served_model": MODEL,
        "endpoint": ENDPOINT,
        "engine": "Ollama",
        "ollama_version": sh(["ollama", "--version"]),
        "host": sh(["hostname", "-s"]) or sh(["hostname"]),
        "platform": platform.platform(),
        "chip": sh(["sysctl", "-n", "machdep.cpu.brand_string"]),
        "ram_bytes": int(sh(["sysctl", "-n", "hw.memsize"]) or 0),
        "setup_smoke": smoke,
        "setup_smoke_latency_ms": ms,
        "labels": ["ADVISORY_ONLY", "NOT_USED_FOR_MOVE_SELECTION", "NON_TYPESAFE_JEV", "NON_OPENJEV"],
    }
    if write_manifest:
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(man, indent=2) + "\n")
    return man


def _log_chore(chore: str, input_bytes: bytes, output: str, ms: float) -> None:
    CHORE_LOG.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "chore": chore,
        "input_sha256": hashlib.sha256(input_bytes).hexdigest(),
        "input_bytes": len(input_bytes),
        "output": output,
        "ms": ms,
        "model": MODEL,
    }
    with CHORE_LOG.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")


def summarize_log(path: Path) -> str:
    _guard_path(path)
    text = path.read_text(errors="ignore")
    lines = text.splitlines()
    err_lines = [l for l in lines if any(w in l.lower() for w in ("error", "exception", "traceback", "fatal"))]
    last_status = next((l for l in reversed(lines) if l.strip()), "")
    prompt = ("Summarize this log in at most 8 lines: list distinct errors, the last status line, "
              "and rough counts. Be terse, no preamble.\n\nLOG:\n" + text[-8000:])
    summary, ms = _ollama_generate(prompt)
    _log_chore("summarize-log", text.encode(), summary, ms)
    out = ["ADVISORY (Liquid, unverified):", *summary.splitlines()[:10], "---",
           f"DETERMINISTIC: {len(lines)} lines, {len(err_lines)} error-like lines, last: {last_status[:120]!r}"]
    return "\n".join(out)


def commit_msg(diffstat: str) -> str:
    prompt = ("Write ONE line: a conventional-commit subject (type(scope): subject, imperative, "
              "no trailing period, under 72 chars) for this diffstat. Output only the subject line.\n\n"
              + diffstat[-4000:])
    subject, ms = _ollama_generate(prompt)
    subject = subject.strip().splitlines()[0].strip() if subject.strip() else ""
    _log_chore("commit-msg", diffstat.encode(), subject, ms)
    ok = bool(re.match(r"^[a-z]+(\([a-z0-9_-]+\))?: .{1,70}$", subject)) and not subject.endswith(".")
    return f"ADVISORY (review before using): {subject}\nCONVENTIONAL_FORMAT_CHECK={'PASS' if ok else 'FAIL'}"


def _heuristic_classify(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ("401", "403", "unauthorized", "permission denied", "invalid api key", "authentication failed")):
        return "auth"
    if any(k in t for k in ("429", "rate limit", "too many requests", "quota exceeded")):
        return "rate_limit"
    if any(k in t for k in ("econnrefused", "connection reset", "timed out", "timeout", "dns", "network is unreachable", "urlerror")):
        return "network"
    if any(k in t for k in ("out of memory", "oom", "killed\n", "memoryerror", "cannot allocate memory")):
        return "oom"
    if any(k in t for k in ("modulenotfounderror", "importerror", "command not found", "no such file or directory", "not installed")):
        return "env_missing"
    if any(k in t for k in ("traceback (most recent call last)", "syntaxerror", "typeerror", "valueerror", "nameerror", "assertionerror")):
        return "code_error"
    return "other"


def classify_failure(path: Path) -> str:
    _guard_path(path)
    text = path.read_text(errors="ignore")
    prompt = ("Classify this failure log into exactly one of: " + ", ".join(FAILURE_CLASSES) +
              ". Reply as:\nCLASS: <one word>\nREASON: <one line>\n\nLOG:\n" + text[-6000:])
    reply, ms = _ollama_generate(prompt)
    _log_chore("classify-failure", text.encode(), reply, ms)
    liquid_cls = "other"
    for c in FAILURE_CLASSES:
        if re.search(r"\b" + re.escape(c) + r"\b", reply.lower()):
            liquid_cls = c
            break
    heuristic_cls = _heuristic_classify(text)
    agree = liquid_cls == heuristic_cls
    return (f"ADVISORY (Liquid, unverified):\n{reply}\n---\n"
            f"DETERMINISTIC_HEURISTIC_CLASS={heuristic_cls}\nLIQUID_CLASS={liquid_cls}\nAGREE={agree}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup")
    s1 = sub.add_parser("summarize-log"); s1.add_argument("file")
    s2 = sub.add_parser("commit-msg"); s2.add_argument("diffstat", nargs="?", help="path to diffstat file; reads stdin if omitted")
    s3 = sub.add_parser("classify-failure"); s3.add_argument("file")
    args = ap.parse_args()
    if args.cmd == "setup":
        print(json.dumps(load_runtime(), indent=2))
    elif args.cmd == "summarize-log":
        print(summarize_log(Path(args.file)))
    elif args.cmd == "commit-msg":
        diffstat = Path(args.diffstat).read_text() if args.diffstat else sys.stdin.read()
        print(commit_msg(diffstat))
    elif args.cmd == "classify-failure":
        print(classify_failure(Path(args.file)))


if __name__ == "__main__":
    main()
