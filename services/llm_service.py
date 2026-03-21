# # services/llm_service.py
#
# import json
# import os
# import re
# import requests
# from typing import Dict, Any
#
# # ----- 直接在代码中写入凭证和地址（可替代环境变量） -----
# # 请修改下面的值为你的实际APIKey、接口地址和模型名。
# API_KEY = "bce-v3/ALTAK-JktPGDNrqjuN28JnfLaTb/dfcf7357a98596b79d2ecffc1f6304a9fc3e8c86"
# API_URL = "https://qianfan.baidubce.com/v2/chat/completions"  # 接口地址
# MODEL   = "ernie-5.0-thinking-preview"                  # 使用的模型
# # ------------------------------------------------------
#
# # 配置说明：
# # 在环境变量中设置 WENXIN_API_KEY 或 WENXIN_BEARER_TOKEN，
# # 其值即为从百度文心控制台获取到的API Key。如果你只拿到
# # AccessKey/SecretKey，则可在服务器端按 API 文档签名生成
# # bce-v3/ALTAK-… 形式的 Bearer token 并设置为 WENXIN_BEARER_TOKEN。
# # 可选配置：
# #   WENXIN_API_URL  - 文心API地址，设置为你提供的接口地址，如
# #                     https://qianfan.baidubce.com/v2/chat/completions
# #   WENXIN_MODEL    - 使用的模型名称
#
# class LLMService:
#     @staticmethod
#     def _extract_json_object(text: str) -> Dict[str, Any]:
#         """从模型返回文本中尽量提取 JSON 对象。支持 ```json 代码块或前后带解释文本。"""
#         if not text:
#             return {}
#
#         content = text.strip()
#
#         # 1) 直接尝试
#         try:
#             obj = json.loads(content)
#             return obj if isinstance(obj, dict) else {}
#         except Exception:
#             pass
#
#         # 2) 提取 markdown 代码块
#         fenced = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", content, flags=re.IGNORECASE)
#         for block in fenced:
#             try:
#                 obj = json.loads(block.strip())
#                 if isinstance(obj, dict):
#                     return obj
#             except Exception:
#                 continue
#
#         # 3) 提取第一个平衡大括号对象
#         start = content.find('{')
#         if start != -1:
#             depth = 0
#             end = -1
#             for i in range(start, len(content)):
#                 ch = content[i]
#                 if ch == '{':
#                     depth += 1
#                 elif ch == '}':
#                     depth -= 1
#                     if depth == 0:
#                         end = i
#                         break
#             if end != -1:
#                 candidate = content[start:end + 1]
#                 try:
#                     obj = json.loads(candidate)
#                     return obj if isinstance(obj, dict) else {}
#                 except Exception:
#                     pass
#
#         return {}
#
#     @staticmethod
#     def extract_document_info(text: str) -> Dict[str, Any]:
#         """
#         使用大模型从OCR文本中提取公文字段。
#
#         返回包含键 document_no、title、issuing_unit、security_level、
#         received_date 的字典。若调用失败返回空字典。
#         """
#         prompt = f"""请从以下公文文本中，精确提取以下字段信息。如果找不到对应信息，则留空。
#
# 需要提取的字段：
# 1.  **文号**（document_no）：优先提取最像“正式发文字号”的字符串，通常格式如"华科办〔2026〕10号"、"XX〔2023〕XX号"。
#     注意：
#     - 必须包含“〔年份〕”与“号”优先；
#     - 不要把普通编号（如000001）当作文号；
#     - 若正文中有“文号：...”则优先使用该值；
#     - 若存在多个候选，选择最完整、最正式的一项。
# 2.  **标题**（title）：公文的完整标题。通常包含“关于”、“通知”、“通告”等关键词，
#     不应该是纯数字或非常简短的编号。请避免将页眉中的流水号、文件序列号等纯数字当作标题。
# 3.  **发文单位**（issuing_unit）：发出此公文的单位名称，通常位于文头行或落款处。
# 4.  **密级**（security_level）：如"普通"、"秘密"、"机密"、"绝密"。
# 5.  **紧急程度**（urgency）：如"普通"、"加急"、"特急"。
# 6.  **收文日期**（received_date）：尽量返回ISO日期格式"YYYY-MM-DD"，若无法精确返回原文本。
# 7.  **内容摘要**（content_summary）：对正文进行简短摘要（不超过300字），用于自动填入系统的内容摘要字段。
#
# 示例输入/输出（注意格式）：
# 输入文本：单位：(示例单位)\n文号：示例〔2026〕1号\n标题：关于测试文档提取的通知\n正文：...\n
# 输出JSON：
# {{"document_no": "示例〔2026〕1号", "title": "关于测试文档提取的通知",
#  "issuing_unit": "示例单位", "security_level": "", "urgency": "", "received_date": "", "content_summary": "..."}}
#
# OCR识别文本：
# {text[:3000]}
#
# 请以JSON格式返回结果，键名使用：document_no, title, issuing_unit, security_level, urgency, received_date, content_summary。"""
#
#         try:
#             response_text = LLMService.call_llm_api(prompt)
#             parsed = LLMService._extract_json_object(response_text)
#         except Exception:
#             parsed = {}
#
#         # 兼容常见别名键
#         if not parsed.get('document_no'):
#             parsed['document_no'] = (parsed.get('doc_no') or parsed.get('文号') or '').strip() if isinstance(parsed, dict) else ''
#         if not parsed.get('title'):
#             parsed['title'] = (parsed.get('标题') or '').strip() if isinstance(parsed, dict) else ''
#         if not parsed.get('content_summary'):
#             parsed['content_summary'] = (parsed.get('summary') or parsed.get('摘要') or '').strip() if isinstance(parsed, dict) else ''
#
#         # 清洗LLM原始字段
#         llm_doc_no = (parsed.get('document_no') or '').strip()
#         llm_title = (parsed.get('title') or '').strip()
#         if llm_title.isdigit():
#             llm_title = ''
#
#         # --- 兜底规则：当 LLM 未提取到关键字段时，尝试从 OCR 原文补齐 ---
#         raw_text = text or ''
#
#         def fallback_document_no(src: str) -> str:
#             patterns = [
#                 r'([\u4e00-\u9fa5A-Za-z]{1,20}〔\d{4}〕\d{1,5}号)',
#                 r'([\u4e00-\u9fa5A-Za-z]{1,20}\[\d{4}\]\d{1,5}号)',
#                 r'([\u4e00-\u9fa5A-Za-z]{1,20}（\d{4}）\d{1,5}号)',
#                 r'([\u4e00-\u9fa5A-Za-z]{1,30}发[（(]\d{4}[)）]\d{1,5}号)',
#                 r'([\u4e00-\u9fa5A-Za-z]{1,30}发〔\d{4}〕\d{1,5}号)',
#                 r'文号[：:\s]*([^\n，。；;]{4,50}号)',
#                 r'文号[：:\s]*([A-Za-z0-9\-]{6,30})'
#             ]
#             for p in patterns:
#                 m = re.search(p, src)
#                 if m:
#                     return m.group(1).strip()
#             return ''
#
#         def collect_document_no_candidates(src: str):
#             cands = []
#             patterns = [
#                 r'([\u4e00-\u9fa5A-Za-z]{1,20}〔\d{4}〕\d{1,5}号)',
#                 r'([\u4e00-\u9fa5A-Za-z]{1,20}\[\d{4}\]\d{1,5}号)',
#                 r'([\u4e00-\u9fa5A-Za-z]{1,20}（\d{4}）\d{1,5}号)',
#                 r'([\u4e00-\u9fa5A-Za-z]{1,30}(?:发|办)[（(\[〔]?\d{4}[）)\]〕]?\d{1,5}号)',
#                 r'文号[：:\s]*([^\n，。；;]{4,50}号)',
#                 r'文号[：:\s]*([A-Za-z0-9\-]{6,30})'
#             ]
#             for p in patterns:
#                 for m in re.findall(p, src):
#                     val = (m or '').strip()
#                     if val and val not in cands:
#                         cands.append(val)
#             return cands
#
#         def fallback_title(src: str) -> str:
#             lines = [ln.strip() for ln in src.splitlines() if ln.strip()]
#             # 过滤明显非标题行
#             blacklist_prefix = ('文号', '发文单位', '收文日期', '密级', '紧急程度', '关键词', '备注', '编号', '序号')
#             keywords = ('关于', '通知', '通告', '请示', '报告', '批复', '函', '纪要', '决定', '意见', '方案', '办法')
#
#             for ln in lines[:30]:
#                 if ln.startswith(blacklist_prefix):
#                     continue
#                 if '印章' in ln or '扫描' in ln:
#                     continue
#                 if 4 <= len(ln) <= 80 and any(k in ln for k in keywords):
#                     # 排除明显正文句子（过长且包含多个标点）
#                     if ln.count('，') + ln.count('。') >= 3:
#                         continue
#                     return ln
#             return ''
#
#         def collect_title_candidates(src: str):
#             lines = [ln.strip() for ln in src.splitlines() if ln.strip()]
#             blacklist_prefix = ('文号', '发文单位', '收文日期', '密级', '紧急程度', '关键词', '备注', '编号', '序号')
#             keywords = ('关于', '通知', '通告', '请示', '报告', '批复', '函', '纪要', '决定', '意见', '方案', '办法')
#             cands = []
#             for ln in lines[:40]:
#                 if ln.startswith(blacklist_prefix):
#                     continue
#                 if '印章' in ln or '扫描' in ln:
#                     continue
#                 if 4 <= len(ln) <= 100 and any(k in ln for k in keywords):
#                     if ln not in cands:
#                         cands.append(ln)
#             return cands
#
#         def normalize_date(s: str) -> str:
#             s = (s or '').strip()
#             if not s:
#                 return ''
#             m = re.search(r'(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})', s)
#             if m:
#                 y, mo, d = m.groups()
#                 return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
#             return s
#
#         def is_reasonable_doc_no(s: str) -> bool:
#             s = (s or '').strip()
#             if not s:
#                 return False
#             # 典型噪声词（来自页眉/密级行）
#             if re.search(r'(请妥善保管|仅供相关人员阅|密级|等级|签发|抄送|拟稿|联系电话)', s):
#                 return False
#             if len(s) < 4 or len(s) > 36:
#                 return False
#             # 至少满足：包含年份括号 或 明确“号”
#             if not (re.search(r'[〔【\[（(]\d{4}[〕】\]）)]', s) or ('号' in s)):
#                 return False
#             return True
#
#         def clean_doc_no(s: str) -> str:
#             s = re.sub(r'\s+', '', (s or '').strip())
#             if not s:
#                 return ''
#             # 去掉常见前置噪声
#             s = re.sub(r'^(?:长期|特急|加急|非密|普通|密级|等级|签发)+', '', s)
#             s = re.sub(r'^(?:请妥善保管|仅供相关人员阅)+', '', s)
#             # 尝试提取核心文号片段
#             m = re.search(r'([\u4e00-\u9fa5A-Za-z]{1,16}(?:发电|发|办)?[〔【\[（(]?\d{4}[〕】\]）)]?\d{0,5}号?)', s)
#             if m:
#                 s = m.group(1)
#             return s
#
#         def is_reasonable_title(s: str) -> bool:
#             s = (s or '').strip()
#             if not s:
#                 return False
#             if len(s) < 6 or len(s) > 100:
#                 return False
#             if re.search(r'(发电单位|签发|密级|等级|抄送|拟稿|联系电话)', s):
#                 return False
#             if not any(k in s for k in ('关于', '通知', '通告', '请示', '报告', '批复', '函', '纪要')):
#                 return False
#             return True
#
#         def clean_issuing_unit(s: str) -> str:
#             s = (s or '').strip()
#             if not s:
#                 return ''
#             s = re.sub(r'^(发电单位|发文单位)[:：\s]*', '', s)
#             s = s.replace('(印章)', '').replace('（印章）', '')
#             # 常见干扰后缀
#             s = re.sub(r'(密码发电|发出)$', '', s)
#             s = re.sub(r'\s+', '', s)
#             return s.strip('：:，。;；')
#
#         def pick_unit_from_text(src: str) -> str:
#             lines = [ln.strip() for ln in (src or '').splitlines() if ln.strip()]
#             # 优先“发电单位/发文单位”行
#             for ln in lines[:30]:
#                 m = re.search(r'(?:发电单位|发文单位)[:：\s]*([\u4e00-\u9fa5A-Za-z]{2,30})', ln)
#                 if m:
#                     return clean_issuing_unit(m.group(1))
#             # 其次常规单位行
#             for ln in lines[:50]:
#                 if any(k in ln for k in ('大学', '学院', '委员会', '办公室', '政府', '党委', '局', '厅', '部', '中心', '公司')):
#                     if len(ln) <= 30 and '关于' not in ln:
#                         return clean_issuing_unit(ln)
#             return ''
#
#         def extract_best_date(src: str) -> str:
#             src = src or ''
#             cands = []
#             for y, m, d in re.findall(r'(\d{4})\s*[年\-/]\s*(\d{1,2})\s*[月\-/]\s*(\d{1,2})\s*日?', src):
#                 yi = int(y)
#                 if 2000 <= yi <= 2100:
#                     cands.append((yi, int(m), int(d)))
#             if not cands:
#                 return ''
#             # 优先较新的年份，避免误读成很早年份
#             yi, mo, d = sorted(cands, key=lambda x: (x[0], x[1], x[2]), reverse=True)[0]
#             return f"{yi:04d}-{mo:02d}-{d:02d}"
#
#         def extract_security(src: str) -> str:
#             s = src or ''
#             m = re.search(r'密级\s*[：:]?\s*(绝密|机密|秘密|非密|普通)', s)
#             if m:
#                 v = m.group(1)
#                 return '普通' if v == '非密' else v
#             if '绝密' in s:
#                 return '绝密'
#             if '机密' in s:
#                 return '机密'
#             if '秘密' in s:
#                 return '秘密'
#             if '非密' in s:
#                 return '普通'
#             return ''
#
#         def extract_urgency(src: str) -> str:
#             s = src or ''
#             m = re.search(r'等级\s*[：:]?\s*(特急|加急|平急|急件|普通)', s)
#             if m:
#                 return m.group(1)
#             m2 = re.search(r'紧急(?:程度)?\s*[：:]?\s*(特急|加急|平急|急件|普通)', s)
#             if m2:
#                 return m2.group(1)
#             if '特急' in s:
#                 return '特急'
#             if '加急' in s:
#                 return '加急'
#             if '平急' in s:
#                 return '平急'
#             if '急件' in s:
#                 return '急件'
#             return ''
#
#         def score_doc_no(s: str) -> float:
#             if not s:
#                 return -1
#             score = 0.0
#             if '号' in s:
#                 score += 5
#             if re.search(r'〔\d{4}〕|[（(\[]\d{4}[）)\]]', s):
#                 score += 6
#             if re.search(r'(发|办)', s):
#                 score += 2
#             if re.fullmatch(r'\d+', s.replace(' ', '')):
#                 score -= 8
#             if len(s) > 40:
#                 score -= 3
#             return score
#
#         def score_title(s: str) -> float:
#             if not s:
#                 return -1
#             score = 0.0
#             keywords = ('关于', '通知', '通告', '请示', '报告', '批复', '函', '纪要', '决定', '意见', '方案', '办法')
#             if any(k in s for k in keywords):
#                 score += 6
#             if 8 <= len(s) <= 80:
#                 score += 4
#             if s.isdigit():
#                 score -= 10
#             if s.count('，') + s.count('。') >= 4:
#                 score -= 3
#             return score
#
#         # --- 双通道自动择优：LLM候选 + 规则候选 ---
#         doc_no_candidates = []
#         if llm_doc_no:
#             doc_no_candidates.append(llm_doc_no)
#         for c in collect_document_no_candidates(raw_text):
#             if c not in doc_no_candidates:
#                 doc_no_candidates.append(c)
#         # 兜底单值
#         fb_no = fallback_document_no(raw_text)
#         if fb_no and fb_no not in doc_no_candidates:
#             doc_no_candidates.append(fb_no)
#
#         if doc_no_candidates:
#             parsed['document_no'] = max(doc_no_candidates, key=score_doc_no)
#         else:
#             parsed['document_no'] = ''
#
#         parsed['document_no'] = clean_doc_no(parsed.get('document_no', ''))
#         if not is_reasonable_doc_no(parsed['document_no']):
#             # 再从原文中做一次强约束提取
#             repaired_no = ''
#             compact = re.sub(r'\s+', '', raw_text)
#             m_no = re.search(r'([\u4e00-\u9fa5A-Za-z]{1,16}(?:发电|发|办)?[〔【\[（(]?\d{4}[〕】\]）)]?\d{0,5}号)', compact)
#             if m_no:
#                 repaired_no = clean_doc_no(m_no.group(1))
#             parsed['document_no'] = repaired_no if is_reasonable_doc_no(repaired_no) else ''
#
#         title_candidates = []
#         if llm_title:
#             title_candidates.append(llm_title)
#         for c in collect_title_candidates(raw_text):
#             if c not in title_candidates:
#                 title_candidates.append(c)
#         fb_title = fallback_title(raw_text)
#         if fb_title and fb_title not in title_candidates:
#             title_candidates.append(fb_title)
#
#         if title_candidates:
#             parsed['title'] = max(title_candidates, key=score_title)
#         else:
#             parsed['title'] = ''
#
#         if not is_reasonable_title(parsed.get('title', '')):
#             parsed['title'] = fallback_title(raw_text)
#             if not is_reasonable_title(parsed.get('title', '')):
#                 parsed['title'] = ''
#
#         # 发文单位合理性清洗/回填
#         parsed['issuing_unit'] = clean_issuing_unit(parsed.get('issuing_unit', ''))
#         if not parsed['issuing_unit'] or len(parsed['issuing_unit']) < 2:
#             parsed['issuing_unit'] = pick_unit_from_text(raw_text)
#
#         # 确保返回的字段存在，填空字符串为默认值
#         defaults = {
#             'document_no': '', 'title': '', 'issuing_unit': '',
#             'security_level': '', 'urgency': '', 'received_date': '', 'content_summary': ''
#         }
#         for k, v in defaults.items():
#             if k not in parsed or parsed.get(k) is None:
#                 parsed[k] = v
#
#         # 内容摘要兜底：若模型未给出摘要，使用OCR正文截断填充，避免表单为空
#         if not str(parsed.get('content_summary', '')).strip():
#             compact = re.sub(r'\s+', ' ', raw_text).strip()
#             parsed['content_summary'] = compact[:300] if compact else ''
#
#         # 日期标准化
#         parsed['received_date'] = normalize_date(parsed.get('received_date', ''))
#         if not parsed['received_date']:
#             parsed['received_date'] = extract_best_date(raw_text)
#
#         # 密级/紧急程度兜底
#         if not str(parsed.get('security_level', '')).strip():
#             parsed['security_level'] = extract_security(raw_text)
#         if not str(parsed.get('urgency', '')).strip():
#             parsed['urgency'] = extract_urgency(raw_text)
#
#         return parsed
#
#     @staticmethod
#     def call_llm_api(prompt: str) -> str:
#         """
#         调用文心大模型的chat/completions接口。
#
#         根据示例说明，HTTP请求头中应包含：
#             Authorization: Bearer <API Key>
#         请求体为JSON，包括model和messages字段。
#
#         返回生成的文本内容字符串。
#         """
#         # 优先使用硬编码的常量，如果为空则查环境变量
#         api_key = API_KEY or os.getenv("WENXIN_API_KEY") or os.getenv("WENXIN_BEARER_TOKEN")
#         if not api_key:
#             raise RuntimeError("未在代码或环境变量中配置API Key")
#
#         url = API_URL or os.getenv("WENXIN_API_URL")
#         model = MODEL or os.getenv("WENXIN_MODEL")
#
#         # 若用户未在key前加Bearer，则自动添加
#         auth_value = api_key if api_key.strip().lower().startswith("bearer") else f"Bearer {api_key}"
#
#         headers = {
#             "Content-Type": "application/json",
#             "Authorization": auth_value,
#         }
#         payload = {
#             "model": model,
#             "messages": [{"role": "user", "content": prompt}]
#         }
#
#         resp = requests.post(url, headers=headers, json=payload, timeout=30)
#         if resp.status_code != 200:
#             # 尝试解析返回的JSON以给出更清晰提示
#             try:
#                 err = resp.json()
#             except Exception:
#                 raise RuntimeError(f"LLM请求失败 {resp.status_code}: {resp.text}")
#
#             # 常见错误：model 无效或无权限
#             code = err.get("error", {}).get("code") if isinstance(err, dict) else None
#             if code == "invalid_model":
#                 raise RuntimeError(
#                     f"LLM请求失败 {resp.status_code}: 模型不可用或无权限 (model={model}).\n"
#                     f"请确认你配置的 MODEL 是否正确，或使用平台控制台开通对应模型。\n"
#                     f"当前请求地址: {url}\n返回信息: {json.dumps(err, ensure_ascii=False)}"
#                 )
#
#             raise RuntimeError(f"LLM请求失败 {resp.status_code}: {json.dumps(err, ensure_ascii=False)}")
#
#         data = resp.json()
#         # 解析常见响应结构
#         try:
#             return data.get("choices", [])[0].get("message", {}).get("content", "")
#         except Exception:
#             return resp.text


