# ui/edit_document_dialog.py
"""独立的公文编辑对话框，原来内嵌在DocumentDetailDialog中的SimpleEditDialog移动到此处。"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit, QComboBox,
    QDateEdit, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt


class DocumentEditDialog(QDialog):
    def __init__(self, document_data: dict, db_manager, parent=None):
        super().__init__(parent)
        self.document_data = document_data
        self.db_manager = db_manager
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("编辑公文")
        self.resize(500, 600)

        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # 文号
        self.doc_no_edit = QLineEdit(self.document_data.get('document_no', ''))
        form_layout.addRow("文号:", self.doc_no_edit)

        # 标题
        self.title_edit = QLineEdit(self.document_data.get('title', ''))
        form_layout.addRow("标题:", self.title_edit)

        # 发文单位
        self.issuing_unit_edit = QLineEdit(self.document_data.get('issuing_unit', ''))
        form_layout.addRow("发文单位:", self.issuing_unit_edit)

        # 收文人
        self.receiver_edit = QLineEdit(self.document_data.get('receiver', ''))
        form_layout.addRow("收文人:", self.receiver_edit)

        # 存放位置
        self.storage_location_edit = QLineEdit(self.document_data.get('storage_location', ''))
        form_layout.addRow("存放位置:", self.storage_location_edit)

        # 密级
        self.security_combo = QComboBox()
        self.security_combo.addItems(["普通", "秘密", "机密", "绝密"])
        current_security = self.document_data.get('security_level', '普通')
        idx = self.security_combo.findText(current_security)
        if idx >= 0:
            self.security_combo.setCurrentIndex(idx)
        form_layout.addRow("密级:", self.security_combo)

        # 紧急程度
        self.urgency_combo = QComboBox()
        self.urgency_combo.addItems(["普通", "加急", "特急"])
        current_urgency = self.document_data.get('urgency_level', '普通')
        idx = self.urgency_combo.findText(current_urgency)
        if idx >= 0:
            self.urgency_combo.setCurrentIndex(idx)
        form_layout.addRow("紧急程度:", self.urgency_combo)

        # 文种
        self.doc_type_edit = QLineEdit(self.document_data.get('document_type', ''))
        form_layout.addRow("文种:", self.doc_type_edit)

        # 份数
        self.copies_edit = QLineEdit(str(self.document_data.get('copies', '')))
        form_layout.addRow("份数:", self.copies_edit)

        # 收文日期
        self.received_date_edit = QDateEdit()
        received_date = self.document_data.get('received_date')
        if received_date:
            try:
                from PySide6.QtCore import QDate
                if isinstance(received_date, str):
                    parts = received_date[:10].split('-')
                    if len(parts) == 3:
                        y, m, d = map(int, parts)
                        self.received_date_edit.setDate(QDate(y, m, d))
                    else:
                        self.received_date_edit.setDate(QDate.currentDate())
                else:
                    self.received_date_edit.setDate(QDate.currentDate())
            except Exception:
                self.received_date_edit.setDate(QDate.currentDate())
        else:
            self.received_date_edit.setDate(QDate.currentDate())
        form_layout.addRow("收文日期:", self.received_date_edit)

        # 内容摘要
        self.summary_edit = QTextEdit()
        self.summary_edit.setMaximumHeight(100)
        self.summary_edit.setText(self.document_data.get('content_summary', ''))
        form_layout.addRow("内容摘要:", self.summary_edit)

        # 关键词
        self.keywords_edit = QLineEdit(self.document_data.get('keywords', ''))
        form_layout.addRow("关键词:", self.keywords_edit)

        # 备注
        self.remarks_edit = QTextEdit()
        self.remarks_edit.setMaximumHeight(100)
        self.remarks_edit.setText(self.document_data.get('remarks', ''))
        form_layout.addRow("备注:", self.remarks_edit)

        layout.addLayout(form_layout)

        # 按钮
        button_layout = QHBoxLayout()
        save_button = QPushButton("保存")
        save_button.clicked.connect(self.save_changes)
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def save_changes(self):
        """收集用户输入并尝试写回数据库"""
        try:
            updated_data = {
                'document_no': self.doc_no_edit.text(),
                'title': self.title_edit.text(),
                'issuing_unit': self.issuing_unit_edit.text(),
                'receiver': self.receiver_edit.text(),
                'storage_location': self.storage_location_edit.text(),
                'security_level': self.security_combo.currentText(),
                'urgency_level': self.urgency_combo.currentText(),
                'document_type': self.doc_type_edit.text(),
                'content_summary': self.summary_edit.toPlainText(),
                'keywords': self.keywords_edit.text(),
                'remarks': self.remarks_edit.toPlainText()
            }
            try:
                copies = int(self.copies_edit.text())
                updated_data['copies'] = copies
            except ValueError:
                QMessageBox.warning(self, "警告", "份数必须是数字")
                return

            from PySide6.QtCore import QDate
            date = self.received_date_edit.date()
            updated_data['received_date'] = date.toString("yyyy-MM-dd")

            if hasattr(self.db_manager, 'update_document'):
                success, message = self.db_manager.update_document(
                    self.document_data.get('id'), updated_data
                )
            else:
                success, message = self.update_document_directly(updated_data)

            if success:
                QMessageBox.information(self, "成功", "公文已更新")
                self.accept()
            else:
                QMessageBox.warning(self, "失败", f"更新失败: {message}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存失败: {str(e)}")

    def update_document_directly(self, updated_data):
        """当 db_manager 缺失更新方法时回退到原始 SQL 语句"""
        try:
            from sqlalchemy import text
            set_clauses = []
            params = {}
            for key, value in updated_data.items():
                if value is not None:
                    set_clauses.append(f"{key} = :{key}")
                    params[key] = value
            if not set_clauses:
                return False, "没有要更新的字段"
            set_clause = ", ".join(set_clauses)
            params['document_id'] = self.document_data.get('id')
            query = text(f"""
                            UPDATE receive_documents 
                            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                            WHERE id = :document_id
                        """)
            with self.db_manager.session_scope() as session:
                result = session.execute(query, params)
                session.commit()
                if result.rowcount > 0:
                    return True, "更新成功"
                else:
                    return False, "没有找到要更新的文档"
        except Exception as e:
            return False, f"更新失败: {str(e)}"
