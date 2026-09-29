#!/usr/bin/env bash
# vithia_doctor3.sh — seed FCO -> verify -> operator identity -> credentials -> Vithia -> Mitosis -> breakpoint
# -> Tenki -> verification FCO -> Mitosis writeback -> Vithia verified context -> decider -> outcome -> final root.
# Successor to vithia_doctor2.sh (kept untouched). All verification logic lives in tools/vithia_fcg.py; this script
# is the Gum UX, worktree isolation, secret entry, commit/push and remote-parity layer.
#
#   bash tools/vithia_doctor3.sh --seed-fco evidence/fcg_seeds/<seed>.json        # interactive
#   bash tools/vithia_doctor3.sh --seed-root sha256:<hex> --resolver-dir evidence/fcg_seeds
#   bash tools/vithia_doctor3.sh --seed-fco S --simulate --non-interactive        # dry run: simulated providers, no git writes
#   bash tools/vithia_doctor3.sh --remote <host> [args]                           # run on another Mac over SSH
#   bash tools/vithia_doctor3.sh --watch DIR --parent-root <hex> --session-id ID  # append successors as files appear
#
# Secrets: entered with `gum input --password`, held only in this process's environment, passed to the engine via the
# environment (never argv), never logged, never written to any artifact. Bash `source` is never used.
set -uo pipefail

SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_SLUG="${VITHIA_REPO_SLUG:-biobitworks/jev-space-invaders}"
LOGDIR="$HOME/.vithia/logs"; mkdir -p "$LOGDIR"; chmod 700 "$HOME/.vithia" 2>/dev/null || true
LOG="$LOGDIR/doctor3-$(date +%Y%m%d-%H%M%S).log"; : > "$LOG"
SECRET_VARS=(MI_API_KEY TENKI_API_KEY TYPESAFE_API_KEY ANTHROPIC_API_KEY OPENAI_API_KEY)

# ---------- args ----------
ORIG_ARGS=("$@")
PRINTFWD=0
SEED_FCO=""; SEED_ROOT=""; RESOLVERS=(); SIM=0; NONINT=0; ENV_FILE=""; IDMODE=""; IDPUB=""; DECIDER=""; DECIDERS=""; PROFILE=""
REMOTE=""; WATCH=""; PARENT_ROOT=""; SESSION_ID=""; REVIEW_PR=""; COMMIT_HOOK_SID=""
while (($#)); do case "$1" in
  --seed-fco) SEED_FCO="$2"; shift 2;;  --seed-root) SEED_ROOT="$2"; shift 2;;  --resolver-dir) RESOLVERS+=("$2"); shift 2;;
  --simulate) SIM=1; shift;;  --non-interactive) NONINT=1; shift;;  --env-file) ENV_FILE="$2"; shift 2;;
  --identity-mode) IDMODE="$2"; shift 2;;  --identity-pub-file) IDPUB="$2"; shift 2;;  --decider) DECIDER="$2"; shift 2;;  --deciders) DECIDERS="$2"; shift 2;;  --prompt-profile) PROFILE="$2"; shift 2;;
  --remote) REMOTE="$2"; shift 2;;  --watch) WATCH="$2"; shift 2;;  --parent-root) PARENT_ROOT="$2"; shift 2;;
  --session-id) SESSION_ID="$2"; shift 2;;  --review-pr) REVIEW_PR="$2"; shift 2;;  --_commit-hook) COMMIT_HOOK_SID="$2"; shift 2;;  --_print-forward-args) PRINTFWD=1; shift;;
  -h|--help) sed -n 2,16p "$SELF"; exit 0;;  *) echo "unknown arg: $1" >&2; exit 2;; esac; done

# Every parsed option except --remote HOST is forwarded (shell-quoted) to the remote invocation.
forward_args() { local skip=0 a out=""; for a in ${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"}; do
    if ((skip)); then skip=0; continue; fi
    case "$a" in --remote) skip=1; continue;; --_print-forward-args) continue;; esac
    out+=" $(printf '%q' "$a")"; done; printf '%s' "${out# }"; }
