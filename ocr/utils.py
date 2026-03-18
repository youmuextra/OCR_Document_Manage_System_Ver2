# ocr/utils.py
"""
OCR工具函数
"""

import os
import uuid
import tempfile
import shutil
import json
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List
import logging
import hashlib
from pathlib import Path

logger = logging.getLogger(__name__)

def generate_unique_filename(original_filename: str) -> str:
    """
    生成唯一的文件名
    
    Args:
        original_filename: 原始文件名
        
    Returns:
        唯一的文件名
    """
    # 获取文件扩展名
    _, ext = os.path.splitext(original_filename)
    if not ext:
        ext = '.jpg'  # 默认扩展名
    
    # 生成唯一ID和时间戳
    unique_id = uuid.uuid4().hex[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 新文件名
    new_filename = f"doc_{timestamp}_{unique_id}{ext.lower()}"
    
    return new_filename

def save_uploaded_file(uploaded_file, save_dir: str) -> Tuple[Optional[str], Optional[str]]:
    """
    保存上传的文件
    
    Args:
        uploaded_file: 上传的文件对象或路径
        save_dir: 保存目录
        
    Returns:
        (保存的文件路径, 错误信息)
    """
    try:
        # 确保保存目录存在
        os.makedirs(save_dir, exist_ok=True)
        
        # 处理不同类型的上传文件
        if isinstance(uploaded_file, str):
            # 如果是文件路径
            if os.path.exists(uploaded_file):
                # 生成唯一文件名
                original_filename = os.path.basename(uploaded_file)
                unique_filename = generate_unique_filename(original_filename)
                save_path = os.path.join(save_dir, unique_filename)
                
                # 复制文件
                shutil.copy2(uploaded_file, save_path)
                logger.info(f"文件已复制: {uploaded_file} -> {save_path}")
                
                return save_path, None
            else:
                return None, f"文件不存在: {uploaded_file}"
        
        # 处理类文件对象
        elif hasattr(uploaded_file, 'read'):
            # 从类文件对象读取
            original_filename = getattr(uploaded_file, 'filename', 'unknown')
            unique_filename = generate_unique_filename(original_filename)
            save_path = os.path.join(save_dir, unique_filename)
            
            with open(save_path, 'wb') as f:
                if hasattr(uploaded_file, 'getbuffer'):
                    # BytesIO对象
                    f.write(uploaded_file.getbuffer())
                else:
                    # 其他类文件对象
                    f.write(uploaded_file.read())
            
            logger.info(f"文件已保存: {save_path}")
            return save_path, None
        
        # 处理字节数据
        elif isinstance(uploaded_file, bytes):
            # 字节数据
            unique_filename = generate_unique_filename('image.jpg')
            save_path = os.path.join(save_dir, unique_filename)
            
            with open(save_path, 'wb') as f:
                f.write(uploaded_file)
            
            logger.info(f"字节数据已保存: {save_path}")
            return save_path, None
        
        else:
            return None, f"不支持的文件类型: {type(uploaded_file)}"
            
    except Exception as e:
        logger.error(f"保存文件失败: {e}")
        return None, str(e)

def save_ocr_result(ocr_result: Dict[str, Any], save_dir: str) -> Tuple[Optional[str], Optional[str]]:
    """
    保存OCR识别结果
    
    Args:
        ocr_result: OCR识别结果
        save_dir: 保存目录
        
    Returns:
        (保存的文件路径, 错误信息)
    """
    try:
        # 确保保存目录存在
        os.makedirs(save_dir, exist_ok=True)
        
        # 生成唯一文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ocr_result_{timestamp}.json"
        save_path = os.path.join(save_dir, filename)
        
        # 保存为JSON
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(ocr_result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"OCR结果已保存: {save_path}")
        return save_path, None
        
    except Exception as e:
        logger.error(f"保存OCR结果失败: {e}")
        return None, str(e)

def save_text_result(text: str, save_dir: str, filename: str = None) -> Tuple[Optional[str], Optional[str]]:
    """
    保存文本结果
    
    Args:
        text: 文本内容
        save_dir: 保存目录
        filename: 文件名（可选）
        
    Returns:
        (保存的文件路径, 错误信息)
    """
    try:
        # 确保保存目录存在
        os.makedirs(save_dir, exist_ok=True)
        
        # 生成文件名
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"text_result_{timestamp}.txt"
        
        save_path = os.path.join(save_dir, filename)
        
        # 保存文本
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        logger.info(f"文本结果已保存: {save_path}")
        return save_path, None
        
    except Exception as e:
        logger.error(f"保存文本结果失败: {e}")
        return None, str(e)

def get_file_hash(file_path: str) -> Optional[str]:
    """
    计算文件的哈希值
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件的SHA256哈希值
    """
    try:
        if not os.path.exists(file_path):
            return None
        
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            # 分块读取文件，避免大文件内存问题
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()
        
    except Exception as e:
        logger.error(f"计算文件哈希失败: {e}")
        return None

def is_supported_image_format(filename: str) -> bool:
    """
    检查是否支持的图片格式
    
    Args:
        filename: 文件名
        
    Returns:
        是否支持
    """
    supported_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif'}
    _, ext = os.path.splitext(filename.lower())
    return ext in supported_formats

def is_supported_pdf_format(filename: str) -> bool:
    """
    检查是否支持的PDF格式
    
    Args:
        filename: 文件名
        
    Returns:
        是否支持
    """
    _, ext = os.path.splitext(filename.lower())
    return ext == '.pdf'

def is_supported_file_format(filename: str) -> bool:
    """
    检查是否支持的文件格式
    
    Args:
        filename: 文件名
        
    Returns:
        是否支持
    """
    return is_supported_image_format(filename) or is_supported_pdf_format(filename)

def get_file_size_mb(file_path: str) -> float:
    """
    获取文件大小（MB）
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件大小（MB）
    """
    try:
        if not os.path.exists(file_path):
            return 0.0
        
        size_bytes = os.path.getsize(file_path)
        size_mb = size_bytes / (1024 * 1024)
        
        return round(size_mb, 2)
        
    except Exception as e:
        logger.error(f"获取文件大小失败: {e}")
        return 0.0

def cleanup_temp_files(temp_files: List[str]):
    """
    清理临时文件
    
    Args:
        temp_files: 临时文件列表
    """
    for file_path in temp_files:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"已删除临时文件: {file_path}")
        except Exception as e:
            logger.warning(f"删除临时文件失败 {file_path}: {e}")

