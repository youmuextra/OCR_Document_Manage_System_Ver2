"""硬件对接预留接口层。

- capture_provider: 文件采集（本地文件/摄像头/高拍仪）
- identity_provider: 身份确认（手工确认/读卡器）
"""

from .provider_factory import get_capture_provider, get_identity_provider

__all__ = ["get_capture_provider", "get_identity_provider"]
