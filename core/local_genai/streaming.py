"""
Streaming Utilities
===================
Handles streaming protocol, chunking, and buffering.
Maintains compatibility with both Ollama and Gemini streaming formats.
"""

from typing import AsyncIterator, Optional
import asyncio
import json


class StreamBuffer:
    """
    Buffers and manages streamed data.
    Handles partial chunks and line boundaries.
    """

    def __init__(self, chunk_size: int = 1024):
        """
        Initialize stream buffer.
        
        Args:
            chunk_size: Size of chunks to yield
        """
        self.chunk_size = chunk_size
        self.buffer = b""
        self.closed = False

    def add_data(self, data: bytes):
        """
        Add data to buffer.
        
        Args:
            data: Bytes to add
        """
        self.buffer += data

    def get_line(self) -> Optional[str]:
        """
        Get next complete line from buffer.
        
        Returns:
            Decoded line or None if no complete line available
        """
        if b'\n' not in self.buffer:
            return None
        
        idx = self.buffer.index(b'\n')
        line = self.buffer[:idx].decode('utf-8')
        self.buffer = self.buffer[idx + 1:]
        return line

    def close(self):
        """
        Mark stream as closed.
        """
        self.closed = True

    def has_data(self) -> bool:
        """
        Check if buffer has data.
        
        Returns:
            True if buffer is not empty
        """
        return len(self.buffer) > 0


class StreamParser:
    """
    Parses streaming responses from Ollama.
    Handles JSON line protocol.
    """

    @staticmethod
    async def parse_ollama_stream(stream_iter) -> AsyncIterator[dict]:
        """
        Parse Ollama streaming response.
        
        Args:
            stream_iter: Iterator of bytes from HTTP stream
            
        Yields:
            Parsed JSON objects from stream
        """
        buffer = StreamBuffer()
        
        try:
            async for chunk in stream_iter:
                buffer.add_data(chunk)
                
                while True:
                    line = buffer.get_line()
                    if not line:
                        break
                    
                    try:
                        data = json.loads(line)
                        yield data
                    except json.JSONDecodeError:
                        continue
        finally:
            buffer.close()

    @staticmethod
    def parse_json_line(line: str) -> Optional[dict]:
        """
        Parse single JSON line.
        
        Args:
            line: JSON line string
            
        Returns:
            Parsed dict or None if invalid
        """
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None


class ResponseAggregator:
    """
    Aggregates streaming response chunks into complete messages.
    """

    def __init__(self):
        """Initialize response aggregator."""
        self.chunks = []
        self.metadata = {}

    def add_chunk(self, chunk: dict):
        """
        Add response chunk.
        
        Args:
            chunk: Parsed chunk from stream
        """
        self.chunks.append(chunk)
        if 'model' in chunk:
            self.metadata['model'] = chunk['model']
        if 'created_at' in chunk:
            self.metadata['created_at'] = chunk['created_at']

    def get_content(self) -> str:
        """
        Extract aggregated content from chunks.
        
        Returns:
            Combined message content
        """
        content = ""
        for chunk in self.chunks:
            if 'message' in chunk and 'content' in chunk['message']:
                content += chunk['message']['content']
        return content

    def is_complete(self) -> bool:
        """
        Check if response is complete.
        
        Returns:
            True if final chunk received
        """
        if not self.chunks:
            return False
        return self.chunks[-1].get('done', False)
