# Build Log: Cust-LIFE360-spechub-uploader

## Context
- AE / CSE: Daniel Shively (CSE)
- Customer technical lead: Life360 — API platform team (Jeff)
- Sprint dates: TBD

## Hypothesis
- If we automate the upload of OpenAPI specs from a SwaggerHub-style directory into Postman Spec Hub with auto-generated collections and environments, we will prove that Life360 can migrate their API catalog to Postman with minimal manual effort.

## Success Criteria
- Script discovers all OpenAPI YAML files in the input directory tree
- New specs are created in Postman Spec Hub; existing specs are skipped (idempotent)
- Collections are auto-generated from each uploaded spec via Postman async task API
- Environments are created with variables derived from the spec's servers block (baseUrl, etc.)

## Environment Baseline
- SCM: GitHub (postman-cs/Cust-LIFE360-spechub-uploader)
- CI/CD: N/A (manual script execution)
- Gateway: N/A
- Cloud: N/A (runs locally against Postman API)
- Dev Portal: N/A
- Current Postman usage: Target workspace receives uploaded specs, collections, and environments
- v11/v12: Uses Postman Spec Hub API for spec creation and collection generation

## What We Built
- Python upload script (tools/upload_postman_apis.py) that:
  - Reads credentials from JSON config file (~/.config/postman/config.json)
  - Scans input directory for *.yaml OpenAPI specs
  - Creates Spec Hub entries via Postman REST API (https://api.getpostman.com)
  - Generates Postman collections from specs (async task + polling)
  - Creates environments with server-derived variables
  - Skips existing specs for safe reruns
- Sample OpenAPI 3.0 spec: Life360 Circles API (circles-api-1.0.0.yaml)
- Config file template with Postman API key and workspace ID
- .gitignore for credential files

## Value Unlocked
- Automates bulk spec migration from SwaggerHub to Postman Spec Hub
- Auto-generates collections and environments, eliminating manual import
- Idempotent design allows safe incremental runs as new specs are added

## Reusable Pattern
- SwaggerHub-to-Postman Spec Hub migration script (adaptable to any org with OpenAPI specs)
- Postman API async task polling pattern for collection generation
- Environment variable extraction from OpenAPI servers block

## Product Gaps / Risks
- No Swagger 2.0 → OpenAPI 3.0 conversion (specs must already be OAS 3.x)
- No dependency management file (requirements.txt) — uses only Python stdlib
- Credentials stored in plaintext JSON config (no vault integration)
- No retry/backoff on Postman API rate limits

## Next Step
- Run against Life360's full SwaggerHub spec catalog
- Add support for spec updates (not just creation)
- Integrate into CI pipeline for automated spec sync on merge
