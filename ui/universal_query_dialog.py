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
    QTableWidget, QTableWidgetItem, QAbstractItemView
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
        self.resize(600, 400)

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

        # 结果展示使用表格
        self.result_table = QTableWidget(0, 7)
        self.result_table.setHorizontalHeaderLabels([
            "类型", "记录ID", "收文ID", "发文ID", "文号", "标题/流转类型", "状态"
        ])
        self.result_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.result_table.setSelectionMode(QTableWidget.SingleSelection)
        # 双击用于“选择记录”，不允许用户直接编辑单元格
        self.result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.result_table.cellDoubleClicked.connect(self.on_row_double_clicked)
        self.result_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.result_table)

        # 按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.reject)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

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

        # 查询收文和发文
        recv_docs = []
        send_docs = []
        try:
            success, msg, result = self.db_manager.search_documents({'document_no': doc_no}, page=1, page_size=20)
            if success and result and 'documents' in result:
                recv_docs = result['documents']
        except Exception:
            recv_docs = []

        try:
            success, msg, result = self.db_manager.get_send_documents({'document_no': doc_no}, page=1, page_size=20)
            if success and result and 'documents' in result:
                send_docs = result['documents']
        except Exception:
            send_docs = []

        # 跨表补全：若一侧为空，按标题补充关联记录（解决发文误填文号、收文修正后查询断链问题）
        related_send_docs = []
        related_recv_docs = []
        if recv_docs and not send_docs:
            related_send_docs = self._find_related_send_docs(recv_docs)
        if send_docs and not recv_docs:
            related_recv_docs = self._find_related_recv_docs(send_docs)

        # 查询流转记录
        circ_docs = []
        for d in recv_docs:
            rid = d.get('id')
            if rid:
                s, m, r = self.db_manager.get_circulation_records({'document_id': rid, 'document_type': 'receive'})
                if s and r and 'records' in r:
                    circ_docs.extend(r['records'])
        for d in send_docs:
            sid = d.get('id')
            if sid:
                s, m, r = self.db_manager.get_circulation_records({'document_id': sid, 'document_type': 'send'})
                if s and r and 'records' in r:
                    circ_docs.extend(r['records'])

        # 填充表格
        rows = []
        rows_meta = []
        if recv_docs:
            for d in recv_docs:
                rid = d.get('id')
                status_text = self._normalize_doc_status('receive', d)
                rows.append(("收文", rid, rid, "", d.get('document_no', ''), d.get('title', ''), status_text))
                rows_meta.append({
                    'type': 'receive',
                    'record_id': rid,
                    'receive_id': rid,
                    'send_id': '',
                    'document_no': d.get('document_no', ''),
                    'title': d.get('title', ''),
                    'status': status_text
                })
        if related_recv_docs:
            for d in related_recv_docs:
                rid = d.get('id')
                status_text = self._normalize_doc_status('receive', d)
                rows.append(("收文(关联)", rid, rid, "", d.get('document_no', ''), d.get('title', ''), status_text))
                rows_meta.append({
                    'type': 'receive',
                    'record_id': rid,
                    'receive_id': rid,
                    'send_id': '',
                    'document_no': d.get('document_no', ''),
                    'title': d.get('title', ''),
                    'status': status_text,
                    'related': True
                })
        if send_docs:
            for d in send_docs:
                sid = d.get('id')
                status_text = self._normalize_doc_status('send', d)
                rows.append(("发文", sid, "", sid, d.get('document_no', ''), d.get('title', ''), status_text))
                rows_meta.append({
                    'type': 'send',
                    'record_id': sid,
                    'receive_id': '',
                    'send_id': sid,
                    'document_no': d.get('document_no', ''),
                    'title': d.get('title', ''),
                    'status': status_text
                })
        if related_send_docs:
            for d in related_send_docs:
                sid = d.get('id')
                status_text = self._normalize_doc_status('send', d)
                rows.append(("发文(关联)", sid, "", sid, d.get('document_no', ''), d.get('title', ''), status_text))
                rows_meta.append({
                    'type': 'send',
                    'record_id': sid,
                    'receive_id': '',
                    'send_id': sid,
                    'document_no': d.get('document_no', ''),
                    'title': d.get('title', ''),
                    'status': status_text,
                    'related': True
                })
        if circ_docs:
            for c in circ_docs:
                # 流转记录：记录ID=流转ID，文档ID按类型分别落入“收文ID/发文ID”列
                ctype = c.get('document_type')
                recv_id = c.get('receive_id', '') or (c.get('document_id', '') if ctype == 'receive' else '')
                send_id = c.get('send_id', '') or (c.get('document_id', '') if ctype == 'send' else '')
                doc_no = c.get('document_no', '') or ''
                title_or_type = c.get('title', '') or c.get('circulation_type', '')
                rows.append(("流转", c.get('id'), recv_id, send_id, doc_no, title_or_type, c.get('status', '')))
                rows_meta.append({
                    'type': 'circulation',
                    'record_id': c.get('id'),
                    'receive_id': recv_id,
                    'send_id': send_id,
                    'document_no': doc_no,
                    'title': title_or_type,
                    'status': c.get('status', ''),
                    'document_type': ctype
                })

        self._rows_meta = rows_meta

        self.result_table.setRowCount(len(rows) if rows else 1)
        if rows:
            for i, (typ, rid, recv_id, send_id, docno, title, status) in enumerate(rows):
                self.result_table.setItem(i, 0, QTableWidgetItem(str(typ)))
                self.result_table.setItem(i, 1, QTableWidgetItem(str(rid)))
                self.result_table.setItem(i, 2, QTableWidgetItem(str(recv_id)))
                self.result_table.setItem(i, 3, QTableWidgetItem(str(send_id)))
                self.result_table.setItem(i, 4, QTableWidgetItem(str(docno)))
                self.result_table.setItem(i, 5, QTableWidgetItem(str(title)))
                self.result_table.setItem(i, 6, QTableWidgetItem(str(status)))
        else:
            # no results
            self.result_table.setItem(0, 0, QTableWidgetItem("暂无结果"))
            for j in range(1, 7):
                self.result_table.setItem(0, j, QTableWidgetItem(""))

    def on_row_double_clicked(self, row, _column):
        """双击行：回传选中记录信息给调用方。"""
        try:
            if row < 0 or row >= len(self._rows_meta):
                return
            meta = self._rows_meta[row]
            if not isinstance(meta, dict):
                return
            self.record_selected.emit(meta)
        except Exception:
            pass