def create_data_directories():
    """
    创建必要的数据目录
    """
    directories = [
        'data/uploads',          # 上传文件
        'data/ocr_results',      # OCR识别结果
        'data/images',           # 处理后的图片
        'data/preprocessed',     # 预处理后的图片
        'data/database',         # 数据库
        'data/logs',             # 日志文件
        'data/temp',             # 临时文件
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"确保目录存在: {directory}")
        except Exception as e:
            logger.error(f"创建目录失败 {directory}: {e}")

def format_processing_time(seconds: float) -> str:
    """
    格式化处理时间
    
    Args:
        seconds: 秒数
        
    Returns:
        格式化的时间字符串
    """
    if seconds < 1:
        return f"{seconds*1000:.0f}毫秒"
    elif seconds < 60:
        return f"{seconds:.2f}秒"
    else:
        minutes = seconds / 60
        return f"{minutes:.1f}分钟"

def validate_image_file(file_path: str, max_size_mb: float = 10.0) -> Tuple[bool, str]:
    """
    验证图片文件
    
    Args:
        file_path: 文件路径
        max_size_mb: 最大文件大小（MB）
        
    Returns:
        (是否有效, 错误信息)
    """
    # 检查文件是否存在
    if not os.path.exists(file_path):
        return False, f"文件不存在: {file_path}"
    
    # 检查文件大小
    file_size_mb = get_file_size_mb(file_path)
    if file_size_mb > max_size_mb:
        return False, f"文件大小超过限制: {file_size_mb}MB > {max_size_mb}MB"
    
    # 检查文件格式
    if not is_supported_file_format(file_path):
        return False, f"不支持的文件格式: {os.path.splitext(file_path)[1]}"
    
    return True, ""

def get_image_dimensions(file_path: str) -> Tuple[Optional[int], Optional[int]]:
    """
    获取图片尺寸
    
    Args:
        file_path: 文件路径
        
    Returns:
        (宽度, 高度)
    """
    try:
        from PIL import Image
        
        with Image.open(file_path) as img:
            return img.size  # (width, height)
            
    except Exception as e:
        logger.error(f"获取图片尺寸失败: {e}")
        return None, None

def compress_image(input_path: str, output_path: str, quality: int = 85, max_size: int = 2000) -> bool:
    """
    压缩图片
    
    Args:
        input_path: 输入文件路径
        output_path: 输出文件路径
        quality: 图片质量 (1-100)
        max_size: 最大尺寸
        
    Returns:
        是否成功
    """
    try:
        from PIL import Image
        
        with Image.open(input_path) as img:
            # 保持宽高比调整尺寸
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = tuple(int(dim * ratio) for dim in img.size)
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # 保存压缩后的图片
            img.save(output_path, quality=quality, optimize=True)
            
            logger.info(f"图片已压缩: {input_path} -> {output_path}")
            return True
            
    except Exception as e:
        logger.error(f"压缩图片失败: {e}")
        return False