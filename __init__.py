"""
Sequencer ComfyUI Nodes
=======================

Custom nodes for ComfyUI that provide access to the full Sequencer AI
model collection — image generators, video generators, audio generators,
upscalers, style transfer, and more.

One universal node. Every model. Dynamic I/O.

Setup:
    1. Get your API key from sequencer.media → Settings → API Keys
    2. Save to ~/.sequencer/config.json: {"api_key": "sk_your_key"}
    3. Restart ComfyUI

Usage:
    Add "🎯 Sequencer Generate" from the node menu → Sequencer category.
    Select any model from the dropdown, enter a prompt, and queue.
"""

from .nodes.sequencer_node import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

WEB_DIRECTORY = None

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
