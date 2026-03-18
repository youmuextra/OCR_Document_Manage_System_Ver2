# ocr/camera_capture.py
"""
摄像头捕获模块
支持电脑摄像头和可能的手机摄像头
"""

import cv2
import numpy as np
from PySide6.QtCore import QObject, Signal, QTimer, QThread
from PySide6.QtGui import QImage, QPixmap
import logging
import time

logger = logging.getLogger(__name__)

class CameraCapture(QThread):
    """摄像头捕获线程"""
    
    # 信号
    frame_ready = Signal(QPixmap)  # 帧准备好
    camera_opened = Signal()  # 摄像头打开
    camera_closed = Signal()  # 摄像头关闭
    error_occurred = Signal(str)  # 错误发生
    
    def __init__(self, camera_index=0, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.camera = None
        self.is_running = False
        self.frame_width = 640
        self.frame_height = 480
        self.fps = 30
        
    def run(self):
        """运行摄像头捕获"""
        try:
            logger.info(f"尝试打开摄像头 {self.camera_index}...")
            
            # 打开摄像头
            self.camera = cv2.VideoCapture(self.camera_index)
            
            if not self.camera.isOpened():
                self.error_occurred.emit(f"无法打开摄像头 {self.camera_index}")
                return
            
            # 设置摄像头参数
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
            self.camera.set(cv2.CAP_PROP_FPS, self.fps)
            
            self.is_running = True
            self.camera_opened.emit()
            logger.info("摄像头已打开")
            
            # 循环捕获帧
            while self.is_running and self.camera.isOpened():
                ret, frame = self.camera.read()
                
                if not ret:
                    self.error_occurred.emit("无法读取摄像头帧")
                    break
                
                # 转换为QPixmap
                pixmap = self.cv2_to_pixmap(frame)
                if pixmap:
                    self.frame_ready.emit(pixmap)
                
                # 控制帧率
                time.sleep(1.0 / self.fps)
                
        except Exception as e:
            logger.error(f"摄像头捕获错误: {e}")
            self.error_occurred.emit(str(e))
        finally:
            self.stop()
    
    def stop(self):
        """停止摄像头"""
        self.is_running = False
        if self.camera and self.camera.isOpened():
            self.camera.release()
            self.camera = None
            self.camera_closed.emit()
            logger.info("摄像头已关闭")
    
    def capture_frame(self) -> np.ndarray:
        """捕获一帧"""
        if self.camera and self.camera.isOpened():
            ret, frame = self.camera.read()
            if ret:
                return frame
        return None
    
    def capture_and_save(self, file_path: str) -> bool:
        """捕获并保存图片"""
        frame = self.capture_frame()
        if frame is not None:
            try:
                cv2.imwrite(file_path, frame)
                logger.info(f"图片已保存: {file_path}")
                return True
            except Exception as e:
                logger.error(f"保存图片失败: {e}")
        return False
    
    def cv2_to_pixmap(self, cv_image: np.ndarray) -> QPixmap:
        """将OpenCV图像转换为QPixmap"""
        try:
            if cv_image is None:
                return None
            
            # 转换颜色空间 BGR -> RGB
            rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
            
            # 获取图像尺寸
            height, width, channels = rgb_image.shape
            bytes_per_line = channels * width
            
            # 创建QImage
            qimage = QImage(rgb_image.data, width, height, bytes_per_line, QImage.Format_RGB888)
            
            # 转换为QPixmap
            pixmap = QPixmap.fromImage(qimage)
            
            return pixmap
            
        except Exception as e:
            logger.error(f"图像转换失败: {e}")
            return None
    
    def get_available_cameras(self) -> list:
        """获取可用的摄像头列表"""
        available_cameras = []
        
        # 测试前5个摄像头索引
        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available_cameras.append(i)
                cap.release()
        
        logger.info(f"可用摄像头: {available_cameras}")
        return available_cameras
    
    def set_resolution(self, width: int, height: int):
        """设置分辨率"""
        self.frame_width = width
        self.frame_height = height
        
        if self.camera and self.camera.isOpened():
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)