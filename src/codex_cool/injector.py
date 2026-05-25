from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CODEX_CONFIG_DIR = Path.home() / ".codex"
CODEX_CONFIG_PATH = CODEX_CONFIG_DIR / "config.toml"
CODEX_AUTH_PATH = CODEX_CONFIG_DIR / "auth.json"
BACKUP_SUFFIX = ".codex-cool-backup"

PROVIDER_KEY = "codex-cool"
PROVIDER_SECTION_HEADER = f'[model_providers."{PROVIDER_KEY}"]'

def backup_codex_config() -> bool:
    if not CODEX_CONFIG_PATH.exists():
        return False
    backup_path = CODEX_CONFIG_PATH.with_suffix(CODEX_CONFIG_PATH.suffix + BACKUP_SUFFIX)
    if backup_path.exists():
        return True
    shutil.copy2(CODEX_CONFIG_PATH, backup_path)
    logger.info("Backed up codex config to %s", backup_path)
    return True


def restore_codex_config() -> bool:
    backup_path = CODEX_CONFIG_PATH.with_suffix(CODEX_CONFIG_PATH.suffix + BACKUP_SUFFIX)
    if not backup_path.exists():
        return False
    shutil.copy2(backup_path, CODEX_CONFIG_PATH)
    backup_path.unlink()
    logger.info("Restored codex config from backup")
    return True


CLAUDE_DESKTOP_PROFILE_ID = "00000000-0000-4000-8000-000000157210"
CLAUDE_DESKTOP_PROFILE_NAME = "Codex Cool"

CLAUDE_MODEL_ALIASES = [
    "claude-sonnet-4-20250514",
    "claude-opus-4-20250514",
    "claude-haiku-4-5-20251001",
]


def _get_claude_desktop_paths() -> dict[str, Path]:
    if sys.platform == "darwin":
        app_support = Path.home() / "Library" / "Application Support"
        normal_dir = app_support / "Claude"
        threep_dir = app_support / "Claude-3p"
    else:
        local_app_data = Path(os.environ.get(
            "LOCALAPPDATA", Path.home() / "AppData" / "Local"
        ))
        normal_dir = local_app_data / "Claude"
        threep_dir = local_app_data / "Claude-3p"
    config_library = threep_dir / "configLibrary"
    return {
        "normal_config": normal_dir / "claude_desktop_config.json",
        "threep_config": threep_dir / "claude_desktop_config.json",
        "config_library": config_library,
        "profile": config_library / f"{CLAUDE_DESKTOP_PROFILE_ID}.json",
        "meta": config_library / "_meta.json",
        "developer_settings": normal_dir / "developer_settings.json",
    }


