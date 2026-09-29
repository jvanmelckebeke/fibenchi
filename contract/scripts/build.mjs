// Build the package from the artifacts the backend exporters write to backend/.
// Those JSON files stay the single source of truth; nothing here is edited by hand.

import { execFileSync } from 'node:child_process';
import { copyFileSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import jsonSchemaToZodPkg from 'json-schema-to-zod';

const jsonSchemaToZod =
  jsonSchemaToZodPkg.jsonSchemaToZod ?? jsonSchemaToZodPkg.default ?? jsonSchemaToZodPkg;

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const BACKEND = join(ROOT, '..', 'backend');
const GENERATED = join(ROOT, 'src', 'generated');
const DIST = join(ROOT, 'dist');

const ARTIFACTS = [
  'companion.schema.json',
  'companion.calendar.schema.json',
  'indicator.contract.json',
  'indicator.fixtures.json',
];

const HEADER = (source) =>
  `// GENERATED from backend/${source} by contract/scripts/build.mjs. Do not edit by hand.\n`;

const readArtifact = (name) => JSON.parse(readFileSync(join(BACKEND, name), 'utf8'));

// json-schema-to-zod expects draft-07 `definitions` and does not resolve Pydantic's
// 2020-12 `$defs`/`$ref`, so nested models would collapse to z.any(). Inline them.
function deref(node, defs) {
  if (Array.isArray(node)) return node.map((n) => deref(n, defs));
  if (node && typeof node === 'object') {
    if (typeof node.$ref === 'string') {
      const name = node.$ref.split('/').pop();
      if (!defs[name]) throw new Error(`unresolved $ref: ${node.$ref}`);
      return deref(defs[name], defs);
    }
    const out = {};
    for (const [key, value] of Object.entries(node)) {
      if (key === '$defs' || key === 'definitions') continue;
      out[key] = deref(value, defs);
    }
    return out;
  }
  return node;
}

function zodModule(source, name) {
  const schema = readArtifact(source);
  const code = jsonSchemaToZod(deref(schema, schema.$defs ?? schema.definitions ?? {}), {
    name,
    module: 'esm',
  });
  return HEADER(source) + code + '\n';
}

// The interface is written out rather than inferred so a new or renamed field in the
// exporter fails this build instead of silently widening the type.
const INDICATOR_FIELDS = [
  'decimals',
  'deltaFields',
  'fieldDecimals',
  'kernel',
  'key',
  'outputFields',
  'params',
  'platforms',
  'snapshotDerived',
  'usesOhlc',
  'warmup',
];

function indicatorModule() {
  const contract = readArtifact('indicator.contract.json');
  for (const indicator of contract.indicators) {
    const keys = Object.keys(indicator).sort();
    if (keys.join() !== INDICATOR_FIELDS.join()) {
      throw new Error(
        `indicator ${indicator.key} has fields [${keys}], expected [${INDICATOR_FIELDS}]. ` +
          'Update IndicatorSpec in contract/scripts/build.mjs to match the exporter.',
      );
    }
  }
  return (
    HEADER('indicator.contract.json') +
    `export type Platform = 'web' | 'app';\n\n` +
    `export interface IndicatorSpec {\n` +
    `  key: string;\n` +
    `  kernel: string;\n` +
    `  params: Record<string, number>;\n` +
    `  outputFields: string[];\n` +
    `  deltaFields: string[];\n` +
    `  decimals: number;\n` +
    `  fieldDecimals: Record<string, number>;\n` +
    `  warmup: number;\n` +
    `  usesOhlc: boolean;\n` +
    `  snapshotDerived: string | null;\n` +
    `  platforms: Platform[];\n` +
    `}\n\n` +
    `export interface IndicatorContract {\n` +
    `  version: number;\n` +
    `  indicators: IndicatorSpec[];\n` +
    `}\n\n` +
    `export const INDICATOR_CONTRACT: IndicatorContract = ${JSON.stringify(contract, null, 2)};\n`
  );
}

rmSync(GENERATED, { recursive: true, force: true });
rmSync(DIST, { recursive: true, force: true });
mkdirSync(GENERATED, { recursive: true });

writeFileSync(
  join(GENERATED, 'config.schema.ts'),
  zodModule('companion.schema.json', 'companionConfigSchema'),
);
writeFileSync(
  join(GENERATED, 'calendar.schema.ts'),
  zodModule('companion.calendar.schema.json', 'companionCalendarSchema'),
);
writeFileSync(join(GENERATED, 'indicators.ts'), indicatorModule());

execFileSync(join(ROOT, 'node_modules', '.bin', 'tsc'), ['-p', ROOT], { stdio: 'inherit' });

for (const name of ARTIFACTS) copyFileSync(join(BACKEND, name), join(DIST, name));
console.log(`built ${DIST}`);
