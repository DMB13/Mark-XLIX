"""
Client and Live API Interface
==============================
Provides Client, _AsyncClient, and _LiveClient for Google GenAI-compatible API.
Implements true streaming from Ollama using /api/chat with stream=true.
"""

import asyncio
import json
import urllib.request
from typing import Optional
from .models import _Models, types
from .live import OllamaLiveSession
from .models import _LiveResponse, _ServerContent


class _LiveClient:
    """
    Live connection client for audio/streaming sessions.
    Manages connection setup and session creation.
    """

    def connect(self, model: str, config: types.LiveConnectConfig):
        """
        Create a new live session.
        
        Args:
            model: Model identifier
            config: LiveConnectConfig with settings
            
        Returns:
            OllamaLiveSession async context manager
        """
        return OllamaLiveSession(model=model, config=config)


class _AsyncClient:
    """
    Async API client with live audio streaming support.
    Provides access to live session creation.
    """

    def __init__(self):
        """Initialize async client with live connection support."""
        self.live = _LiveClient()


class Client:
    """
    Main entry point for local GenAI API.
    
    Provides:
    - Synchronous models interface (generate_content, etc.)
    - Asynchronous client (aio) with live streaming
    - Full Google GenAI SDK API compatibility
    
    Usage:
        client = Client(api_key="...", http_options={...})
        async with client.aio.live.connect(model="...", config=config) as session:
            await session.send_client_content(...)
            async for response in session.receive():
                process(response)
    """

    def __init__(self, api_key: str = None, http_options: dict = None):
        """
        Initialize GenAI client.
        
        Args:
            api_key: API key (not used for local Ollama, for compatibility)
            http_options: HTTP options dict (e.g., {"api_version": "v1beta"})
        """
        self.api_key = api_key
        self.http_options = http_options or {}
        
        # Sync and async interfaces
        self.models = _Models()
        self.aio = _AsyncClient()
