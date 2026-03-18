# main.py
"""
公文智能管理系统 - 主程序入口
"""

import sys
import os
import traceback
from PySide6.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PySide6.QtGui import QPixmap, QFont, QColor
from PySide6.QtCore import Qt, QTimer, QSize
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow
from database import DatabaseManager
from auth import Authenticator

class DocumentManagementSystem:
    """公文智能管理系统主类"""
    
    def __init__(self):
        self.app = None
        self.db_manager = None
        self.auth = None
        self.current_user = None
        self.main_window = None
        
    def setup(self):
        """系统初始化"""
        print("公文智能管理系统 v1.0.0")
        print("=" * 60)
        
        # 1. 创建Qt应用
        self.app = QApplication(sys.argv)
        
        # 设置应用程序信息
        self.app.setApplicationName("公文智能管理系统")
        self.app.setOrganizationName("OfficeAI")
        self.app.setApplicationVersion("1.0.0")
        
        # 设置全局字体
        self.setup_fonts()
        
        # 2. 显示启动画面
        splash = self.show_splash_screen()
        
        # 3. 初始化数据库
        QTimer.singleShot(1000, lambda: self.init_database(splash))
        
        # 4. 运行应用
        sys.exit(self.app.exec())
    
    def setup_fonts(self):
        """设置字体"""
        font = QFont("Microsoft YaHei", 10)
        self.app.setFont(font)
    
    def show_splash_screen(self):
        """显示启动画面"""
        # 创建一个简单的启动画面
        splash = QSplashScreen()
        splash.setFixedSize(QSize(500, 300))
        
        # 设置样式
        splash.setStyleSheet("""
            QSplashScreen {
                background-color: #2c3e50;
                color: white;
            }
        """)
        
        # 显示消息
        splash.showMessage(
            "正在初始化公文智能管理系统...\n\n"
            "v1.0.0\n"
            "© 2024 OfficeAI\n\n"
            "请稍候...",
            Qt.AlignCenter | Qt.AlignBottom,
            Qt.white
        )
        splash.show()
        
        # 处理事件
        self.app.processEvents()
        
        return splash
    
    def init_database(self, splash):
        """初始化数据库"""
        splash.showMessage("正在初始化数据库...", Qt.AlignCenter | Qt.AlignBottom, Qt.white)
        self.app.processEvents()
        
        try:
            self.db_manager = DatabaseManager()
            self.auth = Authenticator(self.db_manager)
            
            splash.showMessage("正在加载界面...", Qt.AlignCenter | Qt.AlignBottom, Qt.white)
            self.app.processEvents()
            
            # 稍作延迟，让用户看到启动画面
            QTimer.singleShot(1000, lambda: self.show_login(splash))
            
        except Exception as e:
            splash.showMessage(f"初始化失败: {str(e)}", Qt.AlignCenter | Qt.AlignBottom, Qt.red)
            QTimer.singleShot(3000, self.app.quit)
    
    # 在main.py中，确保DatabaseManager被正确初始化
    def show_login(self, splash):
        """显示登录对话框"""
        splash.showMessage("正在加载登录界面...", Qt.AlignCenter | Qt.AlignBottom, Qt.white)
        self.app.processEvents()
    
        # 创建登录对话框
        login_dialog = LoginDialog(self.auth)
    
        # 连接登录成功信号
        login_dialog.login_success.connect(self.on_login_success)
    
        # 关闭启动画面
        splash.finish(login_dialog)
    
        # 显示登录对话框
        login_dialog.exec()
    
    def on_login_success(self, user_info):
        """登录成功回调"""
        self.current_user = user_info
        self.show_main_window()
    
    def show_main_window(self):
        """显示主窗口"""
        try:
            # 导入主窗口
            from ui.main_window import MainWindow
            
            self.main_window = MainWindow(self.db_manager, self.auth, self.current_user)
            self.main_window.show()
            
            # 显示欢迎消息
            welcome_name = self.current_user.get('real_name', self.current_user.get('username'))
            self.main_window.statusBar().showMessage(f"欢迎回来，{welcome_name}！", 5000)
            
        except Exception as e:
            QMessageBox.critical(None, "错误", f"加载主窗口失败: {str(e)}")
            traceback.print_exc()
            self.app.quit()

if __name__ == "__main__":
    # 使用DocumentManagementSystem类启动
    app = DocumentManagementSystem()
    app.setup()