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

### Sprint 3 — Private API Network Promotion
- **Promotion workflow** (`.github/workflows/promote-to-private-network.yml`)
  - Triggers automatically after onboarding or CI pipelines succeed on `main`
  - Quality gate checks: verifies most recent onboard + CI runs passed before promoting
  - Creates a Private API Network folder (idempotent) using the Postman API (`POST /network/private`)
  - Adds qualifying workspaces to the folder; skips already-listed workspaces
  - Supports `workflow_dispatch` with single-API filter and force-promote override
  - Folder name and description configurable via `private_network` block in `life360-api-manifest.json`
- Uses Postman Private API Network REST API: `GET /network/private`, `POST /network/private`
- **Companion action** — `PrivateAPI-promote-auto` packaged as a standalone reusable GitHub Action

### Sprint 4 — Bifrost Integration & CI Pipeline Fix (current)
- **Postman Access Token** — configured `POSTMAN_ACCESS_TOKEN` as a GitHub secret (session token extracted via `postman login` CLI → `~/.postman/postmanrc`)
  - Enables Bifrost workspace-to-repo linking in the API Catalog
  - Enables spec-to-collection cloud linking and sync
  - Enables system environment association
  - Token is session-scoped and requires periodic manual refresh (open-alpha limitation)
- **CI workflow fix** (`.github/workflows/postman-ci-circles-api.yml`)
  - Auto-generated file had escaped `\n` characters instead of real newlines — GitHub Actions rejected it as invalid YAML
  - Reformatted to proper multi-line YAML
  - Fixed `if: ${{ secrets.POSTMAN_SSL_CLIENT_CERT_B64 != '' }}` — GitHub Actions does not allow `secrets` context in step `if` conditions; moved SSL cert check into the run block as a shell conditional
  - Smoke tests now execute successfully (403s expected without Life360 auth credentials)
- **System environment linking** — `system-env-map-json` in the onboard workflow is currently empty; requires system environments to be created in the Postman web UI (API Catalog > System Environments) before they can be mapped. No public API exists to create them programmatically.
- **Enterprise sandbox** — pipeline validated against `sync-annual-enterprise-202603` plan, user `admin-sandbox-ca484575` (userId 53591924)

### Companion Repo: Spec-Migration-Normalize
- Packaged as a standalone composite GitHub Action (`DansFolder/Spec-Migration-Normalize`)
- **Sprint 1**: Ingests SwaggerHub exports (JSON/YAML, Swagger 2.0/OpenAPI 3.x), normalizes to clean OpenAPI 3.x YAML, scaffolds per-service repos (one repo, one service, one workspace)
- **Sprint 2**: Expanded to support 11 API spec formats:
  - **Auto-convert to OpenAPI 3.x**: Swagger 2.0 (swagger2openapi), RAML 0.8 (api-spec-converter), API Blueprint (api-spec-converter), WADL (api-spec-converter), Postman Collection v2.1 (postman-to-openapi)
  - **Passthrough with import guidance**: GraphQL SDL, Protobuf, AsyncAPI (Postman-native), WSDL, HAR (manual/UI import)
- Designed as the first stage of any API-platform-to-Postman migration

### Sprint 5 — End-to-End Migration Pipeline with Spec Normalizer (completed April 2 2026)
- **Full pipeline test**: ingested 5 Life360 SwaggerHub YAML exports through the complete normalizer → repo-per-service → Postman onboarding pipeline
- **Spec-Migration-Normalize as first-class layer**:
  - Ran `ingest.py` in `repo-per-service` mode against `~/Desktop/life360-swaggerhub-exports/`
  - Detected all 5 specs as OpenAPI 3.x, normalized, and scaffolded self-contained repo directories
  - Each scaffolded repo includes: spec, manifest, onboard/governance/promote workflows, .spectral.yaml, README
- **Per-service GitHub repos created** — one repo per API (one repo, one service, one workspace pattern):
  - `danielshively-source/life360-circles-api`
  - `danielshively-source/life360-location-api`
  - `danielshively-source/life360-notifications-api`
  - `danielshively-source/life360-places-api`
  - `danielshively-source/life360-safety-api`