if ((PRINTFWD)); then forward_args; echo; exit 0; fi

# ---------- ui + redacted logging ----------
have_gum() { command -v gum >/dev/null 2>&1; }
redact() { local s="$1" v; for n in "${SECRET_VARS[@]}"; do v="${!n:-}"; [[ -n "$v" ]] && s="${s//"$v"/<redacted>}"; done; printf '%s' "$s"; }
ok()   { have_gum && gum style --foreground 42 "✔ $*" || echo "OK $*"; echo "OK   $(redact "$*")" >>"$LOG"; }
warn() { have_gum && gum style --foreground 214 "! $*" || echo "WARN $*"; echo "WARN $(redact "$*")" >>"$LOG"; }
die()  { have_gum && gum style --foreground 196 --bold "✘ $*" || echo "FAIL $*"; echo "FAIL $(redact "$*")" >>"$LOG"; echo "log: $LOG"; exit 1; }
hdr()  { have_gum && gum style --border rounded --padding "0 1" --border-foreground 99 --bold "$*" || echo "== $* =="; }
# run: quiet step; the logged command is symbolic for secret-bearing stages and redacted otherwise
run()  { local t="$1"; shift; local c; printf -v c '%q ' "$@"; echo "\$ $(redact "$c")" >>"$LOG"
         if "$@" >>"$LOG" 2>&1; then ok "$t"; else tail -n 25 "$LOG"; die "$t"; fi; }
ask_choose() { if ((NONINT)); then echo "$2"; else have_gum && gum choose --header "$1" "${@:2}" || echo "$2"; fi; }

verify_remote() { git fetch -q origin; local b; b="$(git rev-parse --abbrev-ref HEAD)"
  [[ "$(git rev-parse HEAD)" == "$(git rev-parse "origin/$b")" ]] && ok "origin/$b == local $(git rev-parse --short HEAD)" || die "origin/$b does not match local HEAD"; }

# ---------- hook: commit + push a session dir (called by the engine before Tenki, and at the end) ----------
if [[ -n "$COMMIT_HOOK_SID" ]]; then
  cd "$(git rev-parse --show-toplevel)" || exit 1
  B="$(git rev-parse --abbrev-ref HEAD)"; case "$B" in main|master) echo "refusing to commit sessions on $B" >&2; exit 1;; esac
  python scripts/secret_scan.py >>"$LOG" 2>&1 || { echo "secret scan failed" >&2; exit 1; }
  git add -- "evidence/fcg_sessions/$COMMIT_HOOK_SID" >>"$LOG" 2>&1
  git diff --cached --quiet || git commit -q -m "evidence: fcg session $COMMIT_HOOK_SID checkpoint" >>"$LOG" 2>&1 || exit 1
  git push -q origin "$B" >>"$LOG" 2>&1 || { echo "push failed" >&2; exit 1; }
  git fetch -q origin; [[ "$(git rev-parse HEAD)" == "$(git rev-parse "origin/$B")" ]] || { echo "remote parity failed" >&2; exit 1; }
  git rev-parse HEAD; exit 0
fi

have_gum || { command -v brew >/dev/null && echo "brew install gum" ; die "gum is required (https://github.com/charmbracelet/gum)"; }

