# ui/receive_document_dialog.py
"""
收文登记对话框 - 包含OCR识别功能
"""

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QMessageBox, QDateEdit,
    QFormLayout, QGroupBox, QTextEdit, QComboBox,
    QProgressBar, QCheckBox, QStackedWidget
)
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtCore import Qt, QDate, QTimer, Signal
from datetime import datetime
import re
import os
import shutil
import uuid
from providers import get_capture_provider


class FilePage(QWidget):
    """第一步：选择文件并执行OCR的子页面"""

    # 外部监听OCR请求
    ocr_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_path = None
        self.ocr_text = ""
        layout = QVBoxLayout(self)
        self.label = QLabel("未选择文件")
        self.label.setStyleSheet("color: #666;")

        # 本地文件 / 摄像头（高拍仪替代）
        top_btns = QHBoxLayout()
        self.choose_button = QPushButton("📂 选择本地文件")
        self.choose_button.clicked.connect(self.choose_file)
        self.camera_button = QPushButton("📷 摄像头拍摄")
        self.camera_button.clicked.connect(self.open_camera)
        top_btns.addWidget(self.choose_button)
        top_btns.addWidget(self.camera_button)

        self.ocr_button = QPushButton("🔍 OCR识别")
        # 按钮现在总是可以点击，实际行为由父窗口处理
        self.ocr_button.setEnabled(True)
        self.ocr_button.clicked.connect(self.run_ocr)
        layout.addWidget(self.label)
        layout.addLayout(top_btns)
        layout.addWidget(self.ocr_button)

    def choose_file(self):
        parent = self.window()
        if hasattr(parent, 'on_choose_local_file'):
            parent.on_choose_local_file()

    def open_camera(self):
        parent = self.window()
        if hasattr(parent, 'on_camera'):
            parent.on_camera()

    def set_selected_path(self, path):
        """由外部（例如摄像头或父对话框）设置文件路径并更新UI。"""
        self.selected_path = path
        if path and os.path.exists(path):
            self.label.setText(f"📄 {os.path.basename(path)}")
            self.ocr_button.setEnabled(True)
        else:
            self.label.setText("未选择文件")
            self.ocr_button.setEnabled(True)  # 保持可点状态，但动作会做路径检查

    def run_ocr(self):
        # 当按钮按下时，调用顶层对话框的OCR流程。
        parent = self.window()
        if hasattr(parent, 'perform_ocr'):
            # 如果有当前已知路径则传入，否则None，父对话框将弹出OCR处理窗口
            parent.perform_ocr(self.selected_path)

