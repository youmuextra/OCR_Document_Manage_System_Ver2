# ui/ocr_processing_dialog.py
"""
OCR处理对话框
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QMessageBox, QProgressBar, 
    QGroupBox, QTextEdit, QCheckBox, QFrame, QFileDialog,
    QListWidget, QMenu, QAbstractItemView
)
from PySide6.QtGui import QFont, QPixmap, QImage, QBrush, QColor
from PySide6.QtCore import Qt, QTimer, Signal, QThread, Signal
import os
import sys
import traceback
import copy
from datetime import datetime
import logging
from providers import get_capture_provider

# 配置日志
logger = logging.getLogger(__name__)

class OCRWorker(QThread):
    """OCR工作线程 - 使用真实的 OCRProcessor"""
    
    # 定义信号
    progress_updated = Signal(int, str)  # 进度, 消息
    ocr_completed = Signal(dict)  # 识别结果
    error_occurred = Signal(str)  # 错误信息

    # 共享 OCRProcessor，避免多文件队列时重复初始化 PaddleOCR 引擎
    _shared_ocr_processor = None
    
    def __init__(self, file_path, use_simulate=False):
        super().__init__()
        self.file_path = file_path
        self.use_simulate = use_simulate
        self.is_running = True
    
    def run(self):
        """执行OCR识别 - 使用真实的OCRProcessor"""
        try:
            if not os.path.exists(self.file_path):
                self.error_occurred.emit(f"文件不存在: {self.file_path}")
                return
            
            self.progress_updated.emit(10, "正在初始化OCR引擎...")
            
            # 导入OCRProcessor
            try:
                from ocr.ocr_processor import OCRProcessor
            except ImportError as e:
                self.error_occurred.emit(f"无法导入OCR处理器: {e}\n请确保ocr_processor.py存在")
                return
            
            # 检查文件类型
            ext = os.path.splitext(self.file_path)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.pdf']:
                self.error_occurred.emit(f"不支持的文件格式: {ext}")
                return
            
            self.progress_updated.emit(20, "正在创建OCR处理器...")

            # 创建或复用OCR处理器（队列内复用同一实例）
            try:
                if OCRWorker._shared_ocr_processor is None:
                    # 注意：use_simulate应该为False来使用真实OCR
                    OCRWorker._shared_ocr_processor = OCRProcessor(use_gpu=False, lang='ch')
                ocr_processor = OCRWorker._shared_ocr_processor
            except Exception as e:
                self.error_occurred.emit(f"OCR处理器初始化失败: {e}\n请确保已安装PaddleOCR: pip install paddlepaddle paddleocr")
                return
            
            self.progress_updated.emit(30, "正在处理文件...")
            
            # 处理文件
            try:
                if ext == '.pdf':
                    self.progress_updated.emit(40, "正在转换PDF为图片...")
                    result = ocr_processor.process_pdf(self.file_path)
                else:
                    self.progress_updated.emit(40, "正在加载图片...")
                    result = ocr_processor.process_image(self.file_path)
            except Exception as e:
                self.error_occurred.emit(f"OCR处理失败: {e}")
                return
            
            self.progress_updated.emit(80, "正在解析公文信息...")
            
            # 提取公文信息
            document_info = {}
            if result.get('success'):
                document_info = ocr_processor.extract_document_info(result)

            raw_text = (result.get('text', '') or '').strip()

            def _extract_security_level(src: str) -> str:
                s = src or ''
                # 优先匹配“密级 xxx”
                m = __import__('re').search(r'密级\s*[：:]?\s*(绝密|机密|秘密|非密|普通)', s)
                if m:
                    v = m.group(1)
                    return '普通' if v == '非密' else v
                # 次优先：文本内关键字
                if '绝密' in s:
                    return '绝密'
                if '机密' in s:
                    return '机密'
                if '秘密' in s:
                    return '秘密'
                if '非密' in s:
                    return '普通'
                return ''

            def _extract_urgency_level(src: str) -> str:
                s = src or ''
                m = __import__('re').search(r'等级\s*[：:]?\s*(特急|加急|平急|急件|普通)', s)
                if m:
                    return m.group(1)
                m2 = __import__('re').search(r'紧急(?:程度)?\s*[：:]?\s*(特急|加急|平急|急件|普通)', s)
                if m2:
                    return m2.group(1)
                # 关键词兜底（顺序重要）
                if '特急' in s:
                    return '特急'
                if '加急' in s:
                    return '加急'
                if '平急' in s:
                    return '平急'
                if '急件' in s:
                    return '急件'
                return ''

            sec_val = _extract_security_level(raw_text)
            urg_val = _extract_urgency_level(raw_text)
            
            self.progress_updated.emit(90, "正在整理结果...")
            
            # 构建返回结果
            ocr_result = {
                'document_info': {
                    'document_no': document_info.get('document_no', ''),
                    'title': document_info.get('title', ''),
                    'issuing_unit': document_info.get('issuing_unit', ''),
                    'content_summary': document_info.get('content_summary', '') or document_info.get('summary', ''),
                    'keywords': ', '.join(document_info.get('keywords', [])),
                    'security_level': sec_val,
                    'urgency_level': urg_val
                },
                'raw_text': raw_text,
                'confidence': 0.85,  # 可以计算实际置信度
                'processing_time': result.get('processing_time', 0),
                'engine': 'PaddleOCR',
                'quality_warnings': result.get('quality_warnings', []) or [],
                'original_result': result
            }
            
            # 检查是否是模拟数据
            if self.use_simulate:
                logger.warning("⚠️  OCR模拟模式被启用，返回的是模拟数据！")
            
            # 检查是否识别到文本
            raw_text = result.get('text', '').strip()
            if not raw_text or len(raw_text) < 10:
                logger.warning("⚠️  OCR识别结果为空或太短")
            
            self.progress_updated.emit(100, "识别完成！")
            self.ocr_completed.emit(ocr_result)
            
        except Exception as e:
            logger.error(f"❌ OCR处理失败: {e}")
            import traceback
            traceback.print_exc()
            self.error_occurred.emit(f"OCR处理失败: {str(e)}")
    
    def stop(self):
        """停止处理"""
        self.is_running = False


class LLMPostProcessWorker(QThread):
    """LLM后处理线程：避免在UI线程中进行网络请求导致界面卡顿。"""

    progress_updated = Signal(int, str)   # 百分比, 消息
    completed = Signal(list)              # 处理后的结果列表
    failed = Signal(str)                  # 错误信息

    def __init__(self, results_list):
        super().__init__()
        self.results_list = copy.deepcopy(results_list or [])

    def run(self):
        try:
            from services.llm_service import LLMService

            total = len(self.results_list)
            if total == 0:
                self.completed.emit([])
                return

            for i, res in enumerate(self.results_list):
                progress = int((i / max(total, 1)) * 100)
                self.progress_updated.emit(progress, f"正在进行智能提取 ({i+1}/{total})...")

                raw = (res.get('raw_text') or '').strip()
                if raw and len(raw) > 10:
                    try:
                        parsed = LLMService.extract_document_info(raw)
                        doc_info = res.get('document_info', {}) or {}
                        doc_info.update(parsed)
                        if parsed.get('urgency'):
                            doc_info['urgency_level'] = parsed.get('urgency')
                        if parsed.get('content_summary'):
                            doc_info['content_summary'] = parsed.get('content_summary')
                        res['document_info'] = doc_info
                    except Exception as e:
                        logger.exception(f'LLM 提取失败（第{i+1}个文件）: {e}')

            self.progress_updated.emit(100, "智能提取完成")
            self.completed.emit(self.results_list)
        except Exception as e:
            self.failed.emit(str(e))

class OCRProcessingDialog(QDialog):
    """OCR处理对话框"""
    
    def __init__(self, db_manager, current_user, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user
        self.capture_provider = get_capture_provider()
        self.current_image_path = None
        self.selected_image_paths = []
        self.current_queue_index = 0
        self.ocr_results_list = []
        self.ocr_results_by_path = {}
        self.ocr_errors_by_path = {}
        self.file_status_by_path = {}
        self.failed_files = []
        self.current_processing_path = None
        self.preview_mode = 'all'  # all | current
        self.max_multi_select = 10  # 默认最多同时选择10张图片，可按需调整
        self.ocr_result = None
        self.ocr_worker = None
        self.llm_worker = None
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("OCR公文识别")
        self.resize(960, 760)
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        # 标题
        title_label = QLabel("OCR公文识别")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        title_label.setStyleSheet("color: #2c3e50; margin: 10px 0;")
        layout.addWidget(title_label)
        
        # 文件信息：使用可滚动列表预览所有已选文件
        info_group = QGroupBox("文件信息")
        info_layout = QVBoxLayout()

        self.file_list_widget = QListWidget()
        self.file_list_widget.setStyleSheet("color: #666;")
        # 支持单选，以便“仅看当前选中文件结果”模式可联动预览
        self.file_list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.file_list_widget.setFixedHeight(100)
        # 提示信息，告知用户可以右键操作
        hint = QLabel("（右键打开或删除文件）")
        hint.setStyleSheet("color: #888; font-size:11px; margin-left:4px;")
        info_layout.addWidget(hint)
        # 右键菜单
        self.file_list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list_widget.customContextMenuRequested.connect(self._on_file_list_context_menu)
        self.file_list_widget.itemDoubleClicked.connect(self._on_file_item_double_clicked)
        self.file_list_widget.currentRowChanged.connect(self._on_file_selection_changed)
        info_layout.addWidget(self.file_list_widget)
        # 选择文件按钮（支持多选）
        select_btn_layout = QHBoxLayout()
        self.select_files_button = QPushButton("📁 选择文件")
        self.select_files_button.clicked.connect(self.select_files)
        select_btn_layout.addWidget(self.select_files_button)

        self.capture_button = QPushButton("📷 摄像头拍摄")
        self.capture_button.clicked.connect(self.capture_from_camera)
        select_btn_layout.addWidget(self.capture_button)
        select_btn_layout.addStretch()
        info_layout.addLayout(select_btn_layout)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # 进度条
        progress_group = QGroupBox("识别进度")
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel("等待开始...")
        self.progress_label.setStyleSheet("color: #666;")
        progress_layout.addWidget(self.progress_label)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # 识别结果
        result_group = QGroupBox("识别结果")
        result_layout = QVBoxLayout()

        # 预览模式切换按钮
        mode_layout = QHBoxLayout()
        self.show_all_button = QPushButton("看全部结果")
        self.show_all_button.setCheckable(True)
        self.show_current_button = QPushButton("仅看当前选中文件结果")
        self.show_current_button.setCheckable(True)
        self.show_all_button.clicked.connect(self._set_preview_mode_all)
        self.show_current_button.clicked.connect(self._set_preview_mode_current)
        self.show_all_button.setChecked(True)
        self.show_current_button.setChecked(False)
        mode_layout.addWidget(self.show_all_button)
        mode_layout.addWidget(self.show_current_button)
        mode_layout.addStretch()
        result_layout.addLayout(mode_layout)
        
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMinimumHeight(320)
        self.result_text.setPlaceholderText("识别结果将显示在这里...")
        result_layout.addWidget(self.result_text)
        
        result_group.setLayout(result_layout)
        layout.addWidget(result_group)
        
        # 选项
        options_group = QGroupBox("识别选项")
        options_layout = QVBoxLayout()
        
        self.auto_fill_checkbox = QCheckBox("识别完成后自动填充到表单")
        self.auto_fill_checkbox.setChecked(True)
        options_layout.addWidget(self.auto_fill_checkbox)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("▶️ 开始识别")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.start_button.clicked.connect(self.start_ocr)
        self.start_button.setEnabled(False)
        
        self.cancel_button = QPushButton("❌ 取消")
        self.cancel_button.clicked.connect(self.on_cancel)
        
        self.confirm_button = QPushButton("✅ 确认结果")
        self.confirm_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.confirm_button.clicked.connect(self.on_confirm)
        self.confirm_button.setEnabled(False)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()
        button_layout.addWidget(self.confirm_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def on_confirm(self):
        """确认按钮点击事件"""
        if hasattr(self, 'ocr_result') and self.ocr_result:
            self.accept()  # 关闭对话框
        else:
            QMessageBox.warning(self, "警告", "请先完成OCR识别！")

    def _set_preview_mode_all(self):
        """切换为查看全部结果模式。"""
        self.preview_mode = 'all'
        self.show_all_button.setChecked(True)
        self.show_current_button.setChecked(False)
        self._refresh_result_preview()

    def _set_preview_mode_current(self):
        """切换为仅看当前选中文件结果模式。"""
        self.preview_mode = 'current'
        self.show_all_button.setChecked(False)
        self.show_current_button.setChecked(True)
        # 若尚未选择，则默认选中第一项
        if self.file_list_widget.count() > 0 and self.file_list_widget.currentRow() < 0:
            self.file_list_widget.setCurrentRow(0)
        self._refresh_result_preview()

    def _on_file_selection_changed(self, _row):
        """文件列表选中项变化时刷新预览（仅当前文件模式下生效）。"""
        if self.preview_mode == 'current':
            self._refresh_result_preview()

    def _get_display_paths(self):
        """获取当前用于展示的文件路径序列。"""
        if hasattr(self, 'queue') and self.queue:
            return list(self.queue)
        if self.selected_image_paths:
            return list(self.selected_image_paths)
        if self.current_image_path:
            return [self.current_image_path]
        return []

    def _format_file_item_text(self, path):
        """根据状态返回列表展示文字：成功✅、失败❌、未处理不加前缀。"""
        name = os.path.basename(path) if path else "未知文件"
        status = self.file_status_by_path.get(path)
        if status == 'success':
            return f"✅ {name}"
        if status == 'failed':
            return f"❌ {name}"
        return name

    def _update_file_item_status(self, path, status):
        """更新某个文件的状态并刷新列表对应项文字。"""
        if not path:
            return
        self.file_status_by_path[path] = status
        try:
            paths = self._get_display_paths()
            if path in paths:
                idx = paths.index(path)
                if 0 <= idx < self.file_list_widget.count():
                    item = self.file_list_widget.item(idx)
                    item.setText(self._format_file_item_text(path))
                    # 失败项悬浮提示显示详细错误；其他状态清空tooltip
                    if status == 'failed':
                        tip = self.ocr_errors_by_path.get(path, '识别失败（无详细错误信息）')
                        item.setToolTip(tip)
                    else:
                        item.setToolTip("")
        except Exception:
            pass

    def _format_single_result_block(self, path, res):
        """格式化单个文件的预览文本。"""
        file_name = os.path.basename(path) if path else "未知文件"
        if path in self.ocr_errors_by_path:
            return f"=== {file_name} ===\n❌ 识别失败\n{self.ocr_errors_by_path.get(path, '')}"
        if not res:
            if path and path == self.current_processing_path:
                return f"=== {file_name} ===\n⏳ 正在识别中，请稍候..."
            return f"=== {file_name} ===\n⚠️ 尚未识别"

        raw = (res.get('raw_text') or '').strip()
        doc_info = res.get('document_info', {}) or {}
        info_text = f"=== {file_name} ===\n"
        info_text += "提取结果：\n"
        info_text += f"文号: {doc_info.get('document_no', '')}\n"
        info_text += f"标题: {doc_info.get('title', '')}\n"
        info_text += f"发文单位: {doc_info.get('issuing_unit', '')}\n"
        info_text += f"密级: {doc_info.get('security_level', '')}\n"
        info_text += f"紧急程度: {doc_info.get('urgency_level', '')}\n"
        info_text += f"收文时间: {doc_info.get('received_date', '')}\n"
        if not any([doc_info.get('document_no'), doc_info.get('title'), doc_info.get('issuing_unit')]):
            info_text += "⚠️ 未提取到关键字段，请检查原图质量后重试\n"
        return info_text

    def load_cached_results(self, selected_paths, results_list):
        """加载历史OCR结果用于回看，不重新执行识别。"""
        self.selected_image_paths = list(selected_paths or [])
        self.queue = list(selected_paths or [])
        self.ocr_results_list = list(results_list or [])
        self.ocr_results_by_path = {}
        self.file_status_by_path = {}

        self.file_list_widget.clear()
        for i, p in enumerate(self.selected_image_paths):
            self.file_status_by_path[p] = 'success' if i < len(self.ocr_results_list) else None
            self.file_list_widget.addItem(self._format_file_item_text(p))
            if i < len(self.ocr_results_list):
                self.ocr_results_by_path[p] = self.ocr_results_list[i]

        if self.file_list_widget.count() > 0:
            self.file_list_widget.setCurrentRow(0)

        if self.ocr_results_list:
            self.ocr_result = self.ocr_results_list[-1]
            self.confirm_button.setEnabled(True)
        self.start_button.setEnabled(True)
        self.progress_bar.setValue(100)
        self.progress_label.setText("已加载历史识别结果")
        self._refresh_result_preview()

    def _refresh_result_preview(self):
        """根据当前模式刷新“识别结果”文本框。"""
        paths = self._get_display_paths()
        if not paths:
            self.result_text.setText("⚠️ 未选择文件")
            return

        if self.preview_mode == 'current':
            row = self.file_list_widget.currentRow()
            if row < 0:
                row = 0
            if row >= len(paths):
                row = len(paths) - 1
            path = paths[row]
            block = self._format_single_result_block(path, self.ocr_results_by_path.get(path))
            self.result_text.setText(block)
            return

        # all mode
        blocks = [self._format_single_result_block(p, self.ocr_results_by_path.get(p)) for p in paths]
        self.result_text.setText("\n\n".join(blocks) if blocks else "⚠️ 未识别到文本内容")
    
    def set_image_path(self, image_path):
        """设置要处理的图片路径"""
        self.current_image_path = image_path
        # 将单路径视为已选择单个文件，更新列表展示
        self.selected_image_paths = []
        self.file_list_widget.clear()
        if image_path and os.path.exists(image_path):
            self.selected_image_paths.append(image_path)
            self.file_list_widget.addItem(self._format_file_item_text(image_path))
            self.file_list_widget.setCurrentRow(0)
            self.start_button.setEnabled(True)
        else:
            self.file_list_widget.addItem("未选择文件或文件不存在")
            self.start_button.setEnabled(False)
        self._refresh_result_preview()

    def select_files(self):
        """打开文件选择对话框，支持多选并限制最大数量

        如果已经选择过文件，这次选择会追加至队列，直到达到最大上限。
        """
        caption = "选择图片或PDF（最多 %d 个）" % self.max_multi_select
        files, _ = QFileDialog.getOpenFileNames(
            self, caption, os.path.expanduser("~"),
            "Images and PDF (*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.pdf)"
        )
        if not files:
            return
        # 过滤掉已存在的路径
        new_files = [f for f in files if f not in self.selected_image_paths]
        if not new_files:
            return
        total = len(self.selected_image_paths) + len(new_files)
        if total > self.max_multi_select:
            QMessageBox.warning(
                self, "选择太多文件",
                f"最多只能选择 {self.max_multi_select} 个文件；当前已有 {len(self.selected_image_paths)} 个，\n" +
                f"本次选择 {len(new_files)} 个，将超出上限。请重新选择。"
            )
            return
        # 追加新文件并更新列表展示
        self.selected_image_paths.extend(new_files)
        self.current_queue_index = 0
        self.file_list_widget.clear()
        for p in self.selected_image_paths:
            self.file_list_widget.addItem(self._format_file_item_text(p))
        if self.file_list_widget.count() > 0:
            self.file_list_widget.setCurrentRow(0)
        self.start_button.setEnabled(True if self.selected_image_paths or self.current_image_path else False)
        self._refresh_result_preview()

    def capture_from_camera(self):
        """通过摄像头拍摄并加入待识别列表。"""
        try:
            captured_path = self.capture_provider.capture_from_camera(self)
            if not captured_path:
                return

            if captured_path not in self.selected_image_paths:
                if len(self.selected_image_paths) >= self.max_multi_select:
                    QMessageBox.warning(self, "数量超限", f"最多只能选择 {self.max_multi_select} 个文件")
                    return
                self.selected_image_paths.append(captured_path)

            self.current_queue_index = 0
            self.file_list_widget.clear()
            for p in self.selected_image_paths:
                self.file_list_widget.addItem(self._format_file_item_text(p))
            if self.file_list_widget.count() > 0:
                self.file_list_widget.setCurrentRow(self.file_list_widget.count() - 1)

            self.start_button.setEnabled(True)
            self.progress_label.setText(f"已拍摄并加入队列: {os.path.basename(captured_path)}")
            self._refresh_result_preview()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"摄像头拍摄失败: {e}")

    def _on_file_item_double_clicked(self, item):
        """双击文件名时打开文件（平台相关）。"""
        try:
            idx = self.file_list_widget.row(item)
            path = self.selected_image_paths[idx]
            try:
                os.startfile(path)
            except Exception:
                import subprocess, sys
                if sys.platform == 'darwin':
                    subprocess.call(('open', path))
                else:
                    subprocess.call(('xdg-open', path))
        except Exception:
            pass

    def _on_file_list_context_menu(self, pos):
        """右键菜单：打开 / 从列表移除 / 清空"""
        try:
            item = self.file_list_widget.itemAt(pos)
            menu = QMenu(self)
            if item is not None:
                open_action = menu.addAction("打开文件")
                remove_action = menu.addAction("从列表移除")
                action = menu.exec(self.file_list_widget.mapToGlobal(pos))
                if action == open_action:
                    self._on_file_item_double_clicked(item)
                elif action == remove_action:
                    idx = self.file_list_widget.row(item)
                    try:
                        removed_path = self.selected_image_paths.pop(idx)
                        if removed_path in self.ocr_results_by_path:
                            del self.ocr_results_by_path[removed_path]
                        if removed_path in self.ocr_errors_by_path:
                            del self.ocr_errors_by_path[removed_path]
                        if removed_path in self.file_status_by_path:
                            del self.file_status_by_path[removed_path]
                        if removed_path in self.failed_files:
                            self.failed_files = [p for p in self.failed_files if p != removed_path]
                    except Exception:
                        pass
                    self.file_list_widget.takeItem(idx)
                    if self.file_list_widget.count() > 0:
                        self.file_list_widget.setCurrentRow(min(idx, self.file_list_widget.count() - 1))
            else:
                clear_action = menu.addAction("清空列表")
                action = menu.exec(self.file_list_widget.mapToGlobal(pos))
                if action == clear_action:
                    self.selected_image_paths = []
                    self.ocr_results_by_path = {}
                    self.ocr_errors_by_path = {}
                    self.file_status_by_path = {}
                    self.failed_files = []
                    self.file_list_widget.clear()
            self._refresh_result_preview()
        except Exception:
            pass
    
    def start_ocr(self):
        """开始OCR识别"""
        # 支持多文件队列：优先使用 selected_image_paths，其次使用 single current_image_path
        queue = []
        if self.selected_image_paths:
            queue = self.selected_image_paths
        elif self.current_image_path:
            queue = [self.current_image_path]

        if not queue:
            QMessageBox.warning(self, "警告", "请先选择文件")
            return
        
        # 检查文件格式（以队列第一个文件为准）
        first_path = queue[0]
        ext = os.path.splitext(first_path)[1].lower()
        supported_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.pdf']
        
        if ext not in supported_formats:
            QMessageBox.warning(self, "警告", f"不支持的文件格式: {ext}\n支持的格式: {', '.join(supported_formats)}")
            return
        
        # 检查PDF依赖
        if ext == '.pdf':
            try:
                from pdf2image import convert_from_path
            except ImportError as e:
                QMessageBox.critical(
                    self, "缺少依赖", 
                    "PDF处理需要pdf2image库:\n\n"
                    "请运行: pip install pdf2image\n\n"
                    "还需要安装poppler:\n"
                    "Windows: 下载poppler并添加到PATH\n"
                    "macOS: brew install poppler\n"
                    "Linux: sudo apt-get install poppler-utils"
                )
                return
        
        # 初始化队列并启动第一个任务
        self.ocr_results_list = []
        self.ocr_results_by_path = {}
        self.ocr_errors_by_path = {}
        self.file_status_by_path = {}
        self.failed_files = []
        self.current_processing_path = None
        self.current_queue_index = 0
        self.queue = queue

        # 重置列表文本为“未处理”状态（不加前缀）
        self.file_list_widget.clear()
        for p in self.queue:
            self.file_list_widget.addItem(self._format_file_item_text(p))
        if self.file_list_widget.count() > 0:
            self.file_list_widget.setCurrentRow(0)

        self.start_button.setEnabled(False)
        self.confirm_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("正在准备OCR识别...")
        self.result_text.clear()

        # 启动第一个任务（start_next_in_queue 会创建线程并启动）
        self.start_next_in_queue()

    def start_next_in_queue(self):
        """启动队列中的下一个文件的 OCR 处理"""
        try:
            if not hasattr(self, 'queue') or self.current_queue_index >= len(self.queue):
                return
            path = self.queue[self.current_queue_index]
            self.current_processing_path = path
            # 创建OCR工作线程 - 强制禁用模拟模式
            self.ocr_worker = OCRWorker(path, use_simulate=False)
            # 连接信号
            self.ocr_worker.progress_updated.connect(self.update_progress)
            self.ocr_worker.ocr_completed.connect(self.on_ocr_completed)
            self.ocr_worker.error_occurred.connect(self.on_ocr_error)
            # 高亮当前正在处理的文件（如果在列表中）
            try:
                for i in range(self.file_list_widget.count()):
                    it = self.file_list_widget.item(i)
                    it.setBackground(QBrush(QColor('white')))
                # 设置当前项背景色
                if self.current_queue_index < self.file_list_widget.count():
                    cur_item = self.file_list_widget.item(self.current_queue_index)
                    cur_item.setBackground(QBrush(QColor('#e6f7ff')))
                    # 当前文件模式下，自动切换焦点到正在处理项
                    self.file_list_widget.setCurrentRow(self.current_queue_index)
                    self.file_list_widget.scrollToItem(cur_item)
            except Exception:
                pass
            # 当前文件模式下同步刷新预览
            if self.preview_mode == 'current':
                self._refresh_result_preview()
            # 在进度提示区显示当前文件
            self.progress_label.setText(f"正在处理: {os.path.basename(path)} ({self.current_queue_index+1}/{len(self.queue)})")
            # 启动线程
            self.ocr_worker.start()
        except Exception:
            logger.exception('启动下一个OCR任务失败')
    
    def update_progress(self, value, message):
        """更新进度"""
        self.progress_bar.setValue(value)
        self.progress_label.setText(message)
    
    def on_ocr_completed(self, result):
        """OCR识别完成"""
        # 存储此轮结果
        self.ocr_results_list.append(result)
        self.ocr_result = result
        # 按文件路径缓存识别结果，供“全部/当前文件”两种预览模式复用
        try:
            if hasattr(self, 'queue') and self.current_queue_index < len(self.queue):
                cur_path = self.queue[self.current_queue_index]
                self.ocr_results_by_path[cur_path] = result
                self._update_file_item_status(cur_path, 'success')
        except Exception:
            pass

        self._refresh_result_preview()

        # 当前轮日志
        raw_text = (result.get('raw_text') or '').strip()
        if raw_text:
            logger.info(f"✅ OCR识别完成: {len(raw_text)}字符, {len(raw_text.splitlines())}行")
        else:
            logger.warning("OCR识别结果为空")
        
        # 更新状态
        self.progress_label.setText("OCR识别完成！")
        self.confirm_button.setEnabled(True)
        
        # 显示公文信息
        doc_info = result.get('document_info', {})
        if doc_info.get('title'):
            logger.info(f"📄 提取到公文标题: {doc_info.get('title')}")
        
        # 如果队列中还有下一个文件，继续处理
        if hasattr(self, 'queue') and (self.current_queue_index + 1) < len(self.queue):
            self.current_queue_index += 1
            QTimer.singleShot(300, self.start_next_in_queue)
            return

        # 到这里表示队列处理完成
        self.current_processing_path = None
        self.start_button.setEnabled(True)
        self.progress_label.setText("所有文件识别完成！")

        # 只在全部完成后提示一次，避免多图时重复弹窗打断
        total_chars = sum(len((r.get('raw_text') or '')) for r in self.ocr_results_list)
        failed_count = len(self.failed_files)
        if failed_count > 0:
            QMessageBox.warning(
                self,
                "识别完成",
                f"批量识别已完成。\n\n"
                f"成功: {len(self.ocr_results_list)} 个\n"
                f"失败: {failed_count} 个（已自动跳过）\n"
                f"总字符数: {total_chars}"
            )
        else:
            QMessageBox.information(
                self,
                "识别完成",
                f"OCR识别完成！\n\n"
                f"文件数: {len(self.ocr_results_list)}\n"
                f"总字符数: {total_chars}"
            )

        # 如果配置为自动填充，则对每个结果调用 LLM 提取并合并到 document_info
        if self.auto_fill_checkbox.isChecked():
            self.start_llm_postprocess_async()

    def start_llm_postprocess_async(self):
        """异步执行LLM提取，避免阻塞UI导致滚动卡顿。"""
        try:
            if self.llm_worker and self.llm_worker.isRunning():
                return
            self.llm_worker = LLMPostProcessWorker(self.ocr_results_list)
            self.llm_worker.progress_updated.connect(self.on_llm_progress)
            self.llm_worker.completed.connect(self.on_llm_completed)
            self.llm_worker.failed.connect(self.on_llm_failed)
            self.progress_label.setText("正在后台进行智能提取...")
            self.llm_worker.start()
        except Exception:
            logger.exception('自动填充失败: 无法启动LLM后处理线程')

    def on_llm_progress(self, value, message):
        """LLM后处理进度更新。"""
        # 保持OCR进度100%，仅更新文案提示，避免用户误解识别退回
        self.progress_bar.setValue(100)
        self.progress_label.setText(message)

    def on_llm_completed(self, processed_results):
        """LLM后处理完成。"""
        try:
            self.ocr_results_list = processed_results or []
            # 同步更新按路径缓存，便于预览模式展示
            try:
                if hasattr(self, 'queue'):
                    for idx, p in enumerate(self.queue):
                        if idx < len(self.ocr_results_list):
                            self.ocr_results_by_path[p] = self.ocr_results_list[idx]
            except Exception:
                pass

            if self.ocr_results_list:
                self.ocr_result = self.ocr_results_list[-1]
            self._refresh_result_preview()
            self.progress_label.setText("所有文件识别完成（智能提取已完成）")
        except Exception:
            logger.exception('处理LLM完成回调失败')

    def on_llm_failed(self, error_message):
        """LLM后处理失败（不影响OCR结果查看）。"""
        logger.error(f'LLM后处理失败: {error_message}')
        self.progress_label.setText("所有文件识别完成（智能提取失败，已保留OCR结果）")
    
    def get_ocr_result(self):
        """获取OCR结果"""
        return getattr(self, 'ocr_result', None)
    
    def on_ocr_error(self, error_message):
        """OCR识别错误"""
        # 标记当前文件失败，并跳过继续处理后续文件
        cur_path = None
        try:
            if hasattr(self, 'queue') and self.current_queue_index < len(self.queue):
                cur_path = self.queue[self.current_queue_index]
                self.ocr_errors_by_path[cur_path] = error_message
                self._update_file_item_status(cur_path, 'failed')
                self.failed_files.append(cur_path)
        except Exception:
            pass

        self.progress_label.setText(f"识别失败，已跳过: {os.path.basename(cur_path) if cur_path else ''}")
        logger.error(f"OCR识别失败，已跳过文件: {cur_path}, 错误: {error_message}")
        self._refresh_result_preview()

        # 若还有下一个文件，继续队列
        if hasattr(self, 'queue') and (self.current_queue_index + 1) < len(self.queue):
            self.current_queue_index += 1
            QTimer.singleShot(200, self.start_next_in_queue)
            return

        # 队列结束：统一汇总
        self.current_processing_path = None
        success_count = len(self.ocr_results_list)
        failed_count = len(self.failed_files)
        self.start_button.setEnabled(True)
        self.confirm_button.setEnabled(success_count > 0)
        self.progress_label.setText("批量识别结束（含失败项）")
        QMessageBox.warning(
            self,
            "识别结束",
            f"批量识别已完成。\n\n成功: {success_count} 个\n失败: {failed_count} 个（已自动跳过）"
        )
    
    def on_cancel(self):
        """取消识别"""
        if self.ocr_worker and self.ocr_worker.isRunning():
            reply = QMessageBox.question(
                self, 
                "确认取消", 
                "识别正在进行中，确定要取消吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.ocr_worker.stop()
                self.ocr_worker.wait()

        if self.llm_worker and self.llm_worker.isRunning():
            try:
                self.llm_worker.terminate()
                self.llm_worker.wait()
            except Exception:
                pass
        
        self.reject()
