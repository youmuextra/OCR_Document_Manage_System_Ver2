# ui/circulation_dialog.py
"""
流转管理对话框
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QMessageBox, QDateEdit,
    QFormLayout, QGroupBox, QComboBox, QRadioButton,
    QButtonGroup, QTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QTabWidget, QWidget, QAbstractItemView
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, QDate, Signal
from datetime import datetime, timedelta

class CirculationDialog(QDialog):
    """流转管理对话框"""

    # 在成功创建流转记录后通知主窗口整个工作流已完成
    workflow_finished = Signal()
    
    def __init__(self, db_manager, current_user, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user
        self.universal_query_dialog = None
        self.selected_doc_id = None
        self.selected_doc_type = None  # 'receive' | 'send'
        self.selected_doc_title = ''
        self.selected_doc_no = ''
        self.selected_return_flow_id = None
        self.return_row_flow_ids = []
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("公文流转管理")
        self.resize(800, 600)
        
        # 创建选项卡
        self.tab_widget = QTabWidget()
        
        # 发起流转选项卡
        self.initiate_tab = QWidget()
        self.setup_initiate_tab()
        self.tab_widget.addTab(self.initiate_tab, "发起流转")
        
        # 流转记录选项卡
        self.records_tab = QWidget()
        self.setup_records_tab()
        self.tab_widget.addTab(self.records_tab, "流转记录")
        
        layout = QVBoxLayout()
        layout.addWidget(self.tab_widget)
        
        # 关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.reject)
        close_button.setMaximumWidth(100)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def setup_initiate_tab(self):
        """设置发起流转选项卡"""
        layout = QVBoxLayout()
        
        # 流转表单
        form_group = QGroupBox("流转信息")
        form_layout = QFormLayout()
        
        # 文档类型
        self.doc_type_combo = QComboBox()
        self.doc_type_combo.addItems(["收文", "发文"])
        self.doc_type_combo.currentTextChanged.connect(self._on_doc_type_changed)
        self.doc_type_combo.setToolTip("文档类型表示本次流转对象属于收文还是发文。")
        form_layout.addRow("文档类型:", self.doc_type_combo)
        
        # 文档选择（不再手输ID）
        self.doc_pick_display = QLineEdit()
        self.doc_pick_display.setReadOnly(True)
        self.doc_pick_display.setPlaceholderText("请点击“选择文件(公文查询)”后，在查询结果中双击目标公文")
        form_layout.addRow("目标公文*:", self.doc_pick_display)

        # 辅助查询（无需关闭当前流转窗口）
        query_id_layout = QHBoxLayout()
        self.quick_query_btn = QPushButton("选择文件(公文查询)")
        self.quick_query_btn.setMaximumWidth(170)
        self.quick_query_btn.clicked.connect(self.on_open_universal_query)
        query_id_layout.addWidget(self.quick_query_btn)

        self.review_receive_btn = QPushButton("回看收文识别内容")
        self.review_receive_btn.setMaximumWidth(170)
        self.review_receive_btn.clicked.connect(self.on_review_receive_content)
        query_id_layout.addWidget(self.review_receive_btn)
        query_id_layout.addStretch()
        form_layout.addRow("", query_id_layout)
        
        # 流转类型
        self.circulation_type_combo = QComboBox()
        self.circulation_type_combo.addItems(["交接", "借阅", "其他"])
        self.circulation_type_combo.currentTextChanged.connect(self._on_circulation_type_changed)
        form_layout.addRow("流转类型*:", self.circulation_type_combo)
        
        # 取件单位
        self.next_unit_input = QLineEdit()
        self.next_unit_input.setPlaceholderText("请输入取件单位")
        form_layout.addRow("取件单位*:", self.next_unit_input)
        
        # 取件人
        self.next_person_input = QLineEdit()
        self.next_person_input.setPlaceholderText("请输入取件人")
        form_layout.addRow("取件人*:", self.next_person_input)
        
        # 借阅期限（仅借阅时显示）
        self.due_date_input = QDateEdit()
        self.due_date_input.setDate(QDate.currentDate().addDays(7))
        self.due_date_input.setCalendarPopup(True)
        form_layout.addRow("应归还日期:", self.due_date_input)
        
        # 备注
        self.remarks_input = QTextEdit()
        self.remarks_input.setMaximumHeight(80)
        self.remarks_input.setPlaceholderText("请输入备注信息")
        form_layout.addRow("备注:", self.remarks_input)
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.initiate_button = QPushButton("发起流转")
        self.initiate_button.setStyleSheet("background-color: #3498db; color: white;")
        self.initiate_button.clicked.connect(self.on_initiate)
        
        self.clear_button = QPushButton("清空")
        self.clear_button.clicked.connect(self.on_clear)
        
        button_layout.addWidget(self.initiate_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)
        
        self.initiate_tab.setLayout(layout)
        # 默认交接：禁用归还日期；借阅时再启用
        self._on_circulation_type_changed(self.circulation_type_combo.currentText())

    def _on_doc_type_changed(self, text: str):
        """根据文档类型切换，清理已选公文避免类型错配。"""
        # 用户切换类型时清空已选，要求重新从查询中选择
        self.selected_doc_id = None
        self.selected_doc_type = None
        self.selected_doc_title = ''
        self.selected_doc_no = ''
        self.doc_pick_display.clear()

    def _on_circulation_type_changed(self, text: str):
        """根据流转类型启用/禁用应归还日期。"""
        is_borrow = (text == '借阅')
        self.due_date_input.setEnabled(is_borrow)
        if not is_borrow:
            self.due_date_input.setDate(QDate.currentDate().addDays(7))

    def on_open_universal_query(self):
        """在流转窗口内打开通用公文查询（非模态），便于对照填写ID。"""
        try:
            from .universal_query_dialog import UniversalQueryDialog
            if self.universal_query_dialog is None:
                self.universal_query_dialog = UniversalQueryDialog(self.db_manager, self.current_user, self)
                self.universal_query_dialog.setWindowModality(Qt.NonModal)
                try:
                    self.universal_query_dialog.record_selected.connect(self.on_query_record_selected)
                except Exception:
                    pass
            self.universal_query_dialog.show()
            self.universal_query_dialog.raise_()
            self.universal_query_dialog.activateWindow()
            self.status_label.setText("请在公文查询结果中双击目标公文完成选择")
        except Exception as e:
            QMessageBox.warning(self, "提示", f"打开公文查询失败: {e}")

    def on_review_receive_content(self):
        """回看收文识别内容：打开已缓存的收文登记窗口。"""
        parent = self.parent()
        receive_dialog = None
        try:
            if parent and hasattr(parent, 'workflow_dialogs'):
                receive_dialog = parent.workflow_dialogs.get('receive')
        except Exception:
            receive_dialog = None

        if receive_dialog is None:
            QMessageBox.information(self, "提示", "当前没有可回看的收文识别内容。\n请先进入收文管理完成识别。")
            return

        try:
            receive_dialog.setModal(False)
            receive_dialog.setWindowModality(Qt.NonModal)
            receive_dialog.show()
            receive_dialog.raise_()
            receive_dialog.activateWindow()
        except Exception as e:
            QMessageBox.warning(self, "提示", f"打开收文回看窗口失败: {e}")

    def on_query_record_selected(self, record: dict):
        """接收通用查询双击结果并自动回填到流转表单。"""
        try:
            if not isinstance(record, dict):
                return

            recv_id = str(record.get('receive_id') or '').strip()
            send_id = str(record.get('send_id') or '').strip()
            rec_title = str(record.get('title') or '').strip()
            rec_no = str(record.get('document_no') or '').strip()

            # 若来自“关联”行，仍允许使用；优先以“类型”+ID回填
            rtype = str(record.get('type') or '').strip()

            if recv_id and (rtype in ('receive', '收文', '') or not send_id):
                self.doc_type_combo.setCurrentText("收文")
                self.selected_doc_id = int(recv_id)
                self.selected_doc_type = 'receive'
                self.selected_doc_title = rec_title
                self.selected_doc_no = rec_no
                self.doc_pick_display.setText(f"文号={rec_no}  标题={rec_title}")
                self.status_label.setText(f"已选择收文：{rec_no or rec_title}")
            elif send_id:
                self.doc_type_combo.setCurrentText("发文")
                self.selected_doc_id = int(send_id)
                self.selected_doc_type = 'send'
                self.selected_doc_title = rec_title
                self.selected_doc_no = rec_no
                self.doc_pick_display.setText(f"文号={rec_no}  标题={rec_title}")
                self.status_label.setText(f"已选择发文：{rec_no or rec_title}")
            else:
                self.status_label.setText("选中记录未包含可用文号")
        except Exception as e:
            QMessageBox.warning(self, "提示", f"回填失败: {e}")
    
    def setup_records_tab(self):
        """设置流转记录选项卡"""
        layout = QVBoxLayout()
        
        # 查询条件
        query_group = QGroupBox("查询条件")
        query_layout = QFormLayout()
        
        # 文档类型筛选（收文/发文）
        self.query_doc_type_combo = QComboBox()
        self.query_doc_type_combo.addItems(["全部", "收文", "发文"])
        query_layout.addRow("文档类型:", self.query_doc_type_combo)

        # 文号（面向用户，不再要求理解文档ID）
        self.query_doc_no_input = QLineEdit()
        self.query_doc_no_input.setPlaceholderText("请输入文号")
        query_layout.addRow("文号:", self.query_doc_no_input)
        
        # 流转类型
        self.query_type_combo = QComboBox()
        self.query_type_combo.addItems(["全部", "交接", "借阅", "其他"])
        query_layout.addRow("流转类型:", self.query_type_combo)
        
        # 状态
        self.query_status_combo = QComboBox()
        self.query_status_combo.addItems(["全部", "待确认", "已流转", "已借出", "已归还", "已完成", "流转中"])
        query_layout.addRow("状态:", self.query_status_combo)
        
        query_group.setLayout(query_layout)
        layout.addWidget(query_group)
        
        # 查询按钮
        query_button = QPushButton("查询")
        query_button.clicked.connect(self.on_query)
        query_button.setMaximumWidth(100)
        
        button_layout = QHBoxLayout()
        button_layout.addWidget(query_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # 结果表格
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(9)
        self.result_table.setHorizontalHeaderLabels([
            "文档类型", "文号", "标题", "流转类型", "取件信息", "状态", "发起流转时间", "领取时间", "操作"
        ])
        header_tips = {
            "发起流转时间": "该流转记录创建（发起）的时间（精确到秒）。",
            "领取时间": "收件人/取件人实际领取（取走）的时间（精确到秒）。",
        }
        for i in range(self.result_table.columnCount()):
            item = self.result_table.horizontalHeaderItem(i)
            if item and item.text() in header_tips:
                item.setToolTip(header_tips[item.text()])
        self.result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.result_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.Interactive)

        # 关键列固定宽度，避免文号被压缩显示为省略号
        self.result_table.setColumnWidth(0, 90)   # 文档类型
        self.result_table.setColumnWidth(1, 220)  # 文号
        self.result_table.setColumnWidth(2, 220)  # 标题
        self.result_table.setColumnWidth(3, 90)   # 流转类型
        self.result_table.setColumnWidth(4, 180)  # 取件信息
        self.result_table.setColumnWidth(5, 180)  # 状态
        self.result_table.setColumnWidth(6, 170)  # 发起流转时间
        self.result_table.setColumnWidth(7, 170)  # 领取时间
        self.result_table.setColumnWidth(8, 90)   # 操作
        layout.addWidget(self.result_table)

        hint = QLabel("提示：本页仅用于查询与查看流转记录详情；取件/归还请在“取件登记与查询”模块办理。")
        hint.setStyleSheet("color: #666;")
        layout.addWidget(hint)
        
        self.records_tab.setLayout(layout)
    
    def setup_return_tab(self):
        """设置归还管理选项卡"""
        layout = QVBoxLayout()
        
        # 查询条件
        form_group = QGroupBox("查询条件")
        form_layout = QFormLayout()

        self.return_doc_type_combo = QComboBox()
        self.return_doc_type_combo.addItems(["全部", "收文", "发文"])
        form_layout.addRow("文档类型:", self.return_doc_type_combo)

        self.return_doc_no_input = QLineEdit()
        self.return_doc_no_input.setPlaceholderText("请输入文号")
        form_layout.addRow("文号:", self.return_doc_no_input)

        self.return_status_combo = QComboBox()
        self.return_status_combo.addItems(["全部", "待确认", "已借出", "已归还"])
        form_layout.addRow("状态:", self.return_status_combo)

        self.return_search_btn = QPushButton("查询")
        self.return_search_btn.clicked.connect(self.on_return_search)
        form_layout.addRow("", self.return_search_btn)
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        self.return_result_table = QTableWidget()
        self.return_result_table.setColumnCount(7)
        self.return_result_table.setHorizontalHeaderLabels([
            "文档类型", "文号", "标题", "取件信息", "状态", "应还日期", "操作"
        ])
        self.return_result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.return_result_table.horizontalHeader().setStretchLastSection(True)
        self.return_result_table.cellDoubleClicked.connect(self.on_return_row_double_clicked)
        layout.addWidget(self.return_result_table)

        return_hint = QLabel("提示：双击列表可查看详情并自动选中该记录；仅状态为“已借出”的借阅记录可确认归还。")
        return_hint.setStyleSheet("color: #666;")
        layout.addWidget(return_hint)
        
        # 按钮
        self.return_button = QPushButton("确认归还")
        self.return_button.setStyleSheet("background-color: #2ecc71; color: white;")
        self.return_button.clicked.connect(self.on_return)
        self.return_button.setMaximumWidth(150)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.return_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # 状态标签
        self.return_status_label = QLabel("")
        self.return_status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.return_status_label)
        
        self.return_tab.setLayout(layout)
    
    def on_initiate(self):
        """发起流转"""
        # 验证必须已通过查询双击选中文件
        if self.selected_doc_id is None or self.selected_doc_type is None:
            QMessageBox.warning(self, "警告", "请先点击“选择文件(公文查询)”并在结果中双击目标公文")
            return

        # 防止用户切换文档类型导致错配
        expected = 'receive' if self.doc_type_combo.currentText() == '收文' else 'send'
        if self.selected_doc_type != expected:
            QMessageBox.warning(self, "警告", "当前文档类型与已选公文不一致，请重新选择目标公文")
            return

        pickup_unit = self.next_unit_input.text().strip()
        pickup_person = self.next_person_input.text().strip()
        if not pickup_unit:
            QMessageBox.warning(self, "警告", "取件单位不能为空")
            return
        if not pickup_person:
            QMessageBox.warning(self, "警告", "取件人不能为空")
            return

        circ_type = self.circulation_type_combo.currentText().strip()
        init_status = '已借出' if circ_type == '借阅' else '已流转'
    
        # 准备数据
        circulation_data = {
            'document_id': self.selected_doc_id,
            'document_type': self.selected_doc_type,
            'circulation_type': circ_type,
            'next_node_unit': pickup_unit,
            'next_node_person': pickup_person,
            'current_holder_id': self.current_user['id'],
            'borrow_requester_id': self.current_user['id'] if circ_type == '借阅' else None,
            'borrow_date': datetime.now() if circ_type == '借阅' else None,
            'due_date': self.due_date_input.date().toPython() if circ_type == '借阅' else None,
            'status': init_status,
            'remarks': self.remarks_input.toPlainText().strip()
        }
    
        # 执行保存
        self.status_label.setText("正在创建流转记录...")
    
        try:
            success, message, circ_id = self.db_manager.create_circulation_record(
                circulation_data, 
                self.current_user['id']
            )
        
            if success:
                QMessageBox.information(self, "成功", f"流转记录创建成功！\n文号: {self.selected_doc_no or '未识别'}")
                self.on_clear()
                self.status_label.setText(f"流转记录已创建，文号: {self.selected_doc_no or '未识别'}")
                # 整个流程结束
                try:
                    self.workflow_finished.emit()
                except Exception:
                    pass
            else:
                QMessageBox.warning(self, "失败", message)
                self.status_label.setText(f"创建失败: {message}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建失败: {e}")
            self.status_label.setText(f"创建异常: {str(e)}")
    
    def on_clear(self):
        """清空表单"""
        self.selected_doc_id = None
        self.selected_doc_type = None
        self.selected_doc_title = ''
        self.selected_doc_no = ''
        self.doc_pick_display.clear()
        self.next_unit_input.clear()
        self.next_person_input.clear()
        self.remarks_input.clear()
        self.status_label.setText("")
        self.doc_pick_display.setFocus()
    
    def on_query(self):
        """查询流转记录"""
        try:
            filters = {}
            # 文档类型
            doc_type = self.query_doc_type_combo.currentText()
            if doc_type != "全部":
                filters['document_type'] = 'receive' if doc_type == '收文' else 'send'

            # 文号查询（后续在结果集中做文档ID过滤）
            doc_no = self.query_doc_no_input.text().strip()
            # 流转类型
            circ_type = self.query_type_combo.currentText()
            if circ_type != "全部":
                filters['circulation_type'] = circ_type
            # 状态
            status = self.query_status_combo.currentText()
            if status != "全部":
                filters['status'] = status
            success, message, result = self.db_manager.get_circulation_records(filters)
            if success:
                if result and isinstance(result, dict) and 'records' in result:
                    records = result['records']
                    if doc_no:
                        records = self._filter_records_by_doc_no(records, doc_no, doc_type)
                    self.display_results(records)
                    self.status_label.setText(f"查询完成，共找到 {len(records)} 条记录")
                else:
                    QMessageBox.warning(self, "查询失败", f"返回数据格式不正确: {type(result)}")

            else:
                QMessageBox.warning(self, "查询失败", message)
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"查询失败: {e}")
            import traceback
            traceback.print_exc()

    def _filter_records_by_doc_no(self, records, doc_no: str, doc_type_ui: str):
        """按文号过滤流转记录（通过收文/发文表解析出对应文档ID集合）。"""
        target_ids_receive = set()
        target_ids_send = set()

        # 查收文
        if doc_type_ui in ("全部", "收文"):
            try:
                ok, _msg, res = self.db_manager.search_documents({'document_no': doc_no}, page=1, page_size=200)
                for d in ((res or {}).get('documents') or []) if ok else []:
                    if d.get('id') is not None:
                        target_ids_receive.add(int(d.get('id')))
            except Exception:
                pass

        # 查发文
        if doc_type_ui in ("全部", "发文"):
            try:
                ok, _msg, res = self.db_manager.get_send_documents({'document_no': doc_no}, page=1, page_size=200)
                for d in ((res or {}).get('documents') or []) if ok else []:
                    if d.get('id') is not None:
                        target_ids_send.add(int(d.get('id')))
            except Exception:
                pass

        # 没有匹配ID，直接返回空
        if not target_ids_receive and not target_ids_send:
            return []

        out = []
        for r in records or []:
            try:
                r_type = str(r.get('document_type') or '')
                r_id = int(r.get('document_id'))
            except Exception:
                continue
            if r_type == 'receive' and r_id in target_ids_receive:
                out.append(r)
            elif r_type == 'send' and r_id in target_ids_send:
                out.append(r)
        return out
    def display_results(self, records):
        """显示查询结果"""
        def fmt_dt(v):
            if not v:
                return ""
            if hasattr(v, 'strftime'):
                return v.strftime("%Y-%m-%d %H:%M:%S")
            s = str(v).replace('T', ' ').strip()
            return s[:19] if len(s) >= 19 else s

        if not isinstance(records, list):
            records = []
        self.result_table.setRowCount(len(records))
        for i, record in enumerate(records):
            id_text = ""
            action_button = None
            if not isinstance(record, dict):
                for col in range(8):
                    self.result_table.setItem(i, col, QTableWidgetItem(""))
                action_button = QPushButton("无效数据")
                action_button.setEnabled(False)
                self.result_table.setCellWidget(i, 8, action_button)
                continue
            flow_id = record.get('id')
            if flow_id is None or flow_id == '':
                action_button = QPushButton("无记录")
                action_button.setEnabled(False)
            else:
                try:
                    flow_id_int = int(flow_id)
                    action_button = QPushButton("查看")
                    def create_click_handler(record_id):
                        return lambda: self.on_view_record(record_id)
                    action_button.clicked.connect(create_click_handler(flow_id_int))
                except (ValueError, TypeError):
                    action_button = QPushButton("无效记录")
                    action_button.setEnabled(False)
            # 填充列
            # 第0列：文档类型
            doc_type = record.get('document_type', '')
            doc_type_text = '收文' if str(doc_type) == 'receive' else ('发文' if str(doc_type) == 'send' else str(doc_type))
            self.result_table.setItem(i, 0, QTableWidgetItem(doc_type_text))

            # 第1-2列：文号/标题
            doc_no_text = str(record.get('document_no', '') or '')
            title_text = str(record.get('title', '') or '')
            doc_no_item = QTableWidgetItem(doc_no_text)
            title_item = QTableWidgetItem(title_text)
            doc_no_item.setToolTip(doc_no_text)
            title_item.setToolTip(title_text)
            self.result_table.setItem(i, 1, doc_no_item)
            self.result_table.setItem(i, 2, title_item)

            # 第3列：流转类型
            circ_type = record.get('circulation_type', '')
            self.result_table.setItem(i, 3, QTableWidgetItem(str(circ_type)))

            # 第4列：下一节点
            next_unit = record.get('next_node_unit', '')
            next_person = record.get('next_node_person', '')
            next_node = f"{next_unit}/{next_person}" if next_unit or next_person else ""
            self.result_table.setItem(i, 4, QTableWidgetItem(next_node))

            # 第5列：状态
            status = record.get('status', '')
            self.result_table.setItem(i, 5, QTableWidgetItem(str(status)))

            # 第6列：发起流转时间（原创建时间）
            self.result_table.setItem(i, 6, QTableWidgetItem(fmt_dt(record.get('created_at', ''))))

            # 第7列：领取时间
            pickup_time = record.get('pickup_time', '') or record.get('borrow_date', '')
            self.result_table.setItem(i, 7, QTableWidgetItem(fmt_dt(pickup_time)))

            # 第8列：操作按钮
            if action_button is None:
                action_button = QPushButton("无操作")
                action_button.setEnabled(False)

            self.result_table.setCellWidget(i, 8, action_button)

    def on_return_search(self):
        """归还页按文号搜索可归还的借阅流转记录。"""
        try:
            filters = {'circulation_type': '借阅'}
            status = self.return_status_combo.currentText().strip()
            if status and status != '全部':
                filters['status'] = status

            success, message, result = self.db_manager.get_circulation_records(filters)
            if not success:
                QMessageBox.warning(self, '查询失败', message)
                return
            records = (result or {}).get('records', [])

            doc_type_ui = self.return_doc_type_combo.currentText().strip()
            if doc_type_ui != '全部':
                expect = 'receive' if doc_type_ui == '收文' else 'send'
                records = [r for r in records if str(r.get('document_type') or '') == expect]

            doc_no = self.return_doc_no_input.text().strip()
            matched = []
            for record in records:
                rec_no = str(record.get('document_no', '') or '')
                if not doc_no or doc_no in rec_no:
                    matched.append(record)

            self._display_return_results(matched)
            self.return_status_label.setText(f'按文号查询完成，共找到 {len(matched)} 条借阅记录')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'归还搜索失败: {e}')

    def _display_return_results(self, records):
        self.return_row_flow_ids = []
        self.return_result_table.setRowCount(len(records))
        for i, record in enumerate(records):
            flow_id = record.get('id', '')
            self.return_row_flow_ids.append(flow_id)
            doc_type = '收文' if str(record.get('document_type')) == 'receive' else '发文'
            self.return_result_table.setItem(i, 0, QTableWidgetItem(doc_type))
            self.return_result_table.setItem(i, 1, QTableWidgetItem(str(record.get('document_no', '') or '')))
            self.return_result_table.setItem(i, 2, QTableWidgetItem(str(record.get('title', '') or '')))
            next_node = f"{record.get('next_node_unit', '')}/{record.get('next_node_person', '')}".strip('/')
            self.return_result_table.setItem(i, 3, QTableWidgetItem(next_node))
            self.return_result_table.setItem(i, 4, QTableWidgetItem(str(record.get('status', '') or '')))

            due_date = record.get('due_date', '')
            due_date_str = ''
            if due_date:
                if hasattr(due_date, 'strftime'):
                    due_date_str = due_date.strftime('%Y-%m-%d')
                else:
                    due_date_str = str(due_date)
            self.return_result_table.setItem(i, 5, QTableWidgetItem(due_date_str))

            btn = QPushButton('选择此记录')
            btn.setEnabled(str(record.get('status', '')) == '已借出')
            btn.clicked.connect(lambda _=False, fid=flow_id: self._select_return_flow_id(fid))
            self.return_result_table.setCellWidget(i, 6, btn)

    def _select_return_flow_id(self, flow_id):
        self.selected_return_flow_id = flow_id
        self.return_status_label.setText('已选择待归还记录')

    def on_return_row_double_clicked(self, row, _column):
        """归还管理中双击查看详情，同时选中该记录。"""
        try:
            if row < 0 or row >= len(self.return_row_flow_ids):
                return
            flow_id = str(self.return_row_flow_ids[row]).strip()
            if not flow_id:
                return
            self._select_return_flow_id(flow_id)
            self.on_view_record(flow_id)
        except Exception as e:
            QMessageBox.warning(self, '提示', f'打开流转详情失败: {e}')

    def on_view_record(self, flow_id):
        """查看流转记录详情"""
        try:
            print(f"\n[DEBUG] === 开始查看流转记录 ===")
            print(f"[DEBUG] 接收到的flow_id: {flow_id}, 类型: {type(flow_id)}")
            
            # 验证ID
            if flow_id is None or flow_id is False or (isinstance(flow_id, bool) and not flow_id):
                QMessageBox.warning(self, "警告", "无效的流转记录")
                return
            
            # 确保flow_id是整数
            try:
                flow_id_int = int(flow_id)
                print(f"[DEBUG] 转换后的flow_id_int: {flow_id_int}")
            except (ValueError, TypeError) as e:
                QMessageBox.warning(self, "警告", "无效的流转记录")
                return
            
            # 查询数据库
            print(f"[DEBUG] 查询数据库，ID: {flow_id_int}")
            success, message, record = self.db_manager.get_circulation_by_id(flow_id_int)
            
            if success and record:
                print(f"[DEBUG] 查询成功，记录: {record}")
                
                # ✅ 构建详情信息
                detail_text = f"📄 流转记录详情\n"
                detail_text += f"════════════════════\n"
                detail_text += f"文档类型: {record.get('document_type', '未知')}\n"
                if record.get('document_no'):
                    detail_text += f"文号: {record.get('document_no')}\n"
                if record.get('title'):
                    detail_text += f"标题: {record.get('title')}\n"
                detail_text += f"流转类型: {record.get('circulation_type', '未知')}\n"
                detail_text += f"状态: {record.get('status', '未知')}\n"
                
                # 下一节点
                next_node_unit = record.get('next_node_unit', '')
                next_node_person = record.get('next_node_person', '')
                if next_node_unit or next_node_person:
                    detail_text += f"取件信息: {next_node_unit}/{next_node_person}\n"
                
                # 当前持有人
                current_holder = record.get('current_holder_name', '')
                if current_holder:
                    detail_text += f"当前持有人: {current_holder}\n"
                
                # 借阅申请人
                borrow_requester = record.get('borrow_requester_name', '')
                if borrow_requester:
                    detail_text += f"借阅申请人: {borrow_requester}\n"
                
                # 日期信息
                borrow_date = record.get('borrow_date', '')
                if borrow_date:
                    detail_text += f"借阅日期: {borrow_date}\n"
                
                due_date = record.get('due_date', '')
                if due_date:
                    detail_text += f"应还日期: {due_date}\n"
                
                return_date = record.get('return_date', '')
                if return_date:
                    detail_text += f"归还日期: {return_date}\n"
                
                # 备注
                remarks = record.get('remarks', '')
                if remarks:
                    detail_text += f"备注: {remarks}\n"
                
                # 创建信息
                created_by = record.get('created_by_name', '')
                created_at = record.get('created_at', '')
                if created_by or created_at:
                    detail_text += f"创建信息: {created_by} 于 {created_at}"
                
                # ✅ 显示详情弹窗
                print("[DEBUG] 准备显示详情弹窗...")
                QMessageBox.information(self, "流转记录详情", detail_text)
                print("[DEBUG] 详情弹窗已显示")
                
            else:
                print(f"[DEBUG] 查询失败: {message}")
                QMessageBox.warning(self, "警告", f"未找到流转记录\n{message}")
                    
        except Exception as e:
            print(f"[ERROR] 查看流转记录失败: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "错误", f"查看流转记录失败: {e}")
    
    def on_return(self):
        """确认归还"""
        if self.selected_return_flow_id in (None, '', False):
            QMessageBox.warning(self, "警告", "请先在列表中选择要归还的记录")
            return

        circ_id = int(self.selected_return_flow_id)
        
        # 确认对话框
        reply = QMessageBox.question(
            self, 
            "确认归还", 
            "确认归还当前选中记录吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # 仅借阅类型允许归还
                ok_rec, msg_rec, rec = self.db_manager.get_circulation_by_id(circ_id)
                if not ok_rec or not rec:
                    QMessageBox.warning(self, "失败", "未找到对应流转记录")
                    return
                if str(rec.get('circulation_type', '')) != '借阅':
                    QMessageBox.warning(self, "失败", "仅“借阅”类型支持归还确认")
                    return

                success, message = self.db_manager.update_circulation_status(
                    circ_id, 
                    '已归还', 
                    self.current_user['id']
                )
                
                if success:
                    QMessageBox.information(self, "成功", "归还成功！")
                    self.selected_return_flow_id = None
                    self.return_status_label.setText("已归还选中记录")
                    self.on_return_search() if self.return_doc_no_input.text().strip() else None
                    self.on_query()
                else:
                    QMessageBox.warning(self, "失败", message)
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"归还失败: {e}")
