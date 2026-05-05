# Environment Setup Guide

Step-by-step guide for setting up the Life360 SwaggerHub → Postman v12 migration pipeline in your own GitHub org and Postman team.

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| **GitHub CLI** | 2.x+ | `brew install gh` or [cli.github.com](https://cli.github.com) |
| **Git** | 2.x+ | `brew install git` |
| **Python 3** | 3.9+ | `brew install python3` |
| **Node.js** | 20+ | `brew install node` |
| **PyYAML** | any | `pip3 install pyyaml` |
| **Postman CLI** | latest | [learning.postman.com/docs/postman-cli](https://learning.postman.com/docs/postman-cli/postman-cli-installation/) |

## 1. Postman Setup

### Create a Postman API Key

1. Open [Postman](https://go.postman.co) and sign in to your team workspace
2. Go to **Settings → API Keys → Generate API Key**
3. Copy the key (starts with `PMAK-`)
4. Save it — you'll use this as `POSTMAN_API_KEY`

```bash
export POSTMAN_API_KEY="PMAK-your-key-here"
```

### Get a Postman Access Token

The access token is a session token required by Bifrost for workspace-to-repo linking and governance group assignment. It expires and must be refreshed periodically.

```bash
# Log in via the Postman CLI (opens browser)
postman login

# Extract the access token
export POSTMAN_ACCESS_TOKEN=$(cat ~/.postman/postmanrc | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data['login']['_profiles'][0]['accessToken'])
")

echo "Token: ${POSTMAN_ACCESS_TOKEN:0:20}..."
```

> **Note**: This token expires after a few hours. You'll need to re-run `postman login` and re-extract it when it does. This is an open-alpha limitation.

## 2. GitHub Setup

### Authenticate the GitHub CLI

```bash
gh auth login -h github.com -w
```

### Create a GitHub Personal Access Token (PAT)

The pipeline needs a PAT with elevated scopes because the `postman-repo-sync-action` commits generated workflow files (`.github/workflows/postman-ci-*.yml`) back to the repo. The default `GITHUB_TOKEN` does not have permission to create workflow files.

1. Go to **GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. Generate a new token with these scopes:
   - `repo` (full control of private repositories)
   - `workflow` (update GitHub Action workflows)
3. Copy the token
4. Save it — you'll use this as `GH_FALLBACK_TOKEN`

```bash
export GH_FALLBACK_TOKEN="ghp_your-token-here"
```

## 3. Clone the Spec-Migration-Normalize Tool

```bash
git clone https://github.com/danielshively-source/Spec-Migration-Normalize.git
cd Spec-Migration-Normalize
npm install
```

This installs `swagger2openapi`, `api-spec-converter`, and `postman-to-openapi` for multi-format spec conversion.

## 4. Export Specs from SwaggerHub

Download all API specs from SwaggerHub as YAML or JSON files into a single directory:

```bash
mkdir -p ~/life360-exports

# Option A: Manual download from SwaggerHub UI
#   → Each API → Export → Download API → YAML Unresolved

# Option B: SwaggerHub CLI / API (if available)
#   curl -o ~/life360-exports/circles-api-1.2.0.yaml \
#     "https://api.swaggerhub.com/apis/Life360/circles-api/1.2.0/swagger.yaml"
```

Expected structure:

```
~/life360-exports/
├── life360-circles-api-1.2.0.yaml
├── life360-location-api-2.0.0.yaml
├── life360-notifications-api-1.0.0.yaml
├── life360-places-api-1.1.0.yaml
└── life360-safety-api-1.0.0.yaml
```

The normalizer accepts OpenAPI 3.x, Swagger 2.0, RAML 0.8, API Blueprint, WADL, and Postman Collection v2.1 formats. It auto-detects and converts as needed.

## 5. Run the Normalizer

```bash
cd Spec-Migration-Normalize

INPUT_DIR=~/life360-exports \
OUTPUT_DIR=~/life360-repos \
INGEST_MODE=repo-per-service \
ORGANIZATION="Life360" \
DOMAIN="life360-platform" \
DOMAIN_CODE="L360" \
DEFAULT_ENVIRONMENTS='["prod","staging"]' \
STRIP_TITLE_PREFIX="Life360" \
GOVERNANCE_GROUP="Life360 API Platform" \
PRIVATE_NETWORK_FOLDER="Life360 APIs" \
TEMPLATES_DIR=./templates \
python3 ingest.py
```

This produces one directory per API under `~/life360-repos/`:

```
~/life360-repos/
├── circles-api/
│   ├── .github/workflows/
│   │   ├── onboard-apis.yml
│   │   └── api-governance.yml
│   ├── specs/circles-api-1.2.0.yaml
│   ├── api-manifest.json
│   ├── .spectral.yaml
│   ├── .gitignore
│   └── README.md
├── location-api/
├── notifications-api/
├── places-api/
└── safety-api/
```

## 6. Create GitHub Repos and Set Secrets

For each scaffolded service, create a GitHub repo, set the required secrets, and push:

```bash
cd ~/life360-repos

for svc in circles-api location-api notifications-api places-api safety-api; do
  echo "=== Setting up life360-$svc ==="

  # Create the GitHub repo
  gh repo create "Life360/life360-$svc" --private \
    --description "Life360 $svc — Postman v12 onboarding"

  # Set secrets
  echo "$POSTMAN_API_KEY" | gh secret set POSTMAN_API_KEY \
    --repo "Life360/life360-$svc"

  echo "$GH_FALLBACK_TOKEN" | gh secret set GH_FALLBACK_TOKEN \
    --repo "Life360/life360-$svc"

  # Optional: set POSTMAN_ACCESS_TOKEN for Bifrost linking
  echo "$POSTMAN_ACCESS_TOKEN" | gh secret set POSTMAN_ACCESS_TOKEN \
    --repo "Life360/life360-$svc"

  # Initialize and push
  cd "$svc"
  git init -b main
  git add -A
  git commit -m "feat: scaffold $svc from SwaggerHub export [skip ci]"
  git remote add origin "https://github.com/Life360/life360-$svc.git"
  git push -u origin main
  cd ..

  echo ""
done
```

> Replace `Life360/` with your actual GitHub org. Use `--public` instead of `--private` if preferred.

> The `[skip ci]` in the commit message prevents the onboard workflow from triggering on the initial push. This lets you verify the repo contents before running the pipeline.

## 7. Trigger Onboarding

Trigger the onboarding workflow for each service:

```bash
for svc in circles-api location-api notifications-api places-api safety-api; do
  gh workflow run onboard-apis.yml \
    --repo "Life360/life360-$svc" \
    --ref main
  echo "Triggered life360-$svc"
done
```

Monitor progress:

```bash
for svc in circles-api location-api notifications-api places-api safety-api; do
  echo "--- life360-$svc ---"
  gh run list --repo "Life360/life360-$svc" --limit 1 \
    --json name,status,conclusion \
    --jq '.[] | "\(.name): \(.status) (\(.conclusion // "running"))"'
done
```

### What the onboard workflow does

For each API, the workflow:

1. **Bootstrap** — creates a Postman workspace named `[L360] <api-name>`, uploads the spec to Spec Hub, generates Baseline/Smoke/Contract collections, assigns governance group
2. **Repo Sync** — creates environments (prod, staging), generates a CI test workflow, links the workspace to the GitHub repo via Bifrost, commits `.postman/resources.yaml` back to the repo

## 8. Verify

### Check Postman workspaces

```bash
curl -s "https://api.getpostman.com/workspaces" \
  -H "x-api-key: $POSTMAN_API_KEY" | \
  python3 -c "
import json, sys
for ws in json.load(sys.stdin).get('workspaces', []):
    if 'L360' in ws.get('name', ''):
        print(f\"  {ws['name']}: https://go.postman.co/workspace/{ws['id']}\")
"
```

### Check workspace contents

```bash
WS_ID="<workspace-id-from-above>"
curl -s "https://api.getpostman.com/workspaces/$WS_ID" \
  -H "x-api-key: $POSTMAN_API_KEY" | \
  python3 -c "
import json, sys
d = json.load(sys.stdin).get('workspace', {})
print(f\"Workspace: {d['name']}\")
print(f\"Collections: {len(d.get('collections', []))}\")
print(f\"Environments: {len(d.get('environments', []))}\")
for c in d.get('collections', []):
    print(f\"  - {c['name']}\")
"
```

### Expected result per workspace

| Asset | Count | Names |
|-------|-------|-------|
| Collections | 3 | `[Baseline] <api>`, `[Smoke] <api>`, `[Contract] <api>` |
| Environments | 2 | `<api> - prod`, `<api> - staging` |
| Spec Hub entry | 1 | `<api>` |

## 9. Post-Setup: CI Tests

Once onboarding completes, the repo-sync action commits a `postman-ci-<api-name>.yml` workflow to each repo. This runs smoke and contract tests on every push to `main`.

If you want APIs added to the team's Private API Network, do that step manually in the Postman UI per workspace — the pipeline no longer automates it.

### Known fix needed for auto-generated CI workflows

The `postman-repo-sync-action` currently generates CI workflows with a few issues that need manual correction:

| Issue | Fix |
|-------|-----|
| Escaped `\n` instead of real newlines | Replace literal `\n` with actual newlines in the YAML |
| No `paths-ignore` on push trigger | Add `paths-ignore` for `.postman/**`, `postman/**`, workflow files |
| `secrets` in step `if` condition | Move the check into the `run` block as a shell conditional |
| `schedule` cron trigger | Remove unless you want scheduled monitoring |

## Refreshing the Access Token

When `POSTMAN_ACCESS_TOKEN` expires (you'll see 401 errors in workflow runs related to Bifrost or governance), refresh it:

```bash
postman login

NEW_TOKEN=$(cat ~/.postman/postmanrc | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data['login']['_profiles'][0]['accessToken'])
")

for svc in circles-api location-api notifications-api places-api safety-api; do
  echo "$NEW_TOKEN" | gh secret set POSTMAN_ACCESS_TOKEN \
    --repo "Life360/life360-$svc"
  echo "Updated life360-$svc"
done
```

## Adding a New API

To onboard a new Life360 API after initial setup:

1. Export the spec from SwaggerHub
2. Run the normalizer on just that spec
3. Create the GitHub repo, set secrets, push
4. Trigger the onboard workflow

```bash
# Normalize
INPUT_DIR=~/new-export OUTPUT_DIR=~/life360-repos \
INGEST_MODE=repo-per-service ORGANIZATION=Life360 \
DOMAIN=life360-platform DOMAIN_CODE=L360 \
DEFAULT_ENVIRONMENTS='["prod","staging"]' \
STRIP_TITLE_PREFIX=Life360 TEMPLATES_DIR=./templates \
python3 ingest.py

# Create repo + push
cd ~/life360-repos/new-api-name
gh repo create "Life360/life360-new-api-name" --private
# ... (same steps as section 6)
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Onboard workflow fails at git push | `GITHUB_TOKEN` can't create workflow files | Set `GH_FALLBACK_TOKEN` with `workflow` scope |
| Duplicate workspaces in Postman | Onboard ran twice before `.postman/resources.yaml` was committed | Delete the orphan workspace via API; the idempotency guard prevents future duplicates |
| CI workflow triggers on every push | Auto-generated workflow missing `paths-ignore` | Add `paths-ignore` for sync artifact paths |
| 401 on governance/Bifrost steps | `POSTMAN_ACCESS_TOKEN` expired | Re-run `postman login` and update the secret |
| 404 on governance group assignment | Governance group doesn't exist in your Postman team | Create it in Postman web UI first, or remove `governance_mapping` from manifest |
| Spec not visible in API Catalog | Bootstrap uploaded spec but Bifrost link failed | Check `POSTMAN_ACCESS_TOKEN` is set and valid |

## Environment Variables Reference

| Variable | Where Set | Description |
|----------|-----------|-------------|
| `POSTMAN_API_KEY` | GitHub secret | Postman API key for all API calls |
| `POSTMAN_ACCESS_TOKEN` | GitHub secret | Session token for Bifrost and governance (expires) |
| `GH_FALLBACK_TOKEN` | GitHub secret | GitHub PAT with `workflow` + `repo` scopes |
| `INPUT_DIR` | Shell env | Directory containing exported specs (normalizer) |
| `OUTPUT_DIR` | Shell env | Target directory for scaffolded repos (normalizer) |
| `INGEST_MODE` | Shell env | `repo-per-service` or `single-repo` (normalizer) |
| `ORGANIZATION` | Shell env | Organization name for manifest metadata |
| `DOMAIN` | Shell env | Business domain slug |
| `DOMAIN_CODE` | Shell env | Short code used in workspace naming (`[L360]`) |
