"""Agent orchestrator: validates required checks per request type.

Gemini may ADD checks, never remove. No function-calling loop.
Any error = PEND, never a crash or PROCEED.
"""

import yaml
from pathlib import Path
from typing import Optional


def load_config():
    cfg_path = Path("config/rules.yaml")
    if cfg_path.exists():
        with open(cfg_path) as f:
            return yaml.safe_load(f)
    return {"required_checks": {}}


def validate_required_checks(check_results: list, request_type: str) -> Optional[str]:
    """Validate that all required checks for the request type ran. Returns error or None."""
    config = load_config()
    required = config.get("required_checks", {}).get(request_type, [])

    if not required:
        return None

    result_check_ids = {r.get("check", "") for r in check_results}

    missing = [c for c in required if c not in result_check_ids]
    if missing:
        return f"Missing required checks for {request_type}: {missing}"

    return None


def safe_run(fn, *args, **kwargs):
    """Run a function safely. Any error = PEND, never crash."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        return {
            "error": f"Agent error: {str(e)}",
            "result": "PEND"
        }