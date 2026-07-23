"""
Vision and Multimodal Support
=============================
Handles image data in conversations.
Converts inline_data images to Ollama vision model format.
Maintains public API compatibility while supporting multimodal inputs.
"""

import base64
from typing import Optional, Tuple, Dict, Any


class ImageProcessor:
    """
    Processes images for vision model integration.
    Converts between formats and validates image data.
    """

    SUPPORTED_MIME_TYPES = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/gif": "gif",
    }

    @staticmethod
    def validate_mime_type(mime_type: str) -> bool:
        """
        Validate image MIME type is supported.
        
        Args:
            mime_type: MIME type string
            
        Returns:
            True if supported, False otherwise
        """
        return mime_type in ImageProcessor.SUPPORTED_MIME_TYPES

    @staticmethod
    def encode_image_for_ollama(image_data: bytes, mime_type: str) -> Dict[str, Any]:
        """
        Convert image data to Ollama vision model format.
        
        Args:
            image_data: Raw image bytes
            mime_type: Image MIME type (e.g., "image/jpeg")
            
        Returns:
            Dict with base64 encoded image and type for Ollama
            
        Example:
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": "base64_encoded_string"
                }
            }
        """
        if not ImageProcessor.validate_mime_type(mime_type):
            raise ValueError(f"Unsupported MIME type: {mime_type}")
        
        # Encode to base64
        b64_data = base64.b64encode(image_data).decode("ascii")
        
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime_type,
                "data": b64_data
            }
        }

    @staticmethod
    def extract_inline_data(part: Dict[str, Any]) -> Optional[Tuple[bytes, str]]:
        """
        Extract image data from inline_data part in turn.
        
        Args:
            part: Dict part from turns["parts"] containing inline_data
                  Example: {"inline_data": {"mime_type": "image/jpeg", "data": "base64_string"}}
            
        Returns:
            Tuple of (image_bytes, mime_type) or None if not image data
        """
        if not isinstance(part, dict):
            return None
        
        inline_data = part.get("inline_data")
        if not inline_data or not isinstance(inline_data, dict):
            return None
        
        mime_type = inline_data.get("mime_type", "")
        data_str = inline_data.get("data", "")
        
        if not mime_type or not data_str:
            return None
        
        if not ImageProcessor.validate_mime_type(mime_type):
            return None
        
        try:
            # Decode base64 data
            image_bytes = base64.b64decode(data_str)
            return (image_bytes, mime_type)
        except Exception as e:
            print(f"[Vision] Failed to decode image: {e}")
            return None


class MultimodalContext:
    """
    Manages multimodal context in conversation.
    Tracks images and text in the same turn.
    """

    def __init__(self):
        """Initialize multimodal context."""
        self.images: list = []  # List of encoded images
        self.text_parts: list = []  # List of text parts
        self.media_metadata: Dict[str, Any] = {}  # Metadata about media

    def add_image(self, image_bytes: bytes, mime_type: str) -> bool:
        """
        Add image to context.
        
        Args:
            image_bytes: Raw image bytes
            mime_type: Image MIME type
            
        Returns:
            True if added successfully
        """
        try:
            encoded = ImageProcessor.encode_image_for_ollama(image_bytes, mime_type)
            self.images.append(encoded)
            self.media_metadata[f"image_{len(self.images)}"] = {
                "mime_type": mime_type,
                "size": len(image_bytes)
            }
            return True
        except Exception as e:
            print(f"[Multimodal] Failed to add image: {e}")
            return False

    def add_text(self, text: str):
        """Add text to context."""
        if text:
            self.text_parts.append(text)

    def build_message_content(self) -> list:
        """
        Build Ollama message content with images and text.
        
        Returns:
            List of content parts for Ollama message
        """
        content = []
        
        # Add images first
        content.extend(self.images)
        
        # Add text as a single part
        if self.text_parts:
            content.append({
                "type": "text",
                "text": " ".join(self.text_parts)
            })
        
        return content if content else [{"type": "text", "text": ""}]

    def has_images(self) -> bool:
        """Check if context contains images."""
        return len(self.images) > 0

    def clear(self):
        """Clear all multimodal context."""
        self.images.clear()
        self.text_parts.clear()
        self.media_metadata.clear()


class VisionCapabilities:
    """
    Manages vision model capabilities and settings.
    """

    def __init__(self):
        """Initialize vision capabilities."""
        self.enabled = True
        self.max_image_size = 20 * 1024 * 1024  # 20 MB
        self.supported_models = ["llava", "llava-13b", "bakllava"]
        self.current_model = "llava"

    def is_vision_capable(self, model: str) -> bool:
        """
        Check if model supports vision.
        
        Args:
            model: Model name
            
        Returns:
            True if model can process images
        """
        # TODO: Query Ollama for model capabilities
        return model.lower() in self.supported_models or "llava" in model.lower()

    def validate_image(self, image_bytes: bytes) -> bool:
        """
        Validate image before sending to model.
        
        Args:
            image_bytes: Image data
            
        Returns:
            True if image is valid
        """
        return len(image_bytes) <= self.max_image_size
