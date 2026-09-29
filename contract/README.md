# @jvanmelckebeke/fibenchi-contract

The contract between the fibenchi backend and the companion app
([fibenchi-app](https://github.com/jvanmelckebeke/fibenchi-app)). It holds:

- `companionConfigSchema` and `companionCalendarSchema`, Zod schemas for
  `GET /api/companion/config` and `GET /api/companion/calendar`
- `indicatorContractSchema` and `INDICATOR_CONTRACT`, the indicator registry metadata
  and its Zod schema
- the raw artifacts as JSON subpaths, including
  `@jvanmelckebeke/fibenchi-contract/indicator.fixtures.json`, the golden
  fixtures that pin the app's kernels to the pandas reference

The backend exporters in `backend/scripts/` write the JSON artifacts, and
`npm run build` generates everything else from them. Zod is a peer dependency, so
the schemas run on the consumer's own `zod` 3 instance.

The package is ESM-only. Jest (including `jest-expo`) does not transform ESM under
`node_modules`, so a Jest consumer has to exempt it in `transformIgnorePatterns`.

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

The first version was published by hand, because npm can only configure trusted
publishing on a package that already exists.
