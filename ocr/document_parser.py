# ocr/document_parser.py
"""
公文解析器
从OCR结果中提取结构化信息
"""

import re
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DocumentParser:
    """公文解析器"""
    
    def __init__(self):
        # 常见公文类型
        self.document_types = [
            "通知", "通报", "报告", "请示", "批复", 
            "函", "纪要", "决定", "命令", "公告",
            "通告", "意见", "议案", "决议", "指示"
        ]
        
        # 密级
        self.security_levels = ["普通", "秘密", "机密", "绝密"]
        
        # 紧急程度
        self.urgency_levels = ["普通", "平急", "加急", "特急", "急件"]
        
        # 常见发文单位关键词
        self.unit_keywords = [
            "局", "部", "厅", "办公室", "委员会", "政府", 
            "党委", "公司", "学院", "学校", "中心", "所",
            "处", "科", "室", "组", "队", "院"
        ]
    
    def parse_document(self, ocr_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析OCR结果为结构化公文信息
        
        Args:
            ocr_result: OCR处理结果
            
        Returns:
            结构化公文信息
        """
        if not ocr_result.get('success'):
            return {}
        
        text = ocr_result.get('text', '')
        lines = ocr_result.get('lines', [])
        
        result = {
            'document_no': self._parse_document_no(text, lines),
            'title': self._parse_title(text, lines),
            'issuing_unit': self._parse_issuing_unit(text, lines),
            'receiving_unit': self._parse_receiving_unit(text, lines),
            'document_date': self._parse_date(text),
            'document_type': self._parse_document_type(text),
            'security_level': self._parse_security_level(text),
            'urgency_level': self._parse_urgency_level(text),
            'keywords': self._parse_keywords(text),
            'summary': self._parse_summary(text, lines),
            'main_content': self._extract_main_content(text, lines),
            'sender': self._parse_sender(text, lines),
            'receiver': self._parse_receiver(text, lines),
            'copies': self._parse_copies(text),
            'pages': self._parse_pages(text),
            'is_complete': self._check_completeness(text)
        }
        
        return result
    
    def _parse_document_no(self, text: str, lines: List[Dict]) -> str:
        """解析文号"""
        # 文号常见格式
        patterns = [
            r'[\[【〔](.*?)[】〕\]]\s*[第]?\s*(\d+)\s*号',  # [2024]001号
            r'文\s*号\s*[:：]\s*([^\s]+)',               # 文号：001
            r'[（(](\d{4})[）)]\s*(\d+)\s*号',           # (2024)001号
            r'([A-Za-z0-9\-]+)\s*号',                    # ABC-2024-001号
            r'第\s*(\d+)\s*号',                          # 第001号
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                if isinstance(matches[0], tuple):
                    return ''.join(matches[0])
                else:
                    return matches[0]
        
        # 查找包含"号"且长度较短的行
        for line in lines:
            line_text = line.get('text', '')
            if '号' in line_text and len(line_text) < 30:
                # 检查是否包含数字
                if any(char.isdigit() for char in line_text):
                    return line_text.strip()
        
        return ''
    
    def _parse_title(self, text: str, lines: List[Dict]) -> str:
        """解析标题"""
        # 标题特征：包含"关于"，较长，通常在开头
        title_candidates = []
        
        for i, line in enumerate(lines[:20]):  # 只检查前20行
            line_text = line.get('text', '').strip()
            
            # 标题通常包含"关于"且长度适中
            if '关于' in line_text and 10 < len(line_text) < 200:
                title_candidates.append((i, line_text))
        
        if title_candidates:
            # 选择最靠前的候选
            title_candidates.sort(key=lambda x: x[0])
            return title_candidates[0][1]
        
        # 如果没有"关于"，找最长的行
        if lines:
            lines_sorted = sorted(
                [l for l in lines if 20 < len(l.get('text', '')) < 200],
                key=lambda x: len(x.get('text', '')),
                reverse=True
            )
            if lines_sorted:
                return lines_sorted[0].get('text', '').strip()
        
        return ''
    
    def _parse_issuing_unit(self, text: str, lines: List[Dict]) -> str:
        """解析发文单位"""
        # 查找包含单位关键词的行
        for line in lines:
            line_text = line.get('text', '').strip()
            
            # 检查是否包含单位关键词
            for keyword in self.unit_keywords:
                if keyword in line_text and len(line_text) < 100:
                    # 排除明显不是单位的行
                    if not any(word in line_text for word in ['关于', '通知', '报告', '请示']):
                        return line_text
        
        return ''
    
    def _parse_receiving_unit(self, text: str, lines: List[Dict]) -> str:
        """解析主送单位"""
        # 查找"主送"、"收文"等关键词
        keywords = ['主送', '报送', '呈送', '发送', '收文单位', '接收单位']
        
        for i, line in enumerate(lines):
            line_text = line.get('text', '').strip()
            
            for keyword in keywords:
                if keyword in line_text:
                    # 返回当前行或下一行
                    if len(line_text) > len(keyword) + 2:
                        return line_text.replace(keyword, '').strip()
                    elif i + 1 < len(lines):
                        return lines[i + 1].get('text', '').strip()
        
        return ''
    
    def _parse_date(self, text: str) -> str:
        """解析日期"""
        # 多种日期格式
        date_patterns = [
            r'(\d{4})年(\d{1,2})月(\d{1,2})日',  # 2024年1月1日
            r'(\d{4})-(\d{1,2})-(\d{1,2})',      # 2024-01-01
            r'(\d{4})/(\d{1,2})/(\d{1,2})',      # 2024/01/01
            r'(\d{4})\.(\d{1,2})\.(\d{1,2})',    # 2024.01.01
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            if matches:
                year, month, day = matches[0]
                return f"{year}年{int(month)}月{int(day)}日"
        
        return ''
    
    def _parse_document_type(self, text: str) -> str:
        """解析文种"""
        for doc_type in self.document_types:
            if doc_type in text:
                return doc_type
        
        return '其他'
    
    def _parse_security_level(self, text: str) -> str:
        """解析密级"""
        for level in self.security_levels:
            if level in text:
                return level
        
        return '普通'
    
    def _parse_urgency_level(self, text: str) -> str:
        """解析紧急程度"""
        for level in self.urgency_levels:
            if level in text:
                return level
        
        return '普通'
    
    def _parse_keywords(self, text: str) -> List[str]:
        """解析关键词"""
        keywords = []
        
        # 从常见公文类型中提取关键词
        for doc_type in self.document_types:
            if doc_type in text and doc_type not in keywords:
                keywords.append(doc_type)
        
        # 提取其他可能的关键词
        common_terms = ['工作', '管理', '规定', '办法', '条例', '细则', '方案']
        for term in common_terms:
            if term in text and term not in keywords:
                keywords.append(term)
        
        return keywords[:5]  # 最多返回5个
    
    def _parse_summary(self, text: str, lines: List[Dict]) -> str:
        """解析摘要"""
        # 取开头几行非空文本
        summary_lines = []
        
        for line in lines[:10]:
            line_text = line.get('text', '').strip()
            if line_text and len(line_text) > 5:
                # 跳过标题、文号等
                if not any(word in line_text for word in ['关于', '文号', '第', '号']):
                    summary_lines.append(line_text)
            
            if len(summary_lines) >= 3:
                break
        
        return ' '.join(summary_lines)
    
    def _extract_main_content(self, text: str, lines: List[Dict]) -> str:
        """提取正文内容"""
        # 查找正文开始位置（通常从"各"、"为"等开始）
        start_keywords = ['各', '为', '根据', '按照', '经', '现将']
        
        start_index = 0
        for i, line in enumerate(lines):
            line_text = line.get('text', '').strip()
            if line_text and any(line_text.startswith(keyword) for keyword in start_keywords):
                start_index = i
                break
        
        # 提取从开始位置到结尾的内容
        content_lines = []
        for line in lines[start_index:start_index+50]:  # 最多取50行
            line_text = line.get('text', '').strip()
            if line_text:
                content_lines.append(line_text)
        
        return '\n'.join(content_lines)
    
    def _parse_sender(self, text: str, lines: List[Dict]) -> str:
        """解析发文机关负责人"""
        keywords = ['签发', '审核', '拟稿', '负责人']
        
        for i, line in enumerate(lines):
            line_text = line.get('text', '').strip()
            
            for keyword in keywords:
                if keyword in line_text:
                    # 查找冒号后的内容
                    if ':' in line_text or '：' in line_text:
                        parts = re.split(r'[:：]', line_text)
                        if len(parts) > 1:
                            return parts[1].strip()
                    
                    # 或者返回下一行
                    elif i + 1 < len(lines):
                        return lines[i + 1].get('text', '').strip()
        
        return ''
    
    def _parse_receiver(self, text: str, lines: List[Dict]) -> str:
        """解析收文人"""
        keywords = ['收文人', '收件人', '接收人']
        
        for i, line in enumerate(lines):
            line_text = line.get('text', '').strip()
            
            for keyword in keywords:
                if keyword in line_text:
                    if ':' in line_text or '：' in line_text:
                        parts = re.split(r'[:：]', line_text)
                        if len(parts) > 1:
                            return parts[1].strip()
                    elif i + 1 < len(lines):
                        return lines[i + 1].get('text', '').strip()
        
        return ''
    
    def _parse_copies(self, text: str) -> int:
        """解析份数"""
        patterns = [
            r'共\s*(\d+)\s*份',
            r'份\s*数\s*[:：]\s*(\d+)',
            r'(\d+)\s*份',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                try:
                    return int(matches[0])
                except:
                    pass
        
        return 1
    
    def _parse_pages(self, text: str) -> int:
        """解析页数"""
        patterns = [
            r'共\s*(\d+)\s*页',
            r'页\s*数\s*[:：]\s*(\d+)',
            r'(\d+)\s*页',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                try:
                    return int(matches[0])
                except:
                    pass
        
        return 1
    
    def _check_completeness(self, text: str) -> Dict[str, bool]:
        """检查完整性"""
        checks = {
            'has_title': bool(self._parse_title(text, [])),
            'has_document_no': bool(self._parse_document_no(text, [])),
            'has_issuing_unit': bool(self._parse_issuing_unit(text, [])),
            'has_date': bool(self._parse_date(text)),
            'has_content': len(text.strip()) > 100
        }
        
        return checks
