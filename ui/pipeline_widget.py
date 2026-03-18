from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt


class PipelineWidget(QWidget):
    """显示若干阶段的水平管线，当前阶段高亮"""

    def __init__(self, stages, parent=None):
        super().__init__(parent)
        self.stages = stages
        self.current = 0
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setSpacing(20)
        for i, txt in enumerate(self.stages):
            lbl = QLabel(txt)
            lbl.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
            lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(lbl)
            if i != len(self.stages) - 1:
                arrow = QLabel("→")
                arrow.setFont(QFont("Microsoft YaHei", 11))
                layout.addWidget(arrow)
        self._update_colors()

    def setStage(self, idx: int):
        self.current = max(0, min(idx, len(self.stages) - 1))
        self._update_colors()

    def _update_colors(self):
        for i in range(self.layout().count()):
            w = self.layout().itemAt(i).widget()
            if not isinstance(w, QLabel):
                continue
            step = i // 2
            if step == self.current:
                w.setStyleSheet("color: #27ae60;")
            else:
                w.setStyleSheet("color: #444;")
