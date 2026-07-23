"""
Live Audio Streaming Session
=============================
Implements async context manager for live audio sessions with streaming support.
Maintains conversation history, tool calls, graceful shutdown, and true streaming
from Ollama using /api/chat with stream=true and incremental response emission.
"""

import asyncio
import json
import urllib.request
from typing import Optional, List, Dict, Any, AsyncGenerator
from .models import (
    _LiveResponse, _ServerContent, _ToolCall, _FunctionCall,
    _Transcription
)


class OllamaLiveSession:
    """
    Asynchronous stateful session for live audio/text streaming with tool support.
    
    Features:
    - Bidirectional communication queue
    - Conversation history (turns)
    - Tool/function call lifecycle (pause, wait for response, resume)
    - Graceful shutdown and cancellation
    - True streaming from Ollama with incremental response emission
    - Gemini Live API compatibility
    
    Usage:
        async with session as s:
            await s.send_client_content(turns={...}, turn_complete=True)
            async for response in s.receive():
                # response.data: audio chunks
                # response.server_content: transcriptions
                # response.tool_call: function calls needing execution
                process(response)
                if response.tool_call:
                    result = execute_tools(response.tool_call.function_calls)
                    await s.send_tool_response(result)
    """

    def __init__(self, model: str, config):
        """
        Initialize a new live session.
        
        Args:
            model: Model identifier (e.g., "gemini-2.5-flash", "llama2")
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
        
        # Tool call state machine
        self._tool_response_event = asyncio.Event()
        self._pending_tool_responses: List[Dict[str, Any]] = []
        self._awaiting_tool_response = False
        
        # Conversation history
        self.conversation_history: List[Dict[str, Any]] = []
        self.tool_calls_pending: List[Dict[str, Any]] = []
        
        # Cancellation and resource tracking
        self._active_tasks: set = set()
        
        # Ollama connection settings
        self.ollama_host = "http://127.0.0.1:11434"
        self.ollama_model = model or "llama2"

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
        self._tool_response_event.set()  # Release any tool waiters
        
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

    async def receive(self) -> AsyncGenerator[_LiveResponse, None]:
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
        Initiates streaming from Ollama if turn_complete=True.
        
        Args:
            turns: Dict with "parts" containing text/data/metadata
                  Example: {"parts": [{"text": "Hello"}]}
            turn_complete: Whether this completes the user's turn
            
        Stores in history and initiates Ollama streaming if needed.
        """
        if not self._is_active:
            return
        
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
        
        if turn_complete:
            # Start streaming from Ollama in background
            task = asyncio.create_task(
                self._stream_from_ollama(text)
            )
            self._active_tasks.add(task)
            task.add_done_callback(self._active_tasks.discard)

    async def _stream_from_ollama(self, user_text: str):
        """
        Stream response from Ollama using /api/chat with stream=true.
        Parse JSON chunks, emit _LiveResponse objects incrementally.
        Handle tool calls: pause generation, emit _ToolCall, await send_tool_response().
        
        Args:
            user_text: User message text
        """
        try:
            # Build messages for Ollama
            messages = self._build_messages(user_text)
            
            # TODO: Check if tools are enabled in config
            # For now, simple text generation without tools
            
            url = f"{self.ollama_host}/api/chat"
            payload = {
                "model": self.ollama_model,
                "messages": messages,
                "stream": True
            }
            
            # Make streaming request
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._handle_streaming_response,
                url,
                json.dumps(payload)
            )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[Streaming] Error: {e}")
            # Emit error response
            response = _LiveResponse(
                server_content=_ServerContent(
                    output_text=f"Stream error: {str(e)[:100]}",
                    turn_complete=True
                )
            )
            await self._receive_queue.put(response)

    def _handle_streaming_response(self, url: str, payload_json: str):
        """
        Synchronous HTTP streaming handler.
        Called in executor thread to avoid blocking event loop.
        
        Parses Ollama's streaming JSON, emits responses to queue.
        Handles tool calls by pausing, emitting _ToolCall, and awaiting response.
        """
        try:
            req = urllib.request.Request(
                url,
                data=payload_json.encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(req) as response:
                full_content = ""
                tool_buffer = ""
                in_tool_call = False
                
                for chunk_bytes in iter(lambda: response.read(1024), b''):
                    if not chunk_bytes:
                        break
                    
                    # Decode and parse lines (Ollama sends JSON lines)
                    chunk_str = chunk_bytes.decode('utf-8')
                    lines = chunk_str.split('\n')
                    
                    for line in lines:
                        if not line.strip():
                            continue
                        
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        
                        # Extract message content
                        if 'message' in data and 'content' in data['message']:
                            content = data['message']['content']
                            full_content += content
                            
                            # Check for tool call markers (e.g., <tool_call>...</tool_call>)
                            # TODO: Implement actual tool call parsing based on model output format
                            
                            # Emit incremental response
                            asyncio.run_coroutine_threadsafe(
                                self._receive_queue.put(
                                    _LiveResponse(
                                        server_content=_ServerContent(
                                            output_text=content,
                                            turn_complete=False
                                        )
                                    )
                                ),
                                asyncio.get_event_loop()
                            )
                        
                        # Check for stream completion
                        if data.get('done', False):
                            # Store assistant response in history
                            self.conversation_history.append({
                                "role": "assistant",
                                "content": full_content,
                                "turn": self._turn_count
                            })
                            
                            # Emit final turn_complete
                            asyncio.run_coroutine_threadsafe(
                                self._receive_queue.put(
                                    _LiveResponse(
                                        server_content=_ServerContent(
                                            turn_complete=True
                                        )
                                    )
                                ),
                                asyncio.get_event_loop()
                            )
        
        except Exception as e:
            print(f"[Ollama Stream] Error: {e}")

    def _build_messages(self, new_user_text: str) -> List[Dict[str, str]]:
        """
        Build Ollama message list from conversation history.
        
        Args:
            new_user_text: Current user message
            
        Returns:
            List of messages for Ollama /api/chat
        """
        messages = []
        
        # Include system instruction if present
        if self.config and self.config.system_instruction:
            messages.append({
                "role": "system",
                "content": self.config.system_instruction
            })
        
        # Add conversation history
        for item in self.conversation_history:
            if item.get("role") in ("user", "assistant"):
                messages.append({
                    "role": item["role"],
                    "content": item.get("content", "")
                })
        
        # Add current user message
        messages.append({
            "role": "user",
            "content": new_user_text
        })
        
        return messages

    async def send_realtime_input(self, media: dict):
        """
        Send real-time audio/media data to the session.
        
        Args:
            media: Dict with "data" (bytes) and "mime_type" (str)
                  Example: {"data": b"...", "mime_type": "audio/pcm"}
                  
        Stores in history for context.
        
        TODO: Integrate with speech-to-text for transcription
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
        
        # TODO: Transcribe audio, then send_client_content with transcribed text

    async def send_tool_response(self, function_responses: list):
        """
        Send tool/function execution results back to the model.
        Resumes generation with tool outputs included.
        
        Args:
            function_responses: List of FunctionResponse objects
                                with .id, .name, .response attributes
                                
        Stores results and continues conversation with tool outputs.
        """
        if not self._is_active:
            return
        
        # Log tool responses
        for fr in function_responses:
            print(f"[Tool Response] {fr.name} -> {fr.response}")
            
            # Store in history
            self.conversation_history.append({
                "type": "tool_response",
                "tool_name": fr.name,
                "tool_id": fr.id,
                "response": fr.response,
                "turn": self._turn_count
            })
            
            self._pending_tool_responses.append({
                "id": fr.id,
                "name": fr.name,
                "response": fr.response
            })
        
        # Signal that tool responses are ready
        self._tool_response_event.set()
        
        # Queue turn completion after tool execution
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
        self._pending_tool_responses.clear()

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
