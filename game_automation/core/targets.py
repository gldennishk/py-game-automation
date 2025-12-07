import os
import json
from .path_utils import to_absolute_path, get_base_dir

TARGET_DEFINITIONS = {
    "DAILY_BOOK_BUTTON": {
        "template": "game_automation/templates/daily_book_button.png",
        "method": "tm",
        "threshold": 0.83,
        "roi": [0.35, 0.80, 0.65, 0.98]
    },
    "QINGYUN_CARD": {
        "template": "game_automation/templates/qingyun_card.png",
        "method": "tm",
        "threshold": 0.85,
        "roi": [0.05, 0.30, 0.95, 0.75]
    },
    "QINGYUN_TITLE_NORMAL": {
        "template": "game_automation/templates/qingyun_title_normal.png",
        "method": "tm",
        "threshold": 0.88,
        "roi": [0.15, 0.12, 0.85, 0.40]
    },
    "MATCH_BUTTON": {
        "template": "game_automation/templates/match_button.png",
        "method": "tm",
        "threshold": 0.86,
        "roi": [0.25, 0.72, 0.75, 0.93]
    },
    "CANCEL_MATCH_BUTTON": {
        "template": "game_automation/templates/cancel_match_button.png",
        "method": "tm",
        "threshold": 0.86,
        "roi": [0.25, 0.72, 0.75, 0.93]
    },
}

# Convert all built-in target template paths to absolute paths
# This ensures cv2.imread() can correctly load the template images
for target_name, target_cfg in TARGET_DEFINITIONS.items():
    if "template" in target_cfg:
        target_cfg["template"] = to_absolute_path(target_cfg["template"])

# Built-in targets that should never be pruned (defined in code, not from resources.json)
_BUILTIN_TARGETS = set(TARGET_DEFINITIONS.keys())

TARGETS_VERSION = 0

def _load_resources_json():
    try:
        file_path = os.path.join(get_base_dir(), "resources.json")
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

# Import shared path utilities


def reload_targets_from_resources(override: bool = False, default_threshold: float = 0.85, default_roi = [0.0, 0.0, 1.0, 1.0], prune_missing: bool = False):
    """
    Reload target definitions from resources.json.
    
    Args:
        override: If True, overwrite existing targets even if they already exist
        default_threshold: Default confidence threshold for new targets
        default_roi: Default ROI for new targets
        prune_missing: If True, remove targets from TARGET_DEFINITIONS that are not in
                      resources.json (built-in targets are always preserved)
    
    Returns:
        bool: True if TARGET_DEFINITIONS was modified, False otherwise
    
    Note:
        IMPORTANT CONTRACT: All non-builtin targets must be defined in resources.json.
        
        When prune_missing=True, any target in TARGET_DEFINITIONS that is not in
        resources.json (and is not a built-in target) will be removed. This ensures
        that TARGET_DEFINITIONS stays in sync with the persisted resources.json file.
        This is the expected behavior and is triggered automatically by ResourceSidebar.persist().
        
        **Dynamic, non-persisted target additions are NOT SUPPORTED.** Any programmatically
        added targets that are not persisted to resources.json will be automatically removed
        when prune_missing=True is used (which happens on every ResourceSidebar.persist() call).
        
        If you need to add targets dynamically, you must also update resources.json
        via ResourceSidebar.persist() or by directly modifying the file, otherwise
        they will be pruned on the next reload with prune_missing=True.
    """
    global TARGETS_VERSION
    mapping = _load_resources_json()
    
    # Build set of keys that should be retained
    # Include all keys from resources.json plus built-in targets
    keys_to_keep = set(_BUILTIN_TARGETS)
    if mapping:
        keys_to_keep.update(mapping.keys())
    
    changed = False
    
    # Add or update targets from resources.json
    if mapping:
        for name, path in mapping.items():
            # Resolve relative paths to absolute for TemplateMatcher (cv2.imread needs absolute paths)
            abs_path = to_absolute_path(path)
            
            # Check if target already exists
            if name in TARGET_DEFINITIONS:
                # If override is True, always update
                # If override is False, only update if the path has changed (to sync with resources.json)
                existing_path = TARGET_DEFINITIONS[name].get("template", "")
                if override or existing_path != abs_path:
                    # Update existing target (preserve method, threshold, roi if they exist, otherwise use defaults)
                    existing_cfg = TARGET_DEFINITIONS[name]
                    TARGET_DEFINITIONS[name] = {
                        "template": abs_path,
                        "method": existing_cfg.get("method", "tm"),
                        "threshold": existing_cfg.get("threshold", default_threshold),
                        "roi": existing_cfg.get("roi", list(default_roi)),
                    }
                    changed = True
            else:
                # Create new target
                TARGET_DEFINITIONS[name] = {
                    "template": abs_path,
                    "method": "tm",
                    "threshold": default_threshold,
                    "roi": list(default_roi),
                }
                changed = True
    
    # Prune targets that are not in resources.json (if prune_missing is True)
    if prune_missing:
        keys_to_remove = [key for key in TARGET_DEFINITIONS.keys() if key not in keys_to_keep]
        if keys_to_remove:
            # Get caller information for debugging
            import inspect
            caller_info = "unknown"
            try:
                frame = inspect.currentframe()
                if frame and frame.f_back:
                    caller_frame = frame.f_back
                    caller_info = f"{caller_frame.f_code.co_filename}:{caller_frame.f_lineno} ({caller_frame.f_code.co_name})"
            except Exception:
                pass
            # Log pruned keys for debugging/development visibility
            print(f"[targets] Pruning {len(keys_to_remove)} non-persisted target(s): {', '.join(keys_to_remove)}")
            print(f"[targets] Caller: {caller_info}")
            print(f"[targets] Note: Non-persisted, programmatically added targets are unsupported and will be removed.")
            print(f"[targets] To preserve targets, add them to resources.json via ResourceSidebar.persist()")
        for key in keys_to_remove:
            del TARGET_DEFINITIONS[key]
            changed = True
    
    if changed:
        TARGETS_VERSION += 1
    return changed

# Initial optional load from resources.json on import
reload_targets_from_resources(override=False)

