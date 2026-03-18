# ui/search_send_dialog.py
"""
发文查询对话框
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QDateEdit, QGroupBox, QFormLayout, QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt, QDate
from datetime import datetime

class SearchSendDialog(QDialog):
    """发文查询对话框"""
    
    def __init__(self, db_manager, current_user, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("发文查询")
        self.resize(800, 600)
        
        layout = QVBoxLayout()
        
        # 查询条件
        query_group = QGroupBox("查询条件")
        query_layout = QFormLayout()
        
        # 文号
        self.doc_no_input = QLineEdit()
        self.doc_no_input.setPlaceholderText("请输入文号")
        query_layout.addRow("文号:", self.doc_no_input)
        
        # 标题
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("请输入标题")
        query_layout.addRow("标题:", self.title_input)
        
        # 发往单位
        self.send_to_input = QLineEdit()
        self.send_to_input.setPlaceholderText("请输入发往单位")
        query_layout.addRow("发往单位:", self.send_to_input)
        
        # 经办人
        self.processor_input = QLineEdit()
        self.processor_input.setPlaceholderText("请输入经办人")
        query_layout.addRow("经办人:", self.processor_input)
        
        query_group.setLayout(query_layout)
        layout.addWidget(query_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.query_button = QPushButton("查询")
        self.query_button.setStyleSheet("background-color: #4CAF50; color: white;")
        self.query_button.clicked.connect(self.on_query)
        
        self.export_button = QPushButton("导出")
        self.export_button.setEnabled(False)
        
        self.clear_button = QPushButton("清空")
        self.clear_button.clicked.connect(self.on_clear)
        
        button_layout.addWidget(self.query_button)
        button_layout.addWidget(self.export_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # 结果表格
        self.result_table = QTableWidget()
        # ✅ 修改：添加ID列，共10列
        self.result_table.setColumnCount(10)
        self.result_table.setHorizontalHeaderLabels([
            "发文ID",         # ✅ 添加文档ID列
            "文号", 
            "标题", 
            "发文单位", 
            "发往单位", 
            "经办人", 
            "发文日期", 
            "状态", 
            "备注", 
            "操作"
        ])
        
        # 设置列宽
        self.result_table.horizontalHeader().setStretchLastSection(True)
        self.result_table.setColumnWidth(0, 60)   # ID列宽度
        self.result_table.setColumnWidth(1, 120)  # 文号列宽度
        
        layout.addWidget(self.result_table)
        
        # 状态标签
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def on_query(self):
        """查询发文记录"""
        try:
            # ✅ 直接使用self.db_manager，不要重新创建DatabaseManager
            # 收集过滤条件
            filters = {}
        
            doc_no = self.doc_no_input.text().strip()
            if doc_no:
                filters['document_no'] = doc_no
        
            title = self.title_input.text().strip()
            if title:
                filters['title'] = title
        
            send_to = self.send_to_input.text().strip()
            if send_to:
                filters['send_to_unit'] = send_to
        
            processor = self.processor_input.text().strip()
            if processor:
                filters['processor'] = processor
        
            # 使用self.db_manager，而不是重新创建
            success, message, result = self.db_manager.get_send_documents(
                filters=filters,
                page=1,
                page_size=100
            )
        
            if success:
                self.display_results(result['documents'])
                self.export_button.setEnabled(len(result['documents']) > 0)
                self.status_label.setText(f"查询完成，共找到 {result['total']} 条记录")
            else:
                QMessageBox.warning(self, "查询失败", message)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"查询失败: {e}")
    
    def display_results(self, documents):
        """显示查询结果"""
        self.result_table.setRowCount(len(documents))
        
        for i, doc in enumerate(documents):
            self.result_table.setItem(i, 0, QTableWidgetItem(str(doc.get('id', ''))))
            self.result_table.setItem(i, 1, QTableWidgetItem(doc.get('document_no', '')))
            self.result_table.setItem(i, 2, QTableWidgetItem(doc.get('title', '')))
            self.result_table.setItem(i, 3, QTableWidgetItem(doc.get('issuing_unit', '')))
            self.result_table.setItem(i, 4, QTableWidgetItem(doc.get('send_to_unit', '')))
            self.result_table.setItem(i, 5, QTableWidgetItem(doc.get('processor', '')))
            
            # 发文日期
            send_date = doc.get('send_date')
            if send_date and hasattr(send_date, 'strftime'):
                send_date = send_date.strftime("%Y-%m-%d")
            self.result_table.setItem(i, 6, QTableWidgetItem(str(send_date)))
            
            self.result_table.setItem(i, 7, QTableWidgetItem(doc.get('send_status', '')))
            self.result_table.setItem(i, 8, QTableWidgetItem(doc.get('remarks', '')))
            
            # ✅ 修复操作按钮的lambda函数
            action_button = QPushButton("查看")
            # lambda需要checked参数
            action_button.clicked.connect(lambda checked=False, d=doc: self.on_view_document(d))
            self.result_table.setCellWidget(i, 9, action_button)
    
    def on_view_document(self, document):
        """查看发文详情"""
        QMessageBox.information(
            self, 
            "发文详情",
            f"文号: {document.get('document_no')}\n"
            f"标题: {document.get('title')}\n"
            f"发文单位: {document.get('issuing_unit')}\n"
            f"发往单位: {document.get('send_to_unit')}\n"
            f"经办人: {document.get('processor')}\n"
            f"发文日期: {document.get('send_date')}\n"
            f"状态: {document.get('send_status')}\n"
            f"备注: {document.get('remarks')}"
        )
    
    def on_clear(self):
        """清空查询条件"""
        self.doc_no_input.clear()
        self.title_input.clear()
        self.send_to_input.clear()
        self.processor_input.clear()
        self.result_table.setRowCount(0)
        self.status_label.setText("")