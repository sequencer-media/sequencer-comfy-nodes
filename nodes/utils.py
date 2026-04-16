"""
Sequencer ComfyUI Nodes — Utilities

Tensor conversion, payload building, and media processing helpers.
"""

import io
import os
import struct
import tempfile

import numpy as np


def url_to_image_tensor(image_bytes):
    """
    Convert raw image bytes (PNG/JPEG/WebP) to a ComfyUI IMAGE tensor.
    
    ComfyUI IMAGE format: torch.Tensor with shape [B, H, W, C] (float32, 0-1 range)
    
    Uses PIL if available, falls back to basic PNG parsing.
    """
    try:
        # Try PIL first (usually available in ComfyUI environments)
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        
        # Convert to numpy array [H, W, C] float32 0-1
        img_array = np.array(img).astype(np.float32) / 255.0
        
        # Add batch dimension [1, H, W, C]
        import torch
        tensor = torch.from_numpy(img_array).unsqueeze(0)
        return tensor
    except ImportError:
        raise RuntimeError(
            "PIL (Pillow) is required for image processing. "
            "Install it with: pip install Pillow"
        )


def image_tensor_to_bytes(image_tensor, format="PNG"):
    """
    Convert a ComfyUI IMAGE tensor back to image bytes.
    
    Args:
        image_tensor: torch.Tensor [B, H, W, C] float32 0-1
        format: Output format ("PNG" or "JPEG")
    
    Returns:
        bytes: The encoded image
    """
    try:
        from PIL import Image
        import torch
        
        # Take first image from batch
        if image_tensor.dim() == 4:
            img_np = image_tensor[0].cpu().numpy()
        else:
            img_np = image_tensor.cpu().numpy()
        
        # Convert from float32 0-1 to uint8 0-255
        img_np = (img_np * 255.0).clip(0, 255).astype(np.uint8)
        
        img = Image.fromarray(img_np, "RGB")
        buffer = io.BytesIO()
        img.save(buffer, format=format)
        return buffer.getvalue()
    except ImportError:
        raise RuntimeError("PIL (Pillow) is required for image conversion.")


def image_tensor_to_tempfile(image_tensor, format="PNG"):
    """
    Save an IMAGE tensor to a temporary file and return the path.
    Useful for uploading images to the backend.
    """
    ext = ".png" if format == "PNG" else ".jpg"
    img_bytes = image_tensor_to_bytes(image_tensor, format)
    
    fd, path = tempfile.mkstemp(suffix=ext, prefix="sequencer_")
    try:
        os.write(fd, img_bytes)
    finally:
        os.close(fd)
    
    return path


def save_bytes_to_tempfile(data_bytes, suffix=".png"):
    """Save raw bytes to a temp file and return the path."""
    fd, path = tempfile.mkstemp(suffix=suffix, prefix="sequencer_")
    try:
        os.write(fd, data_bytes)
    finally:
        os.close(fd)
    return path


def build_v3_payload(
    model_dict,
    prompt,
    model_id,
    workspace_id,
    media_doc_id,
    aspect_ratio="16:9",
    duration=None,
    seed=None,
    negative_prompt=None,
    strength=None,
    resolution=None,
    source_image_url=None,
    reference_image_urls=None,
    input_audio_url=None,
):
    """
    Build the V3 generation payload, mirroring the AE plugin's buildV3Payload.
    
    Args:
        model_dict:    The full model dict from the registry
        prompt:        User's text prompt
        model_id:      The model's modelId string
        workspace_id:  Workspace ID for Firestore
        media_doc_id:  Media document ID for result storage
        aspect_ratio:  e.g. "16:9", "9:16", "1:1"
        duration:      Video duration in seconds (for video models)
        seed:          Random seed (optional)
        negative_prompt: Negative prompt (optional)
        strength:      Strength/influence parameter (optional)
        resolution:    Output resolution e.g. "1K", "2K", "4K" (optional)
        source_image_url: Input image URL for img2img / img2vid
        reference_image_urls: List of reference image URLs
        input_audio_url: Input audio URL for audio-related models
    
    Returns:
        dict: The payload for the V3 endpoint
    """
    category = model_dict.get("category", "image") if model_dict else "image"
    
    payload = {
        "prompt": prompt,
        "modelId": model_id,
        "mediaType": category if category in ("image", "video", "audio") else "image",
        "aspectRatio": aspect_ratio,
        "mediaDocId": media_doc_id,
        "workspaceId": workspace_id,
        "targetType": "standalone",
        "source": "comfyui-plugin",
    }
    
    # Optional parameters
    if duration is not None and category == "video":
        payload["duration"] = int(duration)
    
    if seed is not None and seed > 0:
        payload["seed"] = int(seed)
    
    if negative_prompt and negative_prompt.strip():
        payload["negativePrompt"] = negative_prompt.strip()
    
    if strength is not None:
        payload["strength"] = float(strength)
    
    if resolution and resolution.strip():
        payload["resolution"] = resolution.strip()
    
    # Source image (for image-to-video, image-to-image, etc.)
    if source_image_url:
        payload["imageUrl"] = source_image_url
        payload["sourceImage"] = source_image_url
    
    # Reference images (for element-to-video, subject reference, etc.)
    if reference_image_urls:
        valid_refs = [u for u in reference_image_urls if u and u.strip()]
        if valid_refs:
            payload["referenceImageUrls"] = valid_refs
    
    # Input audio (for lip sync, voice-to-voice, etc.)
    if input_audio_url:
        payload["inputAudioUrl"] = input_audio_url
    
    return payload


def get_output_type_for_model(model_dict):
    """
    Determine the primary output type based on model category and features.
    Returns: "image", "video", "audio", or "text"
    """
    if not model_dict:
        return "image"
    
    category = model_dict.get("category", "image")
    features = model_dict.get("features", []) or []
    
    # Feature-based overrides
    if "video_to_audio" in features:
        return "video"  # outputs video with audio
    
    if category == "image":
        return "image"
    elif category == "video":
        return "video"
    elif category == "audio":
        return "audio"
    elif category == "chat":
        return "text"
    else:
        return "image"
