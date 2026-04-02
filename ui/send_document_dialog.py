# ui/send_document_dialog.py
"""
发文管理对话框
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QMessageBox, QDateEdit,
    QFormLayout, QGroupBox, QTextEdit, QComboBox, QInputDialog, QMenu
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, QDate, QEvent
from datetime import datetime

class SendDocumentDialog(QDialog):
    """发文管理对话框"""
    DEFAULT_DOC_TYPES = ["鄂厅发", "鄂厅发电", "鄂厅函", "内部公文"]
    
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
        
        # 文号（自动生成）
        self.doc_no_preview = QLineEdit()
        self.doc_no_preview.setReadOnly(True)
        self.doc_no_preview.setPlaceholderText("系统将自动生成文号")
        form_layout.addRow("文号(自动):", self.doc_no_preview)
        
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

        # 密级（必填）
        self.security_combo = QComboBox()
        self.security_combo.addItems(["请选择密级", "普通", "秘密", "机密", "绝密"])
        form_layout.addRow("密级*:", self.security_combo)

        # 文种（用于生成文号，管理员可双击设置）
        self.document_type_combo = QComboBox()
        self._reload_doc_type_options()
        self.document_type_combo.installEventFilter(self)
        self.document_type_combo.setContextMenuPolicy(Qt.CustomContextMenu)
        self.document_type_combo.customContextMenuRequested.connect(self._show_doc_type_context_menu)
        self.document_type_combo.setToolTip("管理员：双击可批量编辑；右键可添加/删除文种")
        form_layout.addRow("文种*:", self.document_type_combo)

        self.doc_type_help_label = QLabel("提示：管理员可双击文种下拉框批量编辑，右键进行添加/删除。")
        self.doc_type_help_label.setStyleSheet("color:#666; font-size:12px;")
        form_layout.addRow("", self.doc_type_help_label)

        # 年份（用于生成文号，管理员可双击设置）
        self.doc_year_label = QLabel(str(self.db_manager.get_document_number_year()))
        self.doc_year_label.setStyleSheet("color:#333;")
        self.doc_year_label.installEventFilter(self)
        self.doc_year_label.setToolTip("管理员双击可修改文号年份")
        form_layout.addRow("文号年份:", self.doc_year_label)
        
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

        # 字段变化时预览文号
        self.title_input.textChanged.connect(self._refresh_doc_no_preview)
        self.security_combo.currentIndexChanged.connect(self._refresh_doc_no_preview)
        self.document_type_combo.currentIndexChanged.connect(self._refresh_doc_no_preview)
        self._refresh_doc_no_preview()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.MouseButtonDblClick and self.current_user.get('role') == 'admin':
            if watched is self.document_type_combo:
                self._edit_doc_types()
                return True
            if watched is self.doc_year_label:
                self._edit_doc_year()
                return True
        return super().eventFilter(watched, event)

    def _reload_doc_type_options(self):
        options = self.db_manager.get_document_type_options()
        self.document_type_combo.clear()
        self.document_type_combo.addItems(options)

    def _show_doc_type_context_menu(self, pos):
        if self.current_user.get('role') != 'admin':
            return

        menu = QMenu(self)
        add_action = menu.addAction("添加文种")
        remove_action = menu.addAction("删除当前文种")
        menu.addSeparator()
        reset_action = menu.addAction("重置为默认文种")

        action = menu.exec(self.document_type_combo.mapToGlobal(pos))
        if action == add_action:
            self._add_doc_type()
        elif action == remove_action:
            self._remove_current_doc_type()
        elif action == reset_action:
            self._reset_doc_types()

    def _add_doc_type(self):
        text, ok = QInputDialog.getText(self, "添加文种", "请输入新的文种名称:")
        if not ok:
            return
        new_type = (text or '').strip()
        if not new_type:
            QMessageBox.warning(self, "提示", "文种不能为空")
            return

        options = self.db_manager.get_document_type_options()
        if new_type in options:
            QMessageBox.information(self, "提示", "该文种已存在")
            return

        options.append(new_type)
        ok2, msg = self.db_manager.set_document_type_options(options)
        if ok2:
            self._reload_doc_type_options()
            self.document_type_combo.setCurrentText(new_type)
            self._refresh_doc_no_preview()
        else:
            QMessageBox.warning(self, "失败", msg)

    def _remove_current_doc_type(self):
        current = self.document_type_combo.currentText().strip()
        if not current:
            QMessageBox.warning(self, "提示", "当前没有可删除的文种")
            return

        options = self.db_manager.get_document_type_options()
        if current not in options:
            return
        if len(options) <= 1:
            QMessageBox.warning(self, "提示", "至少保留一个文种")
            return

        ok = QMessageBox.question(self, "确认", f"确认删除文种“{current}”吗？")
        if ok != QMessageBox.Yes:
            return

        options = [x for x in options if x != current]
        ok2, msg = self.db_manager.set_document_type_options(options)
        if ok2:
            self._reload_doc_type_options()
            self._refresh_doc_no_preview()
        else:
            QMessageBox.warning(self, "失败", msg)

    def _reset_doc_types(self):
        ok = QMessageBox.question(self, "确认", "确认将文种重置为系统默认项吗？")
        if ok != QMessageBox.Yes:
            return

        ok2, msg = self.db_manager.set_document_type_options(self.DEFAULT_DOC_TYPES)
        if ok2:
            self._reload_doc_type_options()
            self._refresh_doc_no_preview()
            QMessageBox.information(self, "成功", "文种已重置为默认项")
        else:
            QMessageBox.warning(self, "失败", msg)

    def _edit_doc_types(self):
        current = '，'.join(self.db_manager.get_document_type_options())
        text, ok = QInputDialog.getText(self, "设置文种", "请输入文种（中文逗号分隔）:", text=current)
        if not ok:
            return

        text = str(text or '').strip()
        if ',' in text:
            QMessageBox.warning(self, "提示", "请使用中文逗号（，）分隔文种，不要使用英文逗号（,）。")
            return

        options = [x.strip() for x in text.split('，') if x.strip()]
        if not options:
            QMessageBox.warning(self, "提示", "文种不能为空")
            return

        ok2, msg = self.db_manager.set_document_type_options(options)
        if ok2:
            self._reload_doc_type_options()
            self._refresh_doc_no_preview()
        else:
            QMessageBox.warning(self, "失败", msg)

    def _edit_doc_year(self):
        cur = self.db_manager.get_document_number_year()
        # 兼容 PySide6：使用位置参数（value, min, max, step），避免关键字参数不被支持
        year, ok = QInputDialog.getInt(self, "设置年份", "请输入文号年份:", cur, 2000, 2100, 1)
        if not ok:
            return
        ok2, msg = self.db_manager.set_document_number_year(year)
        if ok2:
            self.doc_year_label.setText(str(year))
            self._refresh_doc_no_preview()
        else:
            QMessageBox.warning(self, "失败", msg)

    def _refresh_doc_no_preview(self):
        title = self.title_input.text().strip()
        security = self.security_combo.currentText().strip()
        doc_type = self.document_type_combo.currentText().strip()
        if not title or security in ("", "请选择密级") or not doc_type:
            self.doc_no_preview.setText("")
            return
        year = self.db_manager.get_document_number_year()
        ok, msg, doc_no = self.db_manager.generate_document_no(doc_type, year)
        if ok:
            self.doc_no_preview.setText(doc_no)
        else:
            self.doc_no_preview.setText("")
    
    def on_save(self):
        """保存发文记录"""
        # 获取表单数据
        doc_no = self.doc_no_preview.text().strip()
        title = self.title_input.text().strip()
        send_to_unit = self.send_to_unit_input.text().strip()
        processor = self.processor_input.text().strip()
        security_level = self.security_combo.currentText().strip()
        document_type = self.document_type_combo.currentText().strip()
    
        # 验证必填字段
        if not title:
            QMessageBox.warning(self, "警告", "标题不能为空")
            return
    
        if not send_to_unit:
            QMessageBox.warning(self, "警告", "发往单位不能为空")
            return
    
        if not processor:
            QMessageBox.warning(self, "警告", "经办人不能为空")
            return

        if not security_level or security_level == "请选择密级":
            QMessageBox.warning(self, "警告", "密级不能为空")
            return

        if not document_type:
            QMessageBox.warning(self, "警告", "文种不能为空")
            return

        year = self.db_manager.get_document_number_year()
        if not doc_no:
            ok, msg, generated_no = self.db_manager.generate_document_no(document_type, year)
            if not ok:
                QMessageBox.warning(self, "警告", msg)
                return
            doc_no = generated_no
            self.doc_no_preview.setText(doc_no)
    
        # 准备数据
        send_data = {
            'document_no': doc_no,
            'title': title,
            'issuing_unit': self.issuing_unit_input.text().strip(),
            'send_to_unit': send_to_unit,
            'security_level': security_level,
            'document_type': document_type,
            'processor': processor,
            'doc_year': year,
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
                QMessageBox.information(self, "成功", f"发文记录保存成功！\n文号: {doc_no}")
                # 不清空表单，以便用户在流程结束前查看内容
                # self.on_clear()
                self.status_label.setText(f"发文记录已保存，文号: {doc_no}")
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
        self.doc_no_preview.clear()
        self.title_input.clear()
        self.issuing_unit_input.clear()
        self.send_to_unit_input.clear()
        self.security_combo.setCurrentIndex(0)
        self.document_type_combo.setCurrentIndex(0 if self.document_type_combo.count() > 0 else -1)
        self.processor_input.clear()
        self.send_date_input.setDate(QDate.currentDate())
        self.remarks_input.clear()
        self.status_label.setText("")
        self.title_input.setFocus()
    
    def on_search_send(self):
        """查询发文记录（可选功能）"""
        try:
            from .search_send_dialog import SearchSendDialog
            dialog = SearchSendDialog(self.db_manager, self.current_user, self)
            dialog.exec()
        except ImportError as e:
            QMessageBox.warning(self, "功能未实现", f"查询功能未找到: {e}")
