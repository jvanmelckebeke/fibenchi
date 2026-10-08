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
  'companion.portfolio-index.schema.json',
  'indicator.contract.json',
  'indicator.contract.schema.json',
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

// Typed against the schema's inferred type, so tsc rejects contract data that does not
// match its own schema and the app pays no runtime parse.
function indicatorModule() {
  const contract = readArtifact('indicator.contract.json');
  return (
    HEADER('indicator.contract.json') +
    `import type { z } from 'zod';\n` +
    `import type { indicatorContractSchema } from './indicator.schema.js';\n\n` +
    `export const INDICATOR_CONTRACT: z.infer<typeof indicatorContractSchema> = ` +
    `${JSON.stringify(contract, null, 2)};\n`
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
writeFileSync(
  join(GENERATED, 'portfolio-index.schema.ts'),
  zodModule('companion.portfolio-index.schema.json', 'companionPortfolioIndexSchema'),
);
writeFileSync(
  join(GENERATED, 'indicator.schema.ts'),
  zodModule('indicator.contract.schema.json', 'indicatorContractSchema'),
);
writeFileSync(join(GENERATED, 'indicators.ts'), indicatorModule());

execFileSync(join(ROOT, 'node_modules', '.bin', 'tsc'), ['-p', ROOT], { stdio: 'inherit' });

for (const name of ARTIFACTS) copyFileSync(join(BACKEND, name), join(DIST, name));
console.log(`built ${DIST}`);