- **Secrets provisioned** — `POSTMAN_API_KEY` and `GH_FALLBACK_TOKEN` set on all 5 repos
- **Onboarding verified** — all 5 `onboard-apis.yml` workflows completed successfully:
  - 5 Postman workspaces created: `[L360] circles-api`, `[L360] location-api`, `[L360] notifications-api`, `[L360] places-api`, `[L360] safety-api`
  - 5 specs uploaded to Spec Hub
  - 15 collections generated (Baseline + Smoke + Contract per API)
  - Environments (prod, staging) created per workspace
  - CI test workflows auto-generated and committed to each repo
- **Issue found & fixed**: first onboard run failed at git push because default `GITHUB_TOKEN` lacks `workflows` permission to create `.github/workflows/` files. Fix: set `GH_FALLBACK_TOKEN` (PAT with `workflow` scope) on each repo, then re-triggered. Second run succeeded and committed all artifacts.
- **Orphan cleanup**: first run created workspaces but couldn't commit `.postman/resources.yaml`; second run created new workspaces. Deleted 5 orphaned workspaces via API.
- **Enterprise PMAK rotated** — updated `POSTMAN_API_KEY` secret and local `test_config/config.json`
- **Idempotency hardening** (3 duplication vectors fixed):
  1. **onboard-apis.yml** — added `paths-ignore` for `.postman/**`, `postman/**`, `.github/workflows/postman-ci-*` to prevent re-triggering on repo-sync artifact commits
  2. **Resolve step workspace name fallback** — when `.postman/resources.yaml` is missing (first run or failed push), the workflow now searches the Postman API for an existing workspace matching `[DOMAIN_CODE] api-name` before creating a new one; also resolves existing collections by name from the workspace
  3. **postman-ci-*.yml** — auto-generated CI workflows had `on.push` with no path filter (every push to main triggered CI + cascading promote); fixed to add `paths-ignore` for sync artifacts, also fixed escaped `\n` newlines and `secrets` in `if` condition
  - All fixes pushed to all 5 per-service repos with `[skip ci]` to prevent cascade
  - Template updated in `Spec-Migration-Normalize/templates/onboard-apis.yml.tpl` for future scaffolds

### Companion Repo: PrivateAPI-promote-auto
- Standalone composite GitHub Action for quality-gated Private API Network promotion
- Reusable across customers; takes `postman-api-key`, `workspace-id`, `folder-name` as inputs

## Verified Pipeline Flow (April 2 2026 — full 5-API run)
1. **Spec-Migration-Normalize** (local) → detect format → normalize → scaffold per-service repo (spec + manifest + workflows + .spectral.yaml)
2. **Repo creation** → `gh repo create` per service → set `POSTMAN_API_KEY` + `GH_FALLBACK_TOKEN` secrets → `git push`
3. `onboard-apis.yml` → discover manifest → bootstrap workspace + Spec Hub + collections + governance → repo-sync (environments, mock, monitor, CI workflow, Bifrost link) → commit & push
4. `postman-ci-<name>.yml` → install Postman CLI → resolve resource IDs from `.postman/resources.yaml` → run smoke tests → run contract tests → upload results to Postman Cloud
5. `promote-to-private-network.yml` → quality gate (check onboard + CI success) → create PAN folder → add workspace
6. Spec Hub confirmed as source of truth: spec loaded first, then all collections derived from the spec

## Value Unlocked
- **Single pane of glass**: every Life360 API visible in Postman v12 API Catalog
- **Governance from CI**: Spectral lint on PR, Postman governance groups on merge
- **Testing from CI**: contract and smoke tests auto-generated and run per API
- **Zero manual Postman work**: adding an API = YAML file + manifest entry + push
- **Private API Network as quality gate**: only APIs passing lint, smoke, and contract tests are promoted to the team's Private API Network — discoverable by all team members
- **Workspace-repo linking**: Bifrost connects each Postman workspace to the GitHub repo
- **Collection v3 export**: collections synced back to repo as multi-file YAML for version control
- **Multi-format ingestion**: customers migrating from any API platform (SwaggerHub, MuleSoft/RAML, Apiary, etc.) can use Spec-Migration-Normalize to standardize before onboarding