def _read_json(path: Path) -> dict[str, Any]:
    if path.exists():
        text = path.read_text(encoding="utf-8-sig")
        return json.loads(text)
    return {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def _write_deployment_mode(path: Path, mode: str) -> None:
    data = _read_json(path)
    if not isinstance(data, dict):
        data = {}
    data["deploymentMode"] = mode
    if mode == "3p":
        data["devModeEnabled"] = True
    else:
        data.pop("devModeEnabled", None)
    _write_json(path, data)


def _build_gateway_profile(
    base_url: str, api_key: str, models: list[str] | None = None
) -> dict[str, Any]:
    profile: dict[str, Any] = {
        "disableDeploymentModeChooser": True,
        "inferenceGatewayApiKey": api_key,
        "inferenceGatewayAuthScheme": "bearer",
        "inferenceGatewayBaseUrl": base_url,
        "inferenceProvider": "gateway",
    }
    if models:
        profile["inferenceModels"] = models
    return profile


def _write_meta(path: Path, applied_profile_id: str | None = None) -> None:
    data = _read_json(path)
    if not isinstance(data, dict):
        data = {}
    entries = data.get("entries", [])
    entries = [
        e for e in entries
        if isinstance(e, dict) and e.get("id") != CLAUDE_DESKTOP_PROFILE_ID
    ]
    if applied_profile_id:
        entries.append({
            "id": CLAUDE_DESKTOP_PROFILE_ID,
            "name": CLAUDE_DESKTOP_PROFILE_NAME,
        })
        data["appliedId"] = applied_profile_id
    else:
        if data.get("appliedId") == CLAUDE_DESKTOP_PROFILE_ID:
            next_id = None
            for e in entries:
                if isinstance(e, dict) and e.get("id"):
                    next_id = e["id"]
                    break
            if next_id:
                data["appliedId"] = next_id
            else:
                data.pop("appliedId", None)
    data["entries"] = entries
    _write_json(path, data)


def get_claude_inject_status() -> dict[str, Any]:
    paths = _get_claude_desktop_paths()
    normal_config = _read_json(paths["normal_config"])
    threep_config = _read_json(paths["threep_config"])
    profile = _read_json(paths["profile"])
    meta = _read_json(paths["meta"])

    deployment_mode = normal_config.get("deploymentMode", "1p")
    inference_provider = profile.get("inferenceProvider", "")
    base_url = profile.get("inferenceGatewayBaseUrl", "")
    is_injected = (
        deployment_mode == "3p"
        and inference_provider == "gateway"
        and ("127.0.0.1" in base_url or "localhost" in base_url)
    )

    dev_mode_enabled = normal_config.get("devModeEnabled", False)

    return {
        "injected": is_injected,
        "config_exists": paths["normal_config"].exists(),
        "current_base_url": base_url,
        "current_deployment_mode": deployment_mode,
        "current_models": profile.get("inferenceModels", []),
        "dev_mode_enabled": dev_mode_enabled,
    }


def _write_developer_settings(path: Path) -> None:
    data = _read_json(path)
    if not isinstance(data, dict):
        data = {}
    data["allowDevTools"] = True
    data["allowThirdPartyInference"] = True
    _write_json(path, data)
    logger.info("Wrote developer_settings: %s", path)


def _set_node_env() -> None:
    if sys.platform == "darwin":
        import subprocess
        try:
            subprocess.run(
                ["launchctl", "setenv", "NODE_ENV", "production"],
                check=True,
                capture_output=True,
            )
            logger.info("Set NODE_ENV=production via launchctl")
        except Exception as e:
            logger.warning("Failed to set NODE_ENV via launchctl: %s", e)
    else:
        os.environ["NODE_ENV"] = "production"
        logger.info("Set NODE_ENV=production in process environment")


def inject_claude_desktop(
    proxy_host: str,
    proxy_port: int,
    api_key: str = "",
    models: list[str] | None = None,
) -> dict[str, Any]:
    paths = _get_claude_desktop_paths()
    base_url = f"http://{proxy_host}:{proxy_port}"

    if not api_key:
        api_key = f"codex-cool-{os.urandom(8).hex()}"

    claude_models = CLAUDE_MODEL_ALIASES[:max(len(models or []), 1)]
    profile = _build_gateway_profile(base_url, api_key, claude_models)

    try:
        _write_deployment_mode(paths["normal_config"], "3p")
        _write_deployment_mode(paths["threep_config"], "3p")
        _write_json(paths["profile"], profile)
        _write_meta(paths["meta"], CLAUDE_DESKTOP_PROFILE_ID)
        _write_developer_settings(paths["developer_settings"])
        _set_node_env()
    except PermissionError as e:
        logger.error("Permission denied writing claude desktop config: %s", e)
        return {
            "ok": False,
            "error": "permission_denied",
            "message": "无法写入配置文件，请确保 Claude Desktop 已关闭后重试",
        }

    logger.info(
        "Injected claude desktop: base_url=%s, models=%s", base_url, models
    )

    return {
        "ok": True,
        "base_url": base_url,
        "models": claude_models,
        "mapped_from": models or [],
    }


def uninject_claude_desktop() -> dict[str, Any]:
    paths = _get_claude_desktop_paths()

    try:
        _write_deployment_mode(paths["normal_config"], "1p")
        _write_deployment_mode(paths["threep_config"], "1p")

        if paths["profile"].exists():
            paths["profile"].unlink()
            logger.info("Removed claude desktop profile")

        _write_meta(paths["meta"], None)

        dev_settings_path = paths.get("developer_settings")
        if dev_settings_path and dev_settings_path.exists():
            data = _read_json(dev_settings_path)
            data.pop("allowThirdPartyInference", None)
            _write_json(dev_settings_path, data)

        if sys.platform == "darwin":
            import subprocess
            try:
                subprocess.run(
                    ["launchctl", "unsetenv", "NODE_ENV"],
                    capture_output=True,
                )
                logger.info("Unset NODE_ENV via launchctl")
            except Exception:
                pass
        else:
            os.environ.pop("NODE_ENV", None)
    except PermissionError as e:
        logger.error("Permission denied restoring claude desktop config: %s", e)
        return {
            "ok": False,
            "error": "permission_denied",
            "message": "无法写入配置文件，请确保 Claude Desktop 已关闭后重试",
        }

    logger.info("Restored claude desktop to official mode")
    return {"ok": True, "restored": True}


def _read_raw() -> str:
    if CODEX_CONFIG_PATH.exists():
        text = CODEX_CONFIG_PATH.read_text(encoding="utf-8-sig")
        return text
    return ""


def _find_top_level_key(lines: list[str], key: str) -> int | None:
    for i, line in enumerate(lines):
        stripped = line.strip().lstrip("\ufeff")
        if stripped.startswith("["):
            break
        m = re.match(rf'^{re.escape(key)}\s*=', stripped)
        if m:
            return i
    return None


def _find_section_start(lines: list[str], section_header: str) -> int | None:
    for i, line in enumerate(lines):
        if line.strip() == section_header:
            return i
    return None


def _find_next_section(lines: list[str], start: int) -> int:
    for i in range(start + 1, len(lines)):
        if lines[i].strip().startswith("["):
            return i
    return len(lines)


def _is_in_section(lines: list[str], line_idx: int, section_header: str) -> bool:
    for i in range(line_idx - 1, -1, -1):
        stripped = lines[i].strip()
        if stripped.startswith("["):
            return stripped == section_header
    return False


def _set_top_level_key(lines: list[str], key: str, value: str) -> list[str]:
    toml_val = f'"{value}"'
    idx = _find_top_level_key(lines, key)
    if idx is not None:
        lines[idx] = f'{key} = {toml_val}'
    else:
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.strip() and not line.strip().startswith("#") and not line.strip().startswith("["):
                insert_pos = i
                break
            insert_pos = i + 1
        lines.insert(insert_pos, f'{key} = {toml_val}')
    return lines


def _remove_top_level_key(lines: list[str], key: str) -> list[str]:
    idx = _find_top_level_key(lines, key)
    if idx is not None:
        lines.pop(idx)
    return lines


def _ensure_section(lines: list[str], section_header: str) -> list[str]:
    idx = _find_section_start(lines, section_header)
    if idx is not None:
        return lines
    lines.append("")
    lines.append(section_header)
    return lines


def _set_section_key(lines: list[str], section_header: str, key: str, value: str) -> list[str]:
    lines = _ensure_section(lines, section_header)
    section_start = _find_section_start(lines, section_header)
    next_section = _find_next_section(lines, section_start)

    for i in range(section_start + 1, next_section):
        stripped = lines[i].strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = re.match(rf'^{re.escape(key)}\s*=', stripped)
        if m:
            lines[i] = f'{key} = "{value}"'
            return lines

    insert_pos = next_section
    lines.insert(insert_pos, f'{key} = "{value}"')
    return lines


def _remove_section(lines: list[str], section_header: str) -> list[str]:
    start = _find_section_start(lines, section_header)
    if start is None:
        return lines
    end = _find_next_section(lines, start)
    del lines[start:end]
    while start > 0 and start <= len(lines) and lines[start - 1].strip() == "":
        lines.pop(start - 1)
        start -= 1
    return lines


def _get_top_level_value(lines: list[str], key: str) -> str:
    idx = _find_top_level_key(lines, key)
    if idx is None:
        return ""
    stripped = lines[idx].strip()
    _, _, val = stripped.partition("=")
    val = val.strip()
    if val.startswith('"') and val.endswith('"'):
        return val[1:-1]
    if val.startswith("'") and val.endswith("'"):
        return val[1:-1]
    return val


def _get_section_value(lines: list[str], section_header: str, key: str) -> str:
    start = _find_section_start(lines, section_header)
    if start is None:
        return ""
    end = _find_next_section(lines, start)
    for i in range(start + 1, end):
        stripped = lines[i].strip()
        m = re.match(rf'^{re.escape(key)}\s*=', stripped)
        if m:
            _, _, val = stripped.partition("=")
            val = val.strip()
            if val.startswith('"') and val.endswith('"'):
                return val[1:-1]
            if val.startswith("'") and val.endswith("'"):
                return val[1:-1]
            return val
    return ""


def get_inject_status() -> dict[str, Any]:
    lines = _read_raw().splitlines()
    backup_exists = CODEX_CONFIG_PATH.with_suffix(CODEX_CONFIG_PATH.suffix + BACKUP_SUFFIX).exists()

    model_provider = _get_top_level_value(lines, "model_provider")
    base_url = _get_section_value(lines, PROVIDER_SECTION_HEADER, "base_url")

    is_injected = model_provider == PROVIDER_KEY and "127.0.0.1" in base_url

    return {
        "injected": is_injected,
        "backup_exists": backup_exists,
        "current_model": _get_top_level_value(lines, "model"),
        "current_provider": model_provider,
        "current_base_url": base_url,
        "config_exists": CODEX_CONFIG_PATH.exists(),
    }


def inject_codex_config(proxy_host: str, proxy_port: int, model: str = "", api_key: str = "") -> dict[str, Any]:
    backup_codex_config()

    lines = _read_raw().splitlines()
    base_url = f"http://{proxy_host}:{proxy_port}/v1"

    lines = _set_top_level_key(lines, "model_provider", PROVIDER_KEY)
    if model:
        lines = _set_top_level_key(lines, "model", model)

    lines = _set_section_key(lines, PROVIDER_SECTION_HEADER, "name", "Codex-Cool")
    lines = _set_section_key(lines, PROVIDER_SECTION_HEADER, "base_url", base_url)
    lines = _set_section_key(lines, PROVIDER_SECTION_HEADER, "wire_api", "responses")
    if api_key:
        lines = _set_section_key(lines, PROVIDER_SECTION_HEADER, "api_key", api_key)

    CODEX_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines)
    if not text.endswith("\n"):
        text += "\n"
    CODEX_CONFIG_PATH.write_text(text, encoding="utf-8")

    if api_key:
        os.environ["CODEX_COOL_API_KEY"] = api_key

    logger.info("Injected codex config: base_url=%s, model=%s", base_url, model)

    return {
        "ok": True,
        "base_url": base_url,
        "model": model,
        "provider": PROVIDER_KEY,
    }


def uninject_codex_config() -> dict[str, Any]:
    restored = restore_codex_config()

    if not restored:
        lines = _read_raw().splitlines()
        model_provider = _get_top_level_value(lines, "model_provider")
        if model_provider == PROVIDER_KEY:
            lines = _remove_top_level_key(lines, "model_provider")
            lines = _remove_section(lines, PROVIDER_SECTION_HEADER)
            text = "\n".join(lines)
            if not text.endswith("\n"):
                text += "\n"
            CODEX_CONFIG_PATH.write_text(text, encoding="utf-8")
            logger.info("Removed codex-cool provider from config")

    return {"ok": True, "restored": restored}
