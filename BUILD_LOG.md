# Build Log: Life360 SwaggerHub → Postman v12 Migration

## Context
- AE / CSE: Daniel Shively (CSE)
- Customer technical lead: Life360 — API platform team (Jeff)
- Sprint dates: TBD

## Hypothesis
- If we automate the migration of Life360's API catalog from SwaggerHub to Postman v12 using the postman-cs GitHub Action suite, we will give Life360 a single pane of glass for API governance, testing, and catalog management — with CI enforcement from day one.

## Success Criteria
- Every OpenAPI spec in the manifest is onboarded to Postman v12 (workspace, Spec Hub entry, collections, environments)
- Governance groups are assigned automatically during bootstrap
- Contract and smoke tests run in CI on every merge via auto-generated workflows
- PR-time linting enforces OpenAPI standards before specs reach Postman
- The Postman API Catalog surfaces all Life360 APIs as the central registry
- Adding a new API requires only a YAML file and a manifest entry — no manual Postman work

## Environment Baseline
- SCM: GitHub (postman-cs/Cust-LIFE360-spechub-uploader)
- CI/CD: GitHub Actions (postman-cs action suite v0 open-alpha)
- Gateway: N/A
- Cloud: N/A (GitHub-hosted runners)
- Dev Portal: N/A
- Current Postman usage: Target workspaces receive specs, collections, environments via onboarding actions
- Postman version: **v12** — Spec Hub, API Catalog, Collection v3 YAML export, Bifrost workspace linking

## What We Built

### Sprint 1 — Manual Upload Script (completed)
- Python upload script (`tools/upload_postman_apis.py`) for bulk spec migration
- Creates Spec Hub entries, generates collections, creates environments
- Idempotent (skips existing specs)
- Sample OpenAPI 3.0 spec: Life360 Circles API

### Sprint 2 — GitHub Actions CI Pipeline (current)
- **Onboarding workflow** (`.github/workflows/onboard-apis.yml`)
  - Reads `life360-api-manifest.json` and builds a dynamic matrix of APIs
  - Runs `postman-cs/postman-api-onboarding-action@v0` per API
  - Chains: bootstrap (workspace + spec + collections + governance) → repo-sync (environments + monitors + CI + git link)
  - Writes onboarding summary to GitHub Actions step summary
  - Supports `workflow_dispatch` with single-API filter for targeted reruns
- **Governance workflow** (`.github/workflows/api-governance.yml`)
  - PR gate: Spectral OpenAPI linting, manifest validation, spec structure checks
  - Blocks merge on spec violations
- **Spectral ruleset** (`.spectral.yaml`)
  - Extends `spectral:oas` with Life360-specific rule overrides
  - Enforces `servers`, `operationId`, descriptions
- **API manifest** (`life360-api-manifest.json`)
  - Central registry of all APIs to onboard
  - Supports per-API environments, runtime URLs, and optional SwaggerHub URL overrides
- **Auto-generated CI** — repo-sync creates `postman-ci-<name>.yml` per API for ongoing smoke and contract testing

### Sprint 3 — Private API Network Promotion (current)
- **Promotion workflow** (`.github/workflows/promote-to-private-network.yml`)
  - Triggers automatically after onboarding or CI pipelines succeed on `main`
  - Quality gate checks: verifies most recent onboard + CI runs passed before promoting
  - Creates a Private API Network folder (idempotent) using the Postman API (`POST /network/private`)
  - Adds qualifying workspaces to the folder; skips already-listed workspaces
  - Supports `workflow_dispatch` with single-API filter and force-promote override
  - Folder name and description configurable via `private_network` block in `life360-api-manifest.json`
- Uses Postman Private API Network REST API: `GET /network/private`, `POST /network/private`

## Value Unlocked
- **Single pane of glass**: every Life360 API visible in Postman v12 API Catalog
- **Governance from CI**: Spectral lint on PR, Postman governance groups on merge
- **Testing from CI**: contract and smoke tests auto-generated and run per API
- **Zero manual Postman work**: adding an API = YAML file + manifest entry + push
- **Private API Network as quality gate**: only APIs passing lint, smoke, and contract tests are promoted to the team's Private API Network — discoverable by all team members
- **Workspace-repo linking**: Bifrost connects each Postman workspace to the GitHub repo
- **Collection v3 export**: collections synced back to repo as multi-file YAML for version control

## Reusable Pattern
- Manifest-driven API onboarding (adaptable to any org migrating from SwaggerHub or any OpenAPI registry)
- Matrix workflow pattern for parallel per-API GitHub Actions execution
- Spectral + Postman governance dual-layer enforcement
- postman-cs action suite integration template for enterprise customers

## Product Gaps / Risks
- `postman-access-token` requires manual browser login and periodic refresh (open-alpha limitation)
- Private repos need a hosted spec URL since raw.githubusercontent.com may not be reachable by bootstrap fetch
- No Swagger 2.0 → OpenAPI 3.0 auto-conversion (specs must already be OAS 3.x)
- Rate limits on Postman API may affect large catalog migrations (no backoff in actions yet)

## Next Steps
- Run against Life360's full SwaggerHub catalog (all APIs)
- Configure Life360-specific Spectral rules for their API standards
- Set up Postman monitors with cron schedule for production smoke tests
- Evaluate `enable-insights: true` for K8s-deployed services
- Migrate to pinned action versions (e.g. `@v0.12.0`) once stable