# ---------- remote mode (ported from doctor2): fetch this script from git on the host, verify its hash, run there ----------
if [[ -n "$REMOTE" ]]; then
  hdr "Remote mode · $REMOTE"
  ssh -o ConnectTimeout=8 "$REMOTE" true >>"$LOG" 2>&1 || die "cannot ssh to $REMOTE"; ok "ssh $REMOTE"
  B="$(git rev-parse --abbrev-ref HEAD)"; [[ -z "$(git status --porcelain --untracked-files=no)" ]] || die "tracked changes present; commit first"
  git ls-files --error-unmatch tools/vithia_doctor3.sh >/dev/null 2>&1 || die "tools/vithia_doctor3.sh is not committed"
  git fetch -q origin; git diff --quiet "origin/$B" -- tools/vithia_doctor3.sh tools/vithia_fcg.py tools/vithia_e2e_lib.py 2>/dev/null || die "doctor files differ from origin/$B; push first"
  LSHA="$(shasum -a 256 tools/vithia_doctor3.sh | cut -d' ' -f1)"
  RSHA="$(ssh "$REMOTE" "export PATH=/opt/homebrew/bin:/usr/local/bin:\$PATH; C=\$(find \"\$HOME\" -maxdepth 4 -type d -name 'jev*' -not -path '*/Library/*' | while read d; do git -C \"\$d\" remote get-url origin 2>/dev/null | grep -q '$REPO_SLUG' && { echo \"\$d\"; break; }; done); [ -n \"\$C\" ] || exit 3; git -C \"\$C\" fetch -q origin '$B' && git -C \"\$C\" show 'origin/$B:tools/vithia_doctor3.sh' | shasum -a 256 | cut -d' ' -f1")" || die "no clone of $REPO_SLUG on $REMOTE"
  [[ "$RSHA" == "$LSHA" ]] && ok "doctor3 sha256 matches on $REMOTE (${LSHA:0:12}…)" || die "sha256 mismatch local ${LSHA:0:12} vs remote ${RSHA:0:12}"
  [[ -n "$ENV_FILE" ]] && warn "--env-file $ENV_FILE is forwarded as written: it is resolved on $REMOTE, not on this machine"
  gum confirm "Run doctor3 on $REMOTE now? (secrets are entered there, not here)" || exit 0
  ssh -t "$REMOTE" "export PATH=/opt/homebrew/bin:/usr/local/bin:\$PATH; cd \$(find \"\$HOME\" -maxdepth 4 -type d -name 'jev*' -not -path '*/Library/*' | while read d; do git -C \"\$d\" remote get-url origin 2>/dev/null | grep -q '$REPO_SLUG' && { echo \"\$d\"; break; }; done) && git checkout -q '$B' && git pull -q --ff-only && bash tools/vithia_doctor3.sh $(forward_args)"
  exit $?
fi

# ---------- machine + repo ----------
hdr "Vithia doctor 3 · FCG bootstrap · log: $LOG"
for t in git python3; do command -v "$t" >/dev/null || die "$t missing"; done; ok "git, python3"
TOP="$(git rev-parse --show-toplevel 2>/dev/null)" || die "run inside the $REPO_SLUG checkout"
cd "$TOP" || die "cannot cd $TOP"
git remote get-url origin 2>/dev/null | grep -q "$REPO_SLUG" || die "origin is not $REPO_SLUG"
PY="python3"; [[ -x "$TOP/.venv/bin/python" ]] && PY="$TOP/.venv/bin/python"
"$PY" -c "import cryptography" 2>/dev/null || die "python 'cryptography' missing (pip install cryptography)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"; case "$BRANCH" in main|master) die "refusing to write sessions on $BRANCH; use a successor branch";; esac
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || die "tracked changes present; commit or stash first"
git fetch -q origin; ok "branch $BRANCH @ $(git rev-parse --short HEAD)"

# ---------- watch mode ----------
if [[ -n "$WATCH" ]]; then
  [[ -n "$SESSION_ID" && -n "$PARENT_ROOT" ]] || die "--watch needs --session-id and --parent-root"
  MODE=real; ((SIM)) && MODE=sim
  hdr "Watching $WATCH (Ctrl-C to stop)"
  "$PY" tools/vithia_fcg.py watch --session-id "$SESSION_ID" --watch-dir "$WATCH" --parent-root "$PARENT_ROOT" --mitosis "$MODE" --max-events 1000000 \
    ${ENV_FILE:+--env-file "$ENV_FILE"} 2>>"$LOG" | while IFS= read -r line; do
      [[ "$line" == WATCH_ROOT=* ]] && gum style --border double --padding "0 1" --border-foreground 42 "CURRENT ROOT" "${line#WATCH_ROOT=}" || echo "$line"; done
  exit 0
