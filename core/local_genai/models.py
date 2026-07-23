"""
Models and Type Definitions
============================
Provides mock google.genai.types and model client classes.
Maintains compatibility with Google GenAI SDK API surface.
"""

import asyncio
import json
import urllib.request
from typing import Optional, List, Dict, Any


# ====================================================================
# 1. TYPES DEFINITION (Mocks google.genai.types)
# ====================================================================

class types:
    """
    Mock google.genai.types namespace.
    Contains all type/config classes required by main.py.
    """

    class PrebuiltVoiceConfig:
        """Configuration for a prebuilt voice."""
        def __init__(self, voice_name: str = None, **kwargs):
            self.voice_name = voice_name

    class VoiceConfig:
        """Voice configuration wrapper."""
        def __init__(self, prebuilt_voice_config=None, **kwargs):
            self.prebuilt_voice_config = prebuilt_voice_config

    class SpeechConfig:
        """Speech output configuration."""
        def __init__(self, voice_config=None, **kwargs):
            self.voice_config = voice_config

    class SessionResumptionConfig:
        """Configuration for session resumption."""
        def __init__(self, **kwargs):
            pass

    class FunctionResponse:
        """Response from a tool/function call."""
        def __init__(self, id: str, name: str, response: dict):
            self.id = id
            self.name = name
            self.response = response

    class LiveConnectConfig:
        """Configuration for live audio streaming connection."""
        def __init__(
            self,
            response_modalities: list = None,
            system_instruction=None,
            tools: list = None,
            speech_config=None,
            output_audio_transcription=None,
            input_audio_transcription=None,
            session_resumption=None,
            **kwargs
        ):
            self.response_modalities = response_modalities or []
            self.system_instruction = system_instruction
            self.tools = tools or []
            self.speech_config = speech_config
            self.output_audio_transcription = output_audio_transcription
            self.input_audio_transcription = input_audio_transcription
            self.session_resumption = session_resumption


# ====================================================================
# 2. RESPONSE WRAPPER CLASSES
# ====================================================================

class _Transcription:
    """Transcribed text output."""
    def __init__(self, text: str = ""):
        self.text = text


class _ServerContent:
    """Server response content with transcriptions and turn state."""
    def __init__(self, output_text: str = "", input_text: str = "", turn_complete: bool = False):
        self.output_transcription = _Transcription(output_text)
        self.input_transcription = _Transcription(input_text)
        self.turn_complete = turn_complete


class _FunctionCall:
    """Representation of a function/tool call."""
    def __init__(self, name: str, args: dict, id: str = "local_call"):
        self.name = name
        self.args = args
        self.id = id


class _ToolCall:
    """Container for tool/function calls."""
    def __init__(self, function_calls: list):
        self.function_calls = function_calls


class _LiveResponse:
    """Live session response containing audio, transcriptions, or tool calls."""
    def __init__(self, data: bytes = None, server_content=None, tool_call=None):
        self.data = data
        self.server_content = server_content
        self.tool_call = tool_call


# ====================================================================
# 3. MODELS INTERFACE
# ====================================================================

class _Models:
    """
    Models interface for non-streaming generation.
    Connects to local Ollama instance.
    """

    def generate_content(self, model: str, contents, **kwargs):
        """
        Generate content using Ollama's /api/chat endpoint.
        
        Args:
            model: Model name (e.g., "llama2")
            contents: Prompt text or message
            **kwargs: Additional parameters
            
        Returns:
            Object with .text attribute containing response
        """
        # TODO: Implement full Ollama API integration
        # For now, basic HTTP request to Ollama
        url = "http://127.0.0.1:11434/api/chat"

        # Convert contents to string if needed
        prompt_text = str(contents)

        payload = {
            "model": model or "llama2",
            "messages": [{"role": "user", "content": prompt_text}],
            "stream": False
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))

                class LiveResponse:
                    def __init__(self, text):
                        self.text = text

                # Extract message content from Ollama response
                response_text = ""
                if "message" in result and "content" in result["message"]:
                    response_text = result["message"]["content"]
                elif "response" in result:
                    response_text = result["response"]

                return LiveResponse(
                    text=response_text or "Model returned empty response."
                )
        except Exception as e:
            class ErrorResponse:
                def __init__(self, err_msg):
                    self.text = err_msg

            return ErrorResponse(
                err_msg=f"Ollama generation failed. Is local LLM running? Error: {e}"
            )
