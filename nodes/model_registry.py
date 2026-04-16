"""
Sequencer ComfyUI Nodes — Model Registry

Fetches the model catalog from the Sequencer Firestore database
via the REST API and caches it locally. No Firebase SDK required.
"""

import json
import time
import urllib.request
import urllib.error

from .config import FIRESTORE_BASE_URL

# ─── Cache ───
_model_cache = []
_cache_timestamp = 0
CACHE_TTL_SECONDS = 300  # 5 minutes


def _parse_firestore_value(value_obj):
    """Convert a Firestore REST API value object to a Python value."""
    if "stringValue" in value_obj:
        return value_obj["stringValue"]
    elif "integerValue" in value_obj:
        return int(value_obj["integerValue"])
    elif "doubleValue" in value_obj:
        return float(value_obj["doubleValue"])
    elif "booleanValue" in value_obj:
        return value_obj["booleanValue"]
    elif "arrayValue" in value_obj:
        values = value_obj["arrayValue"].get("values", [])
        return [_parse_firestore_value(v) for v in values]
    elif "mapValue" in value_obj:
        fields = value_obj["mapValue"].get("fields", {})
        return {k: _parse_firestore_value(v) for k, v in fields.items()}
    elif "nullValue" in value_obj:
        return None
    elif "timestampValue" in value_obj:
        return value_obj["timestampValue"]
    else:
        return None


def _parse_firestore_document(doc):
    """Convert a Firestore REST document to a flat Python dict."""
    fields = doc.get("fields", {})
    parsed = {}
    for key, value_obj in fields.items():
        parsed[key] = _parse_firestore_value(value_obj)
    
    # Extract document ID from the name path
    name = doc.get("name", "")
    doc_id = name.rsplit("/", 1)[-1] if "/" in name else name
    parsed["id"] = doc_id
    
    return parsed


def fetch_models_from_firestore():
    """
    Fetch all enabled models from the Firestore REST API.
    Uses a structured query to filter by enabled == true.
    Returns a list of model dicts.
    """
    # Use Firestore REST API structured query
    query_url = f"{FIRESTORE_BASE_URL}:runQuery"
    
    query_body = {
        "structuredQuery": {
            "from": [{"collectionId": "models"}],
            "where": {
                "fieldFilter": {
                    "field": {"fieldPath": "enabled"},
                    "op": "EQUAL",
                    "value": {"booleanValue": True}
                }
            },
            "limit": 500
        }
    }
    
    payload = json.dumps(query_body).encode("utf-8")
    req = urllib.request.Request(
        query_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"[Sequencer] Error fetching models: {e}")
        return []
    
    models = []
    for item in data:
        doc = item.get("document")
        if doc:
            parsed = _parse_firestore_document(doc)
            models.append(parsed)
    
    return models


def get_all_models(force_refresh=False):
    """
    Get all enabled models, using cache if available.
    Returns a list of model dicts.
    """
    global _model_cache, _cache_timestamp
    
    now = time.time()
    if not force_refresh and _model_cache and (now - _cache_timestamp) < CACHE_TTL_SECONDS:
        return _model_cache
    
    models = fetch_models_from_firestore()
    if models:
        _model_cache = models
        _cache_timestamp = now
        print(f"[Sequencer] Loaded {len(models)} models from registry")
    elif not _model_cache:
        print("[Sequencer] Warning: No models loaded and cache is empty")
    
    return _model_cache


def get_model_choices():
    """
    Get model choices for the ComfyUI dropdown.
    Returns a list of model IDs (strings) sorted by category + recommended status.
    """
    models = get_all_models()
    
    if not models:
        return ["(no models loaded — check API key)"]
    
    # Sort: recommended first, then by name within each category
    def sort_key(m):
        category_order = {"image": 0, "video": 1, "audio": 2, "chat": 3, "3d": 4, "utility": 5}
        cat = category_order.get(m.get("category", "other"), 9)
        rec = 0 if m.get("recommended") else 1
        name = m.get("name", m.get("modelId", ""))
        return (cat, rec, name)
    
    sorted_models = sorted(models, key=sort_key)
    
    choices = []
    for m in sorted_models:
        model_id = m.get("modelId") or m.get("id", "")
        name = m.get("name", model_id)
        category = m.get("category", "other")
        prefix = "⭐ " if m.get("recommended") else ""
        label = f"{prefix}[{category.upper()}] {name}"
        choices.append(label)
    
    return choices


def get_model_id_from_choice(choice_label):
    """
    Resolve a dropdown choice label back to the model ID.
    """
    models = get_all_models()
    
    # Strip prefix markers
    clean = choice_label.replace("⭐ ", "")
    
    # Extract name from "[CATEGORY] Name" format
    if "] " in clean:
        name_part = clean.split("] ", 1)[1]
    else:
        name_part = clean
    
    # Find matching model
    for m in models:
        model_name = m.get("name", "")
        model_id = m.get("modelId") or m.get("id", "")
        if model_name == name_part or model_id == name_part:
            return model_id
    
    # Fallback: return the label as-is (might be invalid)
    return name_part


def get_model_by_id(model_id):
    """
    Get a model dict by its modelId.
    """
    models = get_all_models()
    for m in models:
        mid = m.get("modelId") or m.get("id", "")
        aid = m.get("apiId", "")
        if mid == model_id or m.get("id") == model_id or aid == model_id:
            return m
    return None


def get_models_by_category(category):
    """
    Filter models by category (image, video, audio, chat, etc.)
    """
    models = get_all_models()
    return [m for m in models if m.get("category") == category]
