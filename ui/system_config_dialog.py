# ui/system_config_dialog.py
"""
系统设置对话框
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QComboBox, QSpinBox,
    QDoubleSpinBox, QCheckBox, QGroupBox, QFormLayout,
    QMessageBox, QTabWidget, QWidget
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from database import DatabaseManager

class SystemConfigDialog(QDialog):
    """系统设置对话框"""
    
    def __init__(self, db_manager, current_user, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user
        self.setup_ui()
        self.load_configs()
    
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("系统设置")
        self.resize(600, 400)
        
        layout = QVBoxLayout()
        
        # 标签页
        self.tab_widget = QTabWidget()
        
        # 系统设置标签页
        system_tab = QWidget()
        system_layout = QFormLayout()
        
        # 系统名称
        self.system_name_input = QLineEdit()
        system_layout.addRow("系统名称:", self.system_name_input)
        
        # 版本
        self.version_input = QLineEdit()
        system_layout.addRow("系统版本:", self.version_input)
        
        system_tab.setLayout(system_layout)
        self.tab_widget.addTab(system_tab, "系统设置")
        
        # OCR设置标签页
        ocr_tab = QWidget()
        ocr_layout = QFormLayout()
        
        # 是否启用OCR
        self.ocr_enable_check = QCheckBox("启用OCR功能")
        ocr_layout.addRow(self.ocr_enable_check)
        
        # OCR置信度阈值
        self.ocr_threshold_spin = QDoubleSpinBox()
        self.ocr_threshold_spin.setRange(0, 1)
        self.ocr_threshold_spin.setSingleStep(0.1)
        self.ocr_threshold_spin.setValue(0.5)
        ocr_layout.addRow("置信度阈值:", self.ocr_threshold_spin)
        
        ocr_tab.setLayout(ocr_layout)
        self.tab_widget.addTab(ocr_tab, "OCR设置")
        
        # 文件设置标签页
        file_tab = QWidget()
        file_layout = QFormLayout()
        
        # 文件大小限制
        self.file_size_spin = QSpinBox()
        self.file_size_spin.setRange(1, 100)
        self.file_size_spin.setSuffix(" MB")
        self.file_size_spin.setValue(10)
        file_layout.addRow("文件大小限制:", self.file_size_spin)
        
        file_tab.setLayout(file_layout)
        self.tab_widget.addTab(file_tab, "文件设置")
        
        layout.addWidget(self.tab_widget)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("保存设置")
        self.save_button.clicked.connect(self.on_save)
        self.save_button.setStyleSheet("background-color: #4CAF50; color: white;")
        
        self.reset_button = QPushButton("恢复默认")
        self.reset_button.clicked.connect(self.on_reset)
        
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        
        # 状态栏
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def load_configs(self):
        """加载配置"""
        # 系统名称
        system_name = self.db_manager.get_config('system.name', '公文智能管理系统')
        self.system_name_input.setText(system_name)
        
        # 系统版本
        system_version = self.db_manager.get_config('system.version', '1.0.0')
        self.version_input.setText(system_version)
        
        # OCR启用
        ocr_enable = self.db_manager.get_config('ocr.enable', True)
        self.ocr_enable_check.setChecked(ocr_enable)
        
        # OCR阈值
        ocr_threshold = self.db_manager.get_config('ocr.confidence_threshold', 0.5)
        self.ocr_threshold_spin.setValue(ocr_threshold)
        
        # 文件大小
        file_size = self.db_manager.get_config('file.max_size_mb', 10)
        self.file_size_spin.setValue(file_size)
    
    def on_save(self):
        """保存设置"""
        try:
            # 系统设置
            self.db_manager.set_config(
                'system.name',
                self.system_name_input.text(),
                'string',
                '系统名称'
            )
            
            self.db_manager.set_config(
                'system.version',
                self.version_input.text(),
                'string',
                '系统版本'
            )
            
            # OCR设置
            self.db_manager.set_config(
                'ocr.enable',
                self.ocr_enable_check.isChecked(),
                'bool',
                '是否启用OCR功能'
            )
            
            self.db_manager.set_config(
                'ocr.confidence_threshold',
                self.ocr_threshold_spin.value(),
                'float',
                'OCR置信度阈值'
            )
            
            # 文件设置
            self.db_manager.set_config(
                'file.max_size_mb',
                self.file_size_spin.value(),
                'int',
                '文件上传最大大小(MB)'
            )
            
            QMessageBox.information(self, "成功", "设置已保存")
            self.status_label.setText("设置保存成功")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存设置失败: {e}")
            self.status_label.setText(f"保存失败: {e}")
    
    def on_reset(self):
        """恢复默认设置"""
        reply = QMessageBox.question(
            self, "确认重置",
            "确定要恢复默认设置吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 清空配置
            with self.db_manager.session_scope() as session:
                session.query(self.db_manager.SystemConfig).delete()
            
            # 重新初始化默认数据
            self.db_manager._init_default_data()
            
            # 重新加载配置
            self.load_configs()
            
            QMessageBox.information(self, "成功", "已恢复默认设置")
            self.status_label.setText("已恢复默认设置")