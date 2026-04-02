# ui/circulation_query_dialog.py
"""
流转查询对话框
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QComboBox, QGroupBox, QFormLayout, QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt
from datetime import datetime

class CirculationQueryDialog(QDialog):
    """流转查询对话框"""
    
    def __init__(self, db_manager, current_user, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("流转记录查询")
        self.resize(900, 600)
        
        layout = QVBoxLayout()
        
        # 查询条件
        query_group = QGroupBox("查询条件")
        query_layout = QFormLayout()
        
        # 文档类型
        self.doc_type_combo = QComboBox()
        self.doc_type_combo.addItems(["全部", "收文", "发文"])
        query_layout.addRow("文档类型:", self.doc_type_combo)
        
        # 文号
        self.doc_no_input = QLineEdit()
        self.doc_no_input.setPlaceholderText("请输入文号")
        query_layout.addRow("文号:", self.doc_no_input)
        
        # 流转类型
        self.circ_type_combo = QComboBox()
        self.circ_type_combo.addItems(["全部", "交接", "借阅", "其他"])
        query_layout.addRow("流转类型:", self.circ_type_combo)
        
        # 状态
        self.status_combo = QComboBox()
        self.status_combo.addItems(["全部", "待确认", "流转中", "已借出", "已归还", "已完成"])
        query_layout.addRow("状态:", self.status_combo)
        
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
        self.result_table.setColumnCount(10)
        self.result_table.setHorizontalHeaderLabels([
            "文档类型", "文号", "标题", "流转类型", "下一节点", "状态", 
            "借阅日期", "应还日期", "实际归还", "创建时间"
        ])
        self.result_table.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(self.result_table)
        
        # 状态标签
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def on_query(self):
        """查询流转记录"""
        try:
            
            filters = {}
            
            # 文档类型
            doc_type = self.doc_type_combo.currentText()
            if doc_type != "全部":
                filters['document_type'] = 'receive' if doc_type == '收文' else 'send'
            
            doc_no = self.doc_no_input.text().strip()
            
            # 流转类型
            circ_type = self.circ_type_combo.currentText()
            if circ_type != "全部":
                filters['circulation_type'] = circ_type
            
            # 状态
            status = self.status_combo.currentText()
            if status != "全部":
                filters['status'] = status
            
            success, message, result = self.db_manager.get_circulation_records(filters)
            
            if success:
                records = result['records']
                if doc_no:
                    records = [r for r in records if doc_no in str(r.get('document_no', '') or '')]
                self.display_results(records)
                self.export_button.setEnabled(len(records) > 0)
                self.status_label.setText(f"查询完成，共找到 {len(records)} 条记录")
            else:
                QMessageBox.warning(self, "查询失败", message)
                
        except ImportError:
            QMessageBox.warning(self, "功能未实现", "流转功能模块未找到")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"查询失败: {e}")
    
    def display_results(self, records):
        """显示查询结果"""
        self.result_table.setRowCount(len(records))
        
        for i, record in enumerate(records):
            dtype = record.get('document_type', '')
            dtype_text = '收文' if dtype == 'receive' else ('发文' if dtype == 'send' else str(dtype))
            self.result_table.setItem(i, 0, QTableWidgetItem(dtype_text))
            self.result_table.setItem(i, 1, QTableWidgetItem(str(record.get('document_no', '') or '')))
            self.result_table.setItem(i, 2, QTableWidgetItem(str(record.get('title', '') or '')))
            self.result_table.setItem(i, 3, QTableWidgetItem(record.get('circulation_type', '')))
            
            # 下一节点
            next_node = f"{record.get('next_node_unit', '')}/{record.get('next_node_person', '')}"
            self.result_table.setItem(i, 4, QTableWidgetItem(next_node.strip('/')))
            
            self.result_table.setItem(i, 5, QTableWidgetItem(record.get('status', '')))
            
            # 日期格式化
            def format_date(date):
                if date and hasattr(date, 'strftime'):
                    return date.strftime("%Y-%m-%d")
                return ""
            
            self.result_table.setItem(i, 6, QTableWidgetItem(format_date(record.get('borrow_date'))))
            self.result_table.setItem(i, 7, QTableWidgetItem(format_date(record.get('due_date'))))
            self.result_table.setItem(i, 8, QTableWidgetItem(format_date(record.get('return_date'))))
            self.result_table.setItem(i, 9, QTableWidgetItem(format_date(record.get('created_at'))))
    
    def on_clear(self):
        """清空查询条件"""
        self.doc_type_combo.setCurrentIndex(0)
        self.doc_no_input.clear()
        self.circ_type_combo.setCurrentIndex(0)
        self.status_combo.setCurrentIndex(0)
        self.result_table.setRowCount(0)
        self.status_label.setText("")
