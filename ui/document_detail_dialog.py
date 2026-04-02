# ui/document_detail_dialog.py
"""
公文详情对话框
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QTextEdit, QComboBox,
    QDateEdit, QFormLayout, QGroupBox, QMessageBox,
    QTabWidget, QWidget, QScrollArea, QSplitter, QFileDialog
)
from PySide6.QtGui import QFont, QPixmap, QImage
from PySide6.QtCore import Qt, QDate, QSize
from database import DatabaseManager
from ocr.ocr_processor import OCRProcessor
from services.llm_service import LLMService
from datetime import datetime
import os
import tempfile
import shutil

# OCR 现在由独立模块处理，使用更通用的 OCRProcessor + 线程封装
from ocr.ocr_thread import OCRThread

# 文档对话框中可选的 OCR 处理器实例将在 __init__ 时创建

class DocumentDetailDialog(QDialog):
    """公文详情对话框"""
    
    def __init__(self, document, db_manager, current_user, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user
        # OCRProcessor 实例准备好，用于异步任务或者其它需求
        self.ocr_processor = OCRProcessor(debug=False)
        
        # 确保document是字典
        if not isinstance(document, dict):
            # 如果是其他类型，尝试转换
            if hasattr(document, '__dict__'):
                self.document = document.__dict__
            else:
                self.document = {}
        else:
            self.document = document
        
        self.setup_ui()
        # ✅ 修复：这里应该调用load_document_data而不是load_document
        self.load_document_data()
    
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("公文详情")
        self.resize(900, 700)
        
        # 主布局
        main_layout = QVBoxLayout()
        
        # 标签页
        self.tab_widget = QTabWidget()
        
        # 基本信息标签页
        self.basic_info_tab = self.create_basic_info_tab()
        self.tab_widget.addTab(self.basic_info_tab, "基本信息")
        
        # OCR识别结果标签页
        self.ocr_result_tab = self.create_ocr_result_tab()
        self.tab_widget.addTab(self.ocr_result_tab, "OCR结果")
        
        # 图片预览标签页
        self.image_preview_tab = self.create_image_preview_tab()
        self.tab_widget.addTab(self.image_preview_tab, "图片预览")
        
        # 操作日志标签页
        self.log_tab = self.create_log_tab()
        self.tab_widget.addTab(self.log_tab, "操作日志")
        # 延迟加载日志，切换标签时触发
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        main_layout.addWidget(self.tab_widget)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.reject)
        self.close_button.setStyleSheet("background-color: #6c757d; color: white;")
        
        self.print_button = QPushButton("打印")
        self.print_button.clicked.connect(self.on_print)
        self.print_button.setEnabled(False)  # 暂不实现
        
        self.export_button = QPushButton("导出")
        self.export_button.clicked.connect(self.on_export)
        
        # 只有管理员才能编辑
        if self.current_user.get('role') == 'admin':
            self.edit_button = QPushButton("编辑")
            self.edit_button.clicked.connect(self.on_edit)
            self.edit_button.setStyleSheet("background-color: #007bff; color: white;")
            button_layout.addWidget(self.edit_button)
        
        button_layout.addWidget(self.print_button)
        button_layout.addWidget(self.export_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
    
    def create_basic_info_tab(self):
        """创建基本信息标签页"""
        tab = QWidget()
        layout = QFormLayout()
        layout.setSpacing(10)
        
        # 基本信息分组
        basic_group = QGroupBox("基本信息")
        basic_layout = QFormLayout()
        
        # 文号
        self.doc_no_label = QLabel()
        basic_layout.addRow("文号:", self.doc_no_label)
        
        # 标题
        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        basic_layout.addRow("标题:", self.title_label)
        
        # 发文单位
        self.issuing_unit_label = QLabel()
        basic_layout.addRow("发文单位:", self.issuing_unit_label)
        
        # 收文日期
        self.received_date_label = QLabel()
        basic_layout.addRow("收文日期:", self.received_date_label)
        
        # 密级
        self.security_level_label = QLabel()
        basic_layout.addRow("密级:", self.security_level_label)
        
        # 紧急程度
        self.urgency_level_label = QLabel()
        basic_layout.addRow("紧急程度:", self.urgency_level_label)
        
        # 文种
        self.document_type_label = QLabel()
        basic_layout.addRow("文种:", self.document_type_label)
        
        # 份数
        self.copies_label = QLabel()
        basic_layout.addRow("份数:", self.copies_label)
        
        basic_group.setLayout(basic_layout)
        layout.addRow(basic_group)
        
        # 收文信息分组
        receive_group = QGroupBox("收文信息")
        receive_layout = QFormLayout()
        
        # 收文人
        self.receiver_label = QLabel()
        receive_layout.addRow("收文人:", self.receiver_label)
        
        # 存放位置
        self.storage_location_label = QLabel()
        receive_layout.addRow("存放位置:", self.storage_location_label)
        
        receive_group.setLayout(receive_layout)
        layout.addRow(receive_group)
        
        # 内容摘要分组
        content_group = QGroupBox("内容摘要")
        content_layout = QVBoxLayout()
        
        self.content_summary_text = QTextEdit()
        self.content_summary_text.setReadOnly(True)
        self.content_summary_text.setMaximumHeight(150)
        content_layout.addWidget(self.content_summary_text)
        
        content_group.setLayout(content_layout)
        layout.addRow(content_group)
        
        # 关键词和备注
        other_group = QGroupBox("其他信息")
        other_layout = QFormLayout()
        
        # 关键词
        self.keywords_label = QLabel()
        other_layout.addRow("关键词:", self.keywords_label)
        
        # 备注
        self.remarks_text = QTextEdit()
        self.remarks_text.setReadOnly(True)
        self.remarks_text.setMaximumHeight(100)
        other_layout.addRow("备注:", self.remarks_text)
        
        other_group.setLayout(other_layout)
        layout.addRow(other_group)
        
        # 系统信息分组
        sys_group = QGroupBox("系统信息")
        sys_layout = QFormLayout()
        
        # 创建人
        self.creator_label = QLabel()
        sys_layout.addRow("创建人:", self.creator_label)
        
        # 创建时间
        self.created_at_label = QLabel()
        sys_layout.addRow("创建时间:", self.created_at_label)
        
        sys_group.setLayout(sys_layout)
        layout.addRow(sys_group)
        
        # 添加弹性空间
        layout.addRow(QWidget())
        
        tab.setLayout(layout)
        return tab
    
    def create_ocr_result_tab(self):
        """创建OCR识别结果标签页"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # OCR结果展示
        self.ocr_text_edit = QTextEdit()
        self.ocr_text_edit.setReadOnly(True)
        layout.addWidget(QLabel("OCR识别结果:"))
        layout.addWidget(self.ocr_text_edit)
        
        # ✅ 修复这里：使用字典的get方法
        ocr_path = self.document.get('ocr_result_path', '')
        if not ocr_path or not os.path.exists(ocr_path):
            self.ocr_text_edit.setPlainText("暂无OCR识别结果")
        else:
            try:
                with open(ocr_path, 'r', encoding='utf-8') as f:
                    ocr_result = f.read()
                self.ocr_text_edit.setPlainText(ocr_result)
            except Exception as e:
                self.ocr_text_edit.setPlainText(f"读取OCR结果失败: {str(e)}")
        
        # ✅ 修复：方法名要与上面定义的一致
        reocr_btn = QPushButton("重新进行OCR识别")
        reocr_btn.clicked.connect(self.on_re_ocr)  # 注意这里的方法名
        layout.addWidget(reocr_btn)
        
        tab.setLayout(layout)
        return tab
    
    def create_image_preview_tab(self):
        """创建图片预览标签页"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # 图片预览区域
        self.image_preview_label = QLabel()
        self.image_preview_label.setAlignment(Qt.AlignCenter)
        self.image_preview_label.setStyleSheet("""
            QLabel {
                border: 2px dashed #dee2e6;
                border-radius: 5px;
                background-color: #f8f9fa;
                padding: 20px;
            }
        """)
        self.image_preview_label.setMinimumHeight(400)
        
        # 如果没有图片，显示提示
        image_path = self.document.get('original_file_path', '')
        if not image_path or not os.path.exists(image_path):
            self.image_preview_label.setText("暂无图片预览")
        else:
            self.load_image_preview()
        
        layout.addWidget(self.image_preview_label)
        
        # 缩放控制
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("缩放:"))
        
        self.zoom_in_button = QPushButton("+")
        self.zoom_in_button.clicked.connect(self.on_zoom_in)
        self.zoom_in_button.setFixedSize(30, 30)
        
        self.zoom_out_button = QPushButton("-")
        self.zoom_out_button.clicked.connect(self.on_zoom_out)
        self.zoom_out_button.setFixedSize(30, 30)
        
        self.reset_zoom_button = QPushButton("重置")
        self.reset_zoom_button.clicked.connect(self.on_reset_zoom)
        
        self.zoom_level_label = QLabel("100%")
        
        zoom_layout.addWidget(self.zoom_in_button)
        zoom_layout.addWidget(self.zoom_out_button)
        zoom_layout.addWidget(self.reset_zoom_button)
        zoom_layout.addStretch()
        zoom_layout.addWidget(self.zoom_level_label)
        
        layout.addLayout(zoom_layout)
        
        tab.setLayout(layout)
        return tab
    
    def create_log_tab(self):
        """创建操作日志标签页"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # 操作日志
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("操作日志将在这里显示...")
        
        layout.addWidget(QLabel("操作日志:"))
        layout.addWidget(self.log_text)
        
        # 如果没有日志，显示提示
        if not hasattr(self, 'logs_loaded') or not self.logs_loaded:
            no_logs_label = QLabel("暂无操作日志")
            no_logs_label.setAlignment(Qt.AlignCenter)
            no_logs_label.setStyleSheet("font-size: 16px; color: #6c757d; padding: 20px;")
            layout.addWidget(no_logs_label)
        
        tab.setLayout(layout)
        return tab
    
    def load_document_data(self):
        """加载公文数据"""
        # ✅ 修复：全部使用字典的get方法
        # 基本信息
        self.doc_no_label.setText(self.document.get('document_no', '无'))
        self.title_label.setText(self.document.get('title', '无'))
        self.issuing_unit_label.setText(self.document.get('issuing_unit', '无'))
        
        received_date = self.document.get('received_date')
        if received_date:
            try:
                # 处理日期格式
                if isinstance(received_date, datetime):
                    self.received_date_label.setText(received_date.strftime("%Y-%m-%d"))
                else:
                    # 尝试解析字符串
                    self.received_date_label.setText(str(received_date)[:10])
            except:
                self.received_date_label.setText(str(received_date))
        else:
            self.received_date_label.setText("无")
        
        self.security_level_label.setText(self.document.get('security_level', '无'))
        self.urgency_level_label.setText(self.document.get('urgency_level', '无'))
        self.document_type_label.setText(self.document.get('document_type', '无'))
        
        copies = self.document.get('copies')
        self.copies_label.setText(str(copies) if copies else "无")
        
        # 收文信息
        self.receiver_label.setText(self.document.get('receiver', '无'))
        self.storage_location_label.setText(self.document.get('storage_location', '无'))
        
        # 内容
        self.content_summary_text.setText(self.document.get('content_summary', '无'))
        self.keywords_label.setText(self.document.get('keywords', '无'))
        self.remarks_text.setText(self.document.get('remarks', '无'))
        
        # 系统信息
        creator = self.document.get('creator')
        if creator:
            if isinstance(creator, dict):
                real_name = creator.get('real_name', '未知')
                username = creator.get('username', '未知')
                self.creator_label.setText(f"{real_name} ({username})")
            elif hasattr(creator, 'real_name'):
                self.creator_label.setText(f"{creator.real_name} ({creator.username})")
            else:
                self.creator_label.setText(str(creator))
        else:
            self.creator_label.setText("未知")
        
        created_at = self.document.get('created_at')
        if created_at:
            try:
                if isinstance(created_at, datetime):
                    self.created_at_label.setText(created_at.strftime("%Y-%m-%d %H:%M:%S"))
                else:
                    self.created_at_label.setText(str(created_at))
            except:
                self.created_at_label.setText("无")
        else:
            self.created_at_label.setText("无")
    
    def load_image_preview(self):
        """加载图片预览"""
        # ✅ 修复：使用字典的get方法
        image_path = self.document.get('original_file_path', '')
        if not image_path or not os.path.exists(image_path):
            return
        
        try:
            # 尝试加载图片
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                # 缩放图片以适应标签
                scaled_pixmap = pixmap.scaled(
                    self.image_preview_label.size() - QSize(40, 40),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.image_preview_label.setPixmap(scaled_pixmap)
                self.original_pixmap = pixmap  # 保存原始图片
                self.current_scale = 1.0
            else:
                self.image_preview_label.setText("图片加载失败")
        except Exception as e:
            self.image_preview_label.setText(f"图片加载失败: {str(e)}")
    
    def load_document_logs(self):
        """加载公文操作日志"""
        with self.db_manager.session_scope() as session:
            logs = session.query(self.db_manager.DocumentLog).filter_by(
                document_id=self.document.id
            ).order_by(self.db_manager.DocumentLog.created_at.desc()).all()

            if logs:
                log_text = ""
                for log in logs:
                    timestamp = log.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    user_name = log.user.username if log.user else "未知用户"
                    log_text += f"[{timestamp}] {user_name} - {log.action}\n"
                    if log.action_details:
                        log_text += f"    详情: {log.action_details}\n"
                    log_text += "\n"

                self.log_text.setText(log_text)
                self.logs_loaded = True
            else:
                self.log_text.setText("暂无操作日志")
                self.logs_loaded = False

    def on_tab_changed(self, index):
        """选项卡切换回调，用于延迟加载日志"""
        if self.tab_widget.tabText(index) == "操作日志":
            if not getattr(self, 'logs_loaded', False):
                self.load_document_logs()
    
    def on_re_ocr(self):
        """重新执行OCR识别 - 使用PaddleOCR"""
        image_path = self.document.get('original_file_path', '')
        if not image_path or not os.path.exists(image_path):
            QMessageBox.warning(self, "警告", "原始文件不存在，无法重新识别")
            return
        
        reply = QMessageBox.question(
            self, "确认重新识别",
            "确定要重新执行OCR识别吗？这将覆盖之前的识别结果。",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 后台执行OCR并保存结果
            self.ocr_thread = OCRThread(
                image_path,
                self.document.get('id'),
                self.db_manager,
                ocr_processor=self.ocr_processor
            )
            self.ocr_thread.ocr_completed.connect(self.on_ocr_completed)
            self.ocr_thread.ocr_error.connect(self.on_ocr_error)
            self.ocr_thread.start()
            QMessageBox.information(self, "处理中", "正在执行OCR，请稍候...")

    def on_ocr_completed(self, document_id, ocr_path, ocr_result):
        """OCR处理完成"""
        try:
            # 更新当前对话框中的OCR结果
            self.ocr_text_edit.setPlainText(ocr_result)
            
            # ✅ 新增：调用大模型提取公文信息
            try:
                document_info = self.extract_document_info_with_llm(ocr_result)
                if document_info:
                    # 自动填充到表单
                    self.auto_fill_form_with_llm_result(document_info)
                    QMessageBox.information(self, "成功", "OCR识别完成，已自动提取公文信息！")
                else:
                    QMessageBox.information(self, "成功", "OCR识别完成！")
            except Exception as e:
                print(f"大模型提取失败，但OCR成功: {e}")
                QMessageBox.information(self, "成功", "OCR识别完成！")
            
            # 更新document字典
            self.document['ocr_result_path'] = ocr_path
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"更新OCR结果失败: {str(e)}")

    def extract_document_info_with_llm(self, text: str) -> dict:
        """通过统一的 LLMService 询问大模型并得到结构化结果。

        :param text: OCR 获取的原始字符串
        :return: 字典，字段为空时值为""或缺失。
        """
        try:
            return LLMService.extract_document_info(text)
        except Exception as e:
            # 出错不阻塞主流程
            print(f"LLM 提取失败: {e}")
            return {}

    def auto_fill_form_with_llm_result(self, info: dict):
        """把从 LLM 得到的信息回写到界面控件中。"""
        if not info:
            return

        if info.get('document_no'):
            self.doc_no_label.setText(info['document_no'])
        if info.get('title'):
            self.title_label.setText(info['title'])
        if info.get('issuing_unit'):
            self.issuing_unit_label.setText(info['issuing_unit'])
        if info.get('security_level'):
            self.security_level_label.setText(info['security_level'])
        if info.get('received_date'):
            self.received_date_label.setText(info.get('received_date',''))

        # 新增：紧急程度和内容摘要
        if info.get('urgency'):
            try:
                self.urgency_level_label.setText(info.get('urgency'))
            except Exception:
                pass
        if info.get('content_summary'):
            try:
                self.content_summary_text.setPlainText(info.get('content_summary'))
            except Exception:
                pass

    def on_ocr_error(self, error_msg):
        """OCR处理出错"""
        QMessageBox.warning(self, "OCR识别失败", error_msg)
    
    def on_zoom_in(self):
        """放大图片"""
        if hasattr(self, 'original_pixmap') and self.original_pixmap:
            self.current_scale *= 1.2
            self.update_image_preview()
    
    def on_zoom_out(self):
        """缩小图片"""
        if hasattr(self, 'original_pixmap') and self.original_pixmap:
            self.current_scale /= 1.2
            if self.current_scale < 0.1:
                self.current_scale = 0.1
            self.update_image_preview()
    
    def on_reset_zoom(self):
        """重置缩放"""
        if hasattr(self, 'original_pixmap') and self.original_pixmap:
            self.current_scale = 1.0
            self.update_image_preview()
    
    def update_image_preview(self):
        """更新图片预览"""
        if hasattr(self, 'original_pixmap') and self.original_pixmap:
            scaled_size = self.original_pixmap.size() * self.current_scale
            scaled_pixmap = self.original_pixmap.scaled(
                scaled_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_preview_label.setPixmap(scaled_pixmap)
            self.zoom_level_label.setText(f"{int(self.current_scale * 100)}%")
    
    def on_print(self):
        """打印"""
        QMessageBox.information(self, "提示", "打印功能待实现")
    
    def on_export(self):
        """导出公文信息"""
        from PySide6.QtWidgets import QFileDialog
        
        # 获取导出的内容
        content = self.generate_export_content()
        
        # 选择保存路径
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "导出公文", 
            f"公文_{self.document.get('document_no', 'unknown')}.txt",
            "文本文件 (*.txt);;所有文件 (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                QMessageBox.information(self, "成功", f"公文已导出到: {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"导出失败: {str(e)}")

    def generate_export_content(self):
        """将当前文档格式化为文本，委托给工具模块处理。"""
        from utils.document_utils import format_document_export
        return format_document_export(self.document)
    
    def on_edit(self):
        """打开独立的编辑对话框并处理保存后的刷新逻辑。"""
        from ui.edit_document_dialog import DocumentEditDialog

        dialog = DocumentEditDialog(self.document, self.db_manager, self)
        if dialog.exec_():
            try:
                if hasattr(self.db_manager, 'get_receive_document_by_id'):
                    success, message, new_doc = self.db_manager.get_receive_document_by_id(
                        self.document.get('id')
                    )
                    if success and new_doc:
                        self.document = new_doc
                        self.load_document_data()
                        QMessageBox.information(self, "成功", "公文信息已更新")
                else:
                    QMessageBox.information(self, "成功", "公文已更新，请刷新查看")
            except Exception as e:
                QMessageBox.warning(self, "警告", f"重新加载数据失败: {str(e)}")

    def refresh_document(self, document_id):
        """刷新公文数据"""
        try:
            # 从数据库重新加载公文信息
            if hasattr(self.db_manager, 'get_receive_document_by_id'):
                success, message, new_doc = self.db_manager.get_receive_document_by_id(document_id)
                if success and new_doc:
                    self.document = new_doc
                    self.load_document_data()
                    
                    # 刷新OCR结果
                    ocr_path = self.document.get('ocr_result_path', '')
                    if ocr_path and os.path.exists(ocr_path):
                        with open(ocr_path, 'r', encoding='utf-8') as f:
                            ocr_result = f.read()
                        self.ocr_text_edit.setPlainText(ocr_result)
                    
                    # 刷新图片预览
                    self.load_image_preview()
        except Exception as e:
            print(f"刷新公文失败: {e}")
