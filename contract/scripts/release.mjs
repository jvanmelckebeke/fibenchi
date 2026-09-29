// Publish the built package from CI. Run after `npm run build`.
//
//   node scripts/release.mjs dev     -> <version>-dev.<hash> under the `dev` dist-tag
//   node scripts/release.mjs latest  -> <version> under `latest`
//
// <hash> is a digest of what the tarball would contain, so a push that leaves the
// contract untouched maps to a version that already exists and publishes nothing.
// The deployed instance runs the dev image, so the app pins the dev prerelease that
// matches it; `latest` follows main for anyone starting from a clean clone.

import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const channel = process.argv[2];
if (channel !== 'dev' && channel !== 'latest') {
  console.error('usage: release.mjs dev|latest');
  process.exit(2);
}

const pkgPath = join(ROOT, 'package.json');
const pkg = JSON.parse(readFileSync(pkgPath, 'utf8'));

function contentHash() {
  const hash = createHash('sha256');
  const walk = (dir) =>
    readdirSync(dir, { withFileTypes: true })
      .sort((a, b) => a.name.localeCompare(b.name))
      .forEach((entry) => {
        const path = join(dir, entry.name);
        if (entry.isDirectory()) return walk(path);
        hash.update(relative(ROOT, path)).update('\0').update(readFileSync(path));
      });
  walk(join(ROOT, 'dist'));
  const { version, contentHash: _, ...manifest } = pkg;
  hash.update(JSON.stringify(manifest));
  return hash.digest('hex').slice(0, 12);
}

function publishedVersions() {
  try {
    const out = execFileSync('npm', ['view', pkg.name, 'versions', '--json'], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    return [].concat(JSON.parse(out));
  } catch (err) {
    if (/E404/.test(String(err.stderr))) return null;
    throw err;
  }
}

const hash = contentHash();
const target = channel === 'dev' ? `${pkg.version}-dev.${hash}` : pkg.version;
const versions = publishedVersions();

// Trusted publishing can only be configured on a package that already exists, so the
// first version is published by hand. Until then there is nothing CI is allowed to
// publish to.
if (versions === null) {
  console.log(`::notice::${pkg.name} is not on the registry yet; skipping publish until the first version is published by hand.`);
  process.exit(0);
}

if (versions.includes(target)) {
  const published = execFileSync('npm', ['view', `${pkg.name}@${target}`, 'contentHash'], {
    encoding: 'utf8',
  }).trim();
  if (published === hash) {
    console.log(`${pkg.name}@${target} is already published with this content`);
    process.exit(0);
  }
  console.error(
    `::error::${pkg.name}@${target} is already published with different content ` +
      `(${published || 'none'} vs ${hash}). Bump the version in contract/package.json.`,
  );
  process.exit(1);
}

writeFileSync(pkgPath, JSON.stringify({ ...pkg, version: target, contentHash: hash }, null, 2) + '\n');
execFileSync('npm', ['publish', '--access', 'public', '--tag', channel], {
  cwd: ROOT,
  stdio: 'inherit',
});
console.log(`published ${pkg.name}@${target} (${channel})`);
