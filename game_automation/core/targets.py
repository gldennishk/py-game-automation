import os
import json

TARGET_DEFINITIONS = {
    "DAILY_BOOK_BUTTON": {
        "template": "templates/daily_book_button.png",
        "method": "tm",
        "threshold": 0.83,
        "roi": [0.35, 0.80, 0.65, 0.98]
    },
    "QINGYUN_CARD": {
        "template": "templates/qingyun_card.png",
        "method": "tm",
        "threshold": 0.85,
        "roi": [0.05, 0.30, 0.95, 0.75]
    },
    "QINGYUN_TITLE_NORMAL": {
        "template": "templates/qingyun_title_normal.png",
        "method": "tm",
        "threshold": 0.88,
        "roi": [0.15, 0.12, 0.85, 0.40]
    },
    "MATCH_BUTTON": {
        "template": "templates/match_button.png",
        "method": "tm",
        "threshold": 0.86,
        "roi": [0.25, 0.72, 0.75, 0.93]
    },
    "CANCEL_MATCH_BUTTON": {
        "template": "templates/cancel_match_button.png",
        "method": "tm",
        "threshold": 0.86,
        "roi": [0.25, 0.72, 0.75, 0.93]
    },
}

TARGETS_VERSION = 0

def _base_dir():
    return os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

def _load_resources_json():
    try:
        file_path = os.path.join(_base_dir(), "resources.json")
        if not os.path.exists(file_path):
            return {}
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        templates = data.get("templates", {})
        if not isinstance(templates, dict):
            return {}
        return templates
    except Exception:
        return {}

def reload_targets_from_resources(override: bool = False, default_threshold: float = 0.85, default_roi = [0.0, 0.0, 1.0, 1.0]):
    global TARGETS_VERSION
    mapping = _load_resources_json()
    if not mapping:
        return False
    changed = False
    for name, path in mapping.items():
        if override or name not in TARGET_DEFINITIONS:
            TARGET_DEFINITIONS[name] = {
                "template": path,
                "method": "tm",
                "threshold": default_threshold,
                "roi": list(default_roi),
            }
            changed = True
    if changed:
        TARGETS_VERSION += 1
    return changed

# Initial optional load from resources.json on import
reload_targets_from_resources(override=False)

