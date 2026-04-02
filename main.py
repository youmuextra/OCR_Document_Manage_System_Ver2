# main.py
"""
公文智能管理系统 - 主程序入口
"""

import sys
import os
import traceback
import webbrowser
from PySide6.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PySide6.QtGui import QPixmap, QFont, QColor
from PySide6.QtCore import Qt, QTimer, QSize
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow
from database import DatabaseManager
from auth import Authenticator
from services.llm_service import LLMService

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

            # 4) 检测并引导 Ollama/模型环境
            self.ensure_ollama_runtime(splash)
            
            splash.showMessage("正在加载界面...", Qt.AlignCenter | Qt.AlignBottom, Qt.white)
            self.app.processEvents()
            
            # 稍作延迟，让用户看到启动画面
            QTimer.singleShot(1000, lambda: self.show_login(splash))
            
        except Exception as e:
            splash.showMessage(f"初始化失败: {str(e)}", Qt.AlignCenter | Qt.AlignBottom, Qt.red)
            QTimer.singleShot(3000, self.app.quit)

    def ensure_ollama_runtime(self, splash):
        """启动阶段检测 Ollama 与模型状态，必要时给出修复引导。"""
        try:
            splash.showMessage("正在检查本地大模型环境...", Qt.AlignCenter | Qt.AlignBottom, Qt.white)
            self.app.processEvents()

            status = LLMService.check_ollama_runtime()

            # 1) 未安装 Ollama
            if not status.get('installed'):
                ans = QMessageBox.question(
                    None,
                    "未检测到 Ollama",
                    "当前机器未检测到 Ollama，OCR 智能提取功能将不可用。\n\n是否现在打开 Ollama 下载页面？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )
                if ans == QMessageBox.Yes:
                    webbrowser.open("https://ollama.com/download")
                return

            # 2) 已安装但服务未运行：尝试自动启动
            if not status.get('server_running'):
                start_result = LLMService.start_ollama_service(wait_seconds=6)
                if not start_result.get('ok'):
                    QMessageBox.warning(
                        None,
                        "Ollama 未启动",
                        f"已检测到 Ollama 但服务未运行，且自动启动失败。\n\n{start_result.get('message', '')}\n\n"
                        f"请手动执行：ollama serve",
                    )
                    return

            # 3) 服务可用但模型未就绪
            status = LLMService.check_ollama_runtime()
            if not status.get('model_ready'):
                ans = QMessageBox.question(
                    None,
                    "模型未就绪",
                    f"已检测到 Ollama，但模型 {LLMService.MODEL_NAME} 尚未安装。\n"
                    "是否现在自动下载？（首次约 1GB）",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )
                if ans == QMessageBox.Yes:
                    splash.showMessage("正在下载大模型，请稍候...", Qt.AlignCenter | Qt.AlignBottom, Qt.white)
                    self.app.processEvents()
                    pull_result = LLMService.pull_model()
                    if not pull_result.get('ok'):
                        QMessageBox.warning(None, "模型下载失败", pull_result.get('message', '未知错误'))
                    else:
                        QMessageBox.information(None, "模型就绪", f"{LLMService.MODEL_NAME} 已下载完成")
        except Exception as e:
            QMessageBox.warning(None, "大模型环境检查失败", f"已跳过检查：{e}")
    
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
            welcome_name = str(self.current_user.get('real_name') or '').strip()
            if not welcome_name or welcome_name.lower() == 'none':
                welcome_name = str(self.current_user.get('username') or '用户').strip() or '用户'
            self.main_window.statusBar().showMessage(f"欢迎回来，{welcome_name}！", 5000)
            
        except Exception as e:
            QMessageBox.critical(None, "错误", f"加载主窗口失败: {str(e)}")
            traceback.print_exc()
            self.app.quit()

if __name__ == "__main__":
    # 使用DocumentManagementSystem类启动
    app = DocumentManagementSystem()
    app.setup()
