# ui/search_document_dialog.py
"""
公文查询对话框
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QMessageBox,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QComboBox, QDateEdit, QGroupBox, QFormLayout, QHeaderView
)
from PySide6.QtGui import QFont, QIntValidator
from PySide6.QtCore import Qt, QDate
from database import DatabaseManager

# 直接使用相对导入
from .document_detail_dialog import DocumentDetailDialog

class SearchDocumentDialog(QDialog):
    """公文查询对话框"""
    
    def __init__(self, db_manager, current_user, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("公文查询")
        self.resize(800, 600)
        
        layout = QVBoxLayout()
        
        # 查询条件
        query_group = QGroupBox("查询条件")
        query_layout = QFormLayout()
        
        # 查询条件分组
        condition_group = QGroupBox("查询条件")
        condition_layout = QFormLayout()
        
        # 标题
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("请输入标题关键词")
        condition_layout.addRow("标题:", self.title_input)
        
        # 文号
        self.doc_no_input = QLineEdit()
        self.doc_no_input.setPlaceholderText("请输入文号")
        condition_layout.addRow("文号:", self.doc_no_input)
        
        # 发文单位
        self.unit_input = QLineEdit()
        self.unit_input.setPlaceholderText("请输入发文单位")
        condition_layout.addRow("发文单位:", self.unit_input)
        
        # 日期范围
        date_layout = QHBoxLayout()
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addMonths(-1))
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        date_layout.addWidget(self.start_date)
        date_layout.addWidget(QLabel("至"))
        date_layout.addWidget(self.end_date)
        condition_layout.addRow("收文日期:", date_layout)
        
        condition_group.setLayout(condition_layout)
        layout.addWidget(condition_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.search_button = QPushButton("查询")
        self.search_button.clicked.connect(self.on_search)
        self.search_button.setStyleSheet("background-color: #4CAF50; color: white;")
        
        self.export_button = QPushButton("导出Excel")
        self.export_button.clicked.connect(self.on_export)
        self.export_button.setEnabled(False)
        
        self.reset_button = QPushButton("重置")
        self.reset_button.clicked.connect(self.on_reset)
        
        button_layout.addWidget(self.search_button)
        button_layout.addWidget(self.export_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # 结果表格
        self.result_table = QTableWidget()
        # ✅ 添加序号和ID列，共8列
        self.result_table.setColumnCount(8)
        self.result_table.setHorizontalHeaderLabels([
            "序号",           # 新增行号
            "收文ID",         # ✅ 文档ID
            "文号", 
            "标题", 
            "发文单位", 
            "收文日期", 
            "密级", 
            "操作"
        ])
        
        # 设置列宽
        self.result_table.horizontalHeader().setStretchLastSection(True)
        self.result_table.setColumnWidth(0, 60)   # ID列宽度
        self.result_table.setColumnWidth(1, 120)  # 文号列宽度
        self.result_table.setColumnWidth(2, 200)  # 标题列宽度
        
        layout.addWidget(self.result_table)
        
        # 状态栏
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def on_search(self):
        """执行查询"""
        # 收集查询条件
        filters = {}
    
        title = self.title_input.text().strip()
        if title:
            filters['title'] = title
    
        doc_no = self.doc_no_input.text().strip()
        if doc_no:
            filters['document_no'] = doc_no
    
        unit = self.unit_input.text().strip()
        if unit:
            filters['issuing_unit'] = unit
    
        filters['start_date'] = self.start_date.date().toPython()
        filters['end_date'] = self.end_date.date().toPython()
    
        # 执行查询
        self.status_label.setText("正在查询...")
    
        # 获取查询结果
        query_result = self.db_manager.search_documents(
            filters=filters,
            page=1,
            page_size=100
        )
    
        # 检查返回值是否为None
        if query_result is None:
            self.status_label.setText("查询失败：数据库返回了None")
            return
    
        # 解包返回值
        try:
            success, message, result = query_result
        except Exception as e:
            self.status_label.setText(f"查询失败：返回值格式错误 - {e}")
            return
    
        if success:
            self.display_results(result['documents'])
            self.export_button.setEnabled(len(result['documents']) > 0)
            self.status_label.setText(f"查询完成，共找到 {result['total']} 条记录")
        else:
            self.status_label.setText(f"查询失败: {message}")
    
    def display_results(self, documents):
        """显示查询结果"""
        self.result_table.setRowCount(len(documents))
        
        for i, doc in enumerate(documents):
            # ✅ 第一列：序号（从1开始）
            self.result_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))

            # 第二列：文档ID
            self.result_table.setItem(i, 1, QTableWidgetItem(str(doc.get('id', ''))))
            
            # 第三列：文号
            self.result_table.setItem(i, 2, QTableWidgetItem(doc.get('document_no', '')))
            
            # 第四列：标题
            self.result_table.setItem(i, 3, QTableWidgetItem(doc.get('title', '')))
            
            # 第五列：发文单位
            self.result_table.setItem(i, 4, QTableWidgetItem(doc.get('issuing_unit', '')))
            
            # 第六列：收文日期
            received_date = doc.get('received_date')
            if received_date and hasattr(received_date, 'strftime'):
                received_date = received_date.strftime("%Y-%m-%d")
            self.result_table.setItem(i, 5, QTableWidgetItem(str(received_date)))
            
            # 第七列：密级
            self.result_table.setItem(i, 6, QTableWidgetItem(doc.get('security_level', '')))
            
            # 第八列：操作
            action_button = QPushButton("查看")
            action_button.clicked.connect(lambda checked=False, d=doc: self.on_view_document(d))
            self.result_table.setCellWidget(i, 7, action_button)
    
    def on_export(self):
        """导出到Excel"""
        # 这里实现导出功能
        self.status_label.setText("导出功能待实现")
    
    def on_reset(self):
        """重置查询条件"""
        self.title_input.clear()
        self.doc_no_input.clear()
        self.unit_input.clear()
        self.start_date.setDate(QDate.currentDate().addMonths(-1))
        self.end_date.setDate(QDate.currentDate())
        self.result_table.setRowCount(0)
        self.status_label.setText("已重置")
    
    def on_view_document(self, document):
        """查看文档详情"""
        try:
            if not isinstance(document, dict) or not document.get('id'):
                QMessageBox.warning(self, "错误", "文档数据无效或缺少ID")
                return

            doc_id = document.get('id')
            if hasattr(self.db_manager, 'get_receive_document_by_id'):
                success, message, full_doc = self.db_manager.get_receive_document_by_id(doc_id)
                if success and full_doc:
                    dialog = DocumentDetailDialog(full_doc, self.db_manager, self.current_user, self)
                else:
                    dialog = DocumentDetailDialog(document, self.db_manager, self.current_user, self)
            else:
                dialog = DocumentDetailDialog(document, self.db_manager, self.current_user, self)

            dialog.exec_()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"查看文档失败: {e}")