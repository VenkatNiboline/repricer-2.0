#!/usr/bin/env bash
# Sync backend secrets from ENV/AmazonCredentials.env to Vercel (production + preview).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/ENV/AmazonCredentials.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE"
  exit 1
fi

cd "$ROOT"

add_env() {
  local key="$1"
  local value="$2"
  local env_name="$3"
  if [ -z "$value" ]; then
    echo "Skip $key ($env_name) — empty"
    return
  fi
  printf '%s' "$value" | npx --yes vercel@latest env add "$key" "$env_name" --force 2>&1 | tail -3
}

while IFS='=' read -r key value; do
  [[ "$key" =~ ^#.*$ ]] && continue
  [[ -z "$key" ]] && continue
  case "$key" in
    LWA_*|SELLER_ID|SUPABASE_*)
      add_env "$key" "$value" production
      add_env "$key" "$value" preview
      ;;
  esac
done < <(grep -E '^[A-Z_]+=' "$ENV_FILE")

echo "Done. Redeploy for changes to take effect."
