# ui/pickup_manager_dialog.py
"""
取件登记与查询对话框
"""

from datetime import datetime
from PySide6.QtCore import QDate, QDateTime
from PySide6.QtWidgets import (
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
)


class PickupManagerDialog(QDialog):
    """取件登记与检索"""

    def __init__(self, db_manager, current_user, parent=None, initial_mode='pickup'):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user
        self.initial_mode = initial_mode
        self.query_row_record_ids = []
        self.setup_ui()
        self.load_records()

    def setup_ui(self):
        self.setWindowTitle("取件登记与查询")
        self.resize(980, 680)

        root = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.register_tab = self._build_register_tab()
        self.query_tab = self._build_query_tab()

        self.tabs.addTab(self.register_tab, "取件登记")
        self.tabs.addTab(self.query_tab, "取件记录查询（含归还）")
        root.addWidget(self.tabs)

        # 根据入口定位页面
        if self.initial_mode == 'return':
            self.tabs.setCurrentIndex(1)
            self.status_label.setText("请在检索页选择记录后点击“登记归还”")
        else:
            self.tabs.setCurrentIndex(0)

    def _build_register_tab(self):
        tab = QDialog()
        layout = QVBoxLayout(tab)

        form_group = QGroupBox("取件登记表单")
        form = QFormLayout(form_group)

        self.doc_no_input = QLineEdit()
        self.doc_no_input.setPlaceholderText("请输入文号")
        form.addRow("文号*:", self.doc_no_input)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("请输入标题")
        form.addRow("标题:", self.title_input)

        self.issuing_unit_input = QLineEdit()
        self.issuing_unit_input.setPlaceholderText("请输入发文单位")
        form.addRow("发文单位:", self.issuing_unit_input)

        self.received_date_input = QDateEdit()
        self.received_date_input.setDate(QDate.currentDate())
        self.received_date_input.setCalendarPopup(True)
        form.addRow("收文日期:", self.received_date_input)

        self.security_level_input = QLineEdit()
        self.security_level_input.setPlaceholderText("例如：普通/秘密/机密")
        form.addRow("密级:", self.security_level_input)

        self.destination_input = QLineEdit()
        self.destination_input.setPlaceholderText("例如：办公室A-302 / 外借至XX单位")
        form.addRow("去向*:", self.destination_input)

        self.picker_name_input = QLineEdit()
        self.picker_name_input.setPlaceholderText("请输入取件人姓名")
        form.addRow("取件人*:", self.picker_name_input)

        self.picker_contact_input = QLineEdit()
        self.picker_contact_input.setPlaceholderText("请输入取件人联系方式")
        form.addRow("联系方式:", self.picker_contact_input)

        self.pickup_time_input = QDateTimeEdit()
        self.pickup_time_input.setDateTime(QDateTime.currentDateTime())
        self.pickup_time_input.setCalendarPopup(True)
        self.pickup_time_input.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        form.addRow("取走时间:", self.pickup_time_input)

        self.remarks_input = QTextEdit()
        self.remarks_input.setMaximumHeight(90)
        self.remarks_input.setPlaceholderText("可填写补充说明")
        form.addRow("备注:", self.remarks_input)

        layout.addWidget(form_group)

        buttons = QHBoxLayout()
        self.save_btn = QPushButton("保存登记")
        self.save_btn.clicked.connect(self.on_save)
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self.on_clear)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.clear_btn)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        return tab

    def _build_query_tab(self):
        tab = QDialog()
        layout = QVBoxLayout(tab)

        filter_group = QGroupBox("取件记录查询条件")
        form = QFormLayout(filter_group)

        self.q_doc_no = QLineEdit()
        self.q_doc_no.setPlaceholderText("按文号检索")
        form.addRow("文号:", self.q_doc_no)

        self.q_issuing_unit = QLineEdit()
        self.q_issuing_unit.setPlaceholderText("按发文单位检索")
        form.addRow("发文单位:", self.q_issuing_unit)

        self.q_title = QLineEdit()
        self.q_title.setPlaceholderText("按标题检索")
        form.addRow("标题:", self.q_title)

        self.q_security = QLineEdit()
        self.q_security.setPlaceholderText("按密级检索")
        form.addRow("密级:", self.q_security)

        self.q_destination = QLineEdit()
        self.q_destination.setPlaceholderText("按去向检索")
        form.addRow("去向:", self.q_destination)

        self.q_picker_name = QLineEdit()
        self.q_picker_name.setPlaceholderText("按取件人检索")
        form.addRow("取件人:", self.q_picker_name)

        layout.addWidget(filter_group)

        hint = QLabel("说明：本页仅查询“取件登记与查询”模块内的取件记录，并可办理归还；不等同于通用公文查询。")
        hint.setStyleSheet("color:#666;")
        layout.addWidget(hint)

        query_buttons = QHBoxLayout()
        self.search_btn = QPushButton("查询取件记录")
        self.search_btn.clicked.connect(self.load_records)
        self.return_btn = QPushButton("登记归还")
        self.return_btn.clicked.connect(self.on_mark_returned)
        query_buttons.addWidget(self.search_btn)
        query_buttons.addWidget(self.return_btn)
        query_buttons.addStretch()
        layout.addLayout(query_buttons)

        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "文号", "标题", "发文单位", "收文日期", "密级",
            "去向", "取件人", "联系方式", "取走时间", "归还时间", "状态"
        ])
        for i in range(self.table.columnCount()):
            item = self.table.horizontalHeaderItem(i)
            if not item:
                continue
            if item.text() == "取走时间":
                item.setToolTip("取件人实际取走公文的时间（精确到秒）。")
            elif item.text() == "归还时间":
                item.setToolTip("取件/借阅后归还公文的时间（精确到秒）。")
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setShowGrid(True)
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #8C96A3;
                border: 1px solid #9AA4B2;
                alternate-background-color: #F7F9FC;
            }
            QHeaderView::section {
                background-color: #EEF2F7;
                border: 1px solid #9AA4B2;
                padding: 4px;
                font-weight: 600;
            }
        """)
        self.table.setAlternatingRowColors(True)
        self.table.setColumnWidth(0, 220)  # 文号
        self.table.setColumnWidth(1, 180)  # 标题
        self.table.setColumnWidth(2, 140)  # 发文单位
        self.table.setColumnWidth(3, 110)  # 收文日期
        self.table.setColumnWidth(4, 80)   # 密级
        self.table.setColumnWidth(5, 170)  # 去向
        self.table.setColumnWidth(6, 100)  # 取件人
        self.table.setColumnWidth(7, 120)  # 联系方式
        self.table.setColumnWidth(8, 170)  # 取走时间
        self.table.setColumnWidth(9, 170)  # 归还时间
        self.table.setColumnWidth(10, 120) # 状态
        layout.addWidget(self.table)

        return tab

    def on_save(self):
        doc_no = self.doc_no_input.text().strip()
        picker_name = self.picker_name_input.text().strip()

        # 若当前取件人与流转中指定取件人不一致，进行二次确认
        try:
            ok_d, _msg_d, designated = self.db_manager.get_latest_designated_picker_by_doc_no(doc_no)
        except Exception:
            ok_d, designated = False, None

        if ok_d and isinstance(designated, dict):
            designated_name = str(designated.get('picker_name') or '').strip()
            if designated_name and picker_name and not self._is_picker_match(picker_name, designated_name):
                tip = (
                    f"当前取件人：{picker_name}\n"
                    f"指定取件人：{designated_name}\n\n"
                    "您并非发起流转时指定的取件人，确定继续领取这篇公文吗？"
                )
                ans = QMessageBox.question(self, "取件人不一致提醒", tip)
                if ans != QMessageBox.Yes:
                    return

        data = {
            'document_no': doc_no,
            'title': self.title_input.text().strip(),
            'issuing_unit': self.issuing_unit_input.text().strip(),
            'received_date': self.received_date_input.date().toPython(),
            'security_level': self.security_level_input.text().strip(),
            'destination': self.destination_input.text().strip(),
            'picker_name': picker_name,
            'picker_contact': self.picker_contact_input.text().strip(),
            'pickup_time': self.pickup_time_input.dateTime().toPython(),
            'remarks': self.remarks_input.toPlainText().strip(),
        }

        ok, msg, _record_id = self.db_manager.create_pickup_record(data, self.current_user.get('id'))
        if ok:
            self.status_label.setText("保存成功")
            QMessageBox.information(self, "成功", msg)
            self.on_clear()
            self.load_records()
        else:
            self.status_label.setText(f"保存失败: {msg}")
            QMessageBox.warning(self, "失败", msg)

    def on_clear(self):
        self.doc_no_input.clear()
        self.title_input.clear()
        self.issuing_unit_input.clear()
        self.received_date_input.setDate(QDate.currentDate())
        self.security_level_input.clear()
        self.destination_input.clear()
        self.picker_name_input.clear()
        self.picker_contact_input.clear()
        self.pickup_time_input.setDateTime(QDateTime.currentDateTime())
        self.remarks_input.clear()

    def _format_datetime_display(self, value):
        if value is None:
            return ""
        text = str(value).replace('T', ' ').strip()
        if text.lower() in ('none', 'null'):
            return ""
        # 去微秒，仅保留到秒
        return text[:19] if len(text) >= 19 else text

    def _is_picker_match(self, current_picker: str, designated_picker: str) -> bool:
        """允许“张三/李四”这种多人指定场景，任一匹配即通过。"""
        cur = str(current_picker or '').strip()
        des = str(designated_picker or '').strip()
        if not cur or not des:
            return True
        candidates = [x.strip() for x in des.replace('，', '/').replace(',', '/').split('/') if x.strip()]
        if not candidates:
            return True
        return cur in candidates

    def load_records(self):
        filters = {
            'document_no': self.q_doc_no.text().strip(),
            'issuing_unit': self.q_issuing_unit.text().strip(),
            'title': self.q_title.text().strip(),
            'security_level': self.q_security.text().strip(),
            'destination': self.q_destination.text().strip(),
            'picker_name': self.q_picker_name.text().strip(),
        }
        filters = {k: v for k, v in filters.items() if v}

        ok, msg, result = self.db_manager.search_pickup_records(filters=filters, page=1, page_size=200)
        if not ok:
            QMessageBox.warning(self, "查询失败", msg)
            return

        records = result.get('records', [])
        self.query_row_record_ids = []
        self.table.setRowCount(len(records))

        for i, rec in enumerate(records):
            self.query_row_record_ids.append(rec.get('id'))
            self.table.setItem(i, 0, QTableWidgetItem(str(rec.get('document_no', ''))))
            self.table.setItem(i, 1, QTableWidgetItem(str(rec.get('title', ''))))
            self.table.setItem(i, 2, QTableWidgetItem(str(rec.get('issuing_unit', ''))))
            self.table.setItem(i, 3, QTableWidgetItem(str(rec.get('received_date', ''))))
            self.table.setItem(i, 4, QTableWidgetItem(str(rec.get('security_level', ''))))
            self.table.setItem(i, 5, QTableWidgetItem(str(rec.get('destination', ''))))
            self.table.setItem(i, 6, QTableWidgetItem(str(rec.get('picker_name', ''))))
            self.table.setItem(i, 7, QTableWidgetItem(str(rec.get('picker_contact', ''))))
            self.table.setItem(i, 8, QTableWidgetItem(self._format_datetime_display(rec.get('pickup_time', ''))))
            self.table.setItem(i, 9, QTableWidgetItem(self._format_datetime_display(rec.get('return_time', ''))))
            self.table.setItem(i, 10, QTableWidgetItem(str(rec.get('status', ''))))

    def on_mark_returned(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择一条记录")
            return

        if row >= len(self.query_row_record_ids):
            QMessageBox.warning(self, "提示", "无法获取记录ID")
            return

        record_id = self.query_row_record_ids[row]
        if not record_id:
            QMessageBox.warning(self, "提示", "无法获取记录ID")
            return
        ok, msg = self.db_manager.mark_pickup_returned(record_id=record_id, user_id=self.current_user.get('id'))
        if ok:
            QMessageBox.information(self, "成功", msg)
            self.load_records()
        else:
            QMessageBox.warning(self, "失败", msg)
