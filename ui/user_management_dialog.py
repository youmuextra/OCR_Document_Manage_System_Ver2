# ui/user_management_dialog.py
"""
用户管理对话框
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QComboBox, QMessageBox, QHeaderView, QGroupBox, QFormLayout
)
from PySide6.QtGui import QFont, QColor
from PySide6.QtCore import Qt
from database import DatabaseManager
from datetime import datetime, date

class UserManagementDialog(QDialog):
    """用户管理对话框"""
    
    def __init__(self, db_manager, current_user, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user
        self.setup_ui()
        self.load_users()
        self.selected_user_id = None
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("用户管理")
        self.resize(700, 500)
        
        layout = QVBoxLayout()
        
        # 添加用户表单
        form_group = QGroupBox("添加/编辑用户")
        form_layout = QFormLayout()
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入用户名")
        form_layout.addRow("用户名:", self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("请输入密码")
        self.password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("密码:", self.password_input)
        
        self.real_name_input = QLineEdit()
        self.real_name_input.setPlaceholderText("请输入真实姓名")
        form_layout.addRow("真实姓名:", self.real_name_input)
        
        self.department_input = QLineEdit()
        self.department_input.setPlaceholderText("请输入部门")
        form_layout.addRow("部门:", self.department_input)
        
        self.role_combo = QComboBox()
        self.role_combo.addItems(["operator", "admin"])
        form_layout.addRow("角色:", self.role_combo)
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        
        self.add_button = QPushButton("添加")
        self.add_button.clicked.connect(self.on_add_user)
        self.add_button.setStyleSheet("background-color: #4CAF50; color: white;")
        
        self.update_button = QPushButton("更新")
        self.update_button.clicked.connect(self.on_update_user)
        self.update_button.setEnabled(False)
        
        self.delete_button = QPushButton("删除")
        self.delete_button.clicked.connect(self.on_delete_user)
        self.delete_button.setStyleSheet("background-color: #f44336; color: white;")
        self.delete_button.setEnabled(False)
        
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.update_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # 用户列表表格
        self.user_table = QTableWidget()
        self.user_table.setColumnCount(6)
        self.user_table.setHorizontalHeaderLabels([
            "ID", "用户名", "真实姓名", "部门", "角色", "最后登录"
        ])
        self.user_table.horizontalHeader().setStretchLastSection(True)
        self.user_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.user_table.itemSelectionChanged.connect(self.on_user_selected)
        
        layout.addWidget(self.user_table)
        
        # 状态栏
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def load_users(self):
        """加载用户列表"""
        try:
            users = self.db_manager.get_all_users()
            self.user_table.setRowCount(len(users))
            for i, user in enumerate(users):
                self.user_table.setItem(i, 0, QTableWidgetItem(str(user.get('id', ''))))
                self.user_table.setItem(i, 1, QTableWidgetItem(user.get('username', '')))
                self.user_table.setItem(i, 2, QTableWidgetItem(user.get('real_name', '')))
                self.user_table.setItem(i, 3, QTableWidgetItem(user.get('department', '')))
                role_val = user.get('role', '')
                role_text = '管理员' if role_val == 'admin' else '经办人'
                self.user_table.setItem(i, 4, QTableWidgetItem(role_text))
                last_login = user.get('last_login')
                if last_login and hasattr(last_login, 'strftime'):
                    last_login_str = last_login.strftime("%Y-%m-%d %H:%M")
                else:
                    last_login_str = str(last_login) if last_login else "从未登录"
                self.user_table.setItem(i, 5, QTableWidgetItem(last_login_str))
            self.status_label.setText(f"已加载 {len(users)} 个用户")
        except Exception as e:
            self.status_label.setText(f"加载用户失败: {e}")
            QMessageBox.warning(self, "错误", f"加载用户失败: {e}")
    def on_add_user(self):
        """添加用户"""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        real_name = self.real_name_input.text().strip()
        department = self.department_input.text().strip()
        role = self.role_combo.currentText()
        
        if not username or not password:
            QMessageBox.warning(self, "警告", "用户名和密码不能为空")
            return
        
        user_data = {
            'username': username,
            'password': password,
            'real_name': real_name,
            'department': department,
            'role': role
        }
        
        success, message = self.db_manager.create_user(user_data)
        
        if success:
            QMessageBox.information(self, "成功", message)
            self.load_users()
            self.clear_form()
        else:
            QMessageBox.warning(self, "失败", message)
    
    def on_update_user(self):
        """更新用户信息"""
        # 检查是否有选中的用户
        if not hasattr(self, 'selected_user_id') or self.selected_user_id is None:
            QMessageBox.warning(self, "警告", "请先选择要更新的用户")
            return

        # 获取表单数据
        username = self.username_input.text().strip()
        real_name = self.real_name_input.text().strip()
        role = self.role_combo.currentText()

        if not username:
            QMessageBox.warning(self, "警告", "用户名不能为空")
            return

        # 通过数据库管理器更新用户
        update_data = {
            'username': username,
            'real_name': real_name,
            'role': role
        }
        success, message = self.db_manager.update_user(self.selected_user_id, update_data)
        if success:
            QMessageBox.information(self, "成功", "用户信息更新成功")
            self.load_users()
        else:
            QMessageBox.warning(self, "失败", message)
    
    def on_delete_user(self):
        """删除用户"""
        # 检查是否有选中的用户
        if not hasattr(self, 'selected_user_id') or self.selected_user_id is None:
            QMessageBox.warning(self, "警告", "请先选择要删除的用户")
            return

        # 不能删除自己
        if self.selected_user_id == self.current_user.get('id'):
            QMessageBox.warning(self, "警告", "不能删除当前登录的用户")
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除用户ID为 {self.selected_user_id} 的用户吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            success, message = self.db_manager.delete_user(self.selected_user_id)
            if success:
                QMessageBox.information(self, "成功", "用户删除成功")
                self.load_users()
                self.clear_form()
            else:
                QMessageBox.warning(self, "失败", message)
    
    def on_user_selected(self):
        """用户被选中"""
        selected_items = self.user_table.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            self.selected_user_id = int(self.user_table.item(row, 0).text())  # 设置selected_user_id
            
            username = self.user_table.item(row, 1).text()
            real_name = self.user_table.item(row, 2).text()
            #department = self.user_table.item(row, 3).text()
            role_text = self.user_table.item(row, 4).text()
            role = 'admin' if role_text == '管理员' else 'operator'
            
            self.username_input.setText(username)
            self.real_name_input.setText(real_name)
            #self.department_input.setText(department)
            self.role_combo.setCurrentText(role)
            self.password_input.clear()
            
            self.update_button.setEnabled(True)
            self.delete_button.setEnabled(True)
            #self.add_button.setEnabled(False)
            
            # 不能删除自己
            if self.selected_user_id == self.current_user.get('id'):
                self.delete_button.setEnabled(False)
                self.delete_button.setText("不能删除自己")
        else:
            # 没有选中任何用户
            self.selected_user_id = None
            self.update_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            self.clear_form()
            #self.add_button.setEnabled(True)
    
    def clear_form(self):
        """清空表单"""
        self.username_input.clear()
        self.password_input.clear()
        self.real_name_input.clear()
        self.department_input.clear()
        self.role_combo.setCurrentIndex(0)
        self.user_table.clearSelection()
