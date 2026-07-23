"""
Conversation History Management
================================
Stores messages in Gemini-compatible roles.
Converts internally to Ollama chat format.
Maintains history for context and debugging.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime


class Message:
    """
    Represents a single message in conversation.
    Stores in Gemini format, converts to Ollama format on demand.
    """

    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_SYSTEM = "system"
    ROLE_FUNCTION = "function"

    def __init__(
        self,
        role: str,
        content: str,
        turn_number: int = 0,
        metadata: Dict[str, Any] = None
    ):
        """
        Initialize message.
        
        Args:
            role: Message role (user, assistant, system, function)
            content: Message content/text
            turn_number: Conversation turn number
            metadata: Additional metadata
        """
        self.role = role
        self.content = content
        self.turn_number = turn_number
        self.timestamp = datetime.now()
        self.metadata = metadata or {}

    def to_gemini_format(self) -> Dict[str, Any]:
        """
        Convert to Gemini API format.
        
        Returns:
            Dict compatible with Gemini API
        """
        return {
            "role": self.role,
            "parts": [{"text": self.content}]
        }

    def to_ollama_format(self) -> Dict[str, str]:
        """
        Convert to Ollama chat format.
        
        Returns:
            Dict compatible with Ollama /api/chat
        """
        # Map Gemini roles to Ollama roles
        role_map = {
            self.ROLE_USER: "user",
            self.ROLE_ASSISTANT: "assistant",
            self.ROLE_SYSTEM: "system",
            self.ROLE_FUNCTION: "assistant",
        }
        
        return {
            "role": role_map.get(self.role, self.role),
            "content": self.content
        }

    def __repr__(self) -> str:
        return f"Message(role={self.role}, content={self.content[:50]}...)"


class ConversationHistory:
    """
    Manages full conversation history.
    Stores in Gemini format, converts to Ollama on demand.
    """

    def __init__(self, max_history: int = 100):
        """
        Initialize conversation history.
        
        Args:
            max_history: Maximum messages to keep (0 for unlimited)
        """
        self.messages: List[Message] = []
        self.max_history = max_history
        self.turn_count = 0

    def add_user_message(self, content: str, metadata: Dict[str, Any] = None):
        """
        Add user message.
        
        Args:
            content: Message content
            metadata: Optional metadata
        """
        self.messages.append(
            Message(Message.ROLE_USER, content, self.turn_count, metadata)
        )
        self._trim_history()

    def add_assistant_message(self, content: str, metadata: Dict[str, Any] = None):
        """
        Add assistant message.
        
        Args:
            content: Message content
            metadata: Optional metadata
        """
        self.messages.append(
            Message(Message.ROLE_ASSISTANT, content, self.turn_count, metadata)
        )
        self.turn_count += 1
        self._trim_history()

    def add_system_message(self, content: str):
        """
        Add system message.
        
        Args:
            content: System message content
        """
        self.messages.insert(
            0,
            Message(Message.ROLE_SYSTEM, content, 0)
        )

    def add_function_response(self, tool_name: str, result: str, metadata: Dict[str, Any] = None):
        """
        Add tool/function response.
        
        Args:
            tool_name: Name of tool that executed
            result: Tool execution result
            metadata: Optional metadata
        """
        meta = metadata or {}
        meta['tool_name'] = tool_name
        self.messages.append(
            Message(Message.ROLE_FUNCTION, result, self.turn_count, meta)
        )

    def get_gemini_format(self) -> List[Dict[str, Any]]:
        """
        Get full history in Gemini API format.
        
        Returns:
            List of messages in Gemini format
        """
        return [msg.to_gemini_format() for msg in self.messages]

    def get_ollama_format(self, include_system: bool = True) -> List[Dict[str, str]]:
        """
        Get full history in Ollama format.
        
        Args:
            include_system: Whether to include system messages
            
        Returns:
            List of messages in Ollama format
        """
        messages = []
        for msg in self.messages:
            if not include_system and msg.role == Message.ROLE_SYSTEM:
                continue
            messages.append(msg.to_ollama_format())
        return messages

    def clear(self):
        """
        Clear all messages.
        """
        self.messages.clear()
        self.turn_count = 0

    def _trim_history(self):
        """
        Trim history if it exceeds max_history.
        Keeps system messages at top.
        """
        if self.max_history > 0 and len(self.messages) > self.max_history:
            # Keep first system message if present
            system_msgs = [m for m in self.messages if m.role == Message.ROLE_SYSTEM]
            other_msgs = [m for m in self.messages if m.role != Message.ROLE_SYSTEM]
            
            # Keep only recent messages
            other_msgs = other_msgs[-(self.max_history - len(system_msgs)):]
            self.messages = system_msgs + other_msgs

    def __len__(self) -> int:
        return len(self.messages)

    def __repr__(self) -> str:
        return f"ConversationHistory(turns={self.turn_count}, messages={len(self.messages)})"
