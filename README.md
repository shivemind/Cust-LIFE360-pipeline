# Cust-LIFE360-spechub-uploader

Automation tool that discovers OpenAPI specification files and uploads them to a **Postman workspace** via the Spec Hub API, with automatic collection generation and environment setup.

## How It Works

```mermaid
flowchart TD
    subgraph input [Input]
        A1["swaggerhub_apis/ directory"]
        A2["*.yaml OpenAPI specs"]
    end

    subgraph config [Configuration]
        B1["~/.config/postman/config.json"]
        B2[POSTMAN_API_KEY]
        B3[POSTMAN_WORKSPACE_ID]
    end

    subgraph upload [Upload Pipeline]
        C1[Scan directory for YAML files]
        C2[Check existing specs in workspace]
        C3{Spec exists?}
        C4[Create Spec Hub entry]
        C5[Skip - already exists]
        C6["Generate Collection (async + poll)"]
        C7[Create Environment from servers block]
    end

    subgraph output [Postman Workspace]
        D1[Spec Hub Entries]
        D2[Generated Collections]
        D3["Environments (baseUrl, etc.)"]
    end

    input --> C1
    config --> C1
    C1 --> C2 --> C3
    C3 -->|No| C4 --> C6 --> C7
    C3 -->|Yes| C5
    C4 --> D1
    C6 --> D2
    C7 --> D3
```

## Setup

```mermaid
flowchart LR
    A[Create config.json] --> B[Add OpenAPI specs to swaggerhub_apis/]
    B --> C[Run upload script]
    C --> D[Specs in Postman Spec Hub]
    D --> E[Collections auto-generated]
    D --> F[Environments auto-created]
```

### Prerequisites

- Python 3.8+
- A valid Postman API key with workspace write permissions

### Configuration

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

### Adding New Specs

1. Create a folder under `swaggerhub_apis/` with the project name
2. Place your OpenAPI YAML file inside (e.g., `swaggerhub_apis/my-api/my-api-1.0.0.yaml`)
3. Run the upload script — it will only process new specs (idempotent)

## Included Specs

| Path | Description |
|------|-------------|
| `swaggerhub_apis/life360/circles-api-1.0.0.yaml` | OpenAPI 3.0 spec for the Life360 Circles API (`GET /circles`, `GET /circles/{circleId}`) against `https://api.life360.com/v3` |

## Project Structure

```
Cust-LIFE360-spechub-uploader/
├── tools/
│   └── upload_postman_apis.py        # Main uploader script
├── swaggerhub_apis/
│   └── life360/
│       └── circles-api-1.0.0.yaml    # Sample OpenAPI spec
├── test_config/
│   └── config.json                   # Local test credentials (git-ignored)
└── .gitignore
```
