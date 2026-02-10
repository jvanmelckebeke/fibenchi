#!/bin/sh
set -e
CI=true pnpm install --frozen-lockfile
exec pnpm dev --host
