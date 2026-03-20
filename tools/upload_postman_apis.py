#!/usr/bin/env python3
"""
Postman Spec Hub Uploader

Reads SwaggerHub API specs from a local directory and uploads them to a Postman
workspace via Spec Hub.  For each spec file a Spec Hub specification is created,
a Postman Collection is generated from it, and an environment is created with
the server URL(s) extracted from the spec.

Already-uploaded specs (matched by name) are skipped (upsert behaviour).

Usage:
    python tools/upload_postman_apis.py [--config CONFIG_FILE] [--input INPUT_DIR] [--workspace WORKSPACE_ID]
"""

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
import yaml


POSTMAN_BASE_URL = "https://api.getpostman.com"

COLLECTION_GEN_OPTIONS = {
    "requestNameSource": "Fallback",
    "indentCharacter": "Space",
    "folderStrategy": "Paths",
    "includeAuthInfoInExample": True,
    "enableOptionalParameters": True,
    "keepImplicitHeaders": False,
    "includeDeprecated": True,
    "alwaysInheritAuthentication": False,
    "nestedFolderHierarchy": False,
}


class PostmanConfig:
    """Configuration for Postman API access"""

    def __init__(self, api_key: str, workspace_id: str):
        self.api_key = api_key
        self.workspace_id = workspace_id

    @classmethod
    def from_file(cls, config_path: str) -> "PostmanConfig":
        print(f"Reading Postman credentials at '{config_path}'")
        with open(config_path, "r") as f:
            data = json.load(f)
        return cls(
            api_key=data["POSTMAN_API_KEY"],
            workspace_id=data["POSTMAN_WORKSPACE_ID"],
        )


