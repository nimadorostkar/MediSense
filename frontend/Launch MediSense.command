#!/bin/bash
# Double-click to start the MediSense dev server.
cd "$(dirname "$0")" || exit 1
echo "Starting MediSense…"

# Ensure dependencies are installed AND match this machine's platform.
# (If node_modules was created on another OS, the native Rollup/esbuild
#  binaries won't load — reinstall cleanly in that case.)
needs_install=0
if [ ! -d node_modules ]; then
  needs_install=1
elif ! node -e "require('@rollup/rollup-darwin-x64')" 2>/dev/null \
   && ! node -e "require('@rollup/rollup-darwin-arm64')" 2>/dev/null; then
  echo "Dependencies were built for another platform — reinstalling…"
  rm -rf node_modules package-lock.json
  needs_install=1
fi

if [ "$needs_install" = "1" ]; then
  echo "Installing dependencies…"
  npm install || { echo "npm install failed"; exit 1; }
fi

exec npm run dev
