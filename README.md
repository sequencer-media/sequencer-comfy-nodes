# Sequencer ComfyUI Nodes

> **One node. Every AI model. Dynamic I/O.**

Custom nodes for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) that provide access to the full [Sequencer](https://sequencer.media) AI model collection — image generators, video generators, audio generators, upscalers, style transfer, and more.

---

## Features

- 🎯 **Universal Generation Node** — Single node that works with every model in the Sequencer catalog
- 🔄 **Dynamic Model Selection** — Dropdown populated from the live Sequencer model registry (~50+ models)
- 🖼️ **Image Generation** — Flux, DALL-E, Ideogram, Google Imagen, Recraft, and more
- 📹 **Video Generation** — Veo 3.1, Kling, Minimax, Wan, Luma, and more
- 🔊 **Audio Generation** — ElevenLabs, music generation, sound effects
- ⚡ **Zero Dependencies** — Uses only Python stdlib + packages already in ComfyUI
- 🔒 **Secure** — API key stored locally, all traffic over HTTPS

---

## Installation

### Option A: ComfyUI Manager (Recommended)

1. Open **ComfyUI Manager** → **Install Custom Nodes**
2. Search for **"Sequencer"**
3. Click **Install**
4. Restart ComfyUI

### Option B: Git Clone

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/sequencer-media/sequencer-comfy-nodes.git
```

Restart ComfyUI.

### Option C: Manual Download

1. Download and unzip this repository
2. Place the `sequencer-comfy-nodes` folder in `ComfyUI/custom_nodes/`
3. Restart ComfyUI

---

## Configuration

### Step 1: Get Your API Key

1. Go to [sequencer.media](https://sequencer.media) and sign in
2. Navigate to **Settings → API Keys**
3. Click **Create API Key** and copy it (you won't see it again!)

### Step 2: Get Your Workspace ID

1. In the Sequencer web app, go to the **Dashboard → Images** (or Vidoes)
2. Look at the URL - it contains your workspace ID after `/workspace/`
3. Or create a new workspace in the Sequencer web app

### Step 3: Save Your Config

Create the config file at `~/.sequencer/config.json`:

```json
{
  "api_key": "sk_your_api_key_here",
  "workspace_id": "your_workspace_id_here"
}
```

**Linux/macOS:**
```bash
mkdir -p ~/.sequencer
echo '{"api_key": "sk_YOUR_KEY", "workspace_id": "YOUR_WORKSPACE_ID"}' > ~/.sequencer/config.json
chmod 600 ~/.sequencer/config.json
```

**Windows (PowerShell):**
```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.sequencer"
Set-Content "$env:USERPROFILE\.sequencer\config.json" '{"api_key": "sk_YOUR_KEY", "workspace_id": "YOUR_WORKSPACE_ID"}'
```

**Alternative: Environment Variables**
```bash
export SEQUENCER_API_KEY="sk_your_api_key_here"
export SEQUENCER_WORKSPACE_ID="your_workspace_id_here"
```

---

## Usage

### Basic Text-to-Image

1. Right-click canvas → **Add Node → Sequencer → 🎯 Sequencer Generate**
2. Select a model from the dropdown (e.g., `⭐ [IMAGE] Flux 1.1 Pro`)
3. Enter your prompt
4. Connect the `IMAGE` output to a **Preview Image** or **Save Image** node
5. **Queue Prompt** (or press Ctrl+Enter)

```
┌──────────────────────┐     ┌─────────────────┐
│ 🎯 Sequencer Generate│     │ Preview Image    │
│                      │     │                  │
│ Model: Flux 1.1 Pro  │     │                  │
│ Prompt: "A cat on    │────▶│   [preview]      │
│   the moon"          │     │                  │
│                      │     │                  │
└──────────────────────┘     └─────────────────┘
```

### Image-to-Video

1. Add the Sequencer node and select a video model (e.g., `Veo 3.1 Fast`)
2. Connect a **Load Image** node to the `input_image` input
3. Enter a motion prompt
4. The `VIDEO_URL` output contains the download URL for the generated video

```
┌────────────┐     ┌──────────────────────┐
│ Load Image │     │ 🎯 Sequencer Generate│
│            │────▶│                      │
│ photo.jpg  │     │ Model: Veo 3.1 Fast  │
└────────────┘     │ Prompt: "Slow zoom   │
                   │   with parallax"     │
                   │ Duration: 5          │
                   │                      │──── VIDEO_URL
                   └──────────────────────┘
```

### Multi-Reference Generation

Connect up to 3 reference images for element-to-video or multi-reference models:

```
┌────────────┐     ┌──────────────────────┐
│ ref_img_1  │────▶│ reference_image_1    │
└────────────┘     │                      │
┌────────────┐     │ 🎯 Sequencer Generate│
│ ref_img_2  │────▶│ reference_image_2    │
└────────────┘     │                      │
                   │ Model: Veo 3.1       │
                   │ Prompt: "character   │
                   │   walks through..."  │
                   └──────────────────────┘
```

### Upscaling

1. Select an upscaler model (e.g., `Topaz Upscale`)
2. Connect your source image to `input_image`
3. Set **resolution** to `2K` or `4K`

---

## Available Models

The model dropdown is populated live from the Sequencer model registry. Current catalog includes:

### Image Models
| Model | Provider | Features |
|-------|----------|----------|
| Flux 1.1 Pro | Black Forest Labs | text-to-image, img2img |
| Flux 2 Pro | Black Forest Labs | text-to-image, edit, inpaint |
| DALL-E 3 | OpenAI | text-to-image |
| Ideogram 3 | Ideogram | text-to-image, typography |
| Google Imagen 3 | Google | text-to-image |
| Recraft V3 | Recraft | text-to-image, vector |
| Nano Banana | Google | text-to-image, multi-ref |

### Video Models
| Model | Provider | Features |
|-------|----------|----------|
| Veo 3.1 Fast | Google | text-to-video, img-to-video, element-to-video |
| Veo 3 | Google | text-to-video with audio |
| Kling 2.1 | Kuaishou | text-to-video, img-to-video |
| Minimax Video | Minimax | text-to-video, img-to-video |
| Wan 2.1 | Alibaba | text-to-video, img-to-video |

### Audio Models
| Model | Provider | Features |
|-------|----------|----------|
| ElevenLabs v2 | ElevenLabs | text-to-speech |
| Music Generation | Various | text-to-music |

*...and 40+ more. The full list is automatically loaded from your Sequencer account.*

---

## Node Reference

### 🎯 Sequencer Generate

**Inputs (Required):**

| Input | Type | Description |
|-------|------|-------------|
| `model` | Dropdown | AI model selection from the Sequencer catalog |
| `prompt` | String | Text description of what to generate |

**Inputs (Optional):**

| Input | Type | Description |
|-------|------|-------------|
| `aspect_ratio` | Dropdown | Output aspect ratio (16:9, 9:16, 1:1, 4:3, 3:4, 21:9) |
| `input_image` | IMAGE | Source image for img2img, img2vid, upscale, etc. |
| `negative_prompt` | String | What to avoid in the generation |
| `duration` | Int (1-30) | Video duration in seconds |
| `seed` | Int | Random seed (0 = random) |
| `strength` | Float (0-1) | Input image influence strength |
| `resolution` | Dropdown | Output resolution (auto, 1K, 2K, 4K) |
| `reference_image_1/2/3` | IMAGE | Reference images for multi-ref models |
| `api_key_override` | String | Override the config file API key |
| `workspace_id_override` | String | Override the config file workspace ID |

**Outputs:**

| Output | Type | Description |
|--------|------|-------------|
| `IMAGE` | IMAGE | Generated image tensor (or video thumbnail) |
| `VIDEO_URL` | STRING | Video download URL (empty for non-video models) |
| `AUDIO_URL` | STRING | Audio download URL (empty for non-audio models) |

---

## Troubleshooting

### "No Sequencer API key configured"
Create `~/.sequencer/config.json` with your API key. See [Configuration](#configuration).

### "No models loaded"
- Check your internet connection
- Verify your API key is valid at [sequencer.media/settings](https://sequencer.media/settings)
- Restart ComfyUI to refresh the model registry

### "Insufficient credits"
Top up your balance at [sequencer.media](https://sequencer.media).

### "Generation timed out"
Some models (especially video) can take 1-3 minutes. If the timeout persists, check the [Sequencer dashboard](https://sequencer.media) for status.

### Node doesn't appear in the menu
Ensure the folder is named `sequencer-comfy-nodes` and placed directly inside `ComfyUI/custom_nodes/`. Restart ComfyUI completely.

---

## Support

- **Website:** [sequencer.media](https://sequencer.media)
- **Issues:** [GitHub Issues](https://github.com/sequencer-media/sequencer-comfy-nodes/issues)
- **Discord:** [Sequencer Community](https://discord.gg/sequencer)

---

## License

MIT License. See [LICENSE](LICENSE) for details.
