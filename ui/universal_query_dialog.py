# ui/universal_query_dialog.py
"""
通用公文查询对话框

用户只需输入文号，程序会在发文、收文表中查找对应记录，
并展示所有找到的信息以及相关流转记录。如果某类信息不存在
则显示“暂无”。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QMessageBox,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QMenu
)
from PySide6.QtCore import Qt, Signal
import re


class UniversalQueryDialog(QDialog):
    # 双击结果行时发出，供父窗口（如流转管理）回填ID
    record_selected = Signal(dict)

    def __init__(self, db_manager, current_user, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user
        self._rows_meta = []
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("通用公文查询")
        self.resize(1200, 680)

        layout = QVBoxLayout(self)

        # 输入区域
        input_layout = QHBoxLayout()
        self.doc_no_input = QLineEdit()
        self.doc_no_input.setPlaceholderText("请输入文号")
        search_btn = QPushButton("查询")
        search_btn.clicked.connect(self.on_search)
        input_layout.addWidget(QLabel("文号:"))
        input_layout.addWidget(self.doc_no_input)
        input_layout.addWidget(search_btn)
        layout.addLayout(input_layout)

        # 结果展示使用表格（全链路明细）
        self.result_table = QTableWidget(0, 17)
        self.result_table.setHorizontalHeaderLabels([
            "文号", "标题", "密级", "紧急程度", "发文单位", "发文时间", "去向/发往", "经办人",
            "收文时间", "发起流转时间", "流转类型", "取件单位", "取件人", "取件时间", "归还时间",
            "状态", "备注"
        ])
        self._apply_time_header_tooltips()
        self.result_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.result_table.setSelectionMode(QTableWidget.SingleSelection)
        # 双击用于“选择记录”，不允许用户直接编辑单元格
        self.result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.result_table.cellClicked.connect(self.on_cell_clicked)
        self.result_table.cellDoubleClicked.connect(self.on_row_double_clicked)
        self.result_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.result_table.customContextMenuRequested.connect(self.on_table_context_menu)
        self.result_table.horizontalHeader().setStretchLastSection(False)
        # 拉宽关键时间列与状态列，避免“2026-03-20 ...”被截断
        self.result_table.setColumnWidth(0, 260)   # 文号（必须完整显示）
        self.result_table.setColumnWidth(1, 280)   # 标题（可部分显示）
        self.result_table.setColumnWidth(5, 170)   # 发文时间
        self.result_table.setColumnWidth(8, 170)   # 收文时间
        self.result_table.setColumnWidth(9, 170)   # 发起流转时间
        self.result_table.setColumnWidth(13, 170)  # 取件时间
        self.result_table.setColumnWidth(14, 170)  # 归还时间
        self.result_table.setColumnWidth(15, 220)  # 状态
        layout.addWidget(self.result_table)

        # 点击表格单元格时显示完整内容，避免列宽不足导致的信息截断
        self.full_cell_text = QTextEdit()
        self.full_cell_text.setReadOnly(True)
        self.full_cell_text.setPlaceholderText("点击上方任意单元格后，这里显示该单元格完整内容")
        self.full_cell_text.setMaximumHeight(90)
        layout.addWidget(self.full_cell_text)

        # 按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.reject)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _apply_time_header_tooltips(self):
        """为时间列添加悬停提示。"""
        tips = {
            "发文时间": "该公文在发文模块登记/发送的时间（精确到秒）。",
            "收文时间": "该公文在收文模块登记接收的时间（精确到秒）。",
            "发起流转时间": "该公文发起流转记录的时间（精确到秒）。",
            "取件时间": "取件人实际取走公文的时间（精确到秒）。",
            "归还时间": "取件/借阅后归还公文的时间（精确到秒）。",
        }
        for i in range(self.result_table.columnCount()):
            item = self.result_table.horizontalHeaderItem(i)
            if not item:
                continue
            text = item.text()
            if text in tips:
                item.setToolTip(tips[text])

    def _normalize_doc_status(self, doc_type: str, doc: dict) -> str:
        """统一计算通用查询中的状态展示。"""
        if not isinstance(doc, dict):
            return ""

        if doc_type == 'receive':
            # 收文：优先使用业务状态字段
            return str(doc.get('status') or '已收文')

        if doc_type == 'send':
            # 发文：优先 send_status（如已发文/流转中/已归还）
            return str(doc.get('send_status') or doc.get('status') or '已发文')

        return str(doc.get('status') or '')

    def _normalize_title(self, title: str) -> str:
        """标题归一化，用于跨表关联匹配（忽略空白/常见标点差异）。"""
        t = (title or '').strip()
        if not t:
            return ''
        t = t.replace('“', '"').replace('”', '"').replace('’', "'").replace('‘', "'")
        t = re.sub(r'[\s\-—_·,，。；;:：()（）\[\]【】<>《》"\']+', '', t)
        return t

    def _find_related_send_docs(self, recv_docs: list) -> list:
        """当按文号未命中发文时，基于收文标题补充关联发文记录。"""
        related = []
        seen = set()
        for rd in (recv_docs or []):
            title = (rd.get('title') or '').strip()
            if not title:
                continue
            try:
                ok, _msg, res = self.db_manager.get_send_documents({'title': title}, page=1, page_size=50)
                docs = (res or {}).get('documents', []) if ok else []
            except Exception:
                docs = []

            nt = self._normalize_title(title)
            for d in docs:
                sid = d.get('id')
                if sid in seen:
                    continue
                dtitle = (d.get('title') or '').strip()
                nd = self._normalize_title(dtitle)
                # 允许完全一致或强包含匹配
                if nt and nd and (nt == nd or nt in nd or nd in nt):
                    seen.add(sid)
                    related.append(d)
        return related

    def _find_related_recv_docs(self, send_docs: list) -> list:
        """当按文号未命中收文时，基于发文标题补充关联收文记录。"""
        related = []
        seen = set()
        for sd in (send_docs or []):
            title = (sd.get('title') or '').strip()
            if not title:
                continue
            try:
                ok, _msg, res = self.db_manager.search_documents({'title': title}, page=1, page_size=50)
                docs = (res or {}).get('documents', []) if ok else []
            except Exception:
                docs = []

            nt = self._normalize_title(title)
            for d in docs:
                rid = d.get('id')
                if rid in seen:
                    continue
                dtitle = (d.get('title') or '').strip()
                nd = self._normalize_title(dtitle)
                if nt and nd and (nt == nd or nt in nd or nd in nt):
                    seen.add(rid)
                    related.append(d)
        return related

    def on_search(self):
        doc_no = self.doc_no_input.text().strip()
        if not doc_no:
            QMessageBox.warning(self, "警告", "请输入文号后再查询")
            return
        success, msg, rows = self.db_manager.get_universal_query_detail_records(doc_no)
        if not success:
            QMessageBox.warning(self, "查询失败", msg)
            return

        def fmt_dt(v):
            if not v:
                return ""
            if hasattr(v, 'strftime'):
                return v.strftime("%Y-%m-%d %H:%M:%S")
            s = str(v).replace('T', ' ').strip()
            return s[:19] if len(s) >= 19 else s

        def fmt_date(v):
            if not v:
                return ""
            if hasattr(v, 'strftime'):
                return v.strftime("%Y-%m-%d")
            s = str(v).replace('T', ' ').strip()
            return s[:10] if len(s) >= 10 else s

        self._rows_meta = []
        self.full_cell_text.clear()
        self.result_table.setRowCount(len(rows) if rows else 1)
        if not rows:
            self.result_table.setItem(0, 0, QTableWidgetItem("暂无结果"))
            for j in range(1, self.result_table.columnCount()):
                self.result_table.setItem(0, j, QTableWidgetItem(""))
            return

        for i, r in enumerate(rows):
            self.result_table.setItem(i, 0, QTableWidgetItem(str(r.get('文号', ''))))
            title_text = str(r.get('标题', ''))
            title_item = QTableWidgetItem(title_text)
            title_item.setToolTip(title_text)
            self.result_table.setItem(i, 1, title_item)
            self.result_table.setItem(i, 2, QTableWidgetItem(str(r.get('密级', ''))))
            self.result_table.setItem(i, 3, QTableWidgetItem(str(r.get('紧急程度', ''))))
            self.result_table.setItem(i, 4, QTableWidgetItem(str(r.get('发文单位', ''))))
            self.result_table.setItem(i, 5, QTableWidgetItem(fmt_date(r.get('发文时间', ''))))
            self.result_table.setItem(i, 6, QTableWidgetItem(str(r.get('去向/发往', ''))))
            self.result_table.setItem(i, 7, QTableWidgetItem(str(r.get('经办人', ''))))
            self.result_table.setItem(i, 8, QTableWidgetItem(fmt_date(r.get('收文时间', ''))))
            self.result_table.setItem(i, 9, QTableWidgetItem(fmt_dt(r.get('发起流转时间', ''))))
            self.result_table.setItem(i, 10, QTableWidgetItem(str(r.get('流转类型', ''))))
            self.result_table.setItem(i, 11, QTableWidgetItem(str(r.get('取件单位', ''))))
            self.result_table.setItem(i, 12, QTableWidgetItem(str(r.get('取件人', ''))))
            self.result_table.setItem(i, 13, QTableWidgetItem(fmt_dt(r.get('取件时间', ''))))
            self.result_table.setItem(i, 14, QTableWidgetItem(fmt_dt(r.get('归还时间', ''))))
            self.result_table.setItem(i, 15, QTableWidgetItem(str(r.get('状态', ''))))
            self.result_table.setItem(i, 16, QTableWidgetItem(str(r.get('备注', ''))))

            receive_id = r.get('__receive_id', '')
            send_id = r.get('__send_id', '')
            source_type = 'receive' if receive_id else ('send' if send_id else '')
            self._rows_meta.append({
                'type': source_type,
                'record_id': r.get('__record_id', ''),
                'receive_id': receive_id,
                'send_id': send_id,
                'document_no': r.get('文号', ''),
                'title': r.get('标题', ''),
                'status': r.get('状态', ''),
                'document_type': 'receive' if source_type == 'receive' else ('send' if source_type == 'send' else '')
            })

    def on_cell_clicked(self, row, column):
        """点击任意单元格时，在下方展示完整内容。"""
        item = self.result_table.item(row, column)
        header_item = self.result_table.horizontalHeaderItem(column)
        col_name = header_item.text() if header_item else f"第{column + 1}列"
        full_text = item.text() if item else ""
        if not full_text:
            full_text = "（空）"
        self.full_cell_text.setPlainText(f"{col_name}：{full_text}")

    def on_table_context_menu(self, pos):
        """右键菜单：查看完整标题。"""
        item = self.result_table.itemAt(pos)
        row = self.result_table.currentRow() if item is None else item.row()
        if row < 0:
            return

        menu = QMenu(self)
        view_title_action = menu.addAction("查看完整标题")
        action = menu.exec(self.result_table.viewport().mapToGlobal(pos))
        if action == view_title_action:
            title_item = self.result_table.item(row, 1)
            full_title = title_item.text() if title_item else ""
            QMessageBox.information(self, "完整标题", full_title or "（无标题）")

    def on_row_double_clicked(self, row, _column):
        """双击行：回传选中记录信息给调用方。"""
        try:
            if row < 0 or row >= len(self._rows_meta):
                return
            meta = self._rows_meta[row]
            if not isinstance(meta, dict):
                return
            if meta.get('type') not in ('receive', 'send'):
                QMessageBox.information(self, "提示", "请双击“收文”或“发文”行用于流转选择。")
                return
            self.record_selected.emit(meta)
        except Exception:
            pass
