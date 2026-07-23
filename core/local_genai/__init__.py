"""
Local GenAI Package - Public API
=================================
Drop-in replacement for google.genai with 100% backward compatibility.

Exports all public classes and types required by main.py.
No changes needed to main.py imports.

Usage:
    import local_genai as genai
    from local_genai import types
    
    client = genai.Client(api_key="...", http_options={...})
    config = types.LiveConnectConfig(...)
    async with client.aio.live.connect(model="...", config=config) as session:
        await session.send_client_content(turns={...}, turn_complete=True)
        async for response in session.receive():
            process(response)
"""

# ====================================================================
# Import all public API components
# ====================================================================

from .client import Client, _AsyncClient, _LiveClient
from .models import (
    types,
    _Models,
    _LiveResponse,
    _ServerContent,
    _Transcription,
    _FunctionCall,
    _ToolCall,
)
from .live import OllamaLiveSession

# ====================================================================
# Backward Compatibility Aliases
# ====================================================================

# For code that might import LocalLiveSession directly
LocalLiveSession = OllamaLiveSession

# ====================================================================
# Public API
# ====================================================================

__all__ = [
    # Main entry points
    "Client",
    "types",
    
    # Internal classes (for advanced usage)
    "_AsyncClient",
    "_LiveClient",
    "_Models",
    
    # Response types
    "_LiveResponse",
    "_ServerContent",
    "_Transcription",
    "_FunctionCall",
    "_ToolCall",
    
    # Sessions (both names for compatibility)
    "LocalLiveSession",    # Original name (deprecated, use OllamaLiveSession)
    "OllamaLiveSession",   # New name (preferred)
]

__version__ = "1.0.0"
__author__ = "Local GenAI Contributors"
__description__ = "Local GenAI: Offline Gemini Live API Compatible Layer"