fi

# ---------- 1. seed ----------
hdr "1. Seed"
[[ -n "$SEED_FCO$SEED_ROOT" ]] || die "give --seed-fco FILE or --seed-root sha256:HEX"
SEED_ARGS=(); [[ -n "$SEED_FCO" ]] && SEED_ARGS+=(--seed-fco "$SEED_FCO"); [[ -n "$SEED_ROOT" ]] && SEED_ARGS+=(--seed-root "$SEED_ROOT")
for d in "${RESOLVERS[@]:-}"; do [[ -n "$d" ]] && SEED_ARGS+=(--resolver-dir "$d"); done
SEED_COMMIT="$("$PY" - "${SEED_ARGS[@]}" <<'PY'
import sys, json; sys.path.insert(0, "tools")
import argparse, vithia_fcg as F
from pathlib import Path
ap = argparse.ArgumentParser(); ap.add_argument("--seed-fco"); ap.add_argument("--seed-root"); ap.add_argument("--resolver-dir", action="append", default=[])
a = ap.parse_args()
try:
    seed, root = F.load_seed(Path(a.seed_fco) if a.seed_fco else None, a.seed_root, a.resolver_dir)
except F.Stop as e:
    print(f"STOP {e}", file=sys.stderr); sys.exit(2)
print(seed["source_commit"])
PY
)" || die "SEED_RESOLUTION/SEED_FCO_VERIFY failed (see above); nothing was run"
ok "seed verified · source commit ${SEED_COMMIT:0:12}"

# ---------- 2. isolated, pinned source worktree (branch worktree is not touched) ----------
hdr "2. Pinned source (isolated worktree)"
git cat-file -e "$SEED_COMMIT^{commit}" 2>/dev/null || run "fetch seed commit" git fetch origin "$SEED_COMMIT"
SRC="${TMPDIR:-/tmp}/vithia-source-${SEED_COMMIT:0:12}"
# The pinned source worktree only needs the seed's frozen objects; skip Git LFS smudging so a fresh machine never
# downloads unrelated large LFS data (e.g. data/daisy) just to verify a seed.
if [[ -d "$SRC" ]]; then GIT_LFS_SKIP_SMUDGE=1 git -C "$SRC" checkout -q --detach "$SEED_COMMIT" 2>>"$LOG" || die "cannot pin existing source worktree"
else run "worktree add --detach (exact source commit, LFS smudge skipped)" env GIT_LFS_SKIP_SMUDGE=1 git worktree add -q --detach "$SRC" "$SEED_COMMIT"; fi
[[ "$(git -C "$SRC" rev-parse HEAD)" == "$SEED_COMMIT" ]] && ok "SOURCE_PIN=PASS" || die "SOURCE_PIN=FAIL"

# ---------- 3. operator / judge identity (public key only reaches artifacts) ----------
hdr "3. Operator / Judge identity"
if [[ -z "$IDMODE" ]]; then
  CH="$(ask_choose "Operator / Judge identity" "Anonymous verifier" "Existing public key file" "Paste public key" "Generate new local Ed25519 identity")"
  case "$CH" in "Existing public key file") IDMODE=file;; "Paste public key") IDMODE=paste;; "Generate"*) IDMODE=generate;; *) IDMODE=anonymous;; esac
fi
PUBTMP=""
case "$IDMODE" in
  file) [[ -n "$IDPUB" ]] || IDPUB="$(gum input --placeholder "path to a PUBLIC key PEM")"; [[ -f "$IDPUB" ]] || die "public key file not found"; IDMODE=file;;
  paste) PUBTMP="$(mktemp)"; gum write --placeholder "paste a PUBLIC key PEM (Ctrl-D to finish)" > "$PUBTMP"; IDPUB="$PUBTMP"; IDMODE=file;;
  generate) ok "a local Ed25519 keypair will be generated: private key stays in ~/.vithia/identities (mode 600), never committed or sent anywhere";;
  anonymous) warn "anonymous verifier: checkpoint will not be signed (checkpoint_signature_state=NOT_USED)";;
