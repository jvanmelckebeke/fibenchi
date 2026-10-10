// Fail a PR that changes what the package ships without bumping its version.
//
//   node scripts/check-version.mjs <base-ref>
//
// Without this, main's publish would find the version already on the registry with
// other content and fail after the merge, when the fix costs another PR.

import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const base = process.argv[2];
if (!base) {
  console.error('usage: check-version.mjs <base-ref>');
  process.exit(2);
}

const git = (...args) => execFileSync('git', args, { cwd: ROOT, encoding: 'utf8' });

const SHIPPED = [
  ':/backend/companion.schema.json',
  ':/backend/companion.calendar.schema.json',
  ':/backend/companion.portfolio-index.schema.json',
  ':/backend/companion.pulse.schema.json',
  ':/backend/indicator.contract.json',
  ':/backend/indicator.contract.schema.json',
  ':/backend/indicator.fixtures.json',
  ':/contract/src/index.ts',
  ':/contract/scripts/build.mjs',
  ':/contract/tsconfig.json',
];

const changed = git('diff', '--name-only', `${base}...HEAD`, '--', ...SHIPPED).trim();
if (!changed) process.exit(0);

let baseVersion;
try {
  baseVersion = JSON.parse(git('show', `${base}:contract/package.json`)).version;
} catch {
  process.exit(0); // the package does not exist on the base branch yet
}

const version = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8')).version;
if (version === baseVersion) {
  console.error(
    `::error::The contract changed but contract/package.json is still ${version}.\n` +
      `Changed:\n${changed}\n` +
      'Bump it: major when a bundle version (CONFIG_VERSION, CALENDAR_VERSION, PORTFOLIO_INDEX_VERSION, PULSE_VERSION) changes, ' +
      'minor for an additive change such as a new indicator or field, patch otherwise.',
  );
  process.exit(1);
}
