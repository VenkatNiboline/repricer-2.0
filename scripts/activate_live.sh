#!/usr/bin/env bash
# Activate the pricing tool for production use.
# Run from repo root: ./scripts/activate_live.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/ENV/AmazonCredentials.env"
cd "$ROOT"

red() { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[1;33m%s\033[0m\n' "$*"; }

if [ ! -f "$ENV_FILE" ]; then
  red "Missing $ENV_FILE — copy from ENV/AmazonCredentials.env.example"
  exit 1
fi

# shellcheck disable=SC1090
source <(grep -E '^[A-Z_]+=' "$ENV_FILE" | sed 's/^/export /')

echo "=== Amazon Repricer — Go Live Checklist ==="
echo

# 1. Amazon API
if [ "${AMAZON_API_ENABLED:-false}" = "true" ]; then
  green "[ok] AMAZON_API_ENABLED=true (local)"
else
  red "[!!] Set AMAZON_API_ENABLED=true in ENV/AmazonCredentials.env"
  exit 1
fi

for key in LWA_REFRESH_TOKEN LWA_CLIENT_ID LWA_CLIENT_SECRET SELLER_ID; do
  if [ -z "${!key:-}" ]; then
    red "[!!] Missing $key in ENV/AmazonCredentials.env"
    exit 1
  fi
done
green "[ok] Amazon SP-API credentials present"

# 2. Supabase service role (required for history, catalog writes, QC, sales)
if [ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  yellow "[action] SUPABASE_SERVICE_ROLE_KEY is empty."
  echo "  → Supabase Dashboard → Project Settings → API → service_role"
  echo "  → Paste into ENV/AmazonCredentials.env, then re-run this script."
  exit 1
fi
green "[ok] SUPABASE_SERVICE_ROLE_KEY set"

for key in SUPABASE_URL SUPABASE_ANON_KEY CRON_SECRET; do
  if [ -z "${!key:-}" ]; then
    red "[!!] Missing $key in ENV/AmazonCredentials.env"
    exit 1
  fi
done
green "[ok] Supabase URL, anon key, and CRON_SECRET set"

# 3. Vercel env sync
if ! npx --yes vercel@latest whoami &>/dev/null; then
  yellow "[action] Vercel CLI not logged in. Run: npx vercel login"
  exit 1
fi
green "[ok] Vercel CLI authenticated"

echo
echo "Syncing env vars to Vercel (production + preview)..."
"$ROOT/scripts/sync_vercel_env.sh"

# 4. Redeploy production
echo
echo "Redeploying production..."
npx --yes vercel@latest deploy --prod --yes

# 5. Health check
APP_URL="${VERCEL_APP_URL:-https://repricer-2-0.vercel.app}"
echo
echo "Waiting for deployment health check..."
sleep 8
HEALTH=$(curl -s "$APP_URL/api/health" || true)
echo "$HEALTH" | python3 -m json.tool 2>/dev/null || echo "$HEALTH"

if echo "$HEALTH" | grep -q '"amazon_api_enabled": true'; then
  green "[ok] amazon_api_enabled=true on production"
else
  yellow "[warn] amazon_api_enabled is still false — confirm Vercel env and redeploy"
fi

if echo "$HEALTH" | grep -q '"db_write_ready": true'; then
  green "[ok] db_write_ready=true on production"
else
  yellow "[warn] db_write_ready is false — SUPABASE_SERVICE_ROLE_KEY may be missing on Vercel"
fi

echo
yellow "Supabase Edge Function secrets (Dashboard → Edge Functions → Secrets):"
echo "  AMAZON_API_ENABLED=true"
echo "  CRON_SECRET=<same as ENV/AmazonCredentials.env>"
echo "  LWA_REFRESH_TOKEN, LWA_CLIENT_ID, LWA_CLIENT_SECRET, SELLER_ID"
echo
yellow "Supabase project must be ACTIVE (not paused). Cron jobs:"
echo "  sync-amazon-catalog (every 6h), sync-amazon-sales (daily 06:00 UTC), verify-price-reflections (every minute)"
echo
green "Live app: $APP_URL"
echo "Sign in, run Sync catalog on Overview, then test Reprice (dry-run first)."
