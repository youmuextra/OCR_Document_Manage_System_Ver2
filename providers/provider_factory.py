from __future__ import annotations

import os
from functools import lru_cache

from .capture_provider import LocalCaptureProvider, GaopaiyiCaptureProvider
from .identity_provider import ManualIdentityProvider, CardReaderIdentityProvider


@lru_cache(maxsize=1)
def get_capture_provider():
    """获取采集提供者。

    通过环境变量 CAPTURE_PROVIDER 控制：
    - local (默认): 本地文件 + 摄像头
    - gaopaiyi: 高拍仪占位实现
    """
    mode = (os.getenv("CAPTURE_PROVIDER") or "local").strip().lower()
    if mode == "gaopaiyi":
        return GaopaiyiCaptureProvider()
    return LocalCaptureProvider()


@lru_cache(maxsize=1)
def get_identity_provider():
    """获取身份确认提供者。

    通过环境变量 IDENTITY_PROVIDER 控制：
    - manual (默认): 人工确认
    - card_reader: 读卡器占位实现
    """
    mode = (os.getenv("IDENTITY_PROVIDER") or "manual").strip().lower()
    if mode == "card_reader":
        return CardReaderIdentityProvider()
    return ManualIdentityProvider()