## Reusable Pattern
- Manifest-driven API onboarding (adaptable to any org migrating from SwaggerHub or any OpenAPI registry)
- Matrix workflow pattern for parallel per-API GitHub Actions execution
- Spectral + Postman governance dual-layer enforcement
- postman-cs action suite integration template for enterprise customers
- Three companion GitHub Actions packaged for reuse: onboarding (postman-cs), PAN promotion, spec ingestion/normalization

## Product Gaps / Risks
- `postman-access-token` requires manual browser login and periodic refresh (open-alpha limitation)
- System environments can only be created through the Postman web UI — no public API exists
- Governance group assignment returns 404 on some enterprise instances (Bifrost endpoint `configure/workspace-groups` not found)
- Private repos need a hosted spec URL since raw.githubusercontent.com may not be reachable by bootstrap fetch
- `postman-repo-sync-action` generates CI workflow files with escaped newlines instead of real newlines (requires manual fix); also generates `on.push` with no path filter causing cascade triggers
- Rate limits on Postman API may affect large catalog migrations (no backoff in actions yet)
- RAML 1.0 not supported by `api-spec-converter` (only RAML 0.8); `postman-to-openapi` requires Collection v2.1

## Postman Workspaces (as of April 2 2026)

| Service | Workspace ID | URL |
|---------|-------------|-----|
| circles-api | `48e4d8a0-d797-4be4-ad33-6a7f7674bf00` | [Open](https://go.postman.co/workspace/48e4d8a0-d797-4be4-ad33-6a7f7674bf00) |
| location-api | `44143637-79c4-402b-bc22-2ca34f016c45` | [Open](https://go.postman.co/workspace/44143637-79c4-402b-bc22-2ca34f016c45) |
| notifications-api | `224581a5-6486-4140-8e6f-6bdb99f6948a` | [Open](https://go.postman.co/workspace/224581a5-6486-4140-8e6f-6bdb99f6948a) |
| places-api | `5a6cbe9c-c963-4f25-9cf3-a46c571c0255` | [Open](https://go.postman.co/workspace/5a6cbe9c-c963-4f25-9cf3-a46c571c0255) |
| safety-api | `dc732dd0-cbc1-432a-99a8-99e006902d40` | [Open](https://go.postman.co/workspace/dc732dd0-cbc1-432a-99a8-99e006902d40) |

## Verified End-to-End Run (April 2 2026 — 5 Life360 APIs)

| Step | Input | Output | Status |
|------|-------|--------|--------|
| SwaggerHub export → Desktop | 5 OAS 3.0.3 YAML files | `~/Desktop/life360-swaggerhub-exports/` | Done |
| Spec-Migration-Normalize | 5 YAML specs | 5 scaffolded repo dirs in `~/Desktop/life360-scaffolded-repos/` | Done |
| `gh repo create` × 5 | Scaffolded dirs | 5 GitHub repos under `danielshively-source/` | Done |
| Secrets provisioned | `POSTMAN_API_KEY` + `GH_FALLBACK_TOKEN` | Set on all 5 repos | Done |
| `onboard-apis.yml` × 5 | Push to main triggers | 5 workspaces, 5 specs, 15 collections, 10 environments | Done |
| CI workflow generation | repo-sync-action | `postman-ci-*.yml` committed to each repo | Done |
| Idempotency fixes | 3 duplication vectors | `paths-ignore` + workspace name fallback + CI path filter | Done |
| Orphan workspace cleanup | 5 duplicates | Deleted via Postman API | Done |
| QA verification | All 5 repos + workspaces | 100% pass — unique workspaces, correct assets, no duplicates | Done |

## Next Steps
- Create system environments in the Postman web UI and wire IDs into `system-env-map-json` for environment linking
- Configure Life360-specific Spectral rules for their API standards
- Set up Postman monitors with cron schedule for production smoke tests
- Evaluate `enable-insights: true` for K8s-deployed services
- Migrate to pinned action versions (e.g. `@v0.12.0`) once stable
- Automate access token refresh when GA mechanism is available
- Build `tools/migrate.sh` local CLI orchestrator to wrap the full pipeline (normalizer → repo create → secrets → push → trigger)
- Push to `postman-cs` remote (blocked on `shivemind` GitHub token re-auth)
