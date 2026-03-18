# ui/send_document_dialog.py
"""
发文管理对话框
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QMessageBox, QDateEdit,
    QFormLayout, QGroupBox, QTextEdit, QComboBox
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, QDate
from datetime import datetime

class SendDocumentDialog(QDialog):
    """发文管理对话框"""
    
    def __init__(self, db_manager, current_user, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("发文登记")
        self.resize(600, 500)
        
        layout = QVBoxLayout()
        
        # 发文表单分组
        form_group = QGroupBox("发文信息")
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        # 文号
        self.doc_no_input = QLineEdit()
        self.doc_no_input.setPlaceholderText("请输入文号")
        form_layout.addRow("文号*:", self.doc_no_input)
        
        # 标题
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("请输入标题")
        form_layout.addRow("标题*:", self.title_input)
        
        # 发文单位
        self.issuing_unit_input = QLineEdit()
        self.issuing_unit_input.setPlaceholderText("请输入发文单位")
        form_layout.addRow("发文单位:", self.issuing_unit_input)
        
        # 发往单位
        self.send_to_unit_input = QLineEdit()
        self.send_to_unit_input.setPlaceholderText("请输入发往单位")
        form_layout.addRow("发往单位*:", self.send_to_unit_input)

        # M级（必填）
        self.m_level_combo = QComboBox()
        self.m_level_combo.addItems(["请选择M级", "M1", "M2", "M3", "M4"])
        form_layout.addRow("M级*:", self.m_level_combo)
        
        # 经办人
        self.processor_input = QLineEdit()
        self.processor_input.setPlaceholderText("请输入经办人姓名")
        form_layout.addRow("经办人*:", self.processor_input)
        
        # 发文日期
        self.send_date_input = QDateEdit()
        self.send_date_input.setDate(QDate.currentDate())
        self.send_date_input.setCalendarPopup(True)
        form_layout.addRow("发文日期:", self.send_date_input)
        
        # 备注
        self.remarks_input = QTextEdit()
        self.remarks_input.setMaximumHeight(100)
        self.remarks_input.setPlaceholderText("请输入备注信息")
        form_layout.addRow("备注:", self.remarks_input)
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("保存")
        self.save_button.setStyleSheet("background-color: #4CAF50; color: white;")
        self.save_button.clicked.connect(self.on_save)
        
        self.clear_button = QPushButton("清空")
        self.clear_button.clicked.connect(self.on_clear)
        
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def on_save(self):
        """保存发文记录"""
        # 获取表单数据
        doc_no = self.doc_no_input.text().strip()
        title = self.title_input.text().strip()
        send_to_unit = self.send_to_unit_input.text().strip()
        processor = self.processor_input.text().strip()
        m_level = self.m_level_combo.currentText().strip()
    
        # 验证必填字段
        if not doc_no:
            QMessageBox.warning(self, "警告", "文号不能为空")
            return
    
        if not title:
            QMessageBox.warning(self, "警告", "标题不能为空")
            return
    
        if not send_to_unit:
            QMessageBox.warning(self, "警告", "发往单位不能为空")
            return
    
        if not processor:
            QMessageBox.warning(self, "警告", "经办人不能为空")
            return

        if not m_level or m_level == "请选择M级":
            QMessageBox.warning(self, "警告", "M级不能为空")
            return
    
        # 准备数据
        send_data = {
            'document_no': doc_no,
            'title': title,
            'issuing_unit': self.issuing_unit_input.text().strip(),
            'send_to_unit': send_to_unit,
            'm_level': m_level,
            'processor': processor,
            'send_date': self.send_date_input.date().toPython(),
            'remarks': self.remarks_input.toPlainText().strip()
        }
    
        # 执行保存
        self.status_label.setText("正在保存...")
    
        try:
        
            # ✅ 使用现有的db_manager
            success, message, doc_id = self.db_manager.create_send_document(
                send_data, 
                self.current_user['id']
            )
        
            if success:
                QMessageBox.information(self, "成功", f"发文记录保存成功！\n发文ID: {doc_id}\n文号: {doc_no}")
                # 不清空表单，以便用户在流程结束前查看内容
                # self.on_clear()
                self.status_label.setText(f"发文记录已保存，ID: {doc_id}")
            else:
                QMessageBox.warning(self, "失败", message)
                self.status_label.setText(f"保存失败: {message}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")
            self.status_label.setText(f"保存异常: {str(e)}")
        
            # 打印详细错误信息
            import traceback
            print("❌ 保存发文记录时发生异常:")
            traceback.print_exc()
    
    def on_clear(self):
        """清空表单"""
        self.doc_no_input.clear()
        self.title_input.clear()
        self.issuing_unit_input.clear()
        self.send_to_unit_input.clear()
        self.m_level_combo.setCurrentIndex(0)
        self.processor_input.clear()
        self.send_date_input.setDate(QDate.currentDate())
        self.remarks_input.clear()
        self.status_label.setText("")
        self.doc_no_input.setFocus()
    
    def on_search_send(self):
        """查询发文记录（可选功能）"""
        try:
            from .search_send_dialog import SearchSendDialog
            dialog = SearchSendDialog(self.db_manager, self.current_user, self)
            dialog.exec()
        except ImportError as e:
            QMessageBox.warning(self, "功能未实现", f"查询功能未找到: {e}")