class PostmanClient:
    """Client for the Postman REST API (Spec Hub + helpers)"""

    def __init__(self, config: PostmanConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "X-Api-Key": config.api_key,
                "Accept": "application/vnd.api.v10+json",
            }
        )

    # ── low-level helpers ──────────────────────────────────────────────

    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        url = f"{POSTMAN_BASE_URL}{endpoint}"
        resp = self.session.request(method, url, timeout=30, **kwargs)
        return resp

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        resp = self._request("GET", endpoint, params=params)
        if resp.status_code != 200:
            raise Exception(f"GET {endpoint} → {resp.status_code}\n{resp.text}")
        return resp.json()

    def _post(self, endpoint: str, body: Dict) -> Tuple[int, Dict]:
        resp = self._request("POST", endpoint, json=body)
        return resp.status_code, resp.json()

    def _delete(self, endpoint: str) -> None:
        self._request("DELETE", endpoint)

    # ── Spec Hub: specs ────────────────────────────────────────────────

    def list_specs(self, workspace_id: str) -> Dict[str, str]:
        """Return {spec_name: spec_id} for all specs in the workspace."""
        result: Dict[str, str] = {}
        cursor: Optional[str] = None
        while True:
            params: Dict = {"workspaceId": workspace_id}
            if cursor:
                params["cursor"] = cursor
            data = self._get("/specs", params=params)
            for spec in data.get("specs", []):
                result[spec["name"]] = spec["id"]
            cursor = (data.get("meta") or {}).get("nextCursor")
            if not cursor:
                break
        return result

    def create_spec(
        self,
        workspace_id: str,
        name: str,
        spec_type: str,
        file_content: str,
    ) -> str:
        """Create a spec in Spec Hub and return its id."""
        status, data = self._post(
            f"/specs?workspaceId={workspace_id}",
            {
                "name": name,
                "type": spec_type,
                "files": [{"path": "spec.yaml", "content": file_content}],
            },
        )
        if status not in (200, 201):
            raise Exception(f"POST /specs → {status}\n{json.dumps(data)}")
        return data["id"]

    # ── Spec Hub: generate collection ──────────────────────────────────

    def generate_collection(self, spec_id: str, name: str) -> str:
        """Kick off async collection generation; returns the task id."""
        status, data = self._post(
            f"/specs/{spec_id}/generations/collection",
            {"name": name, "options": COLLECTION_GEN_OPTIONS},
        )
        if status not in (200, 201, 202):
            raise Exception(
                f"POST /specs/{spec_id}/generations/collection → {status}\n"
                f"{json.dumps(data)}"
            )
        return data["taskId"]

    def poll_task(
        self, spec_id: str, task_id: str, timeout: int = 120, interval: int = 2
    ) -> Dict:
        """Poll a spec task until it completes or times out."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = self._get(f"/specs/{spec_id}/tasks/{task_id}")
            status = data.get("status", "")
            if status == "completed":
                return data
            if status == "failed":
                detail = data.get("details", "unknown error")
                raise Exception(f"Task {task_id} failed: {detail}")
            time.sleep(interval)
        raise Exception(f"Task {task_id} timed out after {timeout}s")

    def get_generated_collections(self, spec_id: str) -> List[Dict]:
        """Return the list of collections generated from a spec."""
        data = self._get(f"/specs/{spec_id}/generations/collection")
        return data.get("collections", [])

    # ── Environments ───────────────────────────────────────────────────

    def list_environments(self, workspace_id: str) -> Dict[str, str]:
        """Return {env_name: env_id} for all environments in the workspace."""
        data = self._get("/environments", params={"workspace": workspace_id})
        envs = data.get("environments", [])
        return {e["name"]: e["id"] for e in envs}

    def create_environment(
        self,
        workspace_id: str,
        name: str,
        values: List[Dict],
    ) -> str:
        """Create an environment and return its id."""
        status, data = self._post(
            f"/environments?workspace={workspace_id}",
            {
                "environment": {
                    "name": name,
                    "values": values,
                }
            },
        )
        if status not in (200, 201):
            raise Exception(
                f"POST /environments → {status}\n{json.dumps(data)}"
            )
        return data.get("environment", data).get("id", "")


# ── helpers ────────────────────────────────────────────────────────────


def detect_spec_type(content: str) -> str:
    """Return the Postman Spec Hub type string for an OpenAPI spec."""
    if "openapi: 3.1" in content or "openapi: '3.1" in content or 'openapi: "3.1' in content:
        return "OPENAPI:3.0"  # Spec Hub currently accepts 3.0 for 3.1 files too
    if "openapi: 3" in content or "openapi: '3" in content or 'openapi: "3' in content:
        return "OPENAPI:3.0"
    if "swagger: 2" in content or "swagger: '2" in content or 'swagger: "2' in content:
        return "OPENAPI:3.0"  # Spec Hub only supports OPENAPI:3.0 and ASYNCAPI:2.0
    return "OPENAPI:3.0"


def extract_version_from_filename(stem: str) -> Optional[str]:
    match = re.search(r"-([vV]?\d[\d.]*[\w.]*)$", stem)
    return match.group(1) if match else None


def extract_env_variables(content: str) -> List[Dict]:
    """Parse an OpenAPI spec and return environment variables for its servers."""
    try:
        parsed = yaml.safe_load(content)
    except Exception:
        return []

    if not isinstance(parsed, dict):
        return []

    variables: List[Dict] = []
    servers = parsed.get("servers", [])

    if servers and isinstance(servers, list):
        first_url = servers[0].get("url", "") if isinstance(servers[0], dict) else ""
        if first_url:
            variables.append(
                {
                    "key": "baseUrl",
                    "value": first_url.rstrip("/"),
                    "enabled": True,
                    "type": "default",
                }
            )

        for i, server in enumerate(servers):
            if not isinstance(server, dict):
                continue
            url = server.get("url", "")
            desc = server.get("description", f"Server {i + 1}")
            if url and i > 0:
                variables.append(
                    {
                        "key": f"server_{i + 1}_url",
                        "value": url.rstrip("/"),
                        "enabled": True,
                        "type": "default",
                        "description": desc,
                    }
                )

            for var_name, var_def in server.get("variables", {}).items():
                if isinstance(var_def, dict):
                    variables.append(
                        {
                            "key": var_name,
                            "value": str(var_def.get("default", "")),
                            "enabled": True,
                            "type": "default",
                            "description": var_def.get("description", ""),
                        }
                    )

    # Swagger 2.0 host/basePath/schemes
    if not servers:
        host = parsed.get("host", "")
        base_path = parsed.get("basePath", "")
        schemes = parsed.get("schemes", ["https"])
        if host:
            scheme = schemes[0] if schemes else "https"
            base_url = f"{scheme}://{host}{base_path}".rstrip("/")
            variables.append(
                {
                    "key": "baseUrl",
                    "value": base_url,
                    "enabled": True,
                    "type": "default",
                }
            )

    return variables


def discover_specs(input_dir: str) -> Dict[str, List[Tuple[str, str]]]:
    """
    Walk input_dir/{project}/*.yaml and group files by API name.

    Returns {api_name: [(version, filepath), ...]}
    """
    specs: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    input_path = Path(input_dir)

    if not input_path.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    for yaml_file in sorted(input_path.glob("*/*.yaml")):
        try:
            content = yaml_file.read_text()
            parsed = yaml.safe_load(content)
        except Exception as e:
            print(f"  WARNING: Could not parse {yaml_file}: {e}", file=sys.stderr)
            continue

        stem = yaml_file.stem
        filename_version = extract_version_from_filename(stem)

        version = None
        if isinstance(parsed, dict) and isinstance(parsed.get("info"), dict):
            version = str(parsed["info"].get("version", "")).strip() or None

        if not version:
            version = filename_version

        if not version:
            print(
                f"  WARNING: Could not determine version for {yaml_file}, skipping",
                file=sys.stderr,
            )
            continue

        api_name = stem
        for v in filter(None, [filename_version, version]):
            suffix = f"-{v}"
            if stem.endswith(suffix):
                api_name = stem[: -len(suffix)]
                break

        specs[api_name].append((version, str(yaml_file)))

    return dict(specs)


# ── main workflow ──────────────────────────────────────────────────────


