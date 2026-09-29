#!/usr/bin/env bash
set -euo pipefail

VERSION="0.27.2"
BASE="${VITHIA_MI_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/vithia/mitosis-cli-$VERSION}"
BIN="$BASE/node_modules/.bin/mi"

if [[ ! -x "$BIN" ]]; then
  command -v npm >/dev/null 2>&1 || {
    echo "BLOCKED_MISSING_NPM" >&2
    exit 2
  }
  mkdir -p "$BASE"
  cat >"$BASE/package.json" <<JSON
{"name":"vithia-mitosis-cli-runtime","version":"1.0.0","private":true,"dependencies":{"@mitosislabs/sdk":"$VERSION"}}
JSON
  (
    unset MI_API_KEY MITOSIS_API_KEY TENKI_API_KEY TYPESAFE_API_KEY ANTHROPIC_API_KEY OPENAI_API_KEY
    unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
    cd "$BASE"
    npm install --ignore-scripts --no-audit --no-fund --save-exact "@mitosislabs/sdk@$VERSION" >/dev/null
  )
fi

actual="$(node -p "require('$BASE/node_modules/@mitosislabs/sdk/package.json').version")"
if [[ "$actual" != "$VERSION" ]]; then
  echo "MITOSIS_CLI_VERSION_MISMATCH expected=$VERSION observed=$actual" >&2
  exit 3
fi

lock_sha="NOT_AVAILABLE"
if [[ -f "$BASE/package-lock.json" ]]; then
  lock_sha="$(shasum -a 256 "$BASE/package-lock.json" | awk '{print $1}')"
fi

echo "MITOSIS_CLI_VERSION=$actual" >&2
echo "MITOSIS_CLI_RUNTIME_LOCK_SHA256=$lock_sha" >&2
printf '%s\n' "$BIN"
