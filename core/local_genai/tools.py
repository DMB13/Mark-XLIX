"""
Tool and Function Call Management
==================================
Handles tool/function declarations, invocation, and result processing.
Maintains Gemini Live API compatibility while converting to Ollama format.
"""

from typing import List, Dict, Any, Optional, Callable
import json


class ToolDeclaration:
    """
    Represents a single tool/function that the model can call.
    """

    def __init__(self, name: str, description: str, parameters: Dict[str, Any]):
        """
        Initialize tool declaration.
        
        Args:
            name: Tool/function name
            description: What the tool does
            parameters: JSON schema for parameters
        """
        self.name = name
        self.description = description
        self.parameters = parameters
        self._handler: Optional[Callable] = None

    def set_handler(self, handler: Callable):
        """
        Set the handler function for this tool.
        
        Args:
            handler: Async or sync callable that executes the tool
        """
        self._handler = handler

    def to_ollama_format(self) -> Dict[str, Any]:
        """
        Convert to Ollama tool format.
        
        Returns:
            Dict compatible with Ollama /api/chat tools parameter
        """
        # TODO: Implement Ollama tool format conversion
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }

    def to_gemini_format(self) -> Dict[str, Any]:
        """
        Convert to Gemini API tool format.
        
        Returns:
            Dict compatible with Gemini Live API
        """
        return {
            "function_declarations": [{
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }]
        }


class ToolRegistry:
    """
    Registry of all available tools.
    Manages tool declarations and execution.
    """

    def __init__(self):
        """Initialize tool registry."""
        self.tools: Dict[str, ToolDeclaration] = {}

    def register(self, name: str, description: str, parameters: Dict[str, Any]) -> ToolDeclaration:
        """
        Register a new tool.
        
        Args:
            name: Tool name
            description: Tool description
            parameters: Parameter schema
            
        Returns:
            ToolDeclaration that can be configured further
        """
        tool = ToolDeclaration(name, description, parameters)
        self.tools[name] = tool
        return tool

    def get(self, name: str) -> Optional[ToolDeclaration]:
        """
        Get tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            ToolDeclaration or None if not found
        """
        return self.tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all registered tools in Gemini format.
        
        Returns:
            List of tool declarations
        """
        return [tool.to_gemini_format() for tool in self.tools.values()]

    def to_ollama_format(self) -> List[Dict[str, Any]]:
        """
        Convert all tools to Ollama format.
        
        Returns:
            List of tool declarations for Ollama
        """
        return [tool.to_ollama_format() for tool in self.tools.values()]

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Execute a tool by name.
        
        Args:
            tool_name: Name of tool to execute
            arguments: Arguments to pass to tool
            
        Returns:
            Tool execution result
            
        Raises:
            KeyError: If tool not found
            TypeError: If tool not callable
        """
        tool = self.get(tool_name)
        if not tool:
            raise KeyError(f"Tool not found: {tool_name}")
        
        if not tool._handler:
            raise TypeError(f"Tool {tool_name} has no handler")
        
        # TODO: Handle both async and sync handlers
        return await tool._handler(**arguments)


class FunctionCall:
    """
    Represents a function/tool call from the model.
    """

    def __init__(self, name: str, arguments: Dict[str, Any], call_id: str = None):
        """
        Initialize function call.
        
        Args:
            name: Function/tool name
            arguments: Arguments to function
            call_id: Unique identifier for this call
        """
        self.name = name
        self.arguments = arguments
        self.call_id = call_id or "local_call"

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "name": self.name,
            "arguments": self.arguments,
            "id": self.call_id
        }


class FunctionResponse:
    """
    Response from a tool execution.
    """

    def __init__(self, call_id: str, name: str, response: Dict[str, Any]):
        """
        Initialize function response.
        
        Args:
            call_id: ID of the original call
            name: Tool name
            response: Tool execution result
        """
        self.call_id = call_id
        self.name = name
        self.response = response

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary.
        
        Returns:
            Dict representation for sending to model
        """
        return {
            "id": self.call_id,
            "name": self.name,
            "response": self.response
        }
