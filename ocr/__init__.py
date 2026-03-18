# ocr/__init__.py
"""
OCR模块
"""

from .ocr_processor import OCRProcessor
from .camera_capture import CameraCapture
from .image_preprocessor import ImagePreprocessor
from .document_parser import DocumentParser

__all__ = ['OCRProcessor', 'CameraCapture', 'ImagePreprocessor', 'DocumentParser']