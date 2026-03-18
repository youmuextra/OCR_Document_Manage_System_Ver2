# ui/camera_dialog.py
"""摄像头拍照对话框，独立于其它模块。

此类负责打开摄像头、显示实时画面并允许用户拍照。
拍照后会将图像保存到临时目录并通过属性 `file_path` 提供结果。
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import Qt, QTimer
import cv2
import numpy as np
import tempfile
import os
from datetime import datetime


class CameraDialog(QDialog):
    """摄像头拍照对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cap = None
        self.timer = QTimer()
        self.file_path = None
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("摄像头拍照")
        self.resize(800, 600)

        layout = QVBoxLayout()

        # 视频显示区域
        self.video_label = QLabel("正在初始化摄像头...")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 480)
        layout.addWidget(self.video_label)

        # 按钮
        button_layout = QHBoxLayout()

        self.capture_button = QPushButton("📸 拍照")
        self.capture_button.clicked.connect(self.capture_image)
        self.capture_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 16px;
                padding: 10px;
                border-radius: 5px;
            }
        """)

        self.cancel_button = QPushButton("❌ 取消")
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.capture_button)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def start_camera(self):
        """启动摄像头并开始定时更新画面。"""
        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                QMessageBox.warning(self, "错误", "无法打开摄像头")
                self.reject()
                return

            self.timer.timeout.connect(self.update_frame)
            self.timer.start(30)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动摄像头失败: {e}")
            self.reject()

    def update_frame(self):
        """读取并显示当前视频帧。"""
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                    self.video_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.video_label.setPixmap(scaled_pixmap)

    def capture_image(self):
        """拍照并保存到临时文件"""
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                temp_dir = tempfile.gettempdir()
                temp_file = os.path.join(temp_dir, f"camera_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
                cv2.imwrite(temp_file, frame)
                self.file_path = temp_file
                self.accept()

    def closeEvent(self, event):
        """释放摄像头资源"""
        if self.cap and self.cap.isOpened():
            self.cap.release()
        if self.timer.isActive():
            self.timer.stop()
        super().closeEvent(event)
