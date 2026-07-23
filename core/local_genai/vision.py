"""
Vision and Multimodal Module
=============================
Handles image/vision processing for multimodal AI interactions.
Accepts inline_data images from send_client_content(), converts to Ollama vision format.
Maintains compatibility with Gemini Live API while supporting local vision models.
"""

import base64
import io
from typing import Optional, Dict, Any, Tuple
# TODO: Import PIL/Pillow for image processing
# TODO: Import numpy for image manipulation if needed


class ImageProcessor:
    """
    Image processing for vision model compatibility.
    Converts between formats (base64, bytes, PIL Image).
    Validates and prepares images for model input.
    """

    def __init__(self):
        """Initialize image processor."""
        self.supported_formats = ["image/jpeg", "image/png", "image/webp", "image/gif"]

    def decode_inline_data(self, inline_data: Dict[str, str]) -> Tuple[bytes, str]:
        """
        Decode base64 inline image data.
        
        Args:
            inline_data: Dict with "mime_type" and "data" (base64 string)
                        Example: {"mime_type": "image/png", "data": "iVBOR..."}
            
        Returns:
            Tuple of (image bytes, mime_type)
        """
        mime_type = inline_data.get("mime_type", "image/jpeg")
        data_b64 = inline_data.get("data", "")
        
        try:
            image_bytes = base64.b64decode(data_b64)
            return image_bytes, mime_type
        except Exception as e:
            print(f"[Vision] Decode error: {e}")
            return b"", mime_type

    def encode_to_base64(self, image_bytes: bytes) -> str:
        """
        Encode image bytes to base64 string.
        
        Args:
            image_bytes: Raw image bytes
            
        Returns:
            Base64 encoded string
        """
        return base64.b64encode(image_bytes).decode("ascii")

    def validate_image(self, image_bytes: bytes, mime_type: str) -> bool:
        """
        Validate image format and size.
        
        Args:
            image_bytes: Image data
            mime_type: MIME type
            
        Returns:
            True if valid, False otherwise
        """
        if mime_type not in self.supported_formats:
            return False
        
        if len(image_bytes) > 20 * 1024 * 1024:  # 20 MB limit
            return False
        
        # TODO: Validate image header/magic bytes
        return True

    def resize_image(
        self,
        image_bytes: bytes,
        max_width: int = 1024,
        max_height: int = 1024
    ) -> bytes:
        """
        Resize image to fit model constraints.
        
        Args:
            image_bytes: Original image bytes
            max_width: Maximum width in pixels
            max_height: Maximum height in pixels
            
        Returns:
            Resized image bytes
        """
        # TODO: Use PIL to load, resize, and save image
        # For now, return original
        return image_bytes

    def get_image_format_suffix(self, mime_type: str) -> str:
        """Get file extension from MIME type."""
        mapping = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
            "image/gif": "gif"
        }
        return mapping.get(mime_type, "jpg")


class VisionContext:
    """
    Manages images in conversation context.
    Stores images and maintains references in conversation history.
    """

    def __init__(self):
        """Initialize vision context."""
        self.images: Dict[str, Dict[str, Any]] = {}  # image_id -> image data
        self.image_counter = 0

    def add_image(self, image_bytes: bytes, mime_type: str) -> str:
        """
        Add image to context and return ID.
        
        Args:
            image_bytes: Image data
            mime_type: MIME type
            
        Returns:
            Image ID for reference
        """
        self.image_counter += 1
        image_id = f"image_{self.image_counter}"
        
        self.images[image_id] = {
            "bytes": image_bytes,
            "mime_type": mime_type,
            "size": len(image_bytes)
        }
        
        return image_id

    def get_image(self, image_id: str) -> Optional[Dict[str, Any]]:
        """Get image data by ID."""
        return self.images.get(image_id)

    def clear(self):
        """Clear all stored images."""
        self.images.clear()
        self.image_counter = 0


class OllamaVisionFormatter:
    """
    Formats images for Ollama vision model API.
    Converts Gemini-style inline_data to Ollama format.
    """

    @staticmethod
    def format_for_ollama(inline_data: Dict[str, str]) -> Dict[str, str]:
        """
        Convert inline_data to Ollama vision format.
        
        Args:
            inline_data: Gemini format with "mime_type" and "data" (base64)
            
        Returns:
            Dict with Ollama-compatible image representation
        """
        mime_type = inline_data.get("mime_type", "image/jpeg")
        data_b64 = inline_data.get("data", "")
        
        # Ollama expects base64 data in message content
        return {
            "type": "image",
            "mime_type": mime_type,
            "data": data_b64  # Keep as base64
        }

    @staticmethod
    def build_vision_message(text: str, images: list) -> Dict[str, Any]:
        """
        Build a message with text and images for Ollama.
        
        Args:
            text: Text prompt
            images: List of image dicts with "mime_type" and "data"
            
        Returns:
            Message dict for Ollama /api/chat
        """
        content = text
        
        # TODO: If Ollama supports multimodal in message format,
        # include images here. For now, return simple text message.
        
        return {
            "role": "user",
            "content": content,
            "images": images if images else None
        }


# Global vision components
_image_processor: Optional[ImageProcessor] = None
_vision_context: Optional[VisionContext] = None


def get_image_processor() -> ImageProcessor:
    """Get or create global image processor."""
    global _image_processor
    if _image_processor is None:
        _image_processor = ImageProcessor()
    return _image_processor


def get_vision_context() -> VisionContext:
    """Get or create global vision context."""
    global _vision_context
    if _vision_context is None:
        _vision_context = VisionContext()
    return _vision_context
