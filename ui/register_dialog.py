# ui/register_dialog.py
"""
用户注册对话框 - 修复递归错误版本
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QMessageBox, QComboBox,
    QFormLayout, QGroupBox
)
from PySide6.QtGui import QFont, QIcon
from PySide6.QtCore import Qt
import re

class RegisterDialog(QDialog):
    """用户注册对话框"""
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("用户注册")
        self.setFixedSize(500, 550)
        
        # 设置窗口标志
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        # 创建主布局
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # 标题
        title_label = QLabel("用户注册")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        title_label.setStyleSheet("color: #2c3e50; margin: 20px 0;")
        layout.addWidget(title_label)
        
        # 注册表单分组
        form_group = QGroupBox("用户信息")
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        # 用户名
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入用户名（3-20位字母数字）")
        form_layout.addRow("用户名*:", self.username_input)
        
        # 密码
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("请输入密码（至少6位）")
        self.password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("密码*:", self.password_input)
        
        # 确认密码
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setPlaceholderText("请再次输入密码")
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("确认密码*:", self.confirm_password_input)
        
        # 真实姓名
        self.real_name_input = QLineEdit()
        self.real_name_input.setPlaceholderText("请输入真实姓名")
        form_layout.addRow("真实姓名:", self.real_name_input)
        
        # 部门
        self.department_input = QLineEdit()
        self.department_input.setPlaceholderText("请输入部门")
        form_layout.addRow("部门:", self.department_input)
        
        # 职位
        self.position_input = QLineEdit()
        self.position_input.setPlaceholderText("请输入职位")
        form_layout.addRow("职位:", self.position_input)
        
        # 邮箱
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("请输入邮箱")
        form_layout.addRow("邮箱:", self.email_input)
        
        # 电话
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("请输入电话号码")
        form_layout.addRow("电话:", self.phone_input)
        
        # 角色
        self.role_combo = QComboBox()
        self.role_combo.addItems(["普通用户", "管理员"])
        form_layout.addRow("角色:", self.role_combo)
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        
        # 验证标签
        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet("color: #e74c3c;")
        layout.addWidget(self.validation_label)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.register_button = QPushButton("注册")
        self.register_button.setFont(QFont("Microsoft YaHei", 10))
        self.register_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 10px 30px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        self.register_button.clicked.connect(self.on_register)
        self.register_button.setEnabled(False)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setFont(QFont("Microsoft YaHei", 10))
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                padding: 10px 30px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.register_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # ✅ 连接所有输入框到一个统一的验证函数
        self.username_input.textChanged.connect(self.validate_form)
        self.password_input.textChanged.connect(self.validate_form)
        self.confirm_password_input.textChanged.connect(self.validate_form)
        self.email_input.textChanged.connect(self.validate_form)
        self.phone_input.textChanged.connect(self.validate_form)
        
        self.setLayout(layout)
    
    def validate_form(self):
        """统一的表单验证函数 - 避免递归调用"""
        # 获取所有输入值
        username = self.username_input.text().strip()
        password = self.password_input.text()
        confirm_password = self.confirm_password_input.text()
        email = self.email_input.text().strip()
        phone = self.phone_input.text().strip()
        
        # 验证用户名
        if not username:
            self.validation_label.setText("用户名不能为空")
            self.register_button.setEnabled(False)
            return
        
        if len(username) < 3 or len(username) > 20:
            self.validation_label.setText("用户名长度应为3-20位")
            self.register_button.setEnabled(False)
            return
        
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            self.validation_label.setText("用户名只能包含字母、数字和下划线")
            self.register_button.setEnabled(False)
            return
        
        # 验证密码
        if not password:
            self.validation_label.setText("密码不能为空")
            self.register_button.setEnabled(False)
            return
        
        if len(password) < 6:
            self.validation_label.setText("密码长度至少6位")
            self.register_button.setEnabled(False)
            return
        
        # 验证密码匹配
        if not confirm_password:
            self.validation_label.setText("请确认密码")
            self.register_button.setEnabled(False)
            return
        
        if password != confirm_password:
            self.validation_label.setText("两次输入的密码不一致")
            self.register_button.setEnabled(False)
            return
        
        # 验证邮箱（可选）
        if email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            self.validation_label.setText("邮箱格式不正确")
            self.register_button.setEnabled(False)
            return
        
        # 验证电话（可选）
        if phone and not re.match(r'^1[3-9]\d{9}$', phone):
            self.validation_label.setText("请输入有效的手机号码")
            self.register_button.setEnabled(False)
            return
        
        # 所有验证通过
        self.validation_label.setText("")
        self.register_button.setEnabled(True)
    
    def on_register(self):
        """注册按钮点击事件"""
        # 收集用户数据
        user_data = {
            'username': self.username_input.text().strip(),
            'password': self.password_input.text(),
            'real_name': self.real_name_input.text().strip(),
            'department': self.department_input.text().strip(),
            'position': self.position_input.text().strip(),
            'email': self.email_input.text().strip(),
            'phone': self.phone_input.text().strip(),
            'role': 'admin' if self.role_combo.currentText() == '管理员' else 'user'
        }
        
        # 再次验证
        if not user_data['username'] or not user_data['password']:
            QMessageBox.warning(self, "警告", "用户名和密码不能为空")
            return
        
        if len(user_data['username']) < 3 or len(user_data['username']) > 20:
            QMessageBox.warning(self, "警告", "用户名长度应为3-20位")
            return
        
        if not re.match(r'^[a-zA-Z0-9_]+$', user_data['username']):
            QMessageBox.warning(self, "警告", "用户名只能包含字母、数字和下划线")
            return
        
        if len(user_data['password']) < 6:
            QMessageBox.warning(self, "警告", "密码长度至少6位")
            return
        
        if user_data['password'] != self.confirm_password_input.text():
            QMessageBox.warning(self, "警告", "两次输入的密码不一致")
            return
        
        if user_data.get('email') and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', user_data['email']):
            QMessageBox.warning(self, "警告", "邮箱格式不正确")
            return
        
        if user_data.get('phone') and not re.match(r'^1[3-9]\d{9}$', user_data['phone']):
            QMessageBox.warning(self, "警告", "请输入有效的手机号码")
            return
        
        # 禁用按钮，防止重复点击
        self.register_button.setEnabled(False)
        self.validation_label.setText("正在注册...")
        
        # 调用数据库创建用户
        try:
            success, message = self.db_manager.create_user(user_data)
        except Exception as e:
            self.validation_label.setText(f"注册失败: {str(e)}")
            QMessageBox.warning(self, "失败", f"注册失败: {str(e)}")
            self.register_button.setEnabled(True)
            return
        
        if success:
            self.validation_label.setText("注册成功！")
            QMessageBox.information(self, "成功", "用户注册成功！")
            self.accept()  # 关闭对话框并返回Accepted
        else:
            self.validation_label.setText(f"注册失败: {message}")
            QMessageBox.warning(self, "失败", f"注册失败: {message}")
            self.register_button.setEnabled(True)