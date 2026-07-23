"""
Local GenAI Modular Package - Structure Summary
===============================================

This document describes the refactored core/local_genai/ package structure.
All files maintain 100% backward compatibility with main.py imports.

PACKAGE STRUCTURE
=================

core/local_genai/
├── __init__.py           # Public API exports (Client, types)
├── client.py             # Client, _AsyncClient, _LiveClient
├── models.py             # types, _Models, response classes
├── live.py               # OllamaLiveSession (async streaming)
├── streaming.py          # Streaming response handlers [TODO]
├── audio.py              # Speech-to-text & TTS engines
├── tools.py              # Tool/function call handling [TODO]
├── vision.py             # Image processing & multimodal
├── events.py             # Event system for callbacks [TODO]
└── history.py            # Conversation history & context [TODO]

PUBLIC API COMPATIBILITY
========================

From main.py's perspective, nothing changes:

    import local_genai as genai
    from local_genai import types
    
    client = genai.Client(api_key="...", http_options={...})
    config = types.LiveConnectConfig(...)
    async with client.aio.live.connect(model="...", config=config) as session:
        await session.send_client_content(turns={...}, turn_complete=True)
        async for response in session.receive():
            process(response)

MODULE RESPONSIBILITIES
=======================

__init__.py
-----------
• Re-exports: Client, types
• Public interface for entire package
• No implementation details exposed

client.py
---------
• Client: Main entry point
  - client.models: Synchronous model access (_Models instance)
  - client.aio: Async client (_AsyncClient instance)
    - client.aio.live: Live connection client (_LiveClient instance)
      - .connect(model, config) → OllamaLiveSession

models.py
---------
• types: Mock google.genai.types namespace
  - PrebuiltVoiceConfig
  - VoiceConfig
  - SpeechConfig
  - SessionResumptionConfig
  - FunctionResponse
  - LiveConnectConfig
• _Models: Synchronous model operations
  - .generate_content(model, contents, **kwargs)
  - Uses Ollama /api/chat with stream=False
• Response wrapper classes:
  - _Transcription
  - _ServerContent
  - _FunctionCall
  - _ToolCall
  - _LiveResponse

live.py
-------
• OllamaLiveSession: Async streaming session
  - __aenter__ / __aexit__: Async context manager
  - send_client_content(turns, turn_complete): Send user text/images
  - send_realtime_input(media): Send audio stream
  - send_tool_response(function_responses): Return tool results
  - receive(): Async generator for responses
  - close(): Graceful shutdown
• Features:
  - True streaming from Ollama (/api/chat with stream=true)
  - Incremental response emission to UI
  - Conversation history tracking
  - Tool call state machine (pause, await response, resume)
  - Cooperative cancellation (when new audio arrives)
  - Graceful resource cleanup

streaming.py [TODO]
-------------------
• StreamProcessor: JSON line parser for Ollama streams
• Incremental response builder
• Handles partial chunks, line buffering

audio.py
--------
• TranscriptionEngine: Speech-to-text (Whisper/faster-whisper)
  - .transcribe(audio_bytes, sample_rate) → str
• TextToSpeechEngine: Text-to-speech (Piper/Kokoro)
  - .synthesize(text) → (pcm_bytes, sample_rate)
• AudioProcessor: High-level coordinator
  - .speech_to_text()
  - .text_to_speech()
• PCM audio compatible with sounddevice playback

tools.py [TODO]
---------------
• ToolRegistry: Register and manage function declarations
• ToolParser: Parse model output for tool calls
• ToolExecutor: Execute tools and format responses
• Converts Ollama tool format → Gemini _ToolCall/_FunctionCall

vision.py
---------
• ImageProcessor: Image format conversion & validation
  - .decode_inline_data(inline_data) → (bytes, mime_type)
  - .validate_image(bytes, mime_type) → bool
  - .resize_image(bytes, ...) → bytes
• VisionContext: Image lifecycle management
• OllamaVisionFormatter: Convert Gemini → Ollama image format
  - .format_for_ollama(inline_data) → dict
  - .build_vision_message(text, images) → dict

events.py [TODO]
----------------
• EventEmitter: Base event system
• SessionEvent types
  - on_turn_start, on_turn_complete
  - on_tool_call, on_tool_response
  - on_error, on_close
• Event subscription/publishing

history.py [TODO]
-----------------
• ConversationHistory: Store and retrieve turns
  - .add_turn(role, content, metadata)
  - .get_history(limit) → List
  - .export(format) → str (JSON, markdown, etc.)
• ContextWindow: Manage sliding window for large conversations
  - .fit_to_limit(max_tokens)
  - .summarize_old_turns()

STREAMING ARCHITECTURE
======================

Current Flow (send_client_content → receive):

1. User calls: await session.send_client_content({"parts": [{"text": "..."}]})
2. Session stores in conversation_history
3. Session spawns background task: _stream_from_ollama(text)
4. Background task makes HTTP POST to Ollama /api/chat with stream=true
5. For each JSON chunk received:
   - Parse message.content
   - Emit _LiveResponse(server_content=_ServerContent(output_text=chunk))
   - UI receives and displays incrementally
6. When done=true:
   - Store full response in history
   - Emit final _LiveResponse(turn_complete=True)
7. Main loop: async for response in session.receive(): yield response

Tool Call Flow (when model wants to call functions):

1. During streaming, detect tool call markers in model output
2. Parse and emit _LiveResponse(tool_call=_ToolCall([_FunctionCall(...), ...]))
3. Main loop calls _execute_tool() for each function
4. Main loop collects FunctionResponse objects
5. Main loop calls: await session.send_tool_response(responses)
6. Session stores tool results in history
7. Session resumes generation with tool outputs
8. Continue streaming as normal

CANCELLATION STRATEGY
====================

When new audio arrives during generation:

1. New send_realtime_input() call
2. Session detects active streaming task
3. Cancel current streaming task via asyncio.cancel()
4. Drain receive queue (unblock any waiters)
5. Start new streaming task with new audio

This ensures:
- No queue corruption
- Immediate response to user interruption
- Clean task cancellation
- Event loop remains healthy

BACKWARD COMPATIBILITY GUARANTEES
=================================

✓ main.py imports unchanged:
  - "import local_genai as genai"
  - "from local_genai import types"

✓ Client API unchanged:
  - Client(api_key=..., http_options=...)
  - client.models.generate_content()
  - client.aio.live.connect()

✓ Session API unchanged:
  - async with session as s:
  - await s.send_client_content(turns={...}, turn_complete=bool)
  - async for response in s.receive():
  - await s.send_tool_response(responses)

✓ Response types unchanged:
  - _LiveResponse.data (audio bytes)
  - _LiveResponse.server_content.output_transcription.text
  - _LiveResponse.server_content.input_transcription.text
  - _LiveResponse.server_content.turn_complete
  - _LiveResponse.tool_call.function_calls[].name/args/id
  - types.FunctionResponse(id, name, response)

✓ Config types unchanged:
  - types.LiveConnectConfig()
  - types.SpeechConfig()
  - types.VoiceConfig()
  - types.PrebuiltVoiceConfig()
  - types.SessionResumptionConfig()

TESTING & VALIDATION
====================

Recommend:
• Unit tests for each module (no integration needed yet)
• Mock Ollama responses for live.py tests
• Test streaming with partial/incomplete chunks
• Test tool call parsing and response handling
• Test image processing without vision model
• Test audio conversion without actual TTS/STT

STATUS
======

Implemented:
✓ __init__.py - Public API
✓ client.py - Client classes
✓ models.py - Types and response classes, _Models
✓ live.py - OllamaLiveSession with streaming & tool support
✓ audio.py - Audio engine interfaces
✓ vision.py - Image processing

TODO:
□ streaming.py - JSON parser, incremental builder
□ tools.py - Tool registry, parser, executor
□ events.py - Event emitter system
□ history.py - History management & context window
□ Integration with actual Ollama (/api/chat endpoint)
□ Tool call detection & parsing in live.py
□ Error handling & edge cases
□ Logging & debugging helpers

"""
