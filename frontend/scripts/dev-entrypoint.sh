#!/bin/sh
set -eu
cd /app

# The volume survives restarts; reinstall only when dependencies or Node change.
fingerprint="$(node -e 'const fs=require("node:fs"),crypto=require("node:crypto");const h=crypto.createHash("sha256");for(const f of ["package.json","package-lock.json"])h.update(fs.readFileSync(f));h.update(JSON.stringify([process.version,process.platform,process.arch]));process.stdout.write(h.digest("hex"))')"
stamp=node_modules/.ywddzx-dev-dependencies
if [ ! -x node_modules/.bin/vite ] || [ ! -f "$stamp" ] || [ "$(cat "$stamp")" != "$fingerprint" ]; then
  echo "Installing locked frontend dependencies (first start or dependency change)..."
  npm ci --prefer-offline --no-audit --no-fund --fetch-retries=2 --fetch-timeout=30000
  printf '%s' "$fingerprint" > "$stamp"
else
  echo "Frontend dependencies unchanged; reusing node_modules."
fi
exec npm run dev -- --host 0.0.0.0 --strictPort
