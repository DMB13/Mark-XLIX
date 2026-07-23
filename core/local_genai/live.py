"""
Live Audio Streaming Session
=============================
Implements async context manager for live audio sessions.
Maintains conversation history, tool calls, and graceful shutdown.
"""

import asyncio
from typing import Optional, List, Dict, Any
from .models import _LiveResponse, _ServerContent, _ToolCall


class OllamaLiveSession:
    """
    Asynchronous stateful session for live audio/text streaming.
    
    Manages:
    - Bidirectional communication queue
    - Conversation history (turns)
    - Tool call lifecycle
    - Graceful shutdown and cancellation
    - Turn completion events
    
    Usage:
        async with session as s:
            await s.send_client_content(turns={...}, turn_complete=True)
            async for response in s.receive():
                process(response)
    """

    def __init__(self, model: str, config):
        """
        Initialize a new live session.
        
        Args:
            model: Model identifier (e.g., "gemini-2.5-flash")
            config: LiveConnectConfig with system instruction, tools, etc.
        """
        self.model = model
        self.config = config
        
        # Internal state
        self._receive_queue: asyncio.Queue = asyncio.Queue()
        self._send_queue: asyncio.Queue = asyncio.Queue()
        self._is_active = False
        self._shutdown_event = asyncio.Event()
        self._turn_count = 0
        
        # Conversation history
        self.conversation_history: List[Dict[str, Any]] = []
        self.tool_calls_pending: List[Dict[str, Any]] = []
        
        # Cancellation and resource tracking
        self._active_tasks: set = set()

    async def __aenter__(self):
        """
        Enter async context manager.
        Mark session as active.
        """
        self._is_active = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Exit async context manager.
        Gracefully shut down: cancel tasks, drain queues, close resources.
        """
        await self.close()
        return False

    async def close(self):
        """
        Gracefully shutdown the session.
        - Signal shutdown event
        - Cancel pending tasks
        - Clear queues
        - Clean up resources
        """
        self._is_active = False
        self._shutdown_event.set()
        
        # Cancel all active tasks
        for task in list(self._active_tasks):
            if not task.done():
                task.cancel()
        
        # Wait for cancellations to propagate
        if self._active_tasks:
            await asyncio.sleep(0.1)
        
        # Drain queues to unblock any waiters
        while not self._receive_queue.empty():
            try:
                self._receive_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        
        while not self._send_queue.empty():
            try:
                self._send_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        
        # TODO: Close any open network connections, file handles, etc.

    async def receive(self):
        """
        Async generator: yield responses from the session.
        
        Blocks until responses are available or session is closed.
        
        Yields:
            _LiveResponse: Contains audio data, transcriptions, or tool calls
            
        Raises:
            asyncio.CancelledError: If session is cancelled
        """
        try:
            while self._is_active:
                try:
                    # Wait for response with timeout to allow graceful shutdown
                    response = await asyncio.wait_for(
                        self._receive_queue.get(),
                        timeout=1.0
                    )
                    yield response
                except asyncio.TimeoutError:
                    # Check if shutdown requested
                    if self._shutdown_event.is_set():
                        break
                    continue
        except asyncio.CancelledError:
            raise

    async def send_client_content(self, turns: dict, turn_complete: bool = False):
        """
        Send user text input to the session.
        
        Args:
            turns: Dict with "parts" containing text/data/metadata
                  Example: {"parts": [{"text": "Hello"}]}
            turn_complete: Whether this completes the user's turn
            
        Stores in history and queues response.
        
        TODO: Integrate with Ollama API for actual message processing
        """
        self._turn_count += 1
        
        # Extract text from turns
        text = ""
        if turns and "parts" in turns:
            for part in turns["parts"]:
                if isinstance(part, dict) and "text" in part:
                    text = part["text"]
                    break
        
        # Store in conversation history
        self.conversation_history.append({
            "role": "user",
            "content": text,
            "turn": self._turn_count,
            "turn_complete": turn_complete
        })
        
        # TODO: Send to Ollama API
        # For now, queue a simple mock response
        response = _LiveResponse(
            server_content=_ServerContent(
                output_text="Received text input locally.",
                turn_complete=True
            )
        )
        await self._receive_queue.put(response)

    async def send_realtime_input(self, media: dict):
        """
        Send real-time audio/media data to the session.
        
        Args:
            media: Dict with "data" (bytes) and "mime_type" (str)
                  Example: {"data": b"...", "mime_type": "audio/pcm"}
                  
        Stores in history for context.
        
        TODO: Stream audio to Ollama or external speech-to-text service
        """
        if not self._is_active:
            return
        
        # Store media reference in history
        self.conversation_history.append({
            "role": "user",
            "type": "audio",
            "mime_type": media.get("mime_type"),
            "data_size": len(media.get("data", b"")) if media else 0,
            "turn": self._turn_count
        })
        
        # TODO: Process audio stream (transcribe, pass to model, etc.)

    async def send_tool_response(self, function_responses: list):
        """
        Send tool/function execution results back to the model.
        
        Args:
            function_responses: List of FunctionResponse objects
                                with .id, .name, .response attributes
                                
        Stores results and queues continuation.
        
        TODO: Feed results back to Ollama for next turn
        """
        if not self._is_active:
            return
        
        # Log tool responses
        for fr in function_responses:
            print(f"[Local Tool Executed] {fr.name} -> {fr.response}")
            
            # Store in history
            self.conversation_history.append({
                "type": "tool_response",
                "tool_name": fr.name,
                "tool_id": fr.id,
                "response": fr.response,
                "turn": self._turn_count
            })
        
        # Clear pending tool calls
        self.tool_calls_pending.clear()
        
        # Queue turn completion
        response = _LiveResponse(
            server_content=_ServerContent(turn_complete=True)
        )
        await self._receive_queue.put(response)

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """
        Return full conversation history for context or debugging.
        
        Returns:
            List of turns with role, content, metadata
        """
        return list(self.conversation_history)

    def clear_history(self):
        """Clear conversation history for a fresh session."""
        self.conversation_history.clear()
        self._turn_count = 0
        self.tool_calls_pending.clear()

    async def inject_response(self, response: _LiveResponse):
        """
        Inject a response into the receive queue.
        Used internally for testing or special events.
        
        Args:
            response: _LiveResponse to queue
        """
        if self._is_active:
            await self._receive_queue.put(response)

    @property
    def is_active(self) -> bool:
        """Return whether session is currently active."""
        return self._is_active

    @property
    def turn_number(self) -> int:
        """Return current turn count."""
        return self._turn_count
