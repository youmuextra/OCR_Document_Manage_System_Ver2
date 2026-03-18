from PySide6.QtCore import QThread, Signal
import os
import hashlib
import time

class OCRThread(QThread):
    """OCR处理线程，将耗时的识别与数据库保存操作放在后台执行。

    线程完成后会通过信号将结果返回给调用方。
    """
    ocr_completed = Signal(int, str, str)  # document_id, ocr_path, ocr_text
    ocr_error = Signal(str)

    def __init__(self, image_path: str, document_id: int, db_manager, ocr_processor=None):
        super().__init__()
        self.image_path = image_path
        self.document_id = document_id
        self.db_manager = db_manager
        self.ocr_processor = ocr_processor

    def run(self):
        try:
            # 文件存在性检查
            if not os.path.exists(self.image_path):
                self.ocr_error.emit(f"文件不存在: {self.image_path}")
                return

            if self.ocr_processor:
                # OCRProcessor 提供了封装的 ocr_and_save 方法
                success, ocr_path, ocr_text = self.ocr_processor.ocr_and_save(
                    self.image_path, self.document_id, self.db_manager
                )
            else:
                # 回退逻辑：自行调用 paddleocr
                from paddleocr import PaddleOCR

                ocr = PaddleOCR(use_angle_cls=True, lang='ch', use_gpu=False, show_log=False)
                result = ocr.ocr(self.image_path, cls=True)
                ocr_text = self._convert_result(result)
                # 保存OCR文件
                ocr_dir = os.path.join("data", "ocr_results")
                os.makedirs(ocr_dir, exist_ok=True)
                timestamp = int(time.time())
                file_hash = hashlib.md5(self.image_path.encode()).hexdigest()[:8]
                ocr_filename = f"ocr_{timestamp}_{file_hash}.txt"
                ocr_path = os.path.join(ocr_dir, ocr_filename)
                with open(ocr_path, 'w', encoding='utf-8') as f:
                    f.write(ocr_text)
                success, message = self.db_manager.update_ocr_result(self.document_id, ocr_path)
                if not success:
                    self.ocr_error.emit(f"保存OCR结果失败: {message}")
                    return

            if success:
                self.ocr_completed.emit(self.document_id, ocr_path, ocr_text)
            else:
                self.ocr_error.emit(f"OCR处理失败: {ocr_path if ocr_path else ''}")
        except Exception as e:
            self.ocr_error.emit(f"OCR处理异常: {e}")

    def _convert_result(self, result):
        """简单转换原始paddleocr返回的数据为纯文本"""
        if not result or not result[0]:
            return ""
        lines = []
        for item in result[0]:
            if item and len(item) >= 2:
                text = item[1][0] if isinstance(item[1], (list, tuple)) else item[1]
                lines.append(str(text))
        return "\n".join(lines)