def upload_all_specs(
    config_file: str, input_dir: str, workspace_id_override: Optional[str]
):
    config = PostmanConfig.from_file(config_file)
    if workspace_id_override:
        config.workspace_id = workspace_id_override

    client = PostmanClient(config)
    workspace_id = config.workspace_id

    print(f"\nDiscovering specs in: {input_dir}")
    specs = discover_specs(input_dir)
    total_specs = sum(len(v) for v in specs.values())
    print(f"Found {len(specs)} unique API name(s), {total_specs} total spec file(s)\n")

    print(f"Fetching existing specs in workspace: {workspace_id}")
    existing_specs = client.list_specs(workspace_id)
    print(f"Found {len(existing_specs)} existing spec(s) in workspace")

    print(f"Fetching existing environments in workspace: {workspace_id}")
    existing_envs = client.list_environments(workspace_id)
    print(f"Found {len(existing_envs)} existing environment(s) in workspace\n")

    specs_created = 0
    specs_skipped = 0
    collections_generated = 0
    envs_created = 0
    envs_skipped = 0
    failures = 0

    for api_name in sorted(specs.keys()):
        print(f"─ {api_name}")

        for version, filepath in sorted(specs[api_name], key=lambda t: t[0]):
            spec_display_name = f"{api_name} ({version})"
            spec_hub_name = f"{api_name}-{version}"

            if spec_hub_name in existing_specs:
                print(f"  {version} — spec skipped (already exists)")
                specs_skipped += 1
                continue

            content = Path(filepath).read_text()
            spec_type = detect_spec_type(content)

            # ── create spec ────────────────────────────────────────────
            try:
                spec_id = client.create_spec(
                    workspace_id, spec_hub_name, spec_type, content
                )
                existing_specs[spec_hub_name] = spec_id
                specs_created += 1
                print(f"  {version} — spec created (id={spec_id})")
            except Exception as e:
                print(f"  {version} — FAILED to create spec: {e}", file=sys.stderr)
                failures += 1
                continue

            # ── generate collection ────────────────────────────────────
            try:
                task_id = client.generate_collection(spec_id, spec_display_name)
                print(f"  {version} — collection generation started (task={task_id})")
                client.poll_task(spec_id, task_id)
                collections_generated += 1
                print(f"  {version} — collection generated")
            except Exception as e:
                print(
                    f"  {version} — FAILED to generate collection: {e}",
                    file=sys.stderr,
                )
                failures += 1

            # ── create environment ─────────────────────────────────────
            env_name = spec_hub_name
            if env_name in existing_envs:
                print(f"  {version} — environment skipped (already exists)")
                envs_skipped += 1
                continue

            env_vars = extract_env_variables(content)
            if not env_vars:
                print(f"  {version} — environment skipped (no server URLs found)")
                continue

            try:
                env_id = client.create_environment(workspace_id, env_name, env_vars)
                existing_envs[env_name] = env_id
                envs_created += 1
                print(f"  {version} — environment created (id={env_id})")
            except Exception as e:
                print(
                    f"  {version} — FAILED to create environment: {e}",
                    file=sys.stderr,
                )
                failures += 1

    print(
        f"\n✓ Done!  "
        f"specs created: {specs_created}, skipped: {specs_skipped} | "
        f"collections generated: {collections_generated} | "
        f"environments created: {envs_created}, skipped: {envs_skipped} | "
        f"failures: {failures}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Upload SwaggerHub API specs to Postman Spec Hub",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Configuration File Format:
  The config file should be a JSON file at ~/.config/postman/config.json:
  {
      "POSTMAN_API_KEY": "your-api-key-here",
      "POSTMAN_WORKSPACE_ID": "your-workspace-id"
  }

  Your API key can be found at: https://go.postman.co/settings/me/api-keys
  Your workspace ID is the UUID in your Postman workspace URL.

Examples:
  # Upload from default swaggerhub_apis/ directory
  python tools/upload_postman_apis.py

  # Upload from a custom directory
  python tools/upload_postman_apis.py --input ./my-apis

  # Override the target workspace
  python tools/upload_postman_apis.py --workspace abc123-workspace-id
        """,
    )

    default_config = os.path.join(
        os.path.expanduser("~"), ".config/postman/config.json"
    )

    parser.add_argument(
        "--config",
        default=default_config,
        help=f"Path to Postman credentials file (default: {default_config})",
    )
    parser.add_argument(
        "--input",
        default="swaggerhub_apis",
        help="Directory containing downloaded specs (default: swaggerhub_apis)",
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Postman workspace ID (overrides value in config file)",
    )

    args = parser.parse_args()

    if not os.path.exists(args.config):
        print(f"ERROR: Config file not found: {args.config}", file=sys.stderr)
        print(
            "\nCreate it with your Postman API key and workspace ID.",
            file=sys.stderr,
        )
        print("See --help for the expected format.", file=sys.stderr)
        sys.exit(1)

    try:
        upload_all_specs(args.config, args.input, args.workspace)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
