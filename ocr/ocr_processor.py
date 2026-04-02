# ocr/ocr_processor.py
"""
OCR处理器 - 根据您的测试结果完全修复
"""

import os
import sys
import cv2
import numpy as np
from PIL import Image
from pdf2image import convert_from_path
import tempfile
from datetime import datetime
import logging
from typing import Dict, List, Any, Optional, Tuple
import traceback
import re
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OCRProcessor:
    def __init__(self, use_gpu=False, lang='ch', debug=True, 
                 model_dir=None, poppler_path=None):
        """初始化OCR处理器，支持离线模型"""
        self.debug = debug
        self.use_gpu = use_gpu
        self.lang = lang
        self.model_dir = model_dir
        
        # 设置poppler路径
        self.poppler_path = poppler_path
        
        # 初始化OCR引擎
        self._init_ocr_engine()
    
    def _init_ocr_engine(self):
        """初始化OCR引擎 - 支持离线模型"""
        try:
            from paddleocr import PaddleOCR
            
            if self.debug:
                print("初始化PaddleOCR引擎...")
            
            # 准备初始化参数
            init_params = {
                'use_angle_cls': True,
                'lang': self.lang,
                'use_gpu': self.use_gpu,
                'show_log': self.debug,
                'det_db_thresh': 0.3,
                'det_db_box_thresh': 0.3,
                'drop_score': 0.5,
                'use_mp': False,
                'rec_batch_num': 1,
            }
            
            # 如果提供了模型目录，指定模型路径
            if self.model_dir and os.path.exists(self.model_dir):
                if self.debug:
                    print(f"使用自定义模型目录: {self.model_dir}")
                
                # 构建模型路径
                det_model_dir = os.path.join(self.model_dir, "det")
                rec_model_dir = os.path.join(self.model_dir, "rec")
                cls_model_dir = os.path.join(self.model_dir, "cls")
                
                # 检查模型文件是否存在
                if os.path.exists(det_model_dir):
                    init_params['det_model_dir'] = det_model_dir
                    if self.debug:
                        print(f"使用检测模型: {det_model_dir}")
                
                if os.path.exists(rec_model_dir):
                    init_params['rec_model_dir'] = rec_model_dir
                    if self.debug:
                        print(f"使用识别模型: {rec_model_dir}")
                
                if os.path.exists(cls_model_dir):
                    init_params['cls_model_dir'] = cls_model_dir
                    if self.debug:
                        print(f"使用分类模型: {cls_model_dir}")
            else:
                if self.debug:
                    print("使用PaddleOCR默认模型（首次使用需要下载）")
            
            # 初始化OCR引擎
            self.ocr_engine = PaddleOCR(**init_params)
            
            if self.debug:
                print("✅ OCR引擎初始化成功")
                
        except Exception as e:
            error_msg = f"OCR引擎初始化失败: {e}"
            
            # 如果是模型下载失败，提供解决方案
            if "download" in str(e).lower() or "model" in str(e).lower():
                error_msg += "\n\n模型下载失败，请："
                error_msg += "\n1. 检查网络连接"
                error_msg += "\n2. 或手动下载模型文件"
                error_msg += "\n3. 或指定已有的模型目录"
            
            if self.debug:
                print(f"❌ {error_msg}")
            
            raise RuntimeError(error_msg)
    
    def _test_ocr_simple(self) -> bool:
        """简单测试OCR引擎"""
        try:
            # 创建测试图片
            img = np.ones((100, 300, 3), dtype=np.uint8) * 255
            cv2.putText(img, "TEST", (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
            cv2.putText(img, "测试", (30, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
            
            # 保存测试图片
            test_path = "test_ocr_temp.jpg"
            cv2.imwrite(test_path, img)
            
            # 识别
            result = self.ocr_engine.ocr(test_path, cls=False)
            
            # 删除临时文件
            if os.path.exists(test_path):
                os.remove(test_path)
            
            # 解析结果
            if result and isinstance(result, list) and len(result) > 0:
                texts = []
                for line in result[0]:
                    if line and len(line) >= 2:
                        if isinstance(line[1], (list, tuple)) and len(line[1]) >= 1:
                            text = str(line[1][0])
                            texts.append(text)
                
                if texts:
                    logger.info(f"测试识别到文本: {texts}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"测试失败: {e}")
            return False
    
    def _enhance_red(self, img_array: np.ndarray) -> np.ndarray:
        """增强图像中红色区域，返回彩色图像。

        该方法将红色区域转换为高亮灰度，然后与原灰度图混合，目的是
        让PaddleOCR检测到红色字符。"""
        try:
            hsv = cv2.cvtColor(img_array, cv2.COLOR_BGR2HSV)
            # 红色分为两个区间
            lower1 = np.array([0, 50, 50])
            upper1 = np.array([10, 255, 255])
            lower2 = np.array([170, 50, 50])
            upper2 = np.array([180, 255, 255])
            mask1 = cv2.inRange(hsv, lower1, upper1)
            mask2 = cv2.inRange(hsv, lower2, upper2)
            mask = cv2.bitwise_or(mask1, mask2)
            red_gray = cv2.bitwise_and(cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY), mask)
            gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
            combined = cv2.addWeighted(gray, 1.0, red_gray, 1.0, 0)
            # convert back to BGR for OCR engine
            return cv2.cvtColor(combined, cv2.COLOR_GRAY2BGR)
        except Exception as e:
            logger.warning(f"增强红色失败: {e}")
            return img_array

    def _remove_red_watermark(self, img_array: np.ndarray) -> np.ndarray:
        """将图像中的红色水印区域用白色覆盖，减少干扰"""
        try:
            hsv = cv2.cvtColor(img_array, cv2.COLOR_BGR2HSV)
            lower1 = np.array([0, 50, 50])
            upper1 = np.array([10, 255, 255])
            lower2 = np.array([170, 50, 50])
            upper2 = np.array([180, 255, 255])
            mask1 = cv2.inRange(hsv, lower1, upper1)
            mask2 = cv2.inRange(hsv, lower2, upper2)
            mask = cv2.bitwise_or(mask1, mask2)
            result = img_array.copy()
            result[mask > 0] = (255, 255, 255)
            return result
        except Exception as e:
            logger.warning(f"去除红色水印失败: {e}")
            return img_array

    def _desaturate_red(self, img_array: np.ndarray) -> np.ndarray:
        """将图像中红色区域去饱和，保留亮度信息，这样水印变灰，底层内容保留。"""
        try:
            hsv = cv2.cvtColor(img_array, cv2.COLOR_BGR2HSV)
            # 红色范围
            lower1 = np.array([0, 50, 50])
            upper1 = np.array([10, 255, 255])
            lower2 = np.array([170, 50, 50])
            upper2 = np.array([180, 255, 255])
            mask1 = cv2.inRange(hsv, lower1, upper1)
            mask2 = cv2.inRange(hsv, lower2, upper2)
            mask = cv2.bitwise_or(mask1, mask2)
            hsv_out = hsv.copy()
            hsv_out[mask > 0, 1] = 0  # saturation zero
            return cv2.cvtColor(hsv_out, cv2.COLOR_HSV2BGR)
        except Exception as e:
            logger.warning(f"去饱和红色失败: {e}")
            return img_array

    def _preprocess_image(self, img_array: np.ndarray) -> np.ndarray:
        """预处理图片"""
        try:
            # 转换为灰度
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
            else:
                gray = img_array.copy()
            
            # 提高对比度
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            
            # 二值化
            _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # 转换为RGB
            if len(binary.shape) == 2:
                result = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
            else:
                result = binary
            
            return result
            
        except Exception as e:
            logger.warning(f"预处理失败: {e}")
            return img_array

    def _split_red_black_layers(self, img_array: np.ndarray):
        """将图像拆分为红字层和黑字层（白底黑字），用于分层OCR。"""
        try:
            hsv = cv2.cvtColor(img_array, cv2.COLOR_BGR2HSV)

            # 红色掩码（两个色相区间）
            lower1 = np.array([0, 50, 40])
            upper1 = np.array([12, 255, 255])
            lower2 = np.array([168, 50, 40])
            upper2 = np.array([180, 255, 255])
            red_mask = cv2.bitwise_or(
                cv2.inRange(hsv, lower1, upper1),
                cv2.inRange(hsv, lower2, upper2)
            )

            # 黑色掩码（低亮度）
            lower_black = np.array([0, 0, 0])
            upper_black = np.array([180, 255, 95])
            black_mask = cv2.inRange(hsv, lower_black, upper_black)
            # 避免红黑重叠干扰
            black_mask = cv2.bitwise_and(black_mask, cv2.bitwise_not(red_mask))

            gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)

            # 生成白底图：保留掩码区域为原灰度，其他变白
            red_only = np.ones_like(gray) * 255
            red_only[red_mask > 0] = gray[red_mask > 0]

            black_only = np.ones_like(gray) * 255
            black_only[black_mask > 0] = gray[black_mask > 0]

            red_bgr = cv2.cvtColor(red_only, cv2.COLOR_GRAY2BGR)
            black_bgr = cv2.cvtColor(black_only, cv2.COLOR_GRAY2BGR)
            return red_bgr, black_bgr
        except Exception as e:
            logger.warning(f"红黑分层失败: {e}")
            return None, None

    def _run_ocr_try(self, img_try: np.ndarray, desc: str = ""):
        """对单张图进行OCR尝试，返回首个有效结果。"""
        for cls_mode in (False, True):
            try:
                logger.info(f"OCR调用 cls={cls_mode} on {desc}")
                # 注意：PaddleOCR 的 ocr() 不支持在此动态传入 det_db_box_thresh/drop_score
                res = self.ocr_engine.ocr(img_try, cls=cls_mode)
                if res and res[0]:
                    return res
            except Exception as e:
                logger.warning(f"OCR尝试失败 {desc}: {e}")
        return None

    def _score_text_quality(self, text: str) -> float:
        """粗略评估OCR文本质量，分数越高表示越可读。"""
        try:
            if not text:
                return 0.0
            t = text.strip()
            if not t:
                return 0.0

            chinese = len(re.findall(r'[\u4e00-\u9fff]', t))
            words = len([x for x in re.split(r'\s+', t) if x])
            noisy = len(re.findall(r'[xX＊*]{2,}|[=]{2,}|[#]{2,}', t))
            symbols = len(re.findall(r'[^\u4e00-\u9fff\w\s，。；：、（）《》“”‘’\-—\.,;:!?]', t))

            keywords = ('关于', '通知', '通告', '请示', '报告', '批复', '函', '纪要', '文号', '附件', '发电单位', '发文单位', '密级', '等级', '签发')
            kw_hit = sum(1 for k in keywords if k in t)

            score = chinese * 1.2 + words * 0.3 + kw_hit * 8 - noisy * 6 - symbols * 0.5
            return float(max(score, 0.0))
        except Exception:
            return 0.0

    def _normalize_common_ocr_errors(self, text: str) -> str:
        """对常见OCR误识别做轻量归一化（仅做高置信、低风险替换）。"""
        t = text or ''
        if not t:
            return t
        # 常见专名修正
        t = t.replace('华中科技大子', '华中科技大学')
        t = t.replace('华中我技大学', '华中科技大学')
        # 文号常见尾字误识别
        t = t.replace('硚号', '号').replace('研号', '号')
        # OCR把XX识别成双X/那双等的常见情况
        t = t.replace('双X', 'XX').replace('X双', 'XX')
        # 仅在“发电【年份】”语境下替换前缀，降低误伤
        t = re.sub(r'那双发电([【\[]\d{4}[】\]])', r'鄂XX发电\1', t)
        return t

    def _estimate_skew_angle(self, img_array: np.ndarray) -> float:
        """估计页面倾斜角（度）。正负号仅表示方向。"""
        try:
            gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY) if len(img_array.shape) == 3 else img_array
            edges = cv2.Canny(gray, 60, 180, apertureSize=3)
            lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=120, minLineLength=120, maxLineGap=12)
            if lines is None:
                return 0.0
            angles = []
            for l in lines[:200]:
                x1, y1, x2, y2 = l[0]
                dx = x2 - x1
                dy = y2 - y1
                if dx == 0:
                    continue
                angle = np.degrees(np.arctan2(dy, dx))
                # 仅保留接近水平线，降低噪声影响
                if -25 <= angle <= 25:
                    angles.append(angle)
            if not angles:
                return 0.0
            return float(np.median(angles))
        except Exception:
            return 0.0

    def _assess_image_quality(self, img_array: np.ndarray) -> Dict[str, Any]:
        """图像质量评估（清晰度/亮度/倾斜）。"""
        try:
            gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY) if len(img_array.shape) == 3 else img_array
            blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            brightness = float(np.mean(gray))
            skew_angle = self._estimate_skew_angle(img_array)

            warnings = []
            if blur_score < 80:
                warnings.append(f"图片可能模糊（清晰度={blur_score:.1f}）")
            if brightness < 70:
                warnings.append(f"图片偏暗（亮度={brightness:.1f}）")
            elif brightness > 210:
                warnings.append(f"图片偏亮（亮度={brightness:.1f}）")
            if abs(skew_angle) > 3.0:
                warnings.append(f"页面倾斜约 {skew_angle:.1f}°")

            return {
                'blur_score': blur_score,
                'brightness': brightness,
                'skew_angle': skew_angle,
                'warnings': warnings,
                'is_low_quality': len(warnings) > 0,
            }
        except Exception:
            return {
                'blur_score': 0.0,
                'brightness': 0.0,
                'skew_angle': 0.0,
                'warnings': [],
                'is_low_quality': False,
            }

    def _rotate_image(self, img_array: np.ndarray, angle: float) -> np.ndarray:
        """按给定角度旋转图像并保持边界。"""
        h, w = img_array.shape[:2]
        center = (w // 2, h // 2)
        m = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(img_array, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    def _extract_field_hints_from_text(self, text: str) -> Dict[str, str]:
        """从文本快速提取字段候选，用于多候选投票。"""
        if not text:
            return {'document_no': '', 'title': '', 'issuing_unit': '', 'date': ''}

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        doc_no = ''
        title = ''
        unit = ''
        date = ''

        doc_patterns = [
            # 标准发文字号
            r'([\u4e00-\u9fa5A-Za-z]{1,30}(?:发电|发|办)[〔\[（(]?\d{4}[〕\]）)]?\s*\d{1,5}\s*号?)',
            # 电报常见残缺：仅到“发电【2026】”
            r'([\u4e00-\u9fa5A-Za-z]{1,20}(?:发电|发|办)[【〔\[（(]?\d{4}[】〕\]）)]?)',
            # 允许中间有空格的变体，如“鄂 XX 发（2012）10 号”
            r'([\u4e00-\u9fa5A-Za-z]{1,10}\s*[\u4e00-\u9fa5A-Za-z]{0,10}\s*(?:发电|发|办)\s*[〔\[（(]?\d{4}[〕\]）)]?\s*\d{1,5}\s*号?)',
            # 无“发/办”字样但带年份括号的简写，如“鄂XX（2026）1号”
            r'((?!\d{4}年)[\u4e00-\u9fa5A-Za-z]{1,16}[〔\[（(]?\d{4}[〕\]）)]?\s*[\u4e00-\u9fa5A-Za-z0-9]{0,5}\s*号)',
            r'文号[：:\s]*([^\n，。；;]{4,60}号?)',
            r'文号[：:\s]*([A-Za-z0-9\-]{6,30})'
        ]
        for p in doc_patterns:
            m = re.search(p, text)
            if m:
                doc_no = (m.group(1) or '').strip()
                break
        if not doc_no:
            compact = re.sub(r'\s+', '', text)
            # 跨行断裂容错：如“某某发电【2026】硚号”
            cm = re.search(r'([\u4e00-\u9fa5A-Za-z]{1,20}(?:发电|发|办)?[【〔\[（(]?\d{4}[】〕\]）)]?[\u4e00-\u9fa5A-Za-z0-9]{0,8}号)', compact)
            if cm:
                doc_no = cm.group(1)

        title_keywords = ('关于', '通知', '通告', '请示', '报告', '批复', '函', '纪要', '决定', '意见', '方案', '办法')
        title_candidates = []
        for ln in lines[:60]:
            if not (6 <= len(ln) <= 120):
                continue
            if not any(k in ln for k in title_keywords):
                continue
            if re.fullmatch(r'[\d\-_/]+', ln):
                continue
            if '拟稿' in ln or '联系电话' in ln or '抄送' in ln:
                continue
            title_candidates.append(ln)

        def _score_title_candidate(s: str) -> float:
            score = 0.0
            if '关于' in s:
                score += 6
            if any(x in s for x in ('通知', '通告', '请示', '报告', '批复', '函')):
                score += 5
            if 12 <= len(s) <= 60:
                score += 3
            if s.count('，') + s.count('。') >= 3:
                score -= 2
            return score

        if title_candidates:
            title = max(title_candidates, key=_score_title_candidate)

        unit_keywords = ('大学', '学院', '委员会', '办公室', '政府', '党委', '局', '厅', '部', '中心', '公司')
        for ln in lines[:60]:
            if not (2 <= len(ln) <= 40):
                continue
            if not any(k in ln for k in unit_keywords):
                continue
            # 避免把标题、正文句子当单位
            if any(k in ln for k in ('关于', '通知', '请示', '报告', '任务书', '单位:')):
                continue
            if ln.count('，') + ln.count('。') >= 2:
                continue
            unit = ln
            break

        dm = re.search(r'(\d{4}\s*[年\-/]\s*\d{1,2}\s*[月\-/]\s*\d{1,2}\s*日?)', text)
        if dm:
            date = re.sub(r'\s+', '', dm.group(1))

        return {'document_no': doc_no, 'title': title, 'issuing_unit': unit, 'date': date}

    def _vote_best_field_hints(self, texts: List[str]) -> Dict[str, str]:
        """基于多候选OCR文本进行字段级投票择优。"""
        def score_doc_no(s: str) -> float:
            if not s:
                return -1
            score = 0.0
            if '号' in s:
                score += 5
            if re.search(r'〔\d{4}〕|[（(\[]\d{4}[）)\]]', s):
                score += 6
            if re.search(r'(发|办)', s):
                score += 2
            if re.fullmatch(r'\d+', s):
                score -= 6
            if len(s) > 40:
                score -= 3
            return score

        def score_title(s: str) -> float:
            if not s:
                return -1
            score = 0.0
            keywords = ('关于', '通知', '通告', '请示', '报告', '批复', '函', '纪要', '决定', '意见', '方案', '办法')
            if any(k in s for k in keywords):
                score += 6
            if 8 <= len(s) <= 90:
                score += 4
            if re.fullmatch(r'[\d\-_/]+', s):
                score -= 10
            return score

        def score_unit(s: str) -> float:
            if not s:
                return -1
            score = 0.0
            kws = ('大学', '学院', '委员会', '办公室', '政府', '党委', '局', '厅', '部', '中心', '公司')
            if any(k in s for k in kws):
                score += 6
            if len(s) <= 30:
                score += 2
            return score

        def score_date(s: str) -> float:
            if not s:
                return -1
            score = 0.0
            m = re.search(r'(\d{4})', s)
            if m:
                y = int(m.group(1))
                if 2020 <= y <= 2100:
                    score += 6
                elif 2000 <= y < 2020:
                    score += 2
                else:
                    score -= 3
            if '日' in s:
                score += 2
            if '年' in s and '月' in s:
                score += 2
            return score

        hints_all = [self._extract_field_hints_from_text(t) for t in texts if t]
        if not hints_all:
            return {'document_no': '', 'title': '', 'issuing_unit': '', 'date': ''}

        doc_nos = [h.get('document_no', '') for h in hints_all if h.get('document_no')]
        titles = [h.get('title', '') for h in hints_all if h.get('title')]
        units = [h.get('issuing_unit', '') for h in hints_all if h.get('issuing_unit')]
        dates = [h.get('date', '') for h in hints_all if h.get('date')]

        return {
            'document_no': max(doc_nos, key=score_doc_no) if doc_nos else '',
            'title': max(titles, key=score_title) if titles else '',
            'issuing_unit': max(units, key=score_unit) if units else '',
            'date': max(dates, key=score_date) if dates else '',
        }

    def merge_ocr_results(self, page_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """将多页OCR结果合并为单份文档结果（适用于红头1/2这类分页文件）。"""
        valid = [r for r in (page_results or []) if isinstance(r, dict)]
        if not valid:
            return {'success': False, 'text': '', 'field_hints': {}, 'quality_warnings': []}

        texts = [r.get('text', '') for r in valid if r.get('text')]
        merged_text = '\n'.join(texts).strip()

        # 文本投票为主，页级field_hints作为补充
        text_vote = self._vote_best_field_hints(texts)
        hint_pool = [r.get('field_hints') or {} for r in valid]

        def pick_first(field: str) -> str:
            for h in hint_pool:
                v = (h.get(field) or '').strip()
                if v:
                    return v
            return ''

        merged_hints = {
            'document_no': text_vote.get('document_no') or pick_first('document_no'),
            'title': text_vote.get('title') or pick_first('title'),
            'issuing_unit': text_vote.get('issuing_unit') or pick_first('issuing_unit'),
            'date': text_vote.get('date') or pick_first('date'),
        }

        warnings = []
        for r in valid:
            warnings.extend(r.get('quality_warnings', []) or [])

        return {
            'success': any(r.get('success') for r in valid),
            'text': merged_text,
            'field_hints': merged_hints,
            'quality_warnings': warnings,
        }
    
    def _extract_text_from_result(self, result: List) -> List[Dict]:
        """从OCR结果提取文本 - 根据您的输出格式修复"""
        lines = []
        
        if not result or not isinstance(result, list):
            return lines
        
        try:
            for page_idx, page in enumerate(result):
                if not page or not isinstance(page, list):
                    continue
                
                for box_idx, box_info in enumerate(page):
                    if not box_info or len(box_info) < 2:
                        continue
                    
                    # 提取坐标
                    points = []
                    if isinstance(box_info[0], list):
                        points = [[float(p[0]), float(p[1])] for p in box_info[0]]
                    
                    # 提取文本和置信度
                    text = ""
                    confidence = 0.5
                    
                    if isinstance(box_info[1], (list, tuple)):
                        if len(box_info[1]) >= 1:
                            text = str(box_info[1][0])
                        if len(box_info[1]) >= 2:
                            try:
                                confidence = float(box_info[1][1])
                            except:
                                confidence = .5
                    else:
                        text = str(box_info[1])
                    
                    if text and text.strip():
                        # 计算边界框
                        bbox = {}
                        if points:
                            x_coords = [p[0] for p in points]
                            y_coords = [p[1] for p in points]
                            bbox = {
                                'x_min': min(x_coords),
                                'y_min': min(y_coords),
                                'x_max': max(x_coords),
                                'y_max': max(y_coords)
                            }
                        
                        lines.append({
                            'page': page_idx + 1,
                            'index': box_idx,
                            'text': text.strip(),
                            'confidence': confidence,
                            'bbox': bbox,
                            'points': points
                        })
            
            return lines
            
        except Exception as e:
            logger.error(f"提取文本异常: {e}")
            if self.debug:
                logger.error(traceback.format_exc())
            return []
    def extract_document_info(self, ocr_result):
        """从OCR结果提取公文信息 - 修复版"""
        try:
            # 确保有OCR结果
            if not ocr_result or not ocr_result.get('success') or not ocr_result.get('text'):
                return {}
            
            text = ocr_result.get('text', '')
            
            # 初始化结果字典
            info = {
                'document_no': ((ocr_result.get('field_hints') or {}).get('document_no') or ''),
                'title': ((ocr_result.get('field_hints') or {}).get('title') or ''),
                'issuing_unit': ((ocr_result.get('field_hints') or {}).get('issuing_unit') or ''),
                'date': ((ocr_result.get('field_hints') or {}).get('date') or ''),
                'keywords': [],
                'content_summary': text[:300] if text else ''
            }
            
            # 1. 提取文号
            import re
            
            # 常见的文号格式
            patterns = [
                r'〔(.*?)〕\s*\d+\s*号',
                r'[\[【〔](.*?)[】〕\]]\s*\d+\s*号',
                r'文\s*号\s*[:：]\s*(.*?)[\s\n]',
                r'\d{4}\s*[\[【〔].*?[】〕\]]\s*\d+号',
                r'文\s*号\s*[:：]\s*([A-Za-z0-9\-]{6,30})',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    info['document_no'] = match.group(0).strip()
                    break
            
            # 2. 提取标题
            # 寻找包含"关于"的行，通常这是标题
            lines = text.split('\n')
            for line in lines:
                if '关于' in line and len(line) > 10 and len(line) < 200:
                    info['title'] = line.strip()
                    break
            
            # 如果没有找到，使用第一行非空文本作为标题
            if not info['title']:
                for line in lines:
                    if line.strip() and len(line.strip()) > 5:
                        info['title'] = line.strip()
                        break
            
            # 3. 提取发文单位
            # 常见的单位关键词
            unit_keywords = ['院', '校', '局', '部', '厅', '办公室', '委员会', '政府', '党委', '公司', '中心']
            for line in lines:
                for keyword in unit_keywords:
                    if keyword in line and len(line) < 50:
                        info['issuing_unit'] = line.strip()
                        break
                if info['issuing_unit']:
                    break
            
            # 4. 提取日期
            date_patterns = [
                r'\d{4}年\d{1,2}月\d{1,2}日',
                r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    info['date'] = match.group(0)
                    break
            
            # 5. 提取关键词
            keywords = ['通知', '报告', '请示', '批复', '函', '纪要', '决定', '意见', '方案', '办法', '规定', '条例']
            found_keywords = []
            for keyword in keywords:
                if keyword in text:
                    found_keywords.append(keyword)
            info['keywords'] = found_keywords
            
            return info
            
        except Exception as e:
            print(f"提取公文信息失败: {e}")
            return {}    
    
    def process_image(self, image_path: str, preprocess: bool = True, save_debug: bool = True) -> Dict[str, Any]:
        """处理图片文件

        :param save_debug: 如果为True，总是保存变体图像到 ocr_debug 目录，
                           便于诊断即使self.debug为False也会保存。"""
        start_time = time.time()
        # compute debug directory path upfront
        debug_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ocr_debug"))
        if self.debug or save_debug:
            logger.info(f"调试目录: {debug_dir}")
        
        try:
            if not os.path.exists(image_path):
                return {
                    'success': False,
                    'text': '',
                    'lines': [],
                    'processing_time': time.time() - start_time,
                    'error': f'文件不存在: {image_path}'
                }
            
            logger.info(f"处理图片: {image_path}")
            
            # 读取图片（cv2.imread 对包含中文路径支持不好，先尝试PIL）
            img_array = None
            try:
                img_array = cv2.imread(image_path)
            except Exception:
                img_array = None
            if img_array is None:
                # 尝试使用 PIL 打开并转换为 numpy
                try:
                    pil_img = Image.open(image_path).convert('RGB')
                    img_array = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                except Exception as e:
                    return {
                        'success': False,
                        'text': '',
                        'lines': [],
                        'processing_time': time.time() - start_time,
                        'error': f'无法读取图片文件: {e}'
                    }
            
            height, width = img_array.shape[:2]
            logger.info(f"图片尺寸: {width}x{height}")

            # P0-1: 图像质量评估与纠偏
            quality = self._assess_image_quality(img_array)
            quality_warnings = quality.get('warnings', [])
            if quality_warnings:
                logger.warning("图像质量提示: " + "；".join(quality_warnings))

            # 倾斜明显时先纠偏（轻度旋转）
            skew_angle = float(quality.get('skew_angle') or 0.0)
            if abs(skew_angle) > 1.5:
                try:
                    img_array = self._rotate_image(img_array, -skew_angle)
                    logger.info(f"已执行自动纠偏: {-skew_angle:.2f}°")
                except Exception as e:
                    logger.warning(f"自动纠偏失败: {e}")

            # 先尝试红黑分层识别（红色内容在上，黑色内容在下），但不直接返回，后续与常规流程择优
            split_candidate = None
            try:
                red_img, black_img = self._split_red_black_layers(img_array)
                if red_img is not None and black_img is not None:
                    red_res = self._run_ocr_try(red_img, "红字层")
                    black_res = self._run_ocr_try(black_img, "黑字层")

                    red_lines = self._extract_text_from_result(red_res) if red_res else []
                    black_lines = self._extract_text_from_result(black_res) if black_res else []

                    # 分层结果先暂存，后续与常规流程比质量分择优
                    if len(red_lines) + len(black_lines) >= 2:
                        red_text = '\n'.join([ln['text'] for ln in red_lines])
                        black_text = '\n'.join([ln['text'] for ln in black_lines])

                        merged_lines = []
                        for ln in red_lines:
                            item = dict(ln)
                            item['layer'] = 'red'
                            merged_lines.append(item)
                        for ln in black_lines:
                            item = dict(ln)
                            item['layer'] = 'black'
                            merged_lines.append(item)

                        combined_text = '\n'.join([t for t in [red_text, black_text] if t]).strip()
                        split_candidate = {
                            'success': True,
                            'text': combined_text,
                            'red_text': red_text,
                            'black_text': black_text,
                            'lines': merged_lines,
                            'image_size': (width, height)
                        }
                        logger.info(f"分层识别候选: red={len(red_lines)} black={len(black_lines)}")
            except Exception as e:
                logger.warning(f"分层识别尝试失败，回退到常规流程: {e}")
            
            # 准备不同版本的图像用于多次尝试识别
            ocr_result = None
            variants = []  # list of (image, description)
            variants.append((img_array, "原图"))
            try:
                red_img = self._enhance_red(img_array)
                variants.append((red_img, "红色增强"))
            except Exception:
                pass
            try:
                inv_img = cv2.bitwise_not(img_array)
                variants.append((inv_img, "反转图"))
            except Exception:
                pass
            try:
                rmw = self._remove_red_watermark(img_array)
                variants.append((rmw, "去红水印"))
            except Exception:
                pass
            try:
                ds = self._desaturate_red(img_array)
                variants.append((ds, "去饱和红"))
            except Exception:
                pass
            # sharpen variant
            try:
                kernel = np.array([[0,-1,0],[-1,5,-1],[0,-1,0]])
                sharp = cv2.filter2D(img_array, -1, kernel)
                variants.append((sharp, "锐化图"))
            except Exception:
                pass
            # upscale variant (small fonts / faint text)
            try:
                up = cv2.resize(img_array, None, fx=1.6, fy=1.6, interpolation=cv2.INTER_CUBIC)
                variants.append((up, "放大图"))
            except Exception:
                pass
            # denoise variant
            try:
                dn = cv2.fastNlMeansDenoisingColored(img_array, None, 6, 6, 7, 21)
                variants.append((dn, "去噪图"))
            except Exception:
                pass
            # histogram equalization
            try:
                gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
                eq = cv2.equalizeHist(gray)
                eq_col = cv2.cvtColor(eq, cv2.COLOR_GRAY2BGR)
                variants.append((eq_col, "直方图均衡"))
            except Exception:
                pass

            # adaptive threshold variant (may help with faint/grey watermarks)
            try:
                gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
                adap = cv2.adaptiveThreshold(gray, 255,
                                             cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                             cv2.THRESH_BINARY, 11, 2)
                variants.append((cv2.cvtColor(adap, cv2.COLOR_GRAY2BGR), "自适应阈值"))
            except Exception:
                pass

            # morphological opening to remove background noise
            try:
                gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
                _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                kernel = np.ones((3, 3), np.uint8)
                morph = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)
                variants.append((cv2.cvtColor(morph, cv2.COLOR_GRAY2BGR), "开运算"))
            except Exception:
                pass

            # 如果需要预处理，也把预处理版本加入列表
            if preprocess:
                proc = self._preprocess_image(img_array)
                variants.append((proc, "预处理图"))

            # debug: 保存每个变体图片
            # 保存变体图像（debug或save_debug任一为True）
            if self.debug or save_debug:
                # ensure debug_dir inside project workspace
                debug_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ocr_debug"))
                os.makedirs(debug_dir, exist_ok=True)
                for i, (img_var, desc) in enumerate(variants):
                    try:
                        filename = f"variant_{i}_{desc.replace(' ','_')}.jpg"
                        path = os.path.join(debug_dir, filename)
                        cv2.imwrite(path, img_var)
                        logger.info(f"保存变体图像: {path}")
                    except Exception as e:
                        logger.warning(f"无法保存变体 {desc}: {e}")

            # P0-2: 多路OCR候选评分择优（不再在ocr()动态传非法参数）
            ocr_candidates = []
            for img_try, desc in variants:
                logger.info(f"尝试变体: {desc}")
                res = self._run_ocr_try(img_try, desc)
                if not res or not res[0]:
                    continue
                lines_try = self._extract_text_from_result(res)
                if not lines_try:
                    continue
                text_try = '\n'.join([ln['text'] for ln in lines_try]).strip()
                text_try = self._normalize_common_ocr_errors(text_try)
                conf_avg = float(np.mean([float(ln.get('confidence', 0.0) or 0.0) for ln in lines_try])) if lines_try else 0.0
                score_try = self._score_text_quality(text_try) + conf_avg * 20 + min(len(lines_try), 120) * 0.15
                ocr_candidates.append({
                    'desc': desc,
                    'result': res,
                    'lines': lines_try,
                    'text': text_try,
                    'score': score_try,
                    'avg_conf': conf_avg,
                })

            if ocr_candidates:
                ocr_candidates.sort(key=lambda x: x['score'], reverse=True)
                best = ocr_candidates[0]
                ocr_result = best['result']
                lines = best['lines']
                combined_text = best['text']
                logger.info(f"候选择优采用: {best['desc']} score={best['score']:.2f} avg_conf={best['avg_conf']:.3f}")
            else:
                ocr_result = None

            
            
            if not ocr_result:
                low_quality_hint = ""
                if quality_warnings:
                    low_quality_hint = "；".join(quality_warnings)
                return {
                    'success': False,
                    'text': '',
                    'lines': [],
                    'image_size': (width, height),
                    'processing_time': time.time() - start_time,
                    'error': f"OCR识别失败，无结果返回{('。' + low_quality_hint) if low_quality_hint else ''}",
                    'quality_assessment': quality,
                    'quality_warnings': quality_warnings,
                }

            if not lines:
                logger.warning("未提取到文本")
                return {
                    'success': False,
                    'text': '',
                    'lines': [],
                    'image_size': (width, height),
                    'processing_time': time.time() - start_time,
                    'error': '未识别到文本内容',
                    'quality_assessment': quality,
                    'quality_warnings': quality_warnings,
                }

            # 合并文本
            all_text = [line['text'] for line in lines]

            # 与分层候选对比质量，择优输出
            use_split = False
            if split_candidate and split_candidate.get('text'):
                base_score = self._score_text_quality(combined_text)
                split_score = self._score_text_quality(split_candidate.get('text', ''))
                # 只有分层结果明显更好时才采用，避免分层误伤造成文本破碎
                if split_score >= base_score + 8:
                    use_split = True
                logger.info(f"文本质量分: 常规={base_score:.1f}, 分层={split_score:.1f}, 采用分层={use_split}")

            # P0-2（字段级）: 多候选字段投票
            vote_texts = [c.get('text', '') for c in (ocr_candidates or []) if c.get('text')]
            if split_candidate and split_candidate.get('text'):
                vote_texts.append(split_candidate.get('text', ''))
            field_hints = self._vote_best_field_hints(vote_texts)

            if use_split:
                processing_time = time.time() - start_time
                return {
                    'success': True,
                    'text': self._normalize_common_ocr_errors(split_candidate.get('text', '')),
                    'red_text': split_candidate.get('red_text', ''),
                    'black_text': split_candidate.get('black_text', ''),
                    'lines': split_candidate.get('lines', []),
                    'image_size': (width, height),
                    'processing_time': processing_time,
                    'error': '',
                    'color_split_used': True,
                    'quality_assessment': quality,
                    'quality_warnings': quality_warnings,
                    'field_hints': field_hints,
                }
            
            processing_time = time.time() - start_time
            logger.info(f"✅ 识别成功: {len(lines)} 行文本, 耗时: {processing_time:.2f}秒")
            
            if self.debug and len(all_text) > 0:
                for i, text in enumerate(all_text[:5]):
                    logger.info(f"  行{i}: '{text}'")
                if len(all_text) > 5:
                    logger.info(f"  ... 还有 {len(all_text) - 5} 行")
            
            return {
                'success': True,
                'text': self._normalize_common_ocr_errors(combined_text),
                'lines': lines,
                'image_size': (width, height),
                'processing_time': processing_time,
                'error': '',
                'quality_assessment': quality,
                'quality_warnings': quality_warnings,
                'field_hints': field_hints,
                'color_split_used': False,
            }
            
        except Exception as e:
            error_msg = f"图片处理异常: {e}"
            logger.error(error_msg)
            if self.debug:
                logger.error(traceback.format_exc())
            return {
                'success': False,
                'text': '',
                'lines': [],
                'processing_time': time.time() - start_time,
                'error': error_msg
            }
    
    def process_pdf(self, pdf_path, page_limit=5, dpi=200):
        """处理PDF文件"""
        if not self.has_pdf2image:
            return {
                'success': False,
                'text': '',
                'error': '未安装pdf2image，无法处理PDF。请运行: pip install pdf2image'
            }
        
        try:
            from pdf2image import convert_from_path
            
            if not os.path.exists(pdf_path):
                return {'success': False, 'text': '', 'error': 'PDF文件不存在'}
            
            print(f"正在处理PDF: {pdf_path}")
            
            # 转换PDF为图片
            images = []
            
            try:
                if self.poppler_path:
                    # 使用指定的poppler路径
                    images = convert_from_path(
                        pdf_path,
                        poppler_path=self.poppler_path,
                        dpi=dpi,
                        first_page=1,
                        last_page=page_limit
                    )
                else:
                    # 尝试自动查找poppler
                    images = convert_from_path(
                        pdf_path,
                        dpi=dpi,
                        first_page=1,
                        last_page=page_limit
                    )
                    
            except Exception as e:
                print(f"PDF转换失败: {e}")
                return {
                    'success': False,
                    'text': '',
                    'error': f'PDF转换失败: {e}\n请安装poppler: https://github.com/oschwartz10612/poppler-windows/releases\n解压到 C:\\poppler'
                }
            
            if not images:
                return {'success': False, 'text': '', 'error': 'PDF转换无结果'}
            
            print(f"PDF转换完成: {len(images)} 页")
            
            # 处理每一页
            all_texts = []
            
            for page_idx, page_img in enumerate(images, 1):
                print(f"处理第 {page_idx}/{len(images)} 页...")
                
                # 保存为临时文件
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                    temp_path = temp_file.name
                    page_img.save(temp_path, 'JPEG')
                
                try:
                    # 调用您现有的process_image方法
                    result = self.process_image(temp_path, preprocess=True)
                    
                    if result.get('success') and result.get('text', '').strip():
                        all_texts.append(f"=== 第{page_idx}页 ===\n{result['text']}")
                    else:
                        all_texts.append(f"=== 第{page_idx}页 ===\n[识别失败: {result.get('error', '未知错误')}]")
                        
                except Exception as e:
                    all_texts.append(f"=== 第{page_idx}页 ===\n[处理异常: {e}]")
                finally:
                    # 清理临时文件
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except:
                            pass
            
            # 合并结果
            if all_texts:
                return {
                    'success': True,
                    'text': "\n\n".join(all_texts),
                    'total_pages': len(images),
                    'successful_pages': len([t for t in all_texts if "[识别失败]" not in t and "[处理异常]" not in t])
                }
            else:
                return {'success': False, 'text': '', 'error': '所有页面识别失败'}
                
        except Exception as e:
            return {'success': False, 'text': '', 'error': f'PDF处理异常: {e}'}
    
    def process_file(self, file_path, **kwargs):
        """处理任意文件（自动判断类型）"""
        if not os.path.exists(file_path):
            return {'success': False, 'text': '', 'error': '文件不存在'}
        
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.pdf':
            return self.process_pdf(file_path, **kwargs)
        elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']:
            return self.process_image(file_path, **kwargs)
        else:
            return {'success': False, 'text': '', 'error': f'不支持的文件格式: {ext}'}
        
    def ocr_and_save(self, image_path: str, document_id: int, db_manager) -> tuple:
        """
        执行 OCR 并保存结果到数据库
        :param image_path: 图片路径
        :param document_id: 公文 ID
        :param db_manager: 数据库管理器
        :return: (是否成功, OCR结果路径, OCR文本内容)
        """
        try:
            # 调用现有 OCR 处理逻辑
            result = self.process_image(image_path)
            if not result.get('success'):
                return False, "", result.get('error', 'OCR识别失败')

            ocr_text = result['text']
            
            # 保存 OCR 结果
            ocr_dir = os.path.join("data", "ocr_results")
            os.makedirs(ocr_dir, exist_ok=True)
            
            import hashlib
            import time
            timestamp = int(time.time())
            file_hash = hashlib.md5(image_path.encode()).hexdigest()[:8]
            ocr_filename = f"ocr_{timestamp}_{file_hash}.txt"
            ocr_path = os.path.join(ocr_dir, ocr_filename)
            
            with open(ocr_path, 'w', encoding='utf-8') as f:
                f.write(ocr_text)
            
            # 更新数据库
            success, message = db_manager.update_ocr_result(document_id, ocr_path)
            if success:
                return True, ocr_path, ocr_text
            else:
                return False, "", f"保存OCR结果失败: {message}"
                
        except Exception as e:
            logger.error(f"OCR处理异常: {e}")
            return False, "", f"OCR处理异常: {str(e)}"
