# @jvanmelckebeke/fibenchi-contract

The contract between the fibenchi backend and the companion app
([fibenchi-app](https://github.com/jvanmelckebeke/fibenchi-app)). It holds:

- `companionConfigSchema` and `companionCalendarSchema`, Zod schemas for
  `GET /api/companion/config` and `GET /api/companion/calendar`
- `INDICATOR_CONTRACT`, the indicator registry metadata
- the raw artifacts as JSON subpaths, including
  `@jvanmelckebeke/fibenchi-contract/indicator.fixtures.json`, the golden
  fixtures that pin the app's kernels to the pandas reference

The backend exporters in `backend/scripts/` write the four JSON artifacts, and
`npm run build` generates everything else from them. Zod is a peer dependency, so
the schemas run on the consumer's own `zod` 3 instance.

## Versions

CI publishes from `.github/workflows/ci.yaml`:

- a push to `dev` publishes `<version>-dev.<hash>` under the `dev` dist-tag
- a push to `main` publishes `<version>` under `latest`

`<hash>` digests the built contents, so a push that doesn't change the contract
publishes nothing. The deployed instance runs the `dev` image, so the app pins
the `dev` prerelease that matches it, not `latest`.

Bump `version` in `package.json` in the PR that changes a contract. CI fails a
PR that changes the artifacts without a bump. Use major when a bundle version
(`CONFIG_VERSION`, `CALENDAR_VERSION`) changes, minor for an additive change
(a new indicator or field), and patch otherwise. The two bundles version
independently at runtime, but the package has only one major.

## Bootstrapping the registry

npm trusted publishing can only be configured on a package that already exists,
so the first version goes up by hand. Until then CI skips the publish with a
notice. Run this once with npm 11.15 or later, on an account with 2FA enabled:

```bash
mkdir -p /tmp/fibenchi-contract-bootstrap && cd /tmp/fibenchi-contract-bootstrap
cat > package.json <<'EOF'
{
  "name": "@jvanmelckebeke/fibenchi-contract",
  "version": "0.0.0",
  "description": "Placeholder. Real versions are published by fibenchi CI.",
  "license": "Apache-2.0"
}
EOF
npm login
npm publish --access public
npm trust github @jvanmelckebeke/fibenchi-contract \
  --repo jvanmelckebeke/fibenchi --file ci.yaml --allow-publish
```

The web form under the package's Settings > Trusted Publisher does the same:
owner `jvanmelckebeke`, repository `fibenchi`, workflow `ci.yaml`, no
environment. After that, re-run the `contract` job on the latest `dev` push.
