from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class CaptureProvider(ABC):
    """采集提供者抽象层。"""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def select_local_file(self, parent=None) -> Optional[str]:
        """从本地选择文件并返回文件路径。"""
        raise NotImplementedError

    @abstractmethod
    def capture_from_camera(self, parent=None) -> Optional[str]:
        """通过摄像头采集并返回文件路径。"""
        raise NotImplementedError


class LocalCaptureProvider(CaptureProvider):
    """默认本地采集实现：文件选择 + 摄像头拍照。"""

    @property
    def provider_name(self) -> str:
        return "local_capture"

    def select_local_file(self, parent=None) -> Optional[str]:
        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            parent,
            "选择待识别文件",
            "",
            "文档/图片 (*.pdf *.png *.jpg *.jpeg *.bmp *.tif *.tiff);;所有文件 (*.*)",
        )
        return file_path or None

    def capture_from_camera(self, parent=None) -> Optional[str]:
        # 复用现有摄像头对话框，后续可直接替换为高拍仪SDK实现
        from ui.camera_dialog import CameraDialog

        dialog = CameraDialog(parent)
        dialog.start_camera()
        if dialog.exec() == dialog.Accepted and getattr(dialog, "file_path", None):
            return dialog.file_path
        return None


class GaopaiyiCaptureProvider(CaptureProvider):
    """高拍仪预留实现（当前占位）。"""

    @property
    def provider_name(self) -> str:
        return "gaopaiyi_capture_placeholder"

    def select_local_file(self, parent=None) -> Optional[str]:
        # 高拍仪场景不走本地文件，保留兼容
        return None

    def capture_from_camera(self, parent=None) -> Optional[str]:
        # TODO: 对接高拍仪SDK后在这里返回图片路径
        return None
