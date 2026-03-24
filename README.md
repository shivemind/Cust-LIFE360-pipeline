# jeffLife360 — Postman Spec Hub Uploader

Automation tool that discovers OpenAPI specification files and uploads them to a **Postman workspace** via the Spec Hub API, with automatic collection generation and environment setup.

## What It Does

1. **Scans** a local directory tree (`swaggerhub_apis/` by default) for `*.yaml` OpenAPI specs
2. **Creates Spec Hub entries** in the target Postman workspace for any specs not already present
3. **Generates Postman Collections** from each newly uploaded spec (async task with polling)
4. **Creates Environments** with variables derived from the spec's `servers` block (e.g. `baseUrl`)
5. **Skips** specs that already exist in the workspace, making reruns safe (idempotent upsert)

## Included Specs

| Path | Description |
|------|-------------|
| `swaggerhub_apis/life360/circles-api-1.0.0.yaml` | OpenAPI 3.0 spec for the Life360 Circles API (`GET /circles`, `GET /circles/{circleId}`) against `https://api.life360.com/v3` |

Additional specs can be added under `swaggerhub_apis/<project>/` following the same naming convention.

## Prerequisites

- Python 3.8+
- A valid Postman API key with workspace write permissions

## Configuration

Create a config file (default: `~/.config/postman/config.json`):

```json
{
  "POSTMAN_API_KEY": "PMAK-your-api-key",
  "POSTMAN_WORKSPACE_ID": "your-workspace-id"
}
```

> **Security:** The `test_config/` directory is git-ignored to prevent accidental credential commits. Never commit API keys.

## Usage

```bash
python tools/upload_postman_apis.py
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--config` | `~/.config/postman/config.json` | Path to credentials config file |
| `--input` | `swaggerhub_apis` | Directory to scan for OpenAPI YAML files |

## Project Structure

```
jeffLife360/
├── tools/
│   └── upload_postman_apis.py    # Main uploader script
├── swaggerhub_apis/
│   └── life360/
│       └── circles-api-1.0.0.yaml
├── test_config/
│   └── config.json               # Local test credentials (git-ignored)
└── .gitignore
```
