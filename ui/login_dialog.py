# ui/login_dialog.py
"""
登录对话框
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QMessageBox, QCheckBox
)
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtCore import Qt, Signal
import sys
import os

class LoginDialog(QDialog):
    """登录对话框"""
    
    login_success = Signal(dict)  # 登录成功信号
    
    def __init__(self, auth_manager, parent=None):
        super().__init__(parent)
        # 初始化数据库连接
        self.init_database()
        self.auth_manager = auth_manager
        self.setup_ui()
    
    def init_database(self):
        """初始化数据库连接"""
        try:
            from database import DatabaseManager
            self.db_manager = DatabaseManager()
            print("✅ 数据库连接成功")
        except Exception as e:
            print(f"❌ 数据库连接失败: {e}")
            raise
    
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("公文智能管理系统 - 登录")
        self.setFixedSize(400, 350)  # 增加高度以容纳注册按钮
        
        # 设置窗口标志
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        # 创建布局
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # 标题
        title_label = QLabel("公文智能管理系统")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        title_label.setStyleSheet("color: #2c3e50; margin: 20px 0;")
        
        # 用户名输入
        username_layout = QHBoxLayout()
        username_label = QLabel("用户名:")
        username_label.setFixedWidth(60)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入用户名")
        self.username_input.setText("admin")  # 默认用户名
        
        username_layout.addWidget(username_label)
        username_layout.addWidget(self.username_input)
        
        # 密码输入
        password_layout = QHBoxLayout()
        password_label = QLabel("密码:")
        password_label.setFixedWidth(60)
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("请输入密码")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setText("123456")  # 默认密码
        
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password_input)
        
        # 记住密码选项
        self.remember_checkbox = QCheckBox("记住密码")
        self.remember_checkbox.setChecked(True)
        
        # 登录按钮
        self.login_button = QPushButton("登录")
        self.login_button.setFont(QFont("Microsoft YaHei", 10))
        self.login_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1c6ea4;
            }
        """)
        self.login_button.clicked.connect(self.on_login_clicked)
        
        # 注册按钮 - 这是新增的按钮
        self.register_button = QPushButton("注册新用户")
        self.register_button.setFont(QFont("Microsoft YaHei", 10))
        self.register_button.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
            QPushButton:pressed {
                background-color: #219653;
            }
        """)
        self.register_button.clicked.connect(self.on_register_clicked)
        
        # 取消按钮
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setFont(QFont("Microsoft YaHei", 10))
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        self.cancel_button.clicked.connect(self.reject)
        
        # 按钮布局 - 修改为包含3个按钮
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.login_button)
        button_layout.addWidget(self.register_button)
        button_layout.addWidget(self.cancel_button)
        
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #e74c3c;")
        
        # 注册提示
        register_hint = QLabel("新用户请点击'注册新用户'按钮")
        register_hint.setAlignment(Qt.AlignCenter)
        register_hint.setStyleSheet("color: #7f8c8d; font-size: 12px; margin-top: 10px;")
        
        # 添加到主布局
        layout.addWidget(title_label)
        layout.addLayout(username_layout)
        layout.addLayout(password_layout)
        layout.addWidget(self.remember_checkbox)
        layout.addLayout(button_layout)
        layout.addWidget(register_hint)  # 添加注册提示
        layout.addWidget(self.status_label)
        layout.addStretch()
        
        # 设置回车键触发登录
        self.username_input.returnPressed.connect(self.on_login_clicked)
        self.password_input.returnPressed.connect(self.on_login_clicked)
        
        self.setLayout(layout)
    
    def on_login_clicked(self):
        """登录按钮点击事件"""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        if not username or not password:
            self.show_error("用户名和密码不能为空")
            return
        
        # 禁用按钮，防止重复点击
        self.set_ui_enabled(False)
        self.status_label.setText("正在验证...")
        
        # 执行登录
        success, message, user_info = self.auth_manager.login(username, password)
        
        if success:
            self.status_label.setText("登录成功！")
            self.login_success.emit(user_info)
            
            # 如果勾选了记住密码，保存到配置文件（简化版）
            if self.remember_checkbox.isChecked():
                self.save_login_info(username)
            
            # 稍作延迟后关闭对话框
            from PySide6.QtCore import QTimer
            QTimer.singleShot(500, self.accept)
        else:
            self.set_ui_enabled(True)
            self.show_error(message)
    
    def on_register_clicked(self):
        """注册按钮点击事件"""
        try:
            # 导入注册对话框
            from ui.register_dialog import RegisterDialog
            
            # 创建注册对话框
            register_dialog = RegisterDialog(self.db_manager, self)
            register_dialog.setWindowTitle("用户注册 - 公文智能管理系统")
            
            # 显示注册对话框
            if register_dialog.exec() == QDialog.Accepted:
                QMessageBox.information(
                    self, 
                    "注册成功", 
                    "用户注册成功！\n\n请使用新账号登录。"
                )
                # 清空表单
                self.username_input.clear()
                self.password_input.clear()
                self.username_input.setFocus()
                
        except ImportError as e:
            QMessageBox.warning(
                self, 
                "功能未实现", 
                f"注册功能模块未找到:\n\n{str(e)}"
            )
        except Exception as e:
            QMessageBox.critical(
                self, 
                "错误", 
                f"打开注册对话框失败:\n\n{str(e)}"
            )
    
    def set_ui_enabled(self, enabled):
        """设置UI元素启用状态"""
        self.username_input.setEnabled(enabled)
        self.password_input.setEnabled(enabled)
        self.login_button.setEnabled(enabled)
        self.register_button.setEnabled(enabled)
        self.cancel_button.setEnabled(enabled)
        self.remember_checkbox.setEnabled(enabled)
    
    def show_error(self, message):
        """显示错误信息"""
        self.status_label.setText(message)
        
        # 清空密码框
        self.password_input.clear()
        self.password_input.setFocus()
    
    def save_login_info(self, username):
        """保存登录信息（简化版）"""
        # 实际项目中应该加密保存
        try:
            config_dir = os.path.join('data', 'config')
            os.makedirs(config_dir, exist_ok=True)
            
            config_file = os.path.join(config_dir, 'login.ini')
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(f"[Login]\nusername={username}\nremember=true\n")
        except:
            pass  # 保存失败不影响登录
    
    def load_login_info(self):
        """加载登录信息"""
        try:
            config_file = os.path.join('data', 'config', 'login.ini')
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.startswith('username='):
                            username = line.split('=', 1)[1].strip()
                            self.username_input.setText(username)
        except:
            pass