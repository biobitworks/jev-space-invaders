#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PYTHON:-python3}"
EXPLORER="$ROOT/tools/mitosis_fcg_explorer.py"

command -v gum >/dev/null 2>&1 || {
  echo "BLOCKED_MISSING_GUM"
  exit 2
}

if [[ -z "${MI_API_KEY:-}" && -z "${MITOSIS_API_KEY:-}" ]]; then
  MI_API_KEY="$(gum input --password --prompt "Mitosis API key: " --placeholder "mi_…")"
  export MI_API_KEY
fi
trap 'unset MI_API_KEY MITOSIS_API_KEY 2>/dev/null || true' EXIT

open_graph_url() {
  local url="$1"
  [[ -n "$url" && "$url" != "None" ]] || return 0
  gum style --border normal --padding "0 1" "Mitosis graph" "$url"
  if command -v open >/dev/null 2>&1 && gum confirm "Open graph in browser?"; then
    open "$url" >/dev/null 2>&1 || true
  fi
}

while true; do
  choice="$(gum choose     "Materialize executed FCG into Mitosis"     "Probe universal ID / FCO hash / breakpoint / MMR root"     "Verify graph against local FCO/MMR evidence"     "Exit")"

  case "$choice" in
    "Materialize executed FCG into Mitosis")
      tmp_plan="$(mktemp)"
      "$PY" "$EXPLORER" materialize --dry-run >"$tmp_plan"
      node_count="$("$PY" - "$tmp_plan" <<'PY'
import json,sys
print(len(json.load(open(sys.argv[1]))["nodes"]))
PY
)"
      gum style "Planned graph nodes: $node_count"
      if gum confirm "Write/update these idempotent graph nodes in Mitosis?"; then
        tmp_out="$(mktemp)"
        "$PY" "$EXPLORER" materialize | tee "$tmp_out"
        url="$(awk -F= '/^MITOSIS_CITED_GRAPH_URL=/{sub(/^MITOSIS_CITED_GRAPH_URL=/,""); print; exit}' "$tmp_out")"
        open_graph_url "$url"
      fi
      ;;
    "Probe universal ID / FCO hash / breakpoint / MMR root")
      token="$(gum input --prompt "Probe: " --placeholder "agent:… | SHA256 | BP ID | MMR root")"
      [[ -n "$token" ]] || continue
      tmp_out="$(mktemp)"
      "$PY" "$EXPLORER" probe "$token" | tee "$tmp_out"
      url="$(awk -F= '/^PROBE_CITED_GRAPH_URL=/{sub(/^PROBE_CITED_GRAPH_URL=/,""); print; exit}' "$tmp_out")"
      open_graph_url "$url"
      ;;
    "Verify graph against local FCO/MMR evidence")
      "$PY" "$EXPLORER" verify
      ;;
    "Exit")
      break
      ;;
  esac
done
