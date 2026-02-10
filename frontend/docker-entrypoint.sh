#!/bin/sh
set -e
CI=true pnpm install --frozen-lockfile
# pnpm v10 blocks postinstall scripts by default; ensure esbuild binary is executable
chmod +x node_modules/.pnpm/@esbuild+linux-x64@*/node_modules/@esbuild/linux-x64/bin/esbuild 2>/dev/null || true
exec pnpm dev --host
