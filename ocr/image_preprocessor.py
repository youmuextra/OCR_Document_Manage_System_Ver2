# ocr/image_preprocessor.py
"""
图像预处理模块
"""

import cv2
import numpy as np
from PIL import Image
import logging

logger = logging.getLogger(__name__)

class ImagePreprocessor:
    """图像预处理器"""
    
    def __init__(self):
        pass
    
    def preprocess_for_ocr(self, image_path: str, output_path: str = None) -> np.ndarray:
        """
        为OCR预处理图像
        
        Args:
            image_path: 输入图片路径
            output_path: 输出图片路径（可选）
            
        Returns:
            预处理后的图像
        """
        try:
            # 读取图像
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError(f"无法读取图像: {image_path}")
            
            logger.info(f"预处理图像: {image_path}, 原始尺寸: {img.shape}")
            
            # 1. 转换为灰度图
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # 2. 去噪
            denoised = cv2.medianBlur(gray, 3)
            
            # 3. 二值化（自适应阈值）
            binary = cv2.adaptiveThreshold(
                denoised, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )
            
            # 4. 形态学操作（去除噪点）
            kernel = np.ones((2, 2), np.uint8)
            morph = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            
            # 5. 再次去噪
            final = cv2.medianBlur(morph, 3)
            
            # 如果需要保存
            if output_path:
                cv2.imwrite(output_path, final)
                logger.info(f"预处理后的图像已保存: {output_path}")
            
            logger.info("图像预处理完成")
            return final
            
        except Exception as e:
            logger.error(f"图像预处理失败: {e}")
            raise
    
    def rotate_image(self, image: np.ndarray, angle: float) -> np.ndarray:
        """旋转图像"""
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        
        # 计算旋转矩阵
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        # 执行旋转
        rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC)
        
        return rotated
    
    def deskew_image(self, image_path: str) -> np.ndarray:
        """矫正图像倾斜"""
        try:
            # 读取图像
            img = cv2.imread(image_path)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # 二值化
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # 查找轮廓
            coords = np.column_stack(np.where(binary > 0))
            
            if len(coords) > 0:
                # 计算最小旋转矩形
                angle = cv2.minAreaRect(coords)[-1]
                
                # 调整角度
                if angle < -45:
                    angle = -(90 + angle)
                else:
                    angle = -angle
                
                # 旋转图像
                (h, w) = img.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                deskewed = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                
                logger.info(f"图像倾斜矫正: 角度={angle:.2f}度")
                return deskewed
            else:
                logger.warning("未找到有效轮廓，跳过倾斜矫正")
                return img
                
        except Exception as e:
            logger.error(f"倾斜矫正失败: {e}")
            return cv2.imread(image_path)
    
    def enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """增强对比度"""
        # 转换为YUV颜色空间
        yuv = cv2.cvtColor(image, cv2.COLOR_BGR2YUV)
        
        # 对Y通道进行CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        yuv[:,:,0] = clahe.apply(yuv[:,:,0])
        
        # 转换回BGR
        enhanced = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)
        
        return enhanced
    
    def remove_shadow(self, image: np.ndarray) -> np.ndarray:
        """去除阴影"""
        rgb_planes = cv2.split(image)
        
        result_planes = []
        for plane in rgb_planes:
            dilated_img = cv2.dilate(plane, np.ones((7,7), np.uint8))
            bg_img = cv2.medianBlur(dilated_img, 21)
            diff_img = 255 - cv2.absdiff(plane, bg_img)
            result_planes.append(diff_img)
        
        result = cv2.merge(result_planes)
        return result
    
    def resize_image(self, image: np.ndarray, max_size: int = 2000) -> np.ndarray:
        """调整图像大小"""
        h, w = image.shape[:2]
        
        if max(h, w) > max_size:
            scale = max_size / max(h, w)
            new_w = int(w * scale)
            new_h = int(h * scale)
            resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
            logger.info(f"调整图像大小: {w}x{h} -> {new_w}x{new_h}")
            return resized
        
        return image
