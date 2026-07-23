"""
Local GenAI Module
==================
Provides a mock Google GenAI-compatible interface for local LLM and live audio streaming.

Public API:
    - Client: Main entry point for API interactions
    - types: Mock google.genai.types for config classes
    
Maintains backward compatibility with main.py without changes.

Usage:
    import local_genai as genai
    from local_genai import types
    
    client = genai.Client(api_key="...", http_options={...})
    config = types.LiveConnectConfig(...)
    async with client.aio.live.connect(model="...", config=config) as session:
        await session.send_client_content(...)
        async for response in session.receive():
            ...
"""

from .client import Client
from .models import types

__all__ = ["Client", "types"]