esac
grep -q "PRIVATE" "${IDPUB:-/dev/null}" 2>/dev/null && die "that file contains PRIVATE key material; supply the public key only"

# ---------- 4. credentials (interactive; process-local) ----------
hdr "4. Credentials"
if ((SIM)); then ok "simulate mode: no credentials needed"
elif ((NONINT)); then
  for n in "${SECRET_VARS[@]}"; do
    if [[ -n "${!n:-}" ]]; then ok "$n=SET (process environment)"
    elif [[ -n "$ENV_FILE" && -f "$ENV_FILE" ]] && grep -Eq "^(export )?${n}=.+" "$ENV_FILE"; then ok "$n=SET (private env file; read in-process by the safe parser, value never printed)"
    else warn "$n=NOT_SET"; fi
  done
else
  SEL="$(gum choose --no-limit --header "Providers to enter keys for (x = toggle; none = SKIP all)" "MI_API_KEY  (Mitosis)" "TENKI_API_KEY  (Tenki)" "TYPESAFE_API_KEY  (hosted JEV)" "ANTHROPIC_API_KEY" "OPENAI_API_KEY")" || SEL=""
  while IFS= read -r line; do n="${line%% *}"; [[ -z "$n" ]] && continue
    v="$(gum input --password --placeholder "$n (hidden)")"; [[ -n "$v" ]] && export "$n=$v" && ok "$n=SET" || warn "$n skipped"; done <<<"$SEL"
  if [[ -n "$SEL" ]] && [[ "$(gum choose --header "Persist keys?" "No — this process only" "Yes — private chmod-600 file outside git (~/.vithia/credentials.env)")" == Yes* ]]; then
    "$PY" - <<'PY'
import os, pathlib
names = ["MI_API_KEY", "TENKI_API_KEY", "TYPESAFE_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"]
p = pathlib.Path.home() / ".vithia/credentials.env"; p.parent.mkdir(exist_ok=True)
fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f:
    f.write("".join(f"export {n}={os.environ[n]}\n" for n in names if os.environ.get(n)))
print("private credential file written (mode 600)")
PY
    ok "persisted to ~/.vithia/credentials.env (mode 600). Keychain storage is not implemented."
    ENV_FILE="${ENV_FILE:-$HOME/.vithia/credentials.env}"
  fi
fi

# ---------- 5. decider + Tenki review preferences ----------
if [[ -n "$DECIDERS" && -z "$DECIDER" ]]; then DECIDER=scripted; fi
if [[ -z "$DECIDER" ]]; then DECIDER="$(ask_choose "Decider (same Vithia verified-context interface for all; no silent fallback)" scripted "local Ollama" OpenJEV "hosted JEV" "skip decision")"
  case "$DECIDER" in "local Ollama") DECIDER=ollama;; OpenJEV) DECIDER=openjev;; "hosted JEV") DECIDER=jev;; "skip decision") DECIDER=skip;; esac; fi
POST=(); if [[ -n "$REVIEW_PR" ]] && ((! SIM)) && ((! NONINT)); then gum confirm "Post an @tenki-reviewer request on PR #$REVIEW_PR? (visible to others; uses review credit)" && POST=(--post-review-comment); fi