class ReceiveDocumentDialog(QDialog):
    """收文登记对话框（多页向导）"""

    ocr_completed = Signal(dict)

    def __init__(self, db_manager, current_user, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user
        self.capture_provider = get_capture_provider()
        self.current_file_path = None
        self.ocr_result = {}
        self.cached_ocr_results_list = []
        self.cached_selected_paths = []
        self._current_page = 0
        self.setup_ui()
        self.ocr_completed.connect(self.on_ocr_completed)

    def set_ocr_context(self, latest_result=None, results_list=None, selected_paths=None):
        """设置OCR上下文，供“上一步”回看识别结果使用。"""
        self.ocr_result = latest_result or {}
        self.cached_ocr_results_list = list(results_list or [])
        self.cached_selected_paths = list(selected_paths or [])

    def setup_ui(self):
        self.setWindowTitle("收文登记")
        self.resize(700, 600)

        outer = QVBoxLayout(self)

        # 页栈
        self.stack = QStackedWidget()
        self.page_file = FilePage(self)
        self.page_info = QWidget()
        # build form on info page
        form_layout = QFormLayout(self.page_info)
        self.doc_no_input = QLineEdit(); self.doc_no_input.setPlaceholderText("请输入文号")
        form_layout.addRow("文号*:", self.doc_no_input)
        self.title_input = QLineEdit(); self.title_input.setPlaceholderText("请输入标题")
        form_layout.addRow("标题*:", self.title_input)
        self.unit_input = QLineEdit(); self.unit_input.setPlaceholderText("请输入发文单位")
        form_layout.addRow("发文单位:", self.unit_input)
        self.date_input = QDateEdit(); self.date_input.setDate(QDate.currentDate()); self.date_input.setCalendarPopup(True)
        form_layout.addRow("收文日期:", self.date_input)
        self.processor_input = QLineEdit(); self.processor_input.setPlaceholderText("请输入经办人");
        self.processor_input.setText(self.current_user.get('real_name',''))
        form_layout.addRow("经办人:", self.processor_input)
        self.location_input = QLineEdit(); self.location_input.setPlaceholderText("请输入存放位置")
        form_layout.addRow("存放位置:", self.location_input)
        self.security_combo = QComboBox(); self.security_combo.addItems(["普通","秘密","机密","绝密"])
        form_layout.addRow("密级:", self.security_combo)
        self.urgency_combo = QComboBox(); self.urgency_combo.addItems(["普通","平急","加急","特急","急件"])
        form_layout.addRow("紧急程度:", self.urgency_combo)
        self.type_combo = QComboBox(); self.type_combo.addItems(["通知","报告","请示","批复","函","纪要","其他"])
        form_layout.addRow("文种:", self.type_combo)
        self.copies_input = QLineEdit(); self.copies_input.setText("1"); self.copies_input.setMaximumWidth(50)
        form_layout.addRow("份数:", self.copies_input)
        self.content_input = QTextEdit(); self.content_input.setMaximumHeight(100); self.content_input.setPlaceholderText("请输入内容摘要")
        form_layout.addRow("内容摘要:", self.content_input)
        self.keywords_input = QLineEdit(); self.keywords_input.setPlaceholderText("请输入关键词，用逗号分隔")
        form_layout.addRow("关键词:", self.keywords_input)
        self.remarks_input = QTextEdit(); self.remarks_input.setMaximumHeight(80); self.remarks_input.setPlaceholderText("请输入备注信息")
        form_layout.addRow("备注:", self.remarks_input)

        self.stack.addWidget(self.page_file)
        self.stack.addWidget(self.page_info)
        outer.addWidget(self.stack)

        # 导航按钮
        nav = QHBoxLayout()
        self.prev_btn = QPushButton("上一步")
        self.next_btn = QPushButton("下一步")
        self.prev_btn.clicked.connect(self._prev_page)
        self.next_btn.clicked.connect(self._next_page)
        nav.addWidget(self.prev_btn)
        nav.addStretch()
        nav.addWidget(self.next_btn)
        outer.addLayout(nav)

        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666;")
        outer.addWidget(self.status_label)

        self._update_nav()

    def _update_nav(self):
        idx = self.stack.currentIndex()
        self.prev_btn.setEnabled(idx > 0)
        self.next_btn.setText("完成" if idx == self.stack.count() - 1 else "下一步")

    def _next_page(self):
        idx = self.stack.currentIndex()
        if idx < self.stack.count() - 1:
            self._set_page_readonly(idx, True)
            self.stack.setCurrentIndex(idx + 1)
        else:
            self.save_document()
            return
        self._update_nav()

    def _prev_page(self):
        idx = self.stack.currentIndex()
        if idx > 0:
            # 不再回到旧的空白第一页，改为直接弹出识别结果回看窗口
            self.show_ocr_preview_dialog()
            return
        self._update_nav()

    def show_ocr_preview_dialog(self):
        """显示OCR结果回看窗口（不丢失历史识别结果）。"""
        try:
            from ui.ocr_processing_dialog import OCRProcessingDialog
            dlg = OCRProcessingDialog(self.db_manager, self.current_user, self)
            if self.cached_selected_paths and self.cached_ocr_results_list:
                dlg.load_cached_results(self.cached_selected_paths, self.cached_ocr_results_list)
            elif self.current_file_path:
                dlg.set_image_path(self.current_file_path)
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "提示", f"无法打开识别结果回看窗口: {e}")

    def perform_ocr(self, path=None):
        """外部页面调用的OCR入口，可接收文件路径。

        如果提供了路径则预置到OCR对话框并记录，若不提供则直接弹出OCR处理对话框让
        用户选择。完成后会尝试将所选文件保存到 `self.current_file_path` 并更新
        FilePage 的显示。
        """
        if path:
            self.current_file_path = path
            # 同步展示到文件页
            try:
                self.page_file.set_selected_path(path)
            except Exception:
                pass

        # 复用 on_ocr 的业务逻辑，该函数内部已经会弹出 OCRProcessingDialog
        result = self.on_ocr()


        # ensure FilePage label follows current_file_path
        if self.current_file_path:
            try:
                self.page_file.set_selected_path(self.current_file_path)
            except Exception:
                pass

        return result

    def _set_page_readonly(self, page_index, readonly=True):
        page = self.stack.widget(page_index)
        # ``findChildren`` does not accept a tuple of types in PySide6, unlike
        # some PyQt versions. iterate over each class separately.
        for cls in (QLineEdit, QTextEdit, QComboBox):
            for widget in page.findChildren(cls):
                try:
                    widget.setReadOnly(readonly)
                except Exception:
                    widget.setEnabled(not readonly)
    
    def on_ocr(self):
        """OCR识别按钮点击事件"""
        # 不再在此处强制要求已有文件路径；无路径时只打开OCR处理对话框
        try:
            # 尝试导入OCR处理对话框
            from ui.ocr_processing_dialog import OCRProcessingDialog
            
            # 创建OCR处理对话框
            ocr_dialog = OCRProcessingDialog(self.db_manager, self.current_user, self)
            
            # 如果父窗口传了初始路径，则预置
            if hasattr(ocr_dialog, 'set_image_path') and self.current_file_path:
                ocr_dialog.set_image_path(self.current_file_path)
            
            # 显示对话框
            if ocr_dialog.exec() == QDialog.Accepted:
                # 📌 获取OCR结果并尝试从对话框中抓取选择的文件路径
                ocr_result = ocr_dialog.get_ocr_result()  # 添加这个方法
                # 跟踪所选路径（取第一个作为当前文件）
                try:
                    sel = getattr(ocr_dialog, 'selected_image_paths', None)
                    if sel:
                        self.current_file_path = sel[0]
                        self.page_file.set_selected_path(self.current_file_path)
                        self.cached_selected_paths = list(sel)
                    self.cached_ocr_results_list = list(getattr(ocr_dialog, 'ocr_results_list', []) or [])
                except Exception:
                    pass

                # 检查并提示当前文件大小
                if self.current_file_path and os.path.exists(self.current_file_path):
                    file_size = os.path.getsize(self.current_file_path)
                    if file_size > 10 * 1024 * 1024:  # 10MB
                        reply = QMessageBox.question(
                            self,
                            "文件较大",
                            f"文件大小: {file_size/1024/1024:.1f}MB，可能会影响识别速度。\n是否继续？",
                            QMessageBox.Yes | QMessageBox.No
                        )
                        if reply == QMessageBox.No:
                            return

                if ocr_result and 'document_info' in ocr_result:
                    # 合并多页结果（如“红头1+红头2”），避免仅取最后一页导致关键字段缺失
                    combined_info, raw_text = self._merge_ocr_results_for_form(
                        latest_result=ocr_result,
                        results_list=self.cached_ocr_results_list
                    )

                    def _doc_no_ok(v: str) -> bool:
                        s = (v or '').strip()
                        if not s:
                            return False
                        if len(s) < 4 or len(s) > 36:
                            return False
                        if re.search(r'(请妥善保管|仅供相关人员阅|密级|等级|签发|抄送|拟稿|联系电话|长期)', s):
                            return False
                        return bool(re.search(r'[〔【\[（(]\d{4}[〕】\]）)]', s) or ('号' in s))

                    try:
                        from services.llm_service import LLMService
                        if raw_text:
                            llm_info = LLMService.extract_document_info(raw_text)
                            if isinstance(llm_info, dict):
                                # 合并LLM结果：OCR为空时填充；OCR明显不合理时允许覆盖
                                for k, v in llm_info.items():
                                    if not v:
                                        continue
                                    if not combined_info.get(k):
                                        combined_info[k] = v
                                        continue
                                    if k in ('document_no', 'doc_no', 'number') and not _doc_no_ok(str(combined_info.get(k))):
                                        combined_info[k] = v
                    except Exception as exc:
                        # LLM调用失败：记录日志并提示用户，仍使用OCR提取内容
                        import logging
                        logging.getLogger(__name__).warning(f"LLM调用失败: {exc}")
                        self.status_label.setText("自动填充失败，已使用OCR结果")
                        # 不中断流程，继续展示OCR信息
                        pass
                    # 透传原始文本，便于填充阶段做密级/紧急程度兜底判断
                    combined_info['_raw_text'] = raw_text
                    # 发射OCR完成信号
                    self.ocr_completed.emit(combined_info)
                else:
                    self.status_label.setText("OCR识别完成，但未获取到有效信息")
            else:
                self.status_label.setText("OCR识别已取消")
        
        except ImportError as e:
            QMessageBox.warning(
                self, 
                "功能未实现", 
                f"OCR功能模块未找到:\n\n{str(e)}\n\n请确保ui/ocr_processing_dialog.py文件存在。"
            )
        except Exception as e:
            QMessageBox.critical(self, "错误", f"OCR识别失败:\n\n{str(e)}")
            import traceback
            traceback.print_exc()

    def _merge_ocr_results_for_form(self, latest_result: dict, results_list: list):
        """将OCR多结果合并为单份表单数据，优先保留高质量字段。"""
        results = [r for r in (results_list or []) if isinstance(r, dict)]
        if not results and isinstance(latest_result, dict):
            results = [latest_result]

        def _score_doc_no(s: str) -> float:
            if not s:
                return -1
            s = s.strip()
            score = 0.0
            if '号' in s:
                score += 5
            if re.search(r'〔\d{4}〕|[（(\[]\d{4}[）)\]]', s):
                score += 6
            if re.search(r'(发|办|发电)', s):
                score += 2
            if re.search(r'(请妥善保管|仅供相关人员阅|密级|等级|签发|抄送|拟稿|联系电话|长期)', s):
                score -= 10
            if len(s) > 45:
                score -= 3
            return score

        def _clean_doc_no(s: str) -> str:
            s = re.sub(r'\s+', '', (s or '').strip())
            if not s:
                return ''
            s = re.sub(r'^(?:长期|特急|加急|平急|急件|非密|普通|密级|等级|签发)+', '', s)
            s = re.sub(r'^(?:请妥善保管|仅供相关人员阅)+', '', s)
            m = re.search(r'([\u4e00-\u9fa5A-Za-z]{1,16}(?:发电|发|办)?[〔【\[（(]?\d{4}[〕】\]）)]?\d{0,5}号?)', s)
            return m.group(1) if m else s

        def _extract_doc_no_from_text(src: str) -> str:
            """从已识别文本中强制提取文号（用于兜底）。"""
            if not src:
                return ''
            compact = re.sub(r'\s+', '', src)
            patterns = [
                # 电报/发文常见格式
                r'([\u4e00-\u9fa5A-Za-z]{1,16}(?:发电|发|办)[〔【\[（(]?\d{4}[〕】\]）)]?\d{0,5}号)',
                # 普通发文字号
                r'([\u4e00-\u9fa5A-Za-z]{1,16}[〔【\[（(]?\d{4}[〕】\]）)]\d{1,5}号)',
                # 允许“文号：xxx号”
                r'文号[：:]*([^\n，。；;]{4,40}号)'
            ]
            for p in patterns:
                m = re.search(p, compact)
                if m:
                    cand = _clean_doc_no(m.group(1))
                    if _doc_no_ok(cand):
                        return cand
            return ''

        def _doc_no_ok(s: str) -> bool:
            s = (s or '').strip()
            if not s:
                return False
            if len(s) < 4 or len(s) > 36:
                return False
            if re.search(r'(请妥善保管|仅供相关人员阅|密级|等级|签发|抄送|拟稿|联系电话|长期)', s):
                return False
            return bool(re.search(r'[〔【\[（(]\d{4}[〕】\]）)]', s) or ('号' in s))

        def _score_title(s: str) -> float:
            if not s:
                return -1
            score = 0.0
            if '关于' in s:
                score += 6
            if any(k in s for k in ('通知', '通告', '请示', '报告', '批复', '函')):
                score += 5
            if 8 <= len(s) <= 80:
                score += 3
            if s.count('，') + s.count('。') >= 4:
                score -= 2
            return score

        def _score_unit(s: str) -> float:
            if not s:
                return -1
            score = 0.0
            if any(k in s for k in ('大学', '学院', '委员会', '办公室', '政府', '党委', '局', '厅', '部', '中心', '公司')):
                score += 6
            if len(s) <= 30:
                score += 2
            return score

        def _score_date(s: str) -> float:
            if not s:
                return -1
            m = re.search(r'(\d{4})', s)
            score = 0.0
            if m:
                y = int(m.group(1))
                if 2020 <= y <= 2100:
                    score += 6
                elif 2000 <= y < 2020:
                    score += 2
            if '年' in s and '月' in s:
                score += 2
            return score

        doc_no_cands, title_cands, unit_cands, date_cands = [], [], [], []
        summary_cands, keyword_cands, raw_texts = [], [], []

        for r in results:
            doc_info = dict(r.get('document_info') or {})
            # 优先使用逐行OCR结果重建文本，最大限度保留原始换行
            lines_obj = (r.get('original_result') or {}).get('lines') or []
            line_texts = [str(x.get('text', '')).strip() for x in lines_obj if isinstance(x, dict) and str(x.get('text', '')).strip()]
            raw = ('\n'.join(line_texts).strip() if line_texts else (r.get('raw_text') or '').strip())
            if raw:
                raw_texts.append(raw)

            # 先收集 document_info
            if doc_info.get('document_no'):
                doc_no_cands.append(str(doc_info.get('document_no')).strip())
            if doc_info.get('title'):
                title_cands.append(str(doc_info.get('title')).strip())
            if doc_info.get('issuing_unit'):
                unit_cands.append(str(doc_info.get('issuing_unit')).strip())
            if doc_info.get('received_date'):
                date_cands.append(str(doc_info.get('received_date')).strip())
            if doc_info.get('content_summary'):
                summary_cands.append(str(doc_info.get('content_summary')).strip())
            if doc_info.get('keywords'):
                keyword_cands.append(doc_info.get('keywords'))

            # 再收集 original_result.field_hints（通常来自OCR规则提取）
            hints = (r.get('original_result') or {}).get('field_hints') or {}
            if hints.get('document_no'):
                doc_no_cands.append(str(hints.get('document_no')).strip())
            if hints.get('title'):
                title_cands.append(str(hints.get('title')).strip())
            if hints.get('issuing_unit'):
                unit_cands.append(str(hints.get('issuing_unit')).strip())
            if hints.get('date'):
                date_cands.append(str(hints.get('date')).strip())

        merged_raw = '\n'.join([t for t in raw_texts if t]).strip()

        # 从原文再提取密级/紧急程度
        sec_val = ''
        urg_val = ''
        m_sec = re.search(r'密级\s*[：:]?\s*(绝密|机密|秘密|非密|普通)', merged_raw)
        if m_sec:
            sec_val = '普通' if m_sec.group(1) == '非密' else m_sec.group(1)
        elif '绝密' in merged_raw:
            sec_val = '绝密'
        elif '机密' in merged_raw:
            sec_val = '机密'
        elif '秘密' in merged_raw:
            sec_val = '秘密'
        elif '非密' in merged_raw:
            sec_val = '普通'

        m_urg = re.search(r'等级\s*[：:]?\s*(特急|加急|平急|急件|普通)', merged_raw)
        if m_urg:
            urg_val = m_urg.group(1)
        else:
            m_urg2 = re.search(r'紧急(?:程度)?\s*[：:]?\s*(特急|加急|平急|急件|普通)', merged_raw)
            if m_urg2:
                urg_val = m_urg2.group(1)
            elif '特急' in merged_raw:
                urg_val = '特急'
            elif '加急' in merged_raw:
                urg_val = '加急'
            elif '平急' in merged_raw:
                urg_val = '平急'
            elif '急件' in merged_raw:
                urg_val = '急件'

        final_doc_no = max(doc_no_cands, key=_score_doc_no) if doc_no_cands else ''
        final_doc_no = _clean_doc_no(final_doc_no)
        if not _doc_no_ok(final_doc_no):
            final_doc_no = _extract_doc_no_from_text(merged_raw)

        merged_info = {
            'document_no': final_doc_no,
            'title': max(title_cands, key=_score_title) if title_cands else '',
            'issuing_unit': max(unit_cands, key=_score_unit) if unit_cands else '',
            'received_date': max(date_cands, key=_score_date) if date_cands else '',
            # 按用户要求：优先保留OCR原始换行，不重排标点
            'content_summary': (merged_raw[:3000] if merged_raw else (summary_cands[0] if summary_cands else '')),
            'keywords': keyword_cands[0] if keyword_cands else '',
            'security_level': sec_val,
            'urgency_level': urg_val
        }

        return merged_info, merged_raw

    def on_choose_local_file(self):
        """选择本地图片/PDF文件（高拍仪替代方式之一）。"""
        try:
            file_path = self.capture_provider.select_local_file(self)
            if not file_path:
                return

            self.current_file_path = file_path
            file_name = os.path.basename(file_path)
            self.page_file.set_selected_path(file_path)
            self.status_label.setText(f"已选择文件: {file_name}")

            reply = QMessageBox.question(
                self,
                "立即识别",
                "是否立即进行OCR识别？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.on_ocr()
        except Exception as e:
            QMessageBox.warning(self, "提示", f"选择文件失败: {e}")
    
    def on_ocr_completed(self, document_info):
        """OCR识别完成后自动填充表单"""
        try:
            # 自动填充表单
            fields_filled = 0

            def _reasonable_doc_no(s: str) -> bool:
                s = (s or '').strip()
                if not s:
                    return False
                if len(s) < 4 or len(s) > 36:
                    return False
                if re.search(r'(请妥善保管|仅供相关人员阅|密级|等级|签发|抄送|拟稿|联系电话|长期)', s):
                    return False
                return bool(re.search(r'[〔【\[（(]\d{4}[〕】\]）)]', s) or ('号' in s))

            def _clean_unit(s: str) -> str:
                s = (s or '').strip()
                s = re.sub(r'^(发电单位|发文单位)[:：\s]*', '', s)
                s = s.replace('(印章)', '').replace('（印章）', '')
                s = re.sub(r'(密码发电|发出)$', '', s)
                return s.strip('：:，。;； ')

            def _extract_doc_no_fallback(src: str) -> str:
                """当document_no为空时，从原始识别文本强制提取文号。"""
                s = (src or '').strip()
                if not s:
                    return ''
                compact = re.sub(r'\s+', '', s)
                # 先做少量低风险归一化
                compact = compact.replace('硚号', '号').replace('研号', '号')
                compact = compact.replace('双X', 'XX').replace('X双', 'XX')

                patterns = [
                    r'([\u4e00-\u9fa5A-Za-zXx]{1,16}(?:发电|发|办)[〔【\[（(]?\d{4}[〕】\]）)]?\d{0,5}号)',
                    r'([\u4e00-\u9fa5A-Za-zXx]{1,20}[〔【\[（(]\d{4}[〕】\]）)]\d{0,5}号)',
                    r'文号[：:]*([^\n，。；;]{4,40}号)'
                ]
                for p in patterns:
                    m = re.search(p, compact)
                    if m:
                        cand = (m.group(1) or '').strip()
                        # 去掉常见前缀干扰
                        cand = re.sub(r'^(?:长期|特急|加急|平急|急件|非密|普通|密级|等级|签发)+', '', cand)
                        if _reasonable_doc_no(cand):
                            return cand
                return ''

            def _pretty_summary(s: str) -> str:
                txt = (s or '').strip()
                if not txt:
                    return ''
                # 按用户要求：保留原始换行，不改动逗号/分号等标点
                txt = txt.replace('\r\n', '\n').replace('\r', '\n')
                # 若上游异常压成单行，按公文结构关键词补回换行
                if '\n' not in txt:
                    txt = re.sub(r'(发电单位|发文单位|签发|等级|密级|关于)', r'\n\1', txt)
                    txt = re.sub(r'([一二三四五六七八九十]+、)', r'\n\1', txt)
                    txt = re.sub(r'(（[一二三四五六七八九十]+）)', r'\n\1', txt)
                    txt = txt.lstrip('\n')
                txt = re.sub(r'\n{3,}', '\n\n', txt)
                return txt

            def _normalize_security_level(val: str, raw: str) -> str:
                s = (val or '').strip()
                src = f"{s}\n{raw or ''}"
                if '绝密' in src:
                    return '绝密'
                if '机密' in src:
                    return '机密'
                if '秘密' in src:
                    return '秘密'
                if '非密' in src:
                    return '普通'
                if '普通' in s:
                    return '普通'
                return ''

            def _normalize_urgency_level(val: str, raw: str) -> str:
                s = (val or '').strip()
                src = f"{s}\n{raw or ''}"
                if '特急' in src:
                    return '特急'
                if '加急' in src:
                    return '加急'
                if '平急' in src:
                    return '平急'
                if '急件' in src:
                    return '急件'
                if '普通' in s:
                    return '普通'
                return ''

            # 兼容不同来源的字段命名
            doc_no_val = (
                document_info.get('document_no')
                or document_info.get('doc_no')
                or document_info.get('number')
                or ''
            )
            if not _reasonable_doc_no(doc_no_val):
                doc_no_val = ''

            # 兜底：若上游未给到文号，但识别文本里有，则直接回填
            # 注意：从主窗口流程进入时，可能没有 _raw_text，仅有 content_summary
            raw_for_doc = (
                document_info.get('_raw_text')
                or document_info.get('content_summary')
                or document_info.get('summary')
                or ''
            )
            if not doc_no_val:
                doc_no_val = _extract_doc_no_fallback(raw_for_doc)

            summary_val = (
                document_info.get('_raw_text')
                or document_info.get('content_summary')
                or document_info.get('summary')
                or ''
            )
            summary_val = _pretty_summary(summary_val)
            
            if doc_no_val:
                self.doc_no_input.setText(doc_no_val)
                fields_filled += 1
            
            if document_info.get('title'):
                self.title_input.setText(document_info.get('title'))
                fields_filled += 1
            
            unit_val = _clean_unit(document_info.get('issuing_unit') or '')
            if unit_val:
                self.unit_input.setText(unit_val)
                fields_filled += 1
            
            if summary_val:
                self.content_input.setPlainText(summary_val)
                fields_filled += 1
            
            keywords_val = document_info.get('keywords')
            if isinstance(keywords_val, (list, tuple)):
                keywords_val = ', '.join([str(x) for x in keywords_val if str(x).strip()])
            if keywords_val:
                self.keywords_input.setText(str(keywords_val))
                fields_filled += 1

            # 收文日期兼容填充（支持 YYYY-MM-DD / YYYY年M月D日）
            date_val = (document_info.get('received_date') or document_info.get('date') or '').strip()
            if date_val:
                qd = QDate.fromString(date_val, 'yyyy-MM-dd')
                if not qd.isValid():
                    qd = QDate.fromString(date_val, 'yyyy年M月d日')
                if qd.isValid():
                    self.date_input.setDate(qd)
            
            raw_for_level = (document_info.get('_raw_text') or summary_val or '')
            sec_level = _normalize_security_level(document_info.get('security_level', ''), raw_for_level)
            if sec_level:
                # 设置密级
                index = self.security_combo.findText(sec_level)
                if index >= 0:
                    self.security_combo.setCurrentIndex(index)
            
            urg_level = _normalize_urgency_level(
                document_info.get('urgency_level') or document_info.get('urgency') or '',
                raw_for_level
            )
            if urg_level:
                # 设置紧急程度
                index = self.urgency_combo.findText(urg_level)
                if index >= 0:
                    self.urgency_combo.setCurrentIndex(index)
            
            # 显示成功信息
            if fields_filled > 0:
                self.status_label.setText(f"OCR识别完成，已自动填充 {fields_filled} 个字段")
                QMessageBox.information(
                    self, 
                    "OCR识别完成", 
                    f"已从文件中识别并填充了 {fields_filled} 个字段。\n请核对信息后保存。"
                )
                # 自动切换到第二页以便人工核对
                if self.stack.currentIndex() == 0:
                    self.stack.setCurrentIndex(1)
                    self._update_nav()
            else:
                self.status_label.setText("OCR识别完成，但未找到可识别的公文信息")
        
        except Exception as e:
            QMessageBox.warning(self, "警告", f"填充OCR识别结果时出错:\n\n{str(e)}")
    
    def on_camera(self):
        """调用外部摄像头对话框拍照并返回文件路径。"""
        try:
            captured_path = self.capture_provider.capture_from_camera(self)
            if captured_path:
                self.current_file_path = captured_path
                file_name = os.path.basename(captured_path)
                # 同步到 FilePage
                try:
                    self.page_file.set_selected_path(captured_path)
                except Exception:
                    pass
                self.status_label.setText(f"已拍摄照片: {file_name} (支持OCR识别)")

                reply = QMessageBox.question(
                    self,
                    "立即识别",
                    "是否立即对拍摄的照片进行OCR识别？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.on_ocr()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"摄像头功能异常: {e}")

    def save_document(self):
        """保存收文记录"""
        # 验证必填字段
        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "警告", "标题不能为空")
            return
        
        # 准备数据
        document_data = {
            'document_no': self.doc_no_input.text().strip(),
            'title': title,
            'issuing_unit': self.unit_input.text().strip(),
            'received_date': self.date_input.date().toPython(),
            'security_level': self.security_combo.currentText(),
            'urgency_level': self.urgency_combo.currentText(),
            'document_type': self.type_combo.currentText(),
            'copies': int(self.copies_input.text() or 1),
            'content_summary': self.content_input.toPlainText().strip(),
            'keywords': self.keywords_input.text().strip(),
            'remarks': self.remarks_input.toPlainText().strip(),
            'storage_location': self.location_input.text().strip(),
            'receiver': self.processor_input.text().strip(),
        }
        
        # 如果有文件，保存文件路径
        if self.current_file_path and os.path.exists(self.current_file_path):
            # 保存副本到数据目录
            data_dir = "data/images"
            os.makedirs(data_dir, exist_ok=True)
            
            new_filename = f"{uuid.uuid4().hex}{os.path.splitext(self.current_file_path)[1]}"
            new_path = os.path.join(data_dir, new_filename)
            
            try:
                shutil.copy2(self.current_file_path, new_path)
                document_data['original_file_path'] = new_path
            except Exception as e:
                QMessageBox.warning(self, "警告", f"文件保存失败: {e}")
        
        # 保存到数据库
        self.status_label.setText("正在保存...")
        
        try:
            success, message, doc_id = self.db_manager.create_receive_document(
                document_data, 
                self.current_user['id']
            )
            
            if success:
                QMessageBox.information(
                    self, 
                    "成功", 
                    f"收文登记保存成功！\n文号: {document_data.get('document_no', '无')}"
                )
                self.status_label.setText(f"收文记录已保存，ID: {doc_id}")
                # 注意：不立即清空表单，允许用户在整个流程结束前查看
                # self.clear_form()
            else:
                QMessageBox.warning(self, "失败", message)
                self.status_label.setText(f"保存失败: {message}")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")
            self.status_label.setText(f"保存异常: {str(e)}")
    
    def clear_form(self):
        """彻底重置向导中的所有字段。

        这个方法只在完整流程结束时由主窗口调用；
        普通保存操作不应自动触发它，否则用户无法回顾已录入的数据。
        """
        self.doc_no_input.clear()
        self.title_input.clear()
        self.unit_input.clear()
        self.date_input.setDate(QDate.currentDate())
        self.processor_input.setText(self.current_user.get('real_name', ''))
        self.location_input.clear()
        self.content_input.clear()
        self.keywords_input.clear()
        self.remarks_input.clear()
        self.copies_input.setText("1")
        self.security_combo.setCurrentIndex(0)
        self.urgency_combo.setCurrentIndex(0)
        self.type_combo.setCurrentIndex(0)
        self.current_file_path = None
        # 文件页控件在 page_file 对象中
        if hasattr(self, 'page_file'):
            self.page_file.label.setText("未选择文件")
            self.page_file.ocr_button.setEnabled(True)
        self.status_label.setText("")