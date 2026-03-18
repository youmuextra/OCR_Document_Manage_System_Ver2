# ui/main_window.py
"""
主窗口
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QStatusBar, QMenuBar, QMenu, 
    QMessageBox, QApplication, QSplashScreen, QDialog, QProgressDialog
)
from PySide6.QtGui import QFont, QAction
from PySide6.QtCore import Qt
import re


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self, db_manager, auth, current_user, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.auth = auth
        self.current_user = current_user
        
        # 缓存各步骤的对话框实例，以便在流程中来回查看
        self.workflow_dialogs = {
            'send': None,
            'receive': None,
            'circulation': None
        }
        # 通用查询对话框缓存
        self.query_dialog = None
        self.setup_ui()

    def clear_workflow(self):
        """当一个完整流程结束时调用，重置所有步骤的状态并清空表单。

        此方法会尝试关闭并删除已有对话框，然后清除缓存，
        确保下一次打开时是全新的空白页面。
        """
        for key, dlg in list(self.workflow_dialogs.items()):
            if dlg:
                # 如果对话框存在，先调用其清空方法
                if hasattr(dlg, 'on_clear'):
                    dlg.on_clear()
                if hasattr(dlg, 'clear_form'):
                    dlg.clear_form()
                # 关闭并销毁对话框实例
                try:
                    dlg.close()
                    dlg.deleteLater()
                except Exception:
                    pass
                # 删除缓存引用，下次重新创建
                self.workflow_dialogs[key] = None
        # 取消按钮高亮
        self._update_flow_highlight(-1)

    def _show_modeless_dialog(self, dialog):
        """以非模态方式显示对话框，允许用户同时回看主界面其它模块。"""
        dialog.setModal(False)
        dialog.setWindowModality(Qt.NonModal)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _merge_ocr_form_info(self, latest_result: dict, results_list: list):
        """将多页OCR结果合并为一份可用于收文登记的字段字典。"""
        results = [r for r in (results_list or []) if isinstance(r, dict)]
        if not results and isinstance(latest_result, dict):
            results = [latest_result]

        def score_doc_no(s: str) -> float:
            if not s:
                return -1
            score = 0.0
            if '号' in s:
                score += 5
            if re.search(r'〔\d{4}〕|[（(\[]\d{4}[）)\]]', s):
                score += 6
            if re.search(r'(发|办|发电)', s):
                score += 2
            if len(s) > 45:
                score -= 3
            return score

        def score_title(s: str) -> float:
            if not s:
                return -1
            score = 0.0
            if '关于' in s:
                score += 6
            if any(k in s for k in ('通知', '通告', '请示', '报告', '批复', '函')):
                score += 5
            if 8 <= len(s) <= 80:
                score += 3
            return score

        def score_unit(s: str) -> float:
            if not s:
                return -1
            score = 0.0
            if any(k in s for k in ('大学', '学院', '委员会', '办公室', '政府', '党委', '局', '厅', '部', '中心', '公司')):
                score += 6
            if len(s) <= 30:
                score += 2
            return score

        doc_no_cands, title_cands, unit_cands = [], [], []
        summary_cands, raw_texts = [], []

        for r in results:
            di = dict(r.get('document_info') or {})
            raw = (r.get('raw_text') or '').strip()
            if raw:
                raw_texts.append(raw)
            if di.get('document_no'):
                doc_no_cands.append(str(di.get('document_no')).strip())
            if di.get('title'):
                title_cands.append(str(di.get('title')).strip())
            if di.get('issuing_unit'):
                unit_cands.append(str(di.get('issuing_unit')).strip())
            if di.get('content_summary'):
                summary_cands.append(str(di.get('content_summary')).strip())

            hints = (r.get('original_result') or {}).get('field_hints') or {}
            if hints.get('document_no'):
                doc_no_cands.append(str(hints.get('document_no')).strip())
            if hints.get('title'):
                title_cands.append(str(hints.get('title')).strip())
            if hints.get('issuing_unit'):
                unit_cands.append(str(hints.get('issuing_unit')).strip())

        merged_raw = '\n'.join([t for t in raw_texts if t]).strip()
        merged_info = {
            'document_no': max(doc_no_cands, key=score_doc_no) if doc_no_cands else '',
            'title': max(title_cands, key=score_title) if title_cands else '',
            'issuing_unit': max(unit_cands, key=score_unit) if unit_cands else '',
            'content_summary': summary_cands[0] if summary_cands else (merged_raw[:300] if merged_raw else '')
        }
        return merged_info, merged_raw
    
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("公文智能管理系统")
        self.resize(1024, 768)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = QVBoxLayout(central_widget)
        
        # 欢迎标签
        welcome_label = QLabel(f"欢迎使用公文智能管理系统，{self.current_user.get('real_name', '用户')}！")
        layout.addWidget(welcome_label)
        
        # 中央流程按钮
        self.create_flow_buttons(layout)
        welcome_label.setAlignment(Qt.AlignCenter)
        welcome_label.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        welcome_label.setStyleSheet("color: #2c3e50; margin: 50px 0;")
        
        layout.addWidget(welcome_label)
        
        
        # 状态栏
        self.statusBar().showMessage("就绪")
        
        # 创建菜单栏
        self.create_menu_bar()
    
    def create_admin_quick_buttons(self, layout):
        """创建管理员快捷按钮"""
        button_layout = QVBoxLayout()
        
        # 标题
        quick_title = QLabel("快捷操作")
        quick_title.setAlignment(Qt.AlignCenter)
        quick_title.setFont(QFont("Microsoft YaHei", 12))
        button_layout.addWidget(quick_title)
        
        # 按钮行1
        row1 = QHBoxLayout()
        
        send_btn = QPushButton("发文登记")
        send_btn.clicked.connect(self.on_send_document)
        send_btn.setMinimumHeight(50)
        send_btn.setStyleSheet("font-size: 14px;")
        row1.addWidget(send_btn)
        
        receive_btn = QPushButton("收文登记")
        receive_btn.clicked.connect(self.on_receive_document)
        receive_btn.setMinimumHeight(50)
        receive_btn.setStyleSheet("font-size: 14px;")
        row1.addWidget(receive_btn)
        
        button_layout.addLayout(row1)
        
        # 按钮行2
        row2 = QHBoxLayout()
        
        circulation_btn = QPushButton("公文流转")
        circulation_btn.clicked.connect(self.on_circulation)
        circulation_btn.setMinimumHeight(50)
        circulation_btn.setStyleSheet("font-size: 14px;")
        row2.addWidget(circulation_btn)
        
        search_btn = QPushButton("公文查询")
        search_btn.clicked.connect(self.on_search_document)
        search_btn.setMinimumHeight(50)
        search_btn.setStyleSheet("font-size: 14px;")
        row2.addWidget(search_btn)
        
        button_layout.addLayout(row2)
        
        layout.addLayout(button_layout)
    
    def create_user_quick_buttons(self, layout):
        """创建普通用户快捷按钮"""
        button_layout = QVBoxLayout()
        
        # 标题
        quick_title = QLabel("快捷操作")
        quick_title.setAlignment(Qt.AlignCenter)
        quick_title.setFont(QFont("Microsoft YaHei", 12))
        button_layout.addWidget(quick_title)
        
        # 按钮
        send_btn = QPushButton("发文登记")
        send_btn.clicked.connect(self.on_send_document)
        send_btn.setMinimumHeight(60)
        send_btn.setStyleSheet("font-size: 16px;")
        button_layout.addWidget(send_btn)
        
        layout.addLayout(button_layout)

    def create_flow_buttons(self, layout):
        """在中央位置创建发文/收文/流转管理按钮，箭头连接"""
        flow_layout = QHBoxLayout()
        flow_layout.setSpacing(20)
        # 发文
        self.send_btn = QPushButton("发文管理")
        self.send_btn.setMinimumSize(120, 60)
        self.send_btn.clicked.connect(self.on_send_document)
        self.send_btn.setStyleSheet("font-size:16px;")
        flow_layout.addWidget(self.send_btn)
        arrow1 = QLabel("→")
        arrow1.setFont(QFont("Microsoft YaHei", 24))
        arrow1.setAlignment(Qt.AlignCenter)
        flow_layout.addWidget(arrow1)
        # 收文
        self.receive_btn = QPushButton("收文管理")
        self.receive_btn.setMinimumSize(120, 60)
        self.receive_btn.clicked.connect(self.on_receive_document)
        self.receive_btn.setStyleSheet("font-size:16px;")
        if self.current_user.get('role') != 'admin':
            self.receive_btn.setEnabled(False)
            self.receive_btn.setToolTip("仅管理员可使用收文管理")
        flow_layout.addWidget(self.receive_btn)
        arrow2 = QLabel("→")
        arrow2.setFont(QFont("Microsoft YaHei", 24))
        arrow2.setAlignment(Qt.AlignCenter)
        flow_layout.addWidget(arrow2)
        # 流转
        self.circulation_btn = QPushButton("流转管理")
        self.circulation_btn.setMinimumSize(120, 60)
        self.circulation_btn.clicked.connect(self.on_circulation)
        self.circulation_btn.setStyleSheet("font-size:16px;")
        if self.current_user.get('role') != 'admin':
            self.circulation_btn.setEnabled(False)
            self.circulation_btn.setToolTip("仅管理员可使用流转管理")
        flow_layout.addWidget(self.circulation_btn)
        
        layout.addLayout(flow_layout)        # 在流程按钮下方添加一个显眼的通用查询按钮
        self.query_btn = QPushButton("公文查询")
        self.query_btn.setMinimumSize(120, 40)
        self.query_btn.setStyleSheet("font-size:14px; background-color:#f39c12; color:#fff;")
        self.query_btn.clicked.connect(self.on_universal_query)
        layout.addWidget(self.query_btn, alignment=Qt.AlignCenter)        # 初始化高亮
        self._update_flow_highlight(-1)

    def _update_flow_highlight(self, index):
        """高亮当前步骤按钮，index：0=发文,1=收文,2=流转"""
        default = "background-color:none; color:#000;"
        active = "background-color:#27ae60; color:#fff;"
        self.send_btn.setStyleSheet(active if index==0 else default)
        self.receive_btn.setStyleSheet(active if index==1 else default)
        self.circulation_btn.setStyleSheet(active if index==2 else default)
    
    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        current_role = self.current_user.get('role', 'user')
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 查询菜单（所有用户可见）
        query_menu = menubar.addMenu("查询统计")

        universal_query_action = QAction("通用公文查询", self)
        universal_query_action.triggered.connect(self.on_universal_query)
        query_menu.addAction(universal_query_action)

        statistics_action = QAction("统计报表", self)
        statistics_action.triggered.connect(self.on_statistics)
        query_menu.addAction(statistics_action)
        
        # 系统菜单
        sys_menu = menubar.addMenu("系统")
        
        if current_role == 'admin':
            user_action = QAction("用户管理", self)
            user_action.triggered.connect(self.on_user_management)
            sys_menu.addAction(user_action)
            
            config_action = QAction("系统设置", self)
            config_action.triggered.connect(self.on_system_config)
            sys_menu.addAction(config_action)
        
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.on_about)
        sys_menu.addAction(about_action)
    
    def on_send_document(self):
        """发文登记"""
        self._update_flow_highlight(0)
        try:
            if self.workflow_dialogs['send'] is None:
                from .send_document_dialog import SendDocumentDialog
                self.workflow_dialogs['send'] = SendDocumentDialog(
                    self.db_manager, self.current_user, self
                )
            dialog = self.workflow_dialogs['send']
            self._show_modeless_dialog(dialog)
        except ImportError as e:
            QMessageBox.warning(self, "功能未实现", f"发文功能模块未找到: {e}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开发文登记失败: {e}")
    
    def on_search_send(self):
        """发文查询"""
        try:
            from .search_send_dialog import SearchSendDialog
            dialog = SearchSendDialog(self.db_manager, self.current_user, self)
            dialog.exec()
        except ImportError as e:
            QMessageBox.warning(self, "功能未实现", f"发文查询功能未找到: {e}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开发文查询失败: {e}")
    
    def on_circulation(self):
        """公文流转"""
        if self.current_user.get('role') != 'admin':
            QMessageBox.warning(self, "权限不足", "流转管理仅管理员可操作")
            return
        self._update_flow_highlight(2)
        try:
            if self.workflow_dialogs['circulation'] is None:
                from .circulation_dialog import CirculationDialog
                dlg = CirculationDialog(self.db_manager, self.current_user, self)
                # 保留前序步骤数据，避免用户回看时被自动清空
                self.workflow_dialogs['circulation'] = dlg
            dialog = self.workflow_dialogs['circulation']
            self._show_modeless_dialog(dialog)
        except ImportError as e:
            QMessageBox.warning(self, "功能未实现", f"流转功能模块未找到: {e}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开流转管理失败: {e}")
    
    def on_circulation_query(self):
        """流转记录查询"""
        try:
            from .circulation_query_dialog import CirculationQueryDialog
            dialog = CirculationQueryDialog(self.db_manager, self.current_user, self)
            dialog.exec()
        except ImportError as e:
            QMessageBox.warning(self, "功能未实现", f"流转查询功能未找到: {e}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开流转查询失败: {e}")

    def on_universal_query(self):
        """打开通用公文查询对话框"""
        try:
            if self.query_dialog is None:
                from .universal_query_dialog import UniversalQueryDialog
                self.query_dialog = UniversalQueryDialog(self.db_manager, self.current_user, self)
            self.query_dialog.exec()
        except ImportError as e:
            QMessageBox.warning(self, "功能未实现", f"通用查询模块未找到: {e}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开通用查询失败: {e}")
    
    def on_statistics(self):
        """统计报表"""
        try:
            from .statistics_dialog import StatisticsDialog
            dialog = StatisticsDialog(self.db_manager, self.current_user, self)
            dialog.exec()
        except ImportError as e:
            QMessageBox.warning(self, "功能未实现", f"统计功能模块未找到: {e}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开统计报表失败: {e}")
    
    def on_about(self):
        """关于"""
        QMessageBox.about(
            self,
            "关于公文智能管理系统",
            "公文智能管理系统 v2.0\n\n"
            "功能模块：\n"
            "• 发文管理\n"
            "• 收文管理\n"
            "• 公文流转\n"
            "• 统计报表\n\n"
            f"当前用户: {self.current_user.get('real_name', '')}\n"
            f"用户角色: {self.current_user.get('role', 'user')}\n"
        )
    
    def on_ocr_processing(self):
        """OCR公文识别"""
        try:
            from .ocr_processing_dialog import OCRProcessingDialog
            dialog = OCRProcessingDialog(self.db_manager, self.current_user, self)
            dialog.exec()
        except ImportError as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "错误", f"OCR处理功能未找到: {e}")
    
    def on_receive_document(self):
        """收文登记"""
        if self.current_user.get('role') != 'admin':
            QMessageBox.warning(self, "权限不足", "收文管理仅管理员可操作")
            return
        self._update_flow_highlight(1)
        try:
            # 直接先打开 OCR 识别对话框以提升效率，识别成功后再打开收文登记对话框并填充结果
            from .ocr_processing_dialog import OCRProcessingDialog
            ocr_dialog = OCRProcessingDialog(self.db_manager, self.current_user, self)
            if ocr_dialog.exec() == QDialog.Accepted:
                ocr_result = ocr_dialog.get_ocr_result()
                # 创建收文登记对话并填充结果
                from .receive_document_dialog import ReceiveDocumentDialog
                if self.workflow_dialogs['receive'] is None:
                    self.workflow_dialogs['receive'] = ReceiveDocumentDialog(self.db_manager, self.current_user, self)
                dialog = self.workflow_dialogs['receive']

                progress = QProgressDialog("正在准备提取信息...", None, 0, 100, self)
                progress.setWindowTitle("智能提取进度")
                progress.setWindowModality(Qt.ApplicationModal)
                progress.setCancelButton(None)
                progress.setMinimumDuration(0)
                progress.setValue(5)
                QApplication.processEvents()

                if ocr_result and isinstance(ocr_result, dict):
                    doc_info, merged_raw_text = self._merge_ocr_form_info(
                        latest_result=ocr_result,
                        results_list=getattr(ocr_dialog, 'ocr_results_list', []) or []
                    )
                    # 不在主线程同步调用LLM，避免窗口“未响应”；优先使用OCR结果+规则合并

                    # 兼容字段名映射，确保收文表单可识别
                    if doc_info.get('urgency') and not doc_info.get('urgency_level'):
                        doc_info['urgency_level'] = doc_info.get('urgency')
                    if doc_info.get('summary') and not doc_info.get('content_summary'):
                        doc_info['content_summary'] = doc_info.get('summary')
                    progress.setLabelText("正在整理提取结果并自动填充表单...")
                    progress.setValue(80)
                    QApplication.processEvents()
                    # 调用 on_ocr_completed 填充表单
                    try:
                        dialog.set_ocr_context(
                            latest_result=ocr_result,
                            results_list=getattr(ocr_dialog, 'ocr_results_list', []) or [],
                            selected_paths=getattr(ocr_dialog, 'selected_image_paths', []) or []
                        )
                        dialog.on_ocr_completed(doc_info)
                        # 同步文件路径（取第一个已选文件）
                        try:
                            sel = getattr(ocr_dialog, 'selected_image_paths', None)
                            if sel:
                                dialog.current_file_path = sel[0]
                                dialog.page_file.set_selected_path(sel[0])
                        except Exception:
                            pass
                    except Exception:
                        pass
                progress.setLabelText("提取完成")
                progress.setValue(100)
                QApplication.processEvents()
                progress.close()
                self._show_modeless_dialog(dialog)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开收文登记失败: {e}")
    
    def on_search_document(self):
        """公文查询"""
        from .search_document_dialog import SearchDocumentDialog
        dialog = SearchDocumentDialog(self.db_manager, self.current_user, self)
        dialog.exec()
    
    def on_user_management(self):
        """用户管理"""
        from .user_management_dialog import UserManagementDialog
        dialog = UserManagementDialog(self.db_manager, self.current_user, self)
        dialog.exec()
    
    def on_system_config(self):
        """系统设置"""
        from .system_config_dialog import SystemConfigDialog
        dialog = SystemConfigDialog(self.db_manager, self.current_user, self)
        dialog.exec()