# ---------- 6. run the pipeline ----------
hdr "5. Vithia → Mitosis → checkpoint → Tenki → writeback → verified context → decider → final root"
SID="${SESSION_ID:-FCG-$(date -u +%Y%m%dT%H%M%SZ)-$(printf '%04x' $RANDOM)}"
[[ -e "evidence/fcg_sessions/$SID" ]] && die "session directory evidence/fcg_sessions/$SID already exists; sessions are append-only and never reused"
PROV=(--mitosis real --tenki real); ((SIM)) && PROV=(--mitosis sim --tenki sim)
HOOK=(); ((SIM)) || HOOK=(--commit-hook "env VITHIA_BRANCH=$BRANCH bash $SELF --_commit-hook $SID")
export PYTHONUNBUFFERED=1
"$PY" tools/vithia_fcg.py run "${SEED_ARGS[@]}" --source-dir "$SRC" --session-id "$SID" --identity-mode "$IDMODE" ${IDPUB:+--identity-pub-file "$IDPUB"} \
  --decider "$DECIDER" ${DECIDERS:+--deciders "$DECIDERS"} ${PROFILE:+--prompt-profile "$PROFILE"} "${PROV[@]}" ${HOOK[@]+"${HOOK[@]}"} ${REVIEW_PR:+--review-pr "$REVIEW_PR"} ${POST[@]+"${POST[@]}"} ${ENV_FILE:+--env-file "$ENV_FILE"} 2> >(while IFS= read -r l; do echo "$(redact "$l")" >>"$LOG"; done) | tee -a "$LOG"
RC=${PIPESTATUS[0]}
[[ -n "$PUBTMP" ]] && rm -f "$PUBTMP"
((RC == 0)) || die "pipeline stopped (exit $RC): see $LOG — nothing after the failing integrity check was executed"

# ---------- 7. seal: scan, commit, push, remote parity ----------
hdr "6. Seal"
run "secret scan (repo)" "$PY" scripts/secret_scan.py
if ((SIM)); then warn "simulate mode: session left uncommitted in evidence/fcg_sessions/$SID (simulated providers; not evidence of real provider behaviour)"
else
  git add -- "evidence/fcg_sessions/$SID"; git diff --cached --quiet || run "commit session" git commit -q -m "evidence: seal fcg session $SID"
  run "push origin $BRANCH" git push -q origin "$BRANCH"; verify_remote
fi

# ---------- 8. summary ----------
R="evidence/fcg_sessions/$SID/VITHIA_DOCTOR_SESSION_RECEIPT.json"
"$PY" - "$R" "$(git rev-parse --abbrev-ref HEAD)@$(git rev-parse --short HEAD)" "$(((SIM)) && echo NOT_PUSHED_SIMULATED || echo PASS)" <<'PY' | gum style --border double --padding "1 2" --border-foreground 42
import json, sys
r = json.load(open(sys.argv[1])); g = lambda k: r.get(k)
print("VITHIA FCG SESSION COMPLETE\n")
print(f"Seed:            {g('seed_root')}")
print(f"Operator:        {g('operator_public_key_fingerprint')} ({g('operator_identity_mode')})")
print(f"Mitosis:         auth {g('mitosis_auth')} · exact retrieval {g('mitosis_exact_retrieval')}")
print(f"Mitosis id:      {g('mitosis_initial_universal_id')}   (address, not a root)")
print(f"Tenki review:    {g('tenki_code_review')}")
print(f"Tenki execution: auth {g('tenki_auth')} · artifact {g('tenki_artifact_verify')} · session {g('tenki_session')}")
print(f"Replay:          {g('tenki_environment_replay')}  first mismatch {g('tenki_first_mismatch')}")
print(f"Decider:         {g('decider')}")
print(f"PRE CHECKPOINT:  {g('pre_exec_mmr_root')}")
print(f"POST VERIFY:     {g('post_verify_mmr_root')}")
print(f"FINAL FCG ROOT:  {g('final_fcg_mmr_root')}")
print(f"Signature:       {g('checkpoint_signature_state')}")
print(f"Secret scan:     {g('secret_scan')}   Provider mode: {g('provider_mode')}")
print(f"Git:             {sys.argv[2]}   Origin parity: {sys.argv[3]}")
PY
echo "log: $LOG"
