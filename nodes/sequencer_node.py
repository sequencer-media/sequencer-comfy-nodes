"""
Sequencer ComfyUI Nodes — Universal Sequencer Node

A single node that provides access to the entire Sequencer AI model collection.
Select any model from the dropdown, and the node dynamically adapts its behavior
to generate images, videos, audio, or text.

All generation is routed through the Sequencer V3 backend — the same production
infrastructure used by the Sequencer web app and After Effects plugin.
"""

import torch
import numpy as np

from .config import get_api_key, get_workspace_id
from .model_registry import get_model_choices, get_model_id_from_choice, get_model_by_id, get_all_models
from .api_client import (
    resolve_workspace_id,
    create_media_doc,
    start_generation,
    poll_media_status,
    download_media,
)
from .utils import (
    url_to_image_tensor,
    image_tensor_to_tempfile,
    build_v3_payload,
    get_output_type_for_model,
)


# ─── Aspect Ratio Choices ───
ASPECT_RATIOS = ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"]

# ─── Resolution Choices ───
RESOLUTIONS = ["auto", "1K", "2K", "4K"]


class SequencerGenerate:
    """
    Universal Sequencer AI generation node.
    
    Select any model from the Sequencer collection — image generators,
    video generators, audio generators, upscalers, and more. The node
    automatically routes to the correct backend and handles polling,
    download, and tensor conversion.
    
    Outputs:
        IMAGE:     Generated image tensor (for image models), or first frame (for video models)
        VIDEO_URL: Download URL for generated video (empty string for non-video models)
        AUDIO_URL: Download URL for generated audio (empty string for non-audio models)
    """

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        # Fetch model choices from the registry
        # This runs once at registration time, and is refreshed when ComfyUI restarts
        try:
            model_choices = get_model_choices()
        except Exception as e:
            print(f"[Sequencer] Warning: Could not load models: {e}")
            model_choices = ["(error loading models — restart ComfyUI)"]

        return {
            "required": {
                "model": (model_choices, {
                    "default": model_choices[0] if model_choices else "",
                    "tooltip": "Select an AI model from the Sequencer collection. Models are fetched from your account's model registry.",
                }),
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "placeholder": "Describe what you want to generate...",
                    "tooltip": "Text prompt describing the desired output. Be descriptive for best results.",
                }),
            },
            "optional": {
                "aspect_ratio": (ASPECT_RATIOS, {
                    "default": "16:9",
                    "tooltip": "Output aspect ratio. Not all models support all ratios.",
                }),
                "input_image": ("IMAGE", {
                    "tooltip": "Input image for image-to-video, image-to-image, style transfer, upscale, etc.",
                }),
                "negative_prompt": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "placeholder": "Things to avoid in the generation...",
                    "tooltip": "Negative prompt — describe what you DON'T want. Not supported by all models.",
                }),
                "duration": ("INT", {
                    "default": 5,
                    "min": 1,
                    "max": 30,
                    "step": 1,
                    "tooltip": "Video duration in seconds. Only used by video generation models.",
                }),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 2147483647,
                    "tooltip": "Random seed for reproducible results. Set to 0 for random.",
                }),
                "strength": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                    "tooltip": "Strength / influence of the input image. Lower = more faithful to input. Used by img2img and style transfer models.",
                }),
                "resolution": (RESOLUTIONS, {
                    "default": "auto",
                    "tooltip": "Output resolution. Only used by models that support multiple output sizes (e.g., upscalers).",
                }),
                "reference_image_1": ("IMAGE", {
                    "tooltip": "Reference image 1 — for subject/style reference in element-to-video or multi-ref models.",
                }),
                "reference_image_2": ("IMAGE", {
                    "tooltip": "Reference image 2 — for additional subject/style references.",
                }),
                "reference_image_3": ("IMAGE", {
                    "tooltip": "Reference image 3 — for additional subject/style references.",
                }),
                "api_key_override": ("STRING", {
                    "default": "",
                    "placeholder": "sk_...",
                    "tooltip": "Override the API key from ~/.sequencer/config.json. Leave empty to use config file.",
                }),
                "workspace_id_override": ("STRING", {
                    "default": "",
                    "placeholder": "workspace-id",
                    "tooltip": "Override the workspace ID. Leave empty to auto-detect.",
                }),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("IMAGE", "VIDEO_URL", "AUDIO_URL")
    FUNCTION = "generate"
    CATEGORY = "Sequencer"
    OUTPUT_NODE = True

    DESCRIPTION = (
        "Universal Sequencer AI node — access any model from the Sequencer collection. "
        "Generates images, videos, audio, and more. Select a model, enter a prompt, "
        "and connect optional inputs as needed. Results are returned as ComfyUI tensors "
        "and/or download URLs."
    )

    def generate(
        self,
        model,
        prompt,
        aspect_ratio="16:9",
        input_image=None,
        negative_prompt="",
        duration=5,
        seed=0,
        strength=1.0,
        resolution="auto",
        reference_image_1=None,
        reference_image_2=None,
        reference_image_3=None,
        api_key_override="",
        workspace_id_override="",
    ):
        """Execute the generation."""

        # ─── 1. Resolve API Key ───
        api_key = api_key_override.strip() if api_key_override else get_api_key()
        if not api_key:
            raise RuntimeError(
                "No Sequencer API key configured.\n\n"
                "Set up your API key:\n"
                "  1. Go to sequencer.media → Settings → API Keys → Create Key\n"
                "  2. Save it to ~/.sequencer/config.json:\n"
                '     {"api_key": "sk_your_key_here"}\n'
                "  3. Or set the SEQUENCER_API_KEY environment variable\n"
                "  4. Or paste it into the 'api_key_override' input on this node"
            )

        # ─── 2. Resolve Model ───
        model_id = get_model_id_from_choice(model)
        model_dict = get_model_by_id(model_id)
        
        if not model_dict:
            raise RuntimeError(
                f"Model '{model_id}' not found in the registry. "
                "Try restarting ComfyUI to refresh the model list."
            )

        output_type = get_output_type_for_model(model_dict)
        category = model_dict.get("category", "image")
        print(f"[Sequencer] Generating with model: {model_dict.get('name', model_id)} ({category})")

        # ─── 3. Resolve Workspace ───
        workspace_id = workspace_id_override.strip() if workspace_id_override else get_workspace_id()
        if not workspace_id:
            workspace_id = resolve_workspace_id(api_key)
        if not workspace_id:
            raise RuntimeError(
                "No workspace ID configured.\n\n"
                "Add your workspace ID to ~/.sequencer/config.json:\n"
                '  {"api_key": "sk_...", "workspace_id": "your-workspace-id"}\n\n'
                "Find your workspace ID in the Sequencer web app URL:\n"
                "  sequencer.media/dashboard/images → workspace ID is in the URL"
            )

        # ─── 4. Upload Input Images (if connected) ───
        source_image_url = None
        if input_image is not None:
            source_image_url = self._upload_image_tensor(input_image, api_key)

        reference_image_urls = []
        for ref_img in [reference_image_1, reference_image_2, reference_image_3]:
            if ref_img is not None:
                ref_url = self._upload_image_tensor(ref_img, api_key)
                if ref_url:
                    reference_image_urls.append(ref_url)

        # ─── 5. Create Media Document ───
        media_type = category if category in ("image", "video", "audio") else "image"
        media_doc_id = create_media_doc(
            api_key=api_key,
            workspace_id=workspace_id,
            media_type=media_type,
            prompt=prompt,
            model_id=model_id,
            aspect_ratio=aspect_ratio,
        )
        print(f"[Sequencer] Created media doc: {media_doc_id}")

        # ─── 6. Build Payload & Start Generation ───
        payload = build_v3_payload(
            model_dict=model_dict,
            prompt=prompt,
            model_id=model_id,
            workspace_id=workspace_id,
            media_doc_id=media_doc_id,
            aspect_ratio=aspect_ratio,
            duration=duration if category == "video" else None,
            seed=seed if seed > 0 else None,
            negative_prompt=negative_prompt if negative_prompt.strip() else None,
            strength=strength if input_image is not None and strength < 1.0 else None,
            resolution=resolution if resolution != "auto" else None,
            source_image_url=source_image_url,
            reference_image_urls=reference_image_urls if reference_image_urls else None,
            input_audio_url=None,  # TODO: add audio input support
        )

        response = start_generation(api_key, payload)
        print(f"[Sequencer] Generation started: {response}")

        # ─── 7. Poll for Completion ───
        def progress_callback(status, progress):
            pct = int(progress * 100) if progress else 0
            print(f"[Sequencer] Status: {status} ({pct}%)")

        result = poll_media_status(
            api_key=api_key,
            workspace_id=workspace_id,
            media_doc_id=media_doc_id,
            callback=progress_callback,
        )
        
        result_url = result.get("url", "")
        thumbnail_url = result.get("thumbnailUrl", "")
        print(f"[Sequencer] Generation completed: {result_url}")

        # ─── 8. Build Output Tensors ───
        # Default outputs
        empty_image = torch.zeros(1, 64, 64, 3, dtype=torch.float32)
        video_url = ""
        audio_url = ""

        if output_type == "image":
            # Download and convert to IMAGE tensor
            if result_url:
                try:
                    image_bytes = download_media(result_url)
                    image_tensor = url_to_image_tensor(image_bytes)
                    return (image_tensor, video_url, audio_url)
                except Exception as e:
                    print(f"[Sequencer] Warning: Failed to convert image: {e}")
                    return (empty_image, result_url, audio_url)
            return (empty_image, video_url, audio_url)

        elif output_type == "video":
            video_url = result_url
            # Try to get a thumbnail/first-frame as the IMAGE output
            thumb = thumbnail_url or result_url
            if thumb and (thumb.endswith(".png") or thumb.endswith(".jpg") or thumb.endswith(".jpeg") or thumb.endswith(".webp")):
                try:
                    thumb_bytes = download_media(thumb)
                    image_tensor = url_to_image_tensor(thumb_bytes)
                    return (image_tensor, video_url, audio_url)
                except Exception:
                    pass
            return (empty_image, video_url, audio_url)

        elif output_type == "audio":
            audio_url = result_url
            return (empty_image, video_url, audio_url)

        else:
            # text / other — return URL as string
            return (empty_image, result_url, audio_url)

    def _upload_image_tensor(self, image_tensor, api_key):
        """
        Upload an IMAGE tensor to temporary storage for use as a generation input.
        
        For now, saves to a temp file and uses a data URI or direct upload.
        In production, this would upload to Firebase Storage.
        """
        try:
            # Save tensor to temp file
            temp_path = image_tensor_to_tempfile(image_tensor, format="PNG")
            
            # For now, return the local path — the backend handles file:// URIs
            # TODO: Implement proper upload to Firebase Storage or a signed URL endpoint
            print(f"[Sequencer] Saved input image to: {temp_path}")
            
            # Try to upload to a temporary URL
            # For MVP we can base64 encode it inline, but this isn't ideal for large images
            import base64
            with open(temp_path, "rb") as f:
                img_bytes = f.read()
            b64 = base64.b64encode(img_bytes).decode("ascii")
            data_uri = f"data:image/png;base64,{b64}"
            
            return data_uri
        except Exception as e:
            print(f"[Sequencer] Warning: Failed to process input image: {e}")
            return None


# ─── ComfyUI Registration ───

NODE_CLASS_MAPPINGS = {
    "SequencerGenerate": SequencerGenerate,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SequencerGenerate": "🎯 Sequencer Generate",
}
