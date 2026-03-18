# ui/__init__.py
"""
UI模块初始化文件
"""

from .login_dialog import LoginDialog
from .main_window import MainWindow
from .search_document_dialog import SearchDocumentDialog
from .user_management_dialog import UserManagementDialog
from .system_config_dialog import SystemConfigDialog
from .document_detail_dialog import DocumentDetailDialog

__all__ = [
    'LoginDialog',
    'MainWindow', 
    'SearchDocumentDialog',
    'UserManagementDialog',
    'SystemConfigDialog',
    'DocumentDetailDialog'
]