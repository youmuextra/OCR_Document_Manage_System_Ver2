"""文档相关的辅助函数，例如导出文本、格式化等。"""
from datetime import datetime
import os


def format_document_export(doc: dict) -> str:
    """将文档字典转换为可导出的文本格式。

    :param doc: 包含文档字段的字典
    :return: 返回拼接好的字符串
    """
    lines = []
    lines.append("=" * 50)
    lines.append("公文详情")
    lines.append("=" * 50)
    lines.append(f"文号: {doc.get('document_no', '无')}")
    lines.append(f"标题: {doc.get('title', '无')}")
    lines.append(f"发文单位: {doc.get('issuing_unit', '无')}")
    lines.append(f"收文日期: {doc.get('received_date', '无')}")
    lines.append(f"密级: {doc.get('security_level', '无')}")
    lines.append(f"紧急程度: {doc.get('urgency_level', '无')}")
    lines.append(f"文种: {doc.get('document_type', '无')}")
    lines.append(f"份数: {doc.get('copies', '无')}")
    lines.append(f"收文人: {doc.get('receiver', '无')}")
    lines.append(f"存放位置: {doc.get('storage_location', '无')}")
    lines.append("\n内容摘要:")
    lines.append("-" * 30)
    lines.append(doc.get('content_summary', '无'))
    lines.append("\n关键词:")
    lines.append("-" * 30)
    lines.append(doc.get('keywords', '无'))
    lines.append("\n备注:")
    lines.append("-" * 30)
    lines.append(doc.get('remarks', '无'))

    # OCR结果
    ocr_path = doc.get('ocr_result_path', '')
    if ocr_path and os.path.exists(ocr_path):
        try:
            with open(ocr_path, 'r', encoding='utf-8') as f:
                ocr_content = f.read()
            lines.append("\nOCR识别结果:")
            lines.append("-" * 30)
            lines.append(ocr_content)
        except Exception:
            pass

    lines.append("\n" + "=" * 50)
    lines.append(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 50)
    return "\n".join(lines)