import json
import requests
import re
from typing import Dict, Any


class LLMService:
    # 本地 Ollama 配置
    OLLAMA_URL = "http://localhost:11434/api/generate"
    MODEL_NAME = "qwen2.5:1.5b"

    @staticmethod
    def _extract_json_object(text: str) -> Dict[str, Any]:
        """从模型返回文本中提取 JSON，增强了对小模型输出不稳定的处理"""
        if not text: return {}
        # 清洗可能存在的 Markdown 标记
        content = re.sub(r'```json\s*|```', '', text).strip()
        try:
            return json.loads(content)
        except:
            # 备选：正则匹配第一个 { 和最后一个 }
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
        return {}

    @staticmethod
    def call_llm_api(prompt: str) -> str:
        """调用本地 Ollama 接口"""
        payload = {
            "model": LLMService.MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "format": "json",  # 关键：强制 Qwen 输出标准 JSON
            "options": {
                "temperature": 0.1,  # 降低随机性，提高提取稳定性
                "num_ctx": 4096  # 限制上下文窗口，节省 CPU 内存
            }
        }
        try:
            response = requests.post(LLMService.OLLAMA_URL, json=payload, timeout=30)
            if response.status_code == 200:
                return response.json().get("response", "")
        except Exception as e:
            print(f"本地模型调用失败: {e}")
        return ""

    @staticmethod
    def extract_document_info(text: str) -> Dict[str, Any]:
        """从 OCR 文本中提取公文字段"""
        # --- CPU 优化：截取文本核心部分 ---
        # 公文关键信息通常在开头和结尾。截取前 1200 字和后 400 字，减少 CPU 处理压力
        # if len(text) > 1600:
        #     process_text = text[:1200] + "\n...(省略中段)...\n" + text[-400:]
        # else:
        #     process_text = text

        import re

        def refined_preprocess(raw_text: str):
            """
            针对公文的高级预处理函数
            功能：纠错、噪音消除、标题重组、红头清洗
            """
            if not raw_text:
                return "", ""

            # 1. 基础字符标准化 (解决 0/O, l/1, 括号不统一问题)
            confusable_map = {
                "二o": "二〇",
                "二0": "二〇",
                "二O": "二〇",
                "l号": "1号",
                "I号": "1号",
                "i号": "1号",
                "（": "〔", "）": "〕",
                "【": "〔", "】": "〕",
                "[": "〔", "]": "〕",
                "［": "〔", "］": "〕",
                "(": "〔", ")": "〕"
            }
            text = raw_text
            for src, dst in confusable_map.items():
                text = text.replace(src, dst)

            # 2. 物理行拆分与初步清洗
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

            # 过滤掉明显的页码和纯数字杂质
            clean_lines = []
            noise_patterns = [r'^第\d+页', r'^\d+/\d+$', r'^- \d+ -$']
            for ln in lines:
                if not any(re.search(p, ln) for p in noise_patterns):
                    clean_lines.append(ln)

            # 3. 核心逻辑：标题重组 (解决换行导致标题不全)
            # 寻找“关于”开头的行，并尝试与后续行合并，直到遇到公文种类词
            final_title = ""
            keywords = ['通知', '通告', '报告', '请示', '批复', '函', '意见', '方案', '办法', '决定', '纪要']

            for i in range(min(len(clean_lines), 15)):  # 标题通常在前15行
                line = clean_lines[i]
                if "关于" in line:
                    # 尝试向下合并最多 3 行
                    potential_title = "".join(clean_lines[i: i + 4])
                    # 匹配“关于...到...种类词”
                    title_match = re.search(r'(关于.*?(?:' + '|'.join(keywords) + '))', potential_title)
                    if title_match:
                        final_title = title_match.group(1)
                        # 既然找到了标题，我们可以在原始列表中标记它，避免被识别为发文单位
                        break

            # 4. 核心逻辑：发文机关清洗 (解决“政府文件”问题)
            # 我们识别出带有“文件”后缀的红头行，并强制剥离后缀
            processed_lines = []
            for ln in clean_lines:
                new_ln = ln
                # 如果某行以“文件”结尾，且前面是政府/委员会等机构，执行剥离
                if re.search(r'(政府|委员会|办公室|厅|部|局)文件$', ln):
                    new_ln = re.sub(r'文件$', '', ln)

                # 移除“绝密”、“特急”等前缀干扰
                # new_ln = re.sub(r'^(绝密|机密|秘密|普通|特急|加急|平急)\s*', '', new_ln)
                processed_lines.append(new_ln)

            # 5. 重组输出
            # 我们把处理后的行重新拼接，同时把“提取到的完整标题”放在最前面提示 LLM
            header_info = f"【参考标题】：{final_title}\n" if final_title else ""
            refined_text = "\n".join(processed_lines)

            return header_info + refined_text, final_title

        head = text[:250]
        tail = text[-150:] if len(text) > 800 else ""
        process_text_ori = f"{head}\n[...中间内容略...]\n{tail}"
        process_text, rule_title = refined_preprocess(process_text_ori)

        prompt = f"""你是一个公文处理助手。请从以下 OCR 文本中提取信息并严格以 JSON 格式输出。
        如果某个字段缺失，请填入空字符串 ""。

        【示例输入】
        机密
        中共中央办公厅文件
        中办发〔2023〕12号
        关于进一步加强某某工作的通知
        ...[中间内容略]...
        2023年4月5日印发

        【示例输出】
        {{
            "document_no": "中办发〔2023〕12号",
            "title": "关于进一步加强某某工作的通知",
            "issuing_unit": "中共中央办公厅",
            "security_level": "机密",
            "urgency": "",
            "received_date": "2023-04-05",
            "content_summary": "通知要求进一步加强某某工作..."
        }}

        【实际输入】
        {process_text}

        请根据【实际输入】给出【实际输出】，不要包含任何解释性文字。"""

        raw_response = LLMService.call_llm_api(prompt)
        parsed = LLMService._extract_json_object(raw_response)
        print(parsed)

        # 兼容常见别名键
        if not parsed.get('document_no'):
            parsed['document_no'] = (parsed.get('doc_no') or parsed.get('文号') or '').strip() if isinstance(parsed, dict) else ''
        if not parsed.get('title'):
            parsed['title'] = (parsed.get('标题') or '').strip() if isinstance(parsed, dict) else ''
        if not parsed.get('content_summary'):
            parsed['content_summary'] = (parsed.get('summary') or parsed.get('摘要') or '').strip() if isinstance(parsed, dict) else ''

        # 清洗LLM原始字段
        llm_doc_no = (parsed.get('document_no') or '').strip()
        llm_title = (parsed.get('title') or '').strip()
        if llm_title.isdigit():
            llm_title = ''

        # --- 兜底规则：当 LLM 未提取到关键字段时，尝试从 OCR 原文补齐 ---
        raw_text = text or ''

        def fallback_document_no(src: str) -> str:
            patterns = [
                r'([\u4e00-\u9fa5A-Za-z]{1,20}〔\d{4}〕\d{1,5}号)',
                r'([\u4e00-\u9fa5A-Za-z]{1,20}\[\d{4}\]\d{1,5}号)',
                r'([\u4e00-\u9fa5A-Za-z]{1,20}（\d{4}）\d{1,5}号)',
                r'([\u4e00-\u9fa5A-Za-z]{1,30}发[（(]\d{4}[)）]\d{1,5}号)',
                r'([\u4e00-\u9fa5A-Za-z]{1,30}发〔\d{4}〕\d{1,5}号)',
                r'文号[：:\s]*([^\n，。；;]{4,50}号)',
                r'文号[：:\s]*([A-Za-z0-9\-]{6,30})'
            ]
            for p in patterns:
                m = re.search(p, src)
                if m:
                    return m.group(1).strip()
            return ''

        def collect_document_no_candidates(src: str):
            cands = []
            patterns = [
                r'([\u4e00-\u9fa5A-Za-z]{1,20}〔\d{4}〕\d{1,5}号)',
                r'([\u4e00-\u9fa5A-Za-z]{1,20}\[\d{4}\]\d{1,5}号)',
                r'([\u4e00-\u9fa5A-Za-z]{1,20}（\d{4}）\d{1,5}号)',
                r'([\u4e00-\u9fa5A-Za-z]{1,30}(?:发|办)[（(\[〔]?\d{4}[）)\]〕]?\d{1,5}号)',
                r'文号[：:\s]*([^\n，。；;]{4,50}号)',
                r'文号[：:\s]*([A-Za-z0-9\-]{6,30})'
            ]
            for p in patterns:
                for m in re.findall(p, src):
                    val = (m or '').strip()
                    if val and val not in cands:
                        cands.append(val)
            return cands

        def fallback_title(src: str) -> str:
            lines = [ln.strip() for ln in src.splitlines() if ln.strip()]
            # 过滤明显非标题行
            blacklist_prefix = ('文号', '发文单位', '收文日期', '密级', '紧急程度', '关键词', '备注', '编号', '序号')
            keywords = ('关于', '通知', '通告', '请示', '报告', '批复', '函', '纪要', '决定', '意见', '方案', '办法')

            for ln in lines[:30]:
                if ln.startswith(blacklist_prefix):
                    continue
                if '印章' in ln or '扫描' in ln:
                    continue
                if 4 <= len(ln) <= 80 and any(k in ln for k in keywords):
                    # 排除明显正文句子（过长且包含多个标点）
                    if ln.count('，') + ln.count('。') >= 3:
                        continue
                    return ln
            return ''

        def collect_title_candidates(src: str):
            lines = [ln.strip() for ln in src.splitlines() if ln.strip()]
            blacklist_prefix = ('文号', '发文单位', '收文日期', '密级', '紧急程度', '关键词', '备注', '编号', '序号')
            keywords = ('关于', '通知', '通告', '请示', '报告', '批复', '函', '纪要', '决定', '意见', '方案', '办法')
            cands = []
            for ln in lines[:40]:
                if ln.startswith(blacklist_prefix):
                    continue
                if '印章' in ln or '扫描' in ln:
                    continue
                if 4 <= len(ln) <= 100 and any(k in ln for k in keywords):
                    if ln not in cands:
                        cands.append(ln)
            return cands

        def normalize_date(s: str) -> str:
            s = (s or '').strip()
            if not s:
                return ''
            m = re.search(r'(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})', s)
            if m:
                y, mo, d = m.groups()
                return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
            return s

        def is_reasonable_doc_no(s: str) -> bool:
            s = (s or '').strip()
            if not s:
                return False
            # 典型噪声词（来自页眉/密级行）
            if re.search(r'(请妥善保管|仅供相关人员阅|密级|等级|签发|抄送|拟稿|联系电话)', s):
                return False
            if len(s) < 4 or len(s) > 36:
                return False
            # 至少满足：包含年份括号 或 明确“号”
            if not (re.search(r'[〔【\[（(]\d{4}[〕】\]）)]', s) or ('号' in s)):
                return False
            return True

        def clean_doc_no(s: str) -> str:
            s = re.sub(r'\s+', '', (s or '').strip())
            if not s:
                return ''
            # 去掉常见前置噪声
            s = re.sub(r'^(?:长期|特急|加急|非密|普通|密级|等级|签发)+', '', s)
            s = re.sub(r'^(?:请妥善保管|仅供相关人员阅)+', '', s)
            # 尝试提取核心文号片段
            m = re.search(r'([\u4e00-\u9fa5A-Za-z]{1,16}(?:发电|发|办)?[〔【\[（(]?\d{4}[〕】\]）)]?\d{0,5}号?)', s)
            if m:
                s = m.group(1)
            return s

        def is_reasonable_title(s: str) -> bool:
            s = (s or '').strip()
            if not s:
                return False
            if len(s) < 6 or len(s) > 100:
                return False
            if re.search(r'(发电单位|签发|密级|等级|抄送|拟稿|联系电话)', s):
                return False
            if not any(k in s for k in ('关于', '通知', '通告', '请示', '报告', '批复', '函', '纪要')):
                return False
            return True

        def clean_issuing_unit(s: str) -> str:
            s = (s or '').strip()
            if not s:
                return ''
            s = re.sub(r'^(发电单位|发文单位)[:：\s]*', '', s)
            s = s.replace('(印章)', '').replace('（印章）', '')
            # 常见干扰后缀
            s = re.sub(r'(密码发电|发出)$', '', s)
            s = re.sub(r'\s+', '', s)
            return s.strip('：:，。;；')

        def pick_unit_from_text(src: str) -> str:
            lines = [ln.strip() for ln in (src or '').splitlines() if ln.strip()]
            # 优先“发电单位/发文单位”行
            for ln in lines[:30]:
                m = re.search(r'(?:发电单位|发文单位)[:：\s]*([\u4e00-\u9fa5A-Za-z]{2,30})', ln)
                if m:
                    return clean_issuing_unit(m.group(1))
            # 其次常规单位行
            for ln in lines[:50]:
                if any(k in ln for k in ('大学', '学院', '委员会', '办公室', '政府', '党委', '局', '厅', '部', '中心', '公司')):
                    if len(ln) <= 30 and '关于' not in ln:
                        return clean_issuing_unit(ln)
            return ''

        def extract_best_date(src: str) -> str:
            src = src or ''
            cands = []
            for y, m, d in re.findall(r'(\d{4})\s*[年\-/]\s*(\d{1,2})\s*[月\-/]\s*(\d{1,2})\s*日?', src):
                yi = int(y)
                if 2000 <= yi <= 2100:
                    cands.append((yi, int(m), int(d)))
            if not cands:
                return ''
            # 优先较新的年份，避免误读成很早年份
            yi, mo, d = sorted(cands, key=lambda x: (x[0], x[1], x[2]), reverse=True)[0]
            return f"{yi:04d}-{mo:02d}-{d:02d}"

        def extract_security(src: str) -> str:
            s = src or ''
            m = re.search(r'密级\s*[：:]?\s*(绝密|机密|秘密|非密|普通)', s)
            if m:
                v = m.group(1)
                return '普通' if v == '非密' else v
            if '绝密' in s:
                return '绝密'
            if '机密' in s:
                return '机密'
            if '秘密' in s:
                return '秘密'
            if '非密' in s:
                return '普通'
            return ''

        def extract_urgency(src: str) -> str:
            s = src or ''
            m = re.search(r'等级\s*[：:]?\s*(特急|加急|平急|急件|普通)', s)
            if m:
                return m.group(1)
            m2 = re.search(r'紧急(?:程度)?\s*[：:]?\s*(特急|加急|平急|急件|普通)', s)
            if m2:
                return m2.group(1)
            if '特急' in s:
                return '特急'
            if '加急' in s:
                return '加急'
            if '平急' in s:
                return '平急'
            if '急件' in s:
                return '急件'
            return ''

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
            if re.fullmatch(r'\d+', s.replace(' ', '')):
                score -= 8
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
            if 8 <= len(s) <= 80:
                score += 4
            if s.isdigit():
                score -= 10
            if s.count('，') + s.count('。') >= 4:
                score -= 3
            return score

        # --- 双通道自动择优：LLM候选 + 规则候选 ---
        doc_no_candidates = []
        if llm_doc_no:
            doc_no_candidates.append(llm_doc_no)
        for c in collect_document_no_candidates(raw_text):
            if c not in doc_no_candidates:
                doc_no_candidates.append(c)
        # 兜底单值
        fb_no = fallback_document_no(raw_text)
        if fb_no and fb_no not in doc_no_candidates:
            doc_no_candidates.append(fb_no)

        if doc_no_candidates:
            parsed['document_no'] = max(doc_no_candidates, key=score_doc_no)
        else:
            parsed['document_no'] = ''

        parsed['document_no'] = clean_doc_no(parsed.get('document_no', ''))
        if not is_reasonable_doc_no(parsed['document_no']):
            # 再从原文中做一次强约束提取
            repaired_no = ''
            compact = re.sub(r'\s+', '', raw_text)
            m_no = re.search(r'([\u4e00-\u9fa5A-Za-z]{1,16}(?:发电|发|办)?[〔【\[（(]?\d{4}[〕】\]）)]?\d{0,5}号)', compact)
            if m_no:
                repaired_no = clean_doc_no(m_no.group(1))
            parsed['document_no'] = repaired_no if is_reasonable_doc_no(repaired_no) else ''

        title_candidates = []
        if llm_title:
            title_candidates.append(llm_title)
        for c in collect_title_candidates(raw_text):
            if c not in title_candidates:
                title_candidates.append(c)
        fb_title = fallback_title(raw_text)
        if fb_title and fb_title not in title_candidates:
            title_candidates.append(fb_title)

        if title_candidates:
            parsed['title'] = max(title_candidates, key=score_title)
        else:
            parsed['title'] = ''

        if not is_reasonable_title(parsed.get('title', '')):
            parsed['title'] = fallback_title(raw_text)
            if not is_reasonable_title(parsed.get('title', '')):
                parsed['title'] = ''

        # 发文单位合理性清洗/回填
        parsed['issuing_unit'] = clean_issuing_unit(parsed.get('issuing_unit', ''))
        if not parsed['issuing_unit'] or len(parsed['issuing_unit']) < 2:
            parsed['issuing_unit'] = pick_unit_from_text(raw_text)

        # 确保返回的字段存在，填空字符串为默认值
        defaults = {
            'document_no': '', 'title': '', 'issuing_unit': '',
            'security_level': '', 'urgency': '', 'received_date': '', 'content_summary': ''
        }
        for k, v in defaults.items():
            if k not in parsed or parsed.get(k) is None:
                parsed[k] = v

        # 内容摘要兜底：若模型未给出摘要，使用OCR正文截断填充，避免表单为空
        if not str(parsed.get('content_summary', '')).strip():
            compact = re.sub(r'\s+', ' ', raw_text).strip()
            parsed['content_summary'] = compact[:300] if compact else ''
            # parsed['content_summary'] = "LLM RETURNED NOTHING..."

        # 日期标准化
        parsed['received_date'] = normalize_date(parsed.get('received_date', ''))
        if not parsed['received_date']:
            parsed['received_date'] = extract_best_date(raw_text)

        # 密级/紧急程度兜底
        if not str(parsed.get('security_level', '')).strip():
            parsed['security_level'] = extract_security(raw_text)
        if not str(parsed.get('urgency', '')).strip():
            parsed['urgency'] = extract_urgency(raw_text)

        # 发文单位二次清洗：防止 LLM 还是带出了“文件”二字
        if 'issuing_unit' in parsed:
            parsed['issuing_unit'] = re.sub(r'文件$', '', parsed['issuing_unit'].strip())

        print(process_text)
        print(parsed)
        return parsed