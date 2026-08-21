"""
Sequencer ComfyUI Nodes — API Client

Handles all HTTP communication with the Sequencer API Gateway:
  - Generate media via POST /v1/generate
  - Poll status via GET /v1/tasks/{taskId}
  - Fetch default workspace via GET /v1/workspaces

Uses only Python stdlib (urllib, json) — no pip dependencies.
"""

import json
import time
import urllib.request
import urllib.error
import urllib.parse
import uuid

API_BASE_URL = "https://api.sequencer.media/v1"


def _make_auth_headers(api_key):
    """Build auth headers for the Sequencer REST API."""
    return {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }


def resolve_workspace_id(api_key):
    """
    Resolve the user's default workspace from their API key.
    Queries the /v1/workspaces endpoint on the API gateway.
    """
    try:
        url = f"{API_BASE_URL}/workspaces?limit=1"
        req = urllib.request.Request(
            url,
            headers=_make_auth_headers(api_key),
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            workspaces = data.get("workspaces", [])
            if workspaces:
                return workspaces[0].get("id", "")
    except Exception as e:
        print(f"[Sequencer] Could not resolve default workspace: {e}")
    
    return ""


def initiate_generation(api_key, payload):
    """
    Call the V1 API to start a generation task.
    
    Args:
        api_key: Sequencer API key
        payload: Dict with generation parameters (type, model, prompt, workspaceId, etc.)
    
    Returns:
        Response dict from the backend (contains taskId)
    """
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE_URL}/generate",
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
        
        if e.code == 402 or "Insufficient funds" in error_msg:
            raise RuntimeError(f"Insufficient credits. Please top up at sequencer.media. ({error_msg})")
        elif e.code == 401:
            raise RuntimeError(f"Authentication failed. Check your API key. ({error_msg})")
        elif e.code == 403:
            raise RuntimeError(f"Access denied: {error_msg}")
        else:
            raise RuntimeError(f"Generation failed (HTTP {e.code}): {error_msg}")


def poll_task_status(api_key, task_id, max_attempts=120, callback=None):
    """
    Poll the V1 API for generation completion.
    
    Args:
        api_key: Sequencer API key
        task_id: The task ID returned from initiate_generation
        max_attempts: Maximum polling attempts (default 120 = ~4 min)
        callback: Optional callback(status, progress) for progress reporting
    
    Returns:
        Dict with 'status', 'url', 'thumbnailUrl', etc.
    """
    url = f"{API_BASE_URL}/tasks/{urllib.parse.quote(task_id)}"
    
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
        
        status = data.get("status", "generating")
        
        if callback:
            callback(status, data.get("progress", 0.0))
            
        if status == "completed":
            return data.get("result", {})
        elif status == "failed":
            error_msg = data.get("error", "Generation failed — check the Sequencer dashboard for details.")
            raise RuntimeError(f"Generation failed: {error_msg}")
    
    raise RuntimeError(f"Generation timed out after {max_attempts} polling attempts (~{max_attempts * 2}s).")


def download_media(url, timeout=60):
    """
    Download a media file from a URL.
    Returns the raw bytes.
    """
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()
