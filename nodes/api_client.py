"""
Sequencer ComfyUI Nodes — API Client

Handles all HTTP communication with the Sequencer backend:
  - V3 generation endpoint (create media doc + start generation)
  - Firestore REST polling for generation status
  - Media file download

Uses only Python stdlib (urllib, json) — no pip dependencies.
"""

import json
import time
import urllib.request
import urllib.error
import uuid

from .config import V3_ENDPOINT, FIRESTORE_BASE_URL, WORKSPACE_ENDPOINT


def _make_auth_headers(api_key):
    """Build auth headers from an API key."""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "x-api-key": api_key,
    }


def resolve_workspace_id(api_key):
    """
    Resolve the user's default workspace from their API key.
    Queries the workspace manager endpoint.
    Falls back to creating a temporary workspace concept.
    """
    # Try to list workspaces via the workspace manager
    try:
        url = f"{WORKSPACE_ENDPOINT}/list"
        req = urllib.request.Request(
            url,
            headers=_make_auth_headers(api_key),
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            workspaces = data.get("workspaces", [])
            if workspaces:
                # Return the first (default) workspace
                return workspaces[0].get("id", "")
    except Exception as e:
        print(f"[Sequencer] Could not resolve workspace: {e}")
    
    return ""


def create_media_doc(api_key, workspace_id, media_type, prompt, model_id, aspect_ratio="16:9"):
    """
    Create a media document in Firestore via REST API.
    This is the lightweight equivalent of what the AE plugin does with the Firestore SDK.
    
    Returns the media document ID.
    """
    # Generate a unique ID for the media document
    media_doc_id = uuid.uuid4().hex[:20]
    
    # Create the document via Firestore REST
    url = f"{FIRESTORE_BASE_URL}/workspaces/{workspace_id}/media?documentId={media_doc_id}"
    
    doc_body = {
        "fields": {
            "type": {"stringValue": media_type},
            "status": {"stringValue": "generating"},
            "prompt": {"stringValue": prompt},
            "modelId": {"stringValue": model_id},
            "aspectRatio": {"stringValue": aspect_ratio},
            "activeVersion": {"integerValue": "1"},
            "versions": {"arrayValue": {"values": []}},
        }
    }
    
    payload = json.dumps(doc_body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers=_make_auth_headers(api_key),
        method="PATCH"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()  # consume response
        return media_doc_id
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Failed to create media doc (HTTP {e.code}): {error_body}")


def start_generation(api_key, payload):
    """
    Call the V3 generation endpoint to start a generation task.
    
    Args:
        api_key: Sequencer API key
        payload: Dict with generation parameters (prompt, modelId, etc.)
    
    Returns:
        Response dict from the backend
    """
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        V3_ENDPOINT,
        data=data,
        headers=_make_auth_headers(api_key),
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        
        # Parse specific error types
        try:
            error_json = json.loads(error_body)
            error_msg = error_json.get("error", error_body)
        except json.JSONDecodeError:
            error_msg = error_body
        
        if e.code == 402:
            raise RuntimeError(f"Insufficient credits. Please top up at sequencer.media. ({error_msg})")
        elif e.code == 401:
            raise RuntimeError(f"Authentication failed. Check your API key in ~/.sequencer/config.json ({error_msg})")
        elif e.code == 403:
            raise RuntimeError(f"Access denied: {error_msg}")
        else:
            raise RuntimeError(f"Generation failed (HTTP {e.code}): {error_msg}")


def poll_media_status(api_key, workspace_id, media_doc_id, max_attempts=120, callback=None):
    """
    Poll a Firestore media document for generation completion.
    
    Uses the Firestore REST API to check the document status.
    Polls every 2 seconds for the first 30 attempts, then backs off.
    
    Args:
        api_key: Sequencer API key
        workspace_id: Workspace containing the media doc
        media_doc_id: The media document ID to poll
        max_attempts: Maximum polling attempts (default 120 = ~4 min)
        callback: Optional callback(status, progress) for progress reporting
    
    Returns:
        Dict with 'status', 'url', 'thumbnailUrl', etc.
    """
    url = f"{FIRESTORE_BASE_URL}/workspaces/{workspace_id}/media/{media_doc_id}"
    
    for attempt in range(max_attempts):
        # Exponential backoff: 2s for first 20, then scaling up to 8s
        if attempt < 20:
            delay = 2.0
        else:
            delay = min(2.0 * (1.3 ** (attempt - 20)), 8.0)
        
        time.sleep(delay)
        
        try:
            req = urllib.request.Request(url, headers=_make_auth_headers(api_key), method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[Sequencer] Poll attempt {attempt + 1} failed: {e}")
            continue
        
        fields = data.get("fields", {})
        
        # Parse status
        status = fields.get("status", {}).get("stringValue", "generating")
        
        # Check versions array for completion
        versions = fields.get("versions", {}).get("arrayValue", {}).get("values", [])
        
        if versions:
            # Get the latest version
            latest = versions[-1].get("mapValue", {}).get("fields", {})
            version_status = latest.get("status", {}).get("stringValue", "")
            version_url = latest.get("url", {}).get("stringValue", "")
            thumbnail_url = latest.get("thumbnailUrl", {}).get("stringValue", "")
            
            if version_status in ("completed", "up-to-date") and version_url:
                if callback:
                    callback("completed", 1.0)
                return {
                    "status": "completed",
                    "url": version_url,
                    "thumbnailUrl": thumbnail_url or "",
                }
            elif version_status in ("error", "failed"):
                error_msg = latest.get("generationError", {}).get("stringValue", "Generation failed")
                # Check for friendly error
                friendly_error = latest.get("friendlyError", {}).get("mapValue", {}).get("fields", {})
                if friendly_error:
                    error_msg = friendly_error.get("message", {}).get("stringValue", error_msg)
                raise RuntimeError(f"Generation failed: {error_msg}")
        
        if status in ("error", "failed"):
            raise RuntimeError("Generation failed — check the Sequencer dashboard for details.")
        
        # Report progress
        progress = fields.get("progress", {}).get("doubleValue", 0.0)
        if callback:
            callback(status, progress)
    
    raise RuntimeError(f"Generation timed out after {max_attempts} polling attempts (~{max_attempts * 2}s).")


def download_media(url, timeout=60):
    """
    Download a media file from a URL.
    Returns the raw bytes.
    """
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()
