from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional


class IdentityProvider(ABC):
    """身份确认提供者抽象层。"""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def confirm_identity(
        self,
        parent=None,
        expected_user: Optional[Dict[str, Any]] = None,
        scene: str = "",
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """返回: (是否通过, 文本信息, 身份信息字典)"""
        raise NotImplementedError


class ManualIdentityProvider(IdentityProvider):
    """默认人工确认实现（读卡器上线前使用）。"""

    @property
    def provider_name(self) -> str:
        return "manual_identity"

    def confirm_identity(self, parent=None, expected_user=None, scene: str = ""):
        from PySide6.QtWidgets import QMessageBox

        user_name = ""
        if isinstance(expected_user, dict):
            user_name = expected_user.get("real_name") or expected_user.get("username") or ""

        tip = "请确认领取人身份（当前为手工确认模式）"
        if user_name:
            tip += f"\n当前操作人: {user_name}"
        if scene:
            tip += f"\n场景: {scene}"

        reply = QMessageBox.question(
            parent,
            "身份确认",
            tip,
            QMessageBox.Yes | QMessageBox.No,
        )
        ok = reply == QMessageBox.Yes
        return ok, ("已手工确认" if ok else "已取消确认"), {
            "method": "manual",
            "verified_user": user_name,
        }


class CardReaderIdentityProvider(IdentityProvider):
    """读卡器预留实现（当前占位）。"""

    @property
    def provider_name(self) -> str:
        return "card_reader_placeholder"

    def confirm_identity(self, parent=None, expected_user=None, scene: str = ""):
        return False, "读卡器尚未集成，请先使用手工确认模式", {
            "method": "card_reader",
            "scene": scene,
        }
