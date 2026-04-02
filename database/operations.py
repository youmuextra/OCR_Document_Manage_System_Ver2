# database/operations.py
"""
统一的数据库管理器
包含发文、收文、流转等所有功能
"""

import sqlite3
from contextlib import contextmanager
import hashlib
from datetime import datetime, timedelta, date
import os
import json
import re
from typing import Optional, Dict, List, Any, Tuple

class DatabaseManager:
    """统一的数据库管理器"""
    
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = "data/documents.db"
        # ✅ 确保db_path是字符串
        if not isinstance(db_path, str):
            # 如果传入了DatabaseManager对象，尝试获取其db_path属性
            if hasattr(db_path, 'db_path'):
                self.db_path = db_path.db_path
            else:
                # 否则使用默认路径
                self.db_path = "data/documents.db"
        else:
            self.db_path = db_path
        # 确保目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_database()
    
    def init_database(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 启用外键
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # 创建users表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                real_name TEXT,
                department TEXT,
                position TEXT,
                role TEXT DEFAULT 'operator',  -- 'operator' 或 'admin'
                email TEXT,
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                last_login TIMESTAMP
            )
        """)
        
        # 创建默认管理员用户（如果不存在）
        admin_hash = self.hash_password('123456')
        cursor.execute("""
            INSERT OR IGNORE INTO users 
            (username, password_hash, real_name, role) 
            VALUES (?, ?, ?, ?)
        """, ('admin', admin_hash, '系统管理员', 'admin'))

        # 角色体系迁移：旧 user/manager 统一迁移为 operator
        try:
            cursor.execute("UPDATE users SET role = 'operator' WHERE role IN ('user', 'manager', '普通用户')")
            cursor.execute("UPDATE users SET role = 'admin' WHERE role IN ('管理员')")
        except Exception:
            pass
        
        # 创建收文表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS receive_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_no TEXT UNIQUE,
                title TEXT NOT NULL,
                issuing_unit TEXT,
                security_level TEXT DEFAULT '普通',
                urgency_level TEXT DEFAULT '普通',
                document_type TEXT,
                copies INTEGER DEFAULT 1,
                received_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                receiver TEXT,
                storage_location TEXT,
                original_file_path TEXT,
                ocr_result_path TEXT,
                thumbnail_path TEXT,
                content_summary TEXT,
                keywords TEXT,
                remarks TEXT,
                user_id INTEGER,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT '正常',
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        """)
        
        # 创建发文表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS send_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_no TEXT UNIQUE,
                title TEXT NOT NULL,
                issuing_unit TEXT,
                send_to_unit TEXT NOT NULL,
                m_level TEXT DEFAULT '',
                security_level TEXT DEFAULT '普通',
                document_type TEXT DEFAULT '',
                processor TEXT NOT NULL,
                send_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                send_status TEXT DEFAULT '已发文',
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT '正常',
                remarks TEXT,
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        """)

        # 兼容旧库：为 send_documents 补充 m_level 字段
        try:
            cursor.execute("PRAGMA table_info(send_documents)")
            cols = [row[1] for row in cursor.fetchall()]  # row: cid, name, type, ...
            if 'm_level' not in cols:
                cursor.execute("ALTER TABLE send_documents ADD COLUMN m_level TEXT DEFAULT ''")
            if 'security_level' not in cols:
                cursor.execute("ALTER TABLE send_documents ADD COLUMN security_level TEXT DEFAULT '普通'")
            if 'document_type' not in cols:
                cursor.execute("ALTER TABLE send_documents ADD COLUMN document_type TEXT DEFAULT ''")
        except Exception:
            pass
        
        # 创建流转记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS circulation_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                document_type TEXT NOT NULL,  -- 'receive' 或 'send'
                circulation_type TEXT NOT NULL,  -- '交接', '借阅', '其他'
                next_node_unit TEXT,
                next_node_person TEXT,
                current_holder_id INTEGER,
                borrow_requester_id INTEGER,
                borrow_date TIMESTAMP,
                due_date TIMESTAMP,
                return_date TIMESTAMP,
                status TEXT DEFAULT '待确认',
                remarks TEXT,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (current_holder_id) REFERENCES users(id),
                FOREIGN KEY (borrow_requester_id) REFERENCES users(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        """)
        
        # 创建日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                document_type TEXT NOT NULL,
                user_id INTEGER,
                action TEXT NOT NULL,
                action_details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # 取件登记表（用于记录公文去向、取件/归还轨迹）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pickup_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_no TEXT NOT NULL,
                title TEXT,
                issuing_unit TEXT,
                received_date TIMESTAMP,
                security_level TEXT,
                destination TEXT NOT NULL,
                picker_name TEXT NOT NULL,
                picker_contact TEXT,
                pickup_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                return_time TIMESTAMP,
                status TEXT DEFAULT '已取走',
                remarks TEXT,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pickup_doc_no ON pickup_records(document_no)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pickup_picker_name ON pickup_records(picker_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pickup_time ON pickup_records(pickup_time)")
        
        conn.commit()
        conn.close()
        
        print(f"✅ 数据库初始化完成: {self.db_path}")
    
    def hash_password(self, password):
        """密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接（上下文管理器）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    # ==================== 用户相关方法 ====================
    
    def create_user(self, user_data):
        """创建用户"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 检查用户名是否已存在
            cursor.execute("SELECT id FROM users WHERE username = ?", (user_data.get('username'),))
            if cursor.fetchone():
                return False, "用户名已存在"
            
            # 检查邮箱是否已存在
            if user_data.get('email'):
                cursor.execute("SELECT id FROM users WHERE email = ?", (user_data.get('email'),))
                if cursor.fetchone():
                    return False, "邮箱已被注册"
            
            # 准备用户数据
            columns = ['username', 'password_hash']
            values = [user_data.get('username'), self.hash_password(user_data.get('password', ''))]
            
            # 添加其他字段
            optional_fields = ['real_name', 'department', 'position', 'role', 'email', 'phone']
            for field in optional_fields:
                if field in user_data and user_data[field]:
                    columns.append(field)
                    values.append(user_data[field])
            
            # 添加系统字段
            columns.extend(['created_at', 'updated_at'])
            values.extend([datetime.now(), datetime.now()])
            
            # 执行插入
            placeholders = ', '.join(['?' for _ in values])
            sql = f"INSERT INTO users ({', '.join(columns)}) VALUES ({placeholders})"
            
            try:
                cursor.execute(sql, values)
                conn.commit()
                return True, "用户创建成功"
            except Exception as e:
                return False, f"创建用户失败: {e}"
    
    def get_all_users(self):
        """返回所有用户的列表，每个用户为字典"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, real_name, department, role, last_login FROM users ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def update_user(self, user_id, update_data):
        """更新指定用户的字段"""
        if not update_data:
            return False, "没有要更新的字段"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            set_clauses = []
            params = []
            for key, value in update_data.items():
                set_clauses.append(f"{key} = ?")
                params.append(value)
            params.append(datetime.now())
            params.append(user_id)
            sql = f"UPDATE users SET {', '.join(set_clauses)}, updated_at = ? WHERE id = ?"
            try:
                cursor.execute(sql, params)
                conn.commit()
                if cursor.rowcount > 0:
                    return True, "用户更新成功"
                else:
                    return False, "未找到该用户"
            except Exception as e:
                return False, f"更新失败: {e}"

    def delete_user(self, user_id):
        """删除指定用户"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
                if cursor.rowcount > 0:
                    return True, "用户删除成功"
                else:
                    return False, "用户不存在"
            except Exception as e:
                return False, f"删除失败: {e}"
    
    def authenticate_user(self, username, password, expected_role=None):
        """用户认证"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, username, password_hash, real_name, role, 
                       department, position, email, phone, is_active
                FROM users 
                WHERE username = ? 
            """, (username,))
            
            user = cursor.fetchone()
            
            if not user:
                return False, "用户不存在", None
            
            if not user['is_active']:
                return False, "用户已被禁用", None
            
            # 验证密码
            if user['password_hash'] == self.hash_password(password):
                # 更新最后登录时间
                cursor.execute("""
                    UPDATE users 
                    SET last_login = ? 
                    WHERE id = ?
                """, (datetime.now(), user['id']))
                conn.commit()
                
                # 转换为字典
                user_dict = dict(user)
                
                # 移除敏感信息
                if 'password_hash' in user_dict:
                    del user_dict['password_hash']
                if 'is_active' in user_dict:
                    del user_dict['is_active']

                # 登录入口角色校验：经办人(operator) / 管理员(admin)
                actual_role = user_dict.get('role') or 'operator'
                if expected_role and actual_role != expected_role:
                    if expected_role == 'admin':
                        return False, "该账号不是管理员，请切换“我是经办人”登录", None
                    return False, "该账号不是经办人，请切换“我是管理员”登录", None

                # 兜底显示名：避免 real_name 为空/None 时界面显示“None”
                real_name = str(user_dict.get('real_name') or '').strip()
                if not real_name or real_name.lower() == 'none':
                    user_dict['real_name'] = user_dict.get('username') or '用户'
                
                return True, "登录成功", user_dict
            else:
                return False, "密码错误", None
    
    def get_user_by_id(self, user_id):
        """根据ID获取用户"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, real_name, role, department, 
                       position, email, phone, created_at
                FROM users 
                WHERE id = ?
            """, (user_id,))
            
            user = cursor.fetchone()
            if user:
                return dict(user)
            return None
    
    # ==================== 收文相关方法 ====================
    
    def create_document(self, document_data, user_id):
        """创建收文记录（兼容旧方法）"""
        return self.create_receive_document(document_data, user_id)
    
    def create_receive_document(self, document_data, user_id):
        """创建收文记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 检查文号是否已存在
            if document_data.get('document_no'):
                cursor.execute("SELECT id FROM receive_documents WHERE document_no = ?", 
                             (document_data.get('document_no'),))
                if cursor.fetchone():
                    return False, "文号已存在", None
            
            # 准备插入数据
            columns = ['title', 'user_id', 'created_by', 'created_at', 'updated_at', 'status']
            values = [
                document_data.get('title', ''),
                user_id,
                user_id,
                datetime.now(),
                datetime.now(),
                document_data.get('status') or '已收文'
            ]
            
            # 添加其他字段
            field_mapping = {
                'document_no': 'document_no',
                'issuing_unit': 'issuing_unit',
                'security_level': 'security_level',
                'urgency_level': 'urgency_level',
                'document_type': 'document_type',
                'copies': 'copies',
                'received_date': 'received_date',
                'receiver': 'receiver',
                'storage_location': 'storage_location',
                'original_file_path': 'original_file_path',
                'content_summary': 'content_summary',
                'keywords': 'keywords',
                'remarks': 'remarks'
            }
            
            for field, db_field in field_mapping.items():
                if field in document_data and document_data[field] is not None:
                    columns.append(db_field)
                    values.append(document_data[field])
            
            # 执行插入
            placeholders = ', '.join(['?' for _ in values])
            sql = f"INSERT INTO receive_documents ({', '.join(columns)}) VALUES ({placeholders})"
            
            try:
                cursor.execute(sql, values)
                conn.commit()
                doc_id = cursor.lastrowid
                
                # 记录日志
                cursor.execute("""
                    INSERT INTO document_logs 
                    (document_id, document_type, user_id, action, action_details, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (doc_id, 'receive', user_id, 'create', '收文登记', datetime.now()))
                conn.commit()
                
                return True, "收文记录创建成功", doc_id
                
            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint failed" in str(e) and "document_no" in str(e):
                    return False, "文号已存在", None
                return False, f"数据库错误: {e}", None
            except Exception as e:
                return False, f"保存失败: {e}", None
    
    def search_documents(self, filters=None, page=1, page_size=20):
        """搜索公文（兼容旧方法）"""
        return self.search_receive_documents(filters, page, page_size)
    
    def search_receive_documents(self, filters=None, page=1, page_size=20):
        """搜索收文记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 基础查询
            query = "SELECT * FROM receive_documents WHERE 1=1"
            params = []
            
            if filters:
                # 标题模糊查询
                if filters.get('title'):
                    query += " AND title LIKE ?"
                    params.append(f"%{filters.get('title')}%")
                
                # 文号模糊查询
                if filters.get('document_no'):
                    query += " AND document_no LIKE ?"
                    params.append(f"%{filters.get('document_no')}%")
                
                # 发文单位模糊查询
                if filters.get('issuing_unit'):
                    query += " AND issuing_unit LIKE ?"
                    params.append(f"%{filters.get('issuing_unit')}%")
                
                # 日期范围查询
                if filters.get('start_date') and filters.get('end_date'):
                    query += " AND received_date BETWEEN ? AND ?"
                    params.extend([filters.get('start_date'), filters.get('end_date')])
            
            # 获取总数
            count_query = f"SELECT COUNT(*) as total FROM ({query})"
            cursor.execute(count_query, params)
            total = cursor.fetchone()['total']
            
            # 添加分页
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([page_size, (page - 1) * page_size])
            
            # 执行查询
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # 转换为字典列表
            documents = []
            for row in rows:
                doc = dict(row)
                
                # 处理日期字段
                for key in ['received_date', 'created_at', 'updated_at']:
                    if key in doc and doc[key]:
                        try:
                            if isinstance(doc[key], str):
                                doc[key] = datetime.fromisoformat(doc[key])
                        except:
                            pass
                
                documents.append(doc)
            
            return True, "查询成功", {
                'documents': documents,
                'total': total,
                'page': page,
                'page_size': page_size
            }
    
    # ==================== 发文相关方法 ====================
    
    def create_send_document(self, send_data, user_id):
        """创建发文记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 自动生成文号（发文不再手填）
            if not send_data.get('document_no'):
                document_type = (send_data.get('document_type') or '').strip()
                if not document_type:
                    return False, "文种不能为空", None
                year = send_data.get('doc_year') or self.get_document_number_year()
                ok, msg, new_no = self.generate_document_no(document_type, int(year))
                if not ok:
                    return False, msg, None
                send_data['document_no'] = new_no
            
            # 检查文号是否已存在
            if send_data.get('document_no'):
                cursor.execute("SELECT id FROM send_documents WHERE document_no = ?", 
                             (send_data.get('document_no'),))
                if cursor.fetchone():
                    return False, "文号已存在", None
            
            # 验证必填字段
            if not send_data.get('title'):
                return False, "标题不能为空", None
            if not send_data.get('send_to_unit'):
                return False, "发往单位不能为空", None
            if not send_data.get('security_level'):
                return False, "密级不能为空", None
            if not send_data.get('document_type'):
                return False, "文种不能为空", None
            if not send_data.get('processor'):
                return False, "经办人不能为空", None
            
            # 准备插入数据
            columns = [
                'document_no', 'title', 'issuing_unit', 'send_to_unit', 
                'm_level', 'security_level', 'document_type', 'processor', 'send_date', 'send_status', 'remarks',
                'created_by', 'created_at', 'updated_at', 'status'
            ]
            
            # 处理日期
            send_date = send_data.get('send_date')
            if isinstance(send_date, datetime):
                send_date = send_date.isoformat()
            elif not send_date:
                send_date = datetime.now()
            
            values = [
                send_data.get('document_no'),
                send_data.get('title'),
                send_data.get('issuing_unit', ''),
                send_data.get('send_to_unit'),
                send_data.get('m_level', ''),
                send_data.get('security_level', '普通'),
                send_data.get('document_type', ''),
                send_data.get('processor'),
                send_date,
                '已发文',
                send_data.get('remarks', ''),
                user_id,
                datetime.now(),
                datetime.now(),
                '正常'
            ]
            
            # 执行插入
            placeholders = ', '.join(['?' for _ in values])
            sql = f"INSERT INTO send_documents ({', '.join(columns)}) VALUES ({placeholders})"
            
            try:
                cursor.execute(sql, values)
                conn.commit()
                doc_id = cursor.lastrowid
                
                # 记录日志
                cursor.execute("""
                    INSERT INTO document_logs 
                    (document_id, document_type, user_id, action, action_details, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (doc_id, 'send', user_id, 'create', '发文登记', datetime.now()))
                conn.commit()
                
                return True, "发文记录创建成功", doc_id
                
            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint failed" in str(e) and "document_no" in str(e):
                    return False, "文号已存在", None
                return False, f"数据库错误: {e}", None
            except Exception as e:
                return False, f"保存失败: {e}", None
    
    def get_send_documents(self, filters=None, page=1, page_size=20):
        """查询发文记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 基础查询
            query = "SELECT * FROM send_documents WHERE 1=1"
            params = []
            
            if filters:
                # 文号模糊查询
                if filters.get('document_no'):
                    query += " AND document_no LIKE ?"
                    params.append(f"%{filters.get('document_no')}%")
                
                # 标题模糊查询
                if filters.get('title'):
                    query += " AND title LIKE ?"
                    params.append(f"%{filters.get('title')}%")
                
                # 发往单位模糊查询
                if filters.get('send_to_unit'):
                    query += " AND send_to_unit LIKE ?"
                    params.append(f"%{filters.get('send_to_unit')}%")
                
                # 经办人模糊查询
                if filters.get('processor'):
                    query += " AND processor LIKE ?"
                    params.append(f"%{filters.get('processor')}%")

                # 时间范围查询
                if filters.get('start_date'):
                    query += " AND send_date >= ?"
                    params.append(filters.get('start_date'))
                if filters.get('end_date'):
                    query += " AND send_date <= ?"
                    params.append(filters.get('end_date'))
            
            # 获取总数
            count_query = f"SELECT COUNT(*) as total FROM ({query})"
            cursor.execute(count_query, params)
            total = cursor.fetchone()['total']
            
            # 添加分页
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([page_size, (page - 1) * page_size])
            
            # 执行查询
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # 转换为字典列表
            documents = []
            for row in rows:
                doc = dict(row)
                
                # 处理日期字段
                for key in ['send_date', 'created_at', 'updated_at']:
                    if key in doc and doc[key]:
                        try:
                            if isinstance(doc[key], str):
                                doc[key] = datetime.fromisoformat(doc[key])
                        except:
                            pass
                
                documents.append(doc)
            
            return True, "查询成功", {
                'documents': documents,
                'total': total,
                'page': page,
                'page_size': page_size
            }

    def get_document_type_options(self):
        """获取文号文种下拉项。"""
        default_types = ['鄂厅发', '鄂厅发电', '鄂厅函', '内部公文']
        raw = self.get_config('doc.number.types', json.dumps(default_types, ensure_ascii=False))
        try:
            if isinstance(raw, str):
                arr = json.loads(raw) if raw.strip().startswith('[') else [x.strip() for x in raw.split(',') if x.strip()]
            elif isinstance(raw, list):
                arr = raw
            else:
                arr = default_types
        except Exception:
            arr = default_types
        return arr or default_types

    def set_document_type_options(self, options):
        """设置文号文种下拉项。"""
        opts = [str(x).strip() for x in (options or []) if str(x).strip()]
        if not opts:
            return False, '文种列表不能为空'
        self.set_config('doc.number.types', json.dumps(opts, ensure_ascii=False), '文号文种列表')
        return True, '设置成功'

    def get_document_number_year(self):
        """获取文号年份。"""
        raw = self.get_config('doc.number.year', str(datetime.now().year))
        try:
            year = int(str(raw))
            if 2000 <= year <= 2100:
                return year
        except Exception:
            pass
        return datetime.now().year

    def set_document_number_year(self, year):
        """设置文号年份。"""
        y = int(year)
        if y < 2000 or y > 2100:
            return False, '年份不合法'
        self.set_config('doc.number.year', str(y), '文号年份')
        return True, '设置成功'

    def _document_no_exists(self, document_no):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM send_documents WHERE document_no = ? LIMIT 1", (document_no,))
            if cursor.fetchone():
                return True
            cursor.execute("SELECT 1 FROM receive_documents WHERE document_no = ? LIMIT 1", (document_no,))
            return cursor.fetchone() is not None

    def generate_document_no(self, document_type, year):
        """生成唯一文号：文种【年份】序号号。"""
        prefix = (document_type or '').strip()
        prefix = prefix.replace('[', '【').replace(']', '】').replace('(', '【').replace(')', '】')
        prefix = prefix.replace('〔', '【').replace('〕', '】')
        if not prefix:
            return False, '文种不能为空', None
        try:
            y = int(year)
        except Exception:
            return False, '年份不合法', None

        with self.get_connection() as conn:
            cursor = conn.cursor()
            like_pattern = f"{prefix}【{y}】%号"
            cursor.execute("SELECT document_no FROM send_documents WHERE document_no LIKE ?", (like_pattern,))
            rows = cursor.fetchall() or []
            max_seq = 0
            regex = re.compile(rf"^{re.escape(prefix)}【{y}】(\d+)号$")
            for r in rows:
                no = (r['document_no'] or '').strip()
                m = regex.match(no)
                if m:
                    max_seq = max(max_seq, int(m.group(1)))

            seq = max_seq + 1
            # 保险：校验不重复
            while True:
                candidate = f"{prefix}【{y}】{seq}号"
                if not self._document_no_exists(candidate):
                    return True, '生成成功', candidate
                seq += 1
    
    def delete_send_document(self, doc_id, user_id, is_admin=False):
        """删除发文记录"""
        if not is_admin:
            return False, "只有管理员可以删除发文记录"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute("DELETE FROM send_documents WHERE id = ?", (doc_id,))
                conn.commit()
                
                if cursor.rowcount > 0:
                    # 记录日志
                    cursor.execute("""
                        INSERT INTO document_logs 
                        (document_id, document_type, user_id, action, action_details, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (doc_id, 'send', user_id, 'delete', '删除发文记录', datetime.now()))
                    conn.commit()
                    
                    return True, "发文记录删除成功"
                else:
                    return False, "发文记录不存在"
                    
            except Exception as e:
                return False, f"删除失败: {e}"
    
    # ==================== 流转相关方法 ====================

    def _is_receive_completed_by_doc_no(self, cursor, document_no: str) -> Tuple[bool, str]:
        """校验文号是否已完成收文（无收文记录则视为未完成）。"""
        doc_no = str(document_no or '').strip()
        if not doc_no:
            return False, '文号为空，无法校验收文状态'

        cursor.execute(
            """
            SELECT id, status
            FROM receive_documents
            WHERE document_no = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (doc_no,)
        )
        row = cursor.fetchone()
        if not row:
            return False, f'文号【{doc_no}】尚未完成收文登记，不能继续后续操作'

        status_text = str(row['status'] or '').strip()
        if status_text in ('待收文', '未收文'):
            return False, f'文号【{doc_no}】当前为“{status_text}”，请先完成收文后再操作'

        return True, '收文状态已完成'
    
    def create_circulation_record(self, circulation_data, user_id):
        """创建流转记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 验证文档是否存在
            doc_type = circulation_data.get('document_type')
            doc_id = circulation_data.get('document_id')
            
            if doc_type == 'receive':
                table_name = 'receive_documents'
            elif doc_type == 'send':
                table_name = 'send_documents'
            else:
                return False, "文档类型错误", None
            
            cursor.execute(f"SELECT id FROM {table_name} WHERE id = ?", (doc_id,))
            if not cursor.fetchone():
                return False, "文档不存在", None

            # 流转前校验：必须已完成收文（收文文档自身视为已完成，发文需存在对应收文记录）
            cursor.execute(f"SELECT document_no FROM {table_name} WHERE id = ?", (doc_id,))
            doc_row = cursor.fetchone()
            doc_no = (doc_row['document_no'] if doc_row and 'document_no' in doc_row.keys() else '')
            if doc_type == 'send':
                ok_receive, msg_receive = self._is_receive_completed_by_doc_no(cursor, doc_no)
                if not ok_receive:
                    return False, msg_receive, None
            
            # 准备插入数据
            columns = [
                'document_id', 'document_type', 'circulation_type',
                'next_node_unit', 'next_node_person', 'current_holder_id',
                'borrow_requester_id', 'borrow_date', 'due_date', 'status',
                'remarks', 'created_by', 'created_at', 'updated_at'
            ]
            
            # 处理日期
            borrow_date = circulation_data.get('borrow_date')
            due_date = circulation_data.get('due_date')
            
            if borrow_date and isinstance(borrow_date, datetime):
                borrow_date = borrow_date.isoformat()
            
            if due_date and isinstance(due_date, datetime):
                due_date = due_date.isoformat()
            
            values = [
                doc_id,
                doc_type,
                circulation_data.get('circulation_type'),
                circulation_data.get('next_node_unit', ''),
                circulation_data.get('next_node_person', ''),
                circulation_data.get('current_holder_id'),
                circulation_data.get('borrow_requester_id'),
                borrow_date,
                due_date,
                circulation_data.get('status', '待确认'),
                circulation_data.get('remarks', ''),
                user_id,
                datetime.now(),
                datetime.now()
            ]
            
            # 执行插入
            placeholders = ', '.join(['?' for _ in values])
            sql = f"INSERT INTO circulation_records ({', '.join(columns)}) VALUES ({placeholders})"
            
            try:
                cursor.execute(sql, values)
                conn.commit()
                circ_id = cursor.lastrowid

                circulation_type = circulation_data.get('circulation_type')

                # 同步更新原始文档状态：使用创建时传入状态（已流转/已借出）
                doc_status = circulation_data.get('status', '待确认')
                if doc_type == 'receive':
                    cursor.execute(
                        "UPDATE receive_documents SET status = ?, updated_at = ? WHERE id = ?",
                        (doc_status, datetime.now(), doc_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE send_documents SET send_status = ?, updated_at = ? WHERE id = ?",
                        (doc_status, datetime.now(), doc_id)
                    )

                # 记录流转日志
                cursor.execute("""
                    INSERT INTO document_logs
                    (document_id, document_type, user_id, action, action_details, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (doc_id, doc_type, user_id, 'circulation_create', f'发起流转: {circulation_type}', datetime.now()))
                conn.commit()
                
                return True, "流转记录创建成功", circ_id
                
            except Exception as e:
                return False, f"创建失败: {e}", None
    
    def update_circulation_status(self, circulation_id, status, user_id):
        """更新流转状态"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 检查记录是否存在
            cursor.execute("SELECT id, document_id, document_type, circulation_type, status FROM circulation_records WHERE id = ?", (circulation_id,))
            rec = cursor.fetchone()
            if not rec:
                return False, "流转记录不存在"
            doc_id = rec['document_id']
            doc_type = rec['document_type']
            circulation_type = rec['circulation_type']
            current_status = rec['status']

            if status == '已归还':
                if circulation_type != '借阅':
                    return False, '仅“借阅”类型支持归还确认'
                if current_status != '已借出':
                    return False, '该借阅记录尚未完成领取，不能直接归还'
            
            # 如果是归还操作，记录归还时间
            if status == '已归还':
                cursor.execute("""
                    UPDATE circulation_records 
                    SET status = ?, return_date = ?, updated_at = ?
                    WHERE id = ?
                """, (status, datetime.now(), datetime.now(), circulation_id))
            else:
                cursor.execute("""
                    UPDATE circulation_records 
                    SET status = ?, updated_at = ?
                    WHERE id = ?
                """, (status, datetime.now(), circulation_id))

            # 同步更新文档状态
            if doc_type == 'receive':
                cursor.execute(
                    "UPDATE receive_documents SET status = ?, updated_at = ? WHERE id = ?",
                    (status, datetime.now(), doc_id)
                )
            elif doc_type == 'send':
                cursor.execute(
                    "UPDATE send_documents SET send_status = ?, updated_at = ? WHERE id = ?",
                    (status, datetime.now(), doc_id)
                )

            # 记录状态变更日志
            cursor.execute("""
                INSERT INTO document_logs
                (document_id, document_type, user_id, action, action_details, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (doc_id, doc_type, user_id, 'circulation_status', f'流转状态更新为: {status}', datetime.now()))
            
            conn.commit()
            return True, "流转状态更新成功"
    
    def get_circulation_records(self, filters=None, page=1, page_size=20):
        """查询流转记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # ✅ 修改查询，明确指定所有需要的字段
            query = """
                SELECT 
                    cr.id,
                    cr.document_id,
                    cr.document_type,
                    cr.circulation_type,
                    cr.next_node_unit,
                    cr.next_node_person,
                    cr.current_holder_id,
                    cr.borrow_requester_id,
                    cr.borrow_date,
                    cr.due_date,
                    cr.return_date,
                    cr.status,
                    cr.remarks,
                    cr.created_by,
                    cr.created_at,
                    cr.updated_at,
                    CASE WHEN cr.document_type = 'receive' THEN rd.id ELSE NULL END as receive_id,
                    CASE WHEN cr.document_type = 'send' THEN sd.id ELSE NULL END as send_id,
                    CASE WHEN cr.document_type = 'receive' THEN rd.document_no ELSE sd.document_no END as document_no,
                    CASE WHEN cr.document_type = 'receive' THEN rd.title ELSE sd.title END as title,
                    (
                        SELECT MAX(pr.pickup_time)
                        FROM pickup_records pr
                        WHERE pr.document_no = CASE WHEN cr.document_type = 'receive' THEN rd.document_no ELSE sd.document_no END
                    ) as pickup_time
                FROM circulation_records cr
                LEFT JOIN receive_documents rd ON cr.document_type = 'receive' AND cr.document_id = rd.id
                LEFT JOIN send_documents sd ON cr.document_type = 'send' AND cr.document_id = sd.id
                WHERE 1=1
            """
            params = []
            
            if filters:
                # 文档ID
                if filters.get('document_id'):
                    query += " AND cr.document_id = ?"
                    params.append(filters.get('document_id'))

                # 时间范围
                if filters.get('start_date'):
                    query += " AND cr.created_at >= ?"
                    params.append(filters.get('start_date'))
                if filters.get('end_date'):
                    query += " AND cr.created_at <= ?"
                    params.append(filters.get('end_date'))
                
                # 文档类型
                if filters.get('document_type'):
                    query += " AND cr.document_type = ?"
                    params.append(filters.get('document_type'))
                
                # 流转类型
                if filters.get('circulation_type'):
                    query += " AND cr.circulation_type = ?"
                    params.append(filters.get('circulation_type'))
                
                # 状态
                if filters.get('status'):
                    query += " AND cr.status = ?"
                    params.append(filters.get('status'))
            
            # 获取总数
            count_query = f"SELECT COUNT(*) as total FROM ({query}) AS circulation_count"
            cursor.execute(count_query, params)
            total = cursor.fetchone()['total']
            
            # 添加排序和分页
            query += " ORDER BY cr.created_at DESC LIMIT ? OFFSET ?"
            params.extend([page_size, (page - 1) * page_size])
            
            # 执行查询
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # 转换为字典列表
            records = []
            for row in rows:
                # 将行对象转换为字典
                record = {}
                for i, col in enumerate(cursor.description):
                    col_name = col[0]
                    record[col_name] = row[i]
                
                # ✅ 确保id字段存在
                if 'id' not in record and row[0] is not None:
                    record['id'] = row[0]
                
                # 处理日期字段
                for key in ['borrow_date', 'due_date', 'return_date', 'created_at', 'updated_at']:
                    if key in record and record[key]:
                        try:
                            if isinstance(record[key], str):
                                record[key] = datetime.fromisoformat(record[key].replace('Z', '+00:00'))
                        except Exception as e:
                            print(f"[WARNING] 解析日期{key}失败: {record[key]}, 错误: {e}")
                
                records.append(record)
            
            return True, "查询成功", {
                'records': records,
                'total': total,
                'page': page,
                'page_size': page_size
            }

    # ==================== 取件登记相关方法 ====================

    def _get_latest_document_snapshot(self, cursor, document_no: str) -> dict:
        """按文号获取最新公文基础信息（用于取件信息回填）。"""
        doc_no = str(document_no or '').strip()
        if not doc_no:
            return {}

        snapshot = {
            'title': '',
            'issuing_unit': '',
            'security_level': '',
            'received_date': ''
        }

        # 优先收文信息（含收文日期）
        cursor.execute(
            """
            SELECT title, issuing_unit, security_level, received_date, created_at
            FROM receive_documents
            WHERE document_no = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (doc_no,)
        )
        rcv = cursor.fetchone()
        if rcv:
            snapshot['title'] = rcv['title'] or ''
            snapshot['issuing_unit'] = rcv['issuing_unit'] or ''
            snapshot['security_level'] = rcv['security_level'] or ''
            rd = rcv['received_date']
            snapshot['received_date'] = str(rd).replace('T', ' ')[:10] if rd else ''

        # 发文信息作为补充
        cursor.execute(
            """
            SELECT title, issuing_unit, security_level, send_date, created_at
            FROM send_documents
            WHERE document_no = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (doc_no,)
        )
        snd = cursor.fetchone()
        if snd:
            if not snapshot['title']:
                snapshot['title'] = snd['title'] or ''
            if not snapshot['issuing_unit']:
                snapshot['issuing_unit'] = snd['issuing_unit'] or ''
            if not snapshot['security_level']:
                snapshot['security_level'] = snd['security_level'] or ''
            if not snapshot['received_date']:
                sd = snd['send_date']
                snapshot['received_date'] = str(sd).replace('T', ' ')[:10] if sd else ''

        return snapshot

    def create_pickup_record(self, pickup_data, user_id):
        """创建取件登记记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if not pickup_data.get('document_no'):
                return False, "文号不能为空", None
            if not pickup_data.get('destination'):
                return False, "去向不能为空", None
            if not pickup_data.get('picker_name'):
                return False, "取件人不能为空", None

            doc_no = str(pickup_data.get('document_no') or '').strip()

            # 取件前校验：必须先完成收文
            ok_receive, msg_receive = self._is_receive_completed_by_doc_no(cursor, doc_no)
            if not ok_receive:
                return False, msg_receive, None

            snapshot = self._get_latest_document_snapshot(cursor, doc_no)

            pickup_time = pickup_data.get('pickup_time') or datetime.now()
            received_date = pickup_data.get('received_date') or snapshot.get('received_date')

            title = (pickup_data.get('title') or '').strip() or snapshot.get('title', '')
            issuing_unit = (pickup_data.get('issuing_unit') or '').strip() or snapshot.get('issuing_unit', '')
            security_level = (pickup_data.get('security_level') or '').strip() or snapshot.get('security_level', '')

            if isinstance(pickup_time, datetime):
                pickup_time = pickup_time.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(pickup_time, date):
                pickup_time = datetime.combine(pickup_time, datetime.now().time()).strftime('%Y-%m-%d %H:%M:%S')

            if isinstance(received_date, datetime):
                received_date = received_date.strftime('%Y-%m-%d')
            elif isinstance(received_date, date):
                received_date = received_date.strftime('%Y-%m-%d')

            columns = [
                'document_no', 'title', 'issuing_unit', 'received_date',
                'security_level', 'destination', 'picker_name', 'picker_contact',
                'pickup_time', 'return_time', 'status', 'remarks',
                'created_by', 'created_at', 'updated_at'
            ]
            values = [
                pickup_data.get('document_no'),
                title,
                issuing_unit,
                received_date,
                security_level,
                pickup_data.get('destination'),
                pickup_data.get('picker_name'),
                pickup_data.get('picker_contact', ''),
                pickup_time,
                pickup_data.get('return_time'),
                pickup_data.get('status', '已取走'),
                pickup_data.get('remarks', ''),
                user_id,
                datetime.now(),
                datetime.now()
            ]

            try:
                placeholders = ', '.join(['?' for _ in values])
                sql = f"INSERT INTO pickup_records ({', '.join(columns)}) VALUES ({placeholders})"
                cursor.execute(sql, values)
                conn.commit()
                record_id = cursor.lastrowid
                return True, "取件登记成功", record_id
            except Exception as e:
                return False, f"保存失败: {e}", None

    def get_latest_designated_picker_by_doc_no(self, document_no: str):
        """按文号获取最近一次流转中指定的取件人/单位。"""
        doc_no = str(document_no or '').strip()
        if not doc_no:
            return False, '文号不能为空', None

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    cr.next_node_person,
                    cr.next_node_unit,
                    cr.created_at,
                    CASE WHEN cr.document_type='receive' THEN rd.document_no ELSE sd.document_no END AS document_no
                FROM circulation_records cr
                LEFT JOIN receive_documents rd ON cr.document_type='receive' AND cr.document_id=rd.id
                LEFT JOIN send_documents sd ON cr.document_type='send' AND cr.document_id=sd.id
                WHERE (CASE WHEN cr.document_type='receive' THEN rd.document_no ELSE sd.document_no END) = ?
                  AND COALESCE(cr.next_node_person, '') <> ''
                ORDER BY cr.created_at DESC
                LIMIT 1
                """,
                (doc_no,)
            )
            row = cursor.fetchone()
            if not row:
                return False, '未找到指定取件人信息', None
            return True, '查询成功', {
                'document_no': row['document_no'] or doc_no,
                'picker_name': row['next_node_person'] or '',
                'picker_unit': row['next_node_unit'] or '',
                'circulation_time': row['created_at'] or ''
            }

    def mark_pickup_returned(self, record_id, return_time=None, user_id=None):
        """登记归还时间"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            rt = return_time or datetime.now()
            if isinstance(rt, datetime):
                rt = rt.strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute(
                """
                UPDATE pickup_records
                SET return_time = ?, status = '已归还', updated_at = ?
                WHERE id = ?
                """,
                (rt, datetime.now(), record_id)
            )
            conn.commit()

            if cursor.rowcount > 0:
                return True, "归还登记成功"
            return False, "记录不存在"

    def search_pickup_records(self, filters=None, page=1, page_size=20):
        """检索取件登记记录"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM pickup_records WHERE 1=1"
            params = []

            if filters:
                if filters.get('document_no'):
                    query += " AND document_no LIKE ?"
                    params.append(f"%{filters.get('document_no')}%")
                if filters.get('issuing_unit'):
                    query += " AND issuing_unit LIKE ?"
                    params.append(f"%{filters.get('issuing_unit')}%")
                if filters.get('security_level'):
                    query += " AND security_level = ?"
                    params.append(filters.get('security_level'))
                if filters.get('title'):
                    query += " AND title LIKE ?"
                    params.append(f"%{filters.get('title')}%")
                if filters.get('destination'):
                    query += " AND destination LIKE ?"
                    params.append(f"%{filters.get('destination')}%")
                if filters.get('picker_name'):
                    query += " AND picker_name LIKE ?"
                    params.append(f"%{filters.get('picker_name')}%")
                if filters.get('start_date'):
                    query += " AND pickup_time >= ?"
                    params.append(filters.get('start_date'))
                if filters.get('end_date'):
                    query += " AND pickup_time <= ?"
                    params.append(filters.get('end_date'))

            count_query = f"SELECT COUNT(*) as total FROM ({query})"
            cursor.execute(count_query, params)
            total = cursor.fetchone()['total']

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([page_size, (page - 1) * page_size])
            cursor.execute(query, params)
            rows = cursor.fetchall()

            records = [dict(row) for row in rows]

            # 回填历史记录中未登记的标题/发文单位/密级/收文日期
            doc_info_cache = {}
            for rec in records:
                doc_no = str(rec.get('document_no') or '').strip()
                if not doc_no:
                    continue
                need_fill = not rec.get('title') or not rec.get('issuing_unit') or not rec.get('security_level') or not rec.get('received_date')
                if not need_fill:
                    continue
                if doc_no not in doc_info_cache:
                    doc_info_cache[doc_no] = self._get_latest_document_snapshot(cursor, doc_no)
                info = doc_info_cache.get(doc_no) or {}
                if not rec.get('title'):
                    rec['title'] = info.get('title', '')
                if not rec.get('issuing_unit'):
                    rec['issuing_unit'] = info.get('issuing_unit', '')
                if not rec.get('security_level'):
                    rec['security_level'] = info.get('security_level', '')
                if not rec.get('received_date'):
                    rec['received_date'] = info.get('received_date', '')

            return True, "查询成功", {
                'records': records,
                'total': total,
                'page': page,
                'page_size': page_size
            }
    
    # ==================== 统计方法 ====================
    
    def get_statistics(self, start_date=None, end_date=None):
        """获取统计信息 - 修复版"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # ✅ 修复1：确保日期不为None
                from datetime import datetime, timedelta
                if not start_date:
                    start_date = datetime.now() - timedelta(days=30)
                if not end_date:
                    end_date = datetime.now()
                
                # ✅ 修复2：格式化日期用于查询
                if isinstance(start_date, datetime):
                    start_date_str = start_date.strftime('%Y-%m-%d 00:00:00')
                else:
                    start_date_str = str(start_date)
                
                if isinstance(end_date, datetime):
                    end_date_str = end_date.strftime('%Y-%m-%d 23:59:59')
                else:
                    end_date_str = str(end_date)
                
                print(f"📅 统计查询日期范围: {start_date_str} 到 {end_date_str}")
                
                # 收文统计
                cursor.execute("""
                    SELECT COUNT(*) as count 
                    FROM receive_documents 
                    WHERE created_at BETWEEN ? AND ?
                """, (start_date_str, end_date_str))
                
                row = cursor.fetchone()
                receive_count = row['count'] if row and row['count'] is not None else 0
                
                print(f"✅ 收文查询结果: {receive_count}")
                
                # 发文统计
                cursor.execute("""
                    SELECT COUNT(*) as count 
                    FROM send_documents 
                    WHERE created_at BETWEEN ? AND ?
                """, (start_date_str, end_date_str))
                
                row = cursor.fetchone()
                send_count = row['count'] if row and row['count'] is not None else 0
                print(f"✅ 发文查询结果: {send_count}")
                
                # 流转统计
                cursor.execute("""
                    SELECT COUNT(*) as count 
                    FROM circulation_records 
                    WHERE created_at BETWEEN ? AND ?
                """, (start_date_str, end_date_str))
                
                row = cursor.fetchone()
                circulation_count = row['count'] if row and row['count'] is not None else 0
                print(f"✅ 流转查询结果: {circulation_count}")
                
                # 流转状态统计
                circulation_status = {}
                cursor.execute("""
                    SELECT status, COUNT(*) as count 
                    FROM circulation_records 
                    WHERE created_at BETWEEN ? AND ?
                    GROUP BY status
                """, (start_date_str, end_date_str))
                
                rows = cursor.fetchall()
                if rows:
                    for row in rows:
                        if row and 'status' in row and 'count' in row:
                            status = row['status'] or '未知'
                            count = row['count'] or 0
                            circulation_status[status] = count
                
                print(f"✅ 流转状态统计: {circulation_status}")
                
                # ✅ 关键修复：返回datetime对象而不是字符串
                return True, "统计成功", {
                    'receive_count': receive_count,
                    'send_count': send_count,
                    'circulation_count': circulation_count,
                    'circulation_status': circulation_status,
                    'start_date': start_date,  # ✅ 返回datetime对象
                    'end_date': end_date       # ✅ 返回datetime对象
                }
                
        except Exception as e:
            error_msg = f"统计查询失败: {str(e)}"
            print(f"❌ {error_msg}")
            return False, error_msg, None

    def get_statistics_detail_records(self, start_date=None, end_date=None, doc_no_keyword: str = None):
        """获取统一统计明细（收文/发文/流转/取件），支持按文号关键字过滤。"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                if not start_date:
                    start_date = datetime.now() - timedelta(days=30)
                if not end_date:
                    end_date = datetime.now()

                if isinstance(start_date, datetime):
                    start_date_str = start_date.strftime('%Y-%m-%d 00:00:00')
                else:
                    start_date_str = f"{start_date} 00:00:00"

                if isinstance(end_date, datetime):
                    end_date_str = end_date.strftime('%Y-%m-%d 23:59:59')
                else:
                    end_date_str = f"{end_date} 23:59:59"

                doc_map = {}

                def _to_dt(v):
                    if not v:
                        return None
                    if isinstance(v, datetime):
                        return v
                    s = str(v).strip().replace('T', ' ')
                    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
                        try:
                            return datetime.strptime(s[:26], fmt)
                        except Exception:
                            continue
                    return None

                def _fmt(v):
                    if not v:
                        return ''
                    dt = _to_dt(v)
                    if dt:
                        return dt.strftime('%Y-%m-%d %H:%M:%S')
                    s = str(v).replace('T', ' ').strip()
                    return s[:19] if len(s) >= 19 else s

                def _pick_time(cur, new, prefer='max'):
                    c = _to_dt(cur)
                    n = _to_dt(new)
                    if not c:
                        return _fmt(new)
                    if not n:
                        return _fmt(cur)
                    if prefer == 'min':
                        return _fmt(n if n < c else c)
                    return _fmt(n if n > c else c)

                def _merge_text(cur: str, new: str):
                    a = [x for x in [str(cur or '').strip(), str(new or '').strip()] if x]
                    if not a:
                        return ''
                    uniq = []
                    for x in a:
                        if x not in uniq:
                            uniq.append(x)
                    return ' / '.join(uniq)

                def _get_doc(key_doc_no: str, title='', issuing=''):
                    key = str(key_doc_no or '').strip()
                    if not key:
                        key = f"__NO_DOC_NO__::{title or ''}::{issuing or ''}"
                    if key not in doc_map:
                        doc_map[key] = {
                            '文号': key_doc_no or '',
                            '标题': title or '',
                            '密级': '',
                            '紧急程度': '',
                            '发文单位': issuing or '',
                            '发文时间': '',
                            '去向/发往': '',
                            '经办人': '',
                            '收文时间': '',
                            '发起流转时间': '',
                            '流转类型': '',
                            '取件单位': '',
                            '取件人': '',
                            '取件时间': '',
                            '归还时间': '',
                            '状态': '',
                            '备注': '',
                            '__receive_id': '',
                            '__send_id': '',
                            '__status_set': set(),
                        }
                    return doc_map[key]

                # 收文
                cursor.execute("""
                    SELECT id, document_no, title, issuing_unit, received_date, security_level,
                           urgency_level, receiver, status, remarks, created_at
                    FROM receive_documents
                    WHERE created_at BETWEEN ? AND ?
                    ORDER BY created_at DESC
                """, (start_date_str, end_date_str))
                for r in cursor.fetchall() or []:
                    rec = _get_doc(r['document_no'] or '', r['title'] or '', r['issuing_unit'] or '')
                    rec['标题'] = rec['标题'] or (r['title'] or '')
                    rec['发文单位'] = rec['发文单位'] or (r['issuing_unit'] or '')
                    rec['密级'] = rec['密级'] or (r['security_level'] or '')
                    rec['紧急程度'] = rec['紧急程度'] or (r['urgency_level'] or '')
                    rec['经办人'] = _merge_text(rec['经办人'], r['receiver'] or '')
                    rec['收文时间'] = _pick_time(rec['收文时间'], r['received_date'] or r['created_at'], prefer='max')
                    rec['备注'] = _merge_text(rec['备注'], r['remarks'] or '')
                    rec['__receive_id'] = rec['__receive_id'] or r['id']
                    rec['__status_set'].add('已收文')

                # 发文
                cursor.execute("""
                    SELECT id, document_no, title, issuing_unit, send_to_unit, security_level,
                           processor, send_status, send_date, remarks, created_at
                    FROM send_documents
                    WHERE created_at BETWEEN ? AND ?
                    ORDER BY created_at DESC
                """, (start_date_str, end_date_str))
                for r in cursor.fetchall() or []:
                    rec = _get_doc(r['document_no'] or '', r['title'] or '', r['issuing_unit'] or '')
                    rec['标题'] = rec['标题'] or (r['title'] or '')
                    rec['发文单位'] = rec['发文单位'] or (r['issuing_unit'] or '')
                    rec['密级'] = rec['密级'] or (r['security_level'] or '')
                    rec['发文时间'] = _pick_time(rec['发文时间'], r['send_date'] or r['created_at'], prefer='max')
                    rec['去向/发往'] = _merge_text(rec['去向/发往'], r['send_to_unit'] or '')
                    rec['经办人'] = _merge_text(rec['经办人'], r['processor'] or '')
                    rec['备注'] = _merge_text(rec['备注'], r['remarks'] or '')
                    rec['__send_id'] = rec['__send_id'] or r['id']
                    rec['__status_set'].add('已发文')

                # 流转
                cursor.execute("""
                    SELECT
                        cr.id, cr.document_id, cr.document_type, cr.circulation_type, cr.next_node_unit, cr.next_node_person,
                        cr.status, cr.borrow_date, cr.return_date, cr.created_at, cr.remarks,
                        CASE WHEN cr.document_type='receive' THEN rd.document_no ELSE sd.document_no END AS document_no,
                        CASE WHEN cr.document_type='receive' THEN rd.title ELSE sd.title END AS title,
                        CASE WHEN cr.document_type='receive' THEN rd.issuing_unit ELSE sd.issuing_unit END AS issuing_unit,
                        CASE WHEN cr.document_type='receive' THEN rd.received_date ELSE '' END AS received_date,
                        CASE WHEN cr.document_type='send' THEN sd.send_date ELSE '' END AS send_date,
                        CASE WHEN cr.document_type='receive' THEN rd.receiver ELSE sd.processor END AS handler_name
                    FROM circulation_records cr
                    LEFT JOIN receive_documents rd ON cr.document_type='receive' AND cr.document_id=rd.id
                    LEFT JOIN send_documents sd ON cr.document_type='send' AND cr.document_id=sd.id
                    WHERE cr.created_at BETWEEN ? AND ?
                    ORDER BY cr.created_at DESC
                """, (start_date_str, end_date_str))
                for r in cursor.fetchall() or []:
                    rec = _get_doc(r['document_no'] or '', r['title'] or '', r['issuing_unit'] or '')
                    rec['标题'] = rec['标题'] or (r['title'] or '')
                    rec['发文单位'] = rec['发文单位'] or (r['issuing_unit'] or '')
                    rec['发文时间'] = _pick_time(rec['发文时间'], r['send_date'], prefer='max')
                    rec['收文时间'] = _pick_time(rec['收文时间'], r['received_date'], prefer='max')
                    rec['经办人'] = _merge_text(rec['经办人'], r['handler_name'] or '')
                    rec['发起流转时间'] = _pick_time(rec['发起流转时间'], r['created_at'], prefer='max')
                    rec['流转类型'] = _merge_text(rec['流转类型'], r['circulation_type'] or '')
                    rec['取件单位'] = _merge_text(rec['取件单位'], r['next_node_unit'] or '')
                    rec['取件人'] = _merge_text(rec['取件人'], r['next_node_person'] or '')
                    rec['取件时间'] = _pick_time(rec['取件时间'], r['borrow_date'], prefer='max')
                    rec['归还时间'] = _pick_time(rec['归还时间'], r['return_date'], prefer='max')
                    rec['备注'] = _merge_text(rec['备注'], r['remarks'] or '')
                    if r['document_type'] == 'receive':
                        rec['__receive_id'] = rec['__receive_id'] or r['document_id']
                    else:
                        rec['__send_id'] = rec['__send_id'] or r['document_id']
                    rec['__status_set'].add('已流转')
                    status_raw = str(r['status'] or '').strip()
                    for token in ('已流转', '已借出', '已归还', '已完成'):
                        if token in status_raw:
                            rec['__status_set'].add(token)

                # 取件
                cursor.execute("""
                    SELECT id, document_no, title, issuing_unit, received_date, security_level,
                           destination, picker_name, status, pickup_time, return_time, remarks, created_at
                    FROM pickup_records
                    WHERE created_at BETWEEN ? AND ?
                    ORDER BY created_at DESC
                """, (start_date_str, end_date_str))
                for r in cursor.fetchall() or []:
                    rec = _get_doc(r['document_no'] or '', r['title'] or '', r['issuing_unit'] or '')
                    rec['标题'] = rec['标题'] or (r['title'] or '')
                    rec['发文单位'] = rec['发文单位'] or (r['issuing_unit'] or '')
                    rec['密级'] = rec['密级'] or (r['security_level'] or '')
                    rec['收文时间'] = _pick_time(rec['收文时间'], r['received_date'], prefer='max')
                    rec['去向/发往'] = _merge_text(rec['去向/发往'], r['destination'] or '')
                    rec['取件单位'] = _merge_text(rec['取件单位'], r['destination'] or '')
                    rec['取件人'] = _merge_text(rec['取件人'], r['picker_name'] or '')

                    pickup_raw = r['pickup_time']
                    pickup_text = str(pickup_raw or '').replace('T', ' ').strip()
                    # 历史数据若仅保存日期或显示为00:00:00，回退使用创建时间
                    created_at_val = r['created_at'] if 'created_at' in r.keys() else None
                    if pickup_text and (len(pickup_text) <= 10 or pickup_text.endswith('00:00:00')) and created_at_val:
                        pickup_raw = created_at_val

                    rec['取件时间'] = _pick_time(rec['取件时间'], pickup_raw, prefer='max')
                    rec['归还时间'] = _pick_time(rec['归还时间'], r['return_time'], prefer='max')
                    rec['备注'] = _merge_text(rec['备注'], r['remarks'] or '')
                    if r['pickup_time']:
                        rec['__status_set'].add('已取出')
                    if r['return_time']:
                        rec['__status_set'].add('已归还')
                    status_raw = str(r['status'] or '').strip()
                    for token in ('已取出', '已归还'):
                        if token in status_raw:
                            rec['__status_set'].add(token)

                # 文号过滤（按聚合后记录过滤）
                records = list(doc_map.values())

                # 聚合状态串
                status_order = ['已发文', '已收文', '未收文(异常)', '已流转', '已借出', '已取出', '已归还', '已完成']
                for rec in records:
                    status_set = rec.get('__status_set', set())
                    has_downstream = any(s in status_set for s in ('已流转', '已借出', '已取出', '已归还', '已完成'))
                    if has_downstream and '已收文' not in status_set:
                        status_set.add('未收文(异常)')
                    seq = [s for s in status_order if s in status_set]
                    rec['状态'] = '/'.join(seq)

                if doc_no_keyword:
                    kw = str(doc_no_keyword).strip()
                    if kw:
                        records = [x for x in records if kw in str(x.get('文号') or '')]

                def _sort_key(rec: dict):
                    for k in ('发起流转时间', '取件时间', '归还时间', '收文时间', '发文时间'):
                        dt = _to_dt(rec.get(k))
                        if dt:
                            return dt
                    return datetime.min

                for rec in records:
                    # 清理内部字段
                    rec.pop('__status_set', None)

                records.sort(key=_sort_key, reverse=True)
                return True, '查询成功', records
        except Exception as e:
            return False, f'统计明细查询失败: {e}', []

    def get_universal_query_detail_records(self, doc_no_keyword: str):
        """通用公文查询明细：按文号关键字返回全链路记录。"""
        if not str(doc_no_keyword or '').strip():
            return False, '文号不能为空', []
        return self.get_statistics_detail_records(date(2000, 1, 1), datetime.now(), doc_no_keyword=doc_no_keyword)

    # ==================== 上下文管理器方法 ====================
        
    def session_scope(self):
        """提供数据库会话上下文（兼容SQLAlchemy风格）"""
        from contextlib import contextmanager
        
        @contextmanager
        def get_session():
            """获取数据库会话"""
            with self.get_connection() as conn:
                yield conn
        
        return get_session()
    
    # ==================== 配置管理方法 ====================
    
    def get_config(self, key, default=None):
        """获取系统配置"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 检查config表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_config'")
            if not cursor.fetchone():
                # 创建system_config表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS system_config (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        description TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 插入默认配置
                default_configs = [
                    ('system.name', '公文智能管理系统', '系统名称'),
                    ('system.version', '2.0', '系统版本'),
                    ('system.company', '默认公司', '公司名称'),
                ]
                
                cursor.executemany(
                    "INSERT OR IGNORE INTO system_config (key, value, description) VALUES (?, ?, ?)",
                    default_configs
                )
                
                conn.commit()
            
            # 查询配置
            cursor.execute("SELECT value FROM system_config WHERE key = ?", (key,))
            row = cursor.fetchone()
            
            if row:
                return row['value']
            else:
                return default
    
    def set_config(self, key, value, description=None):
        """设置系统配置"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 检查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_config'")
            if not cursor.fetchone():
                # 创建表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS system_config (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        description TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            
            if description:
                cursor.execute("""
                    INSERT OR REPLACE INTO system_config (key, value, description, updated_at) 
                    VALUES (?, ?, ?, ?)
                """, (key, value, description, datetime.now()))
            else:
                cursor.execute("""
                    INSERT OR REPLACE INTO system_config (key, value, updated_at) 
                    VALUES (?, ?, ?)
                """, (key, value, datetime.now()))
            
            conn.commit()
            return True
    
    def get_all_configs(self):
        """获取所有系统配置"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 检查表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_config'")
            if not cursor.fetchone():
                return []
            
            cursor.execute("SELECT key, value, description FROM system_config ORDER BY key")
            rows = cursor.fetchall()
            
            configs = []
            for row in rows:
                configs.append({
                    'key': row['key'],
                    'value': row['value'],
                    'description': row['description']
                })
            
            return configs
    
    def update_ocr_result(self, document_id, ocr_path):
        """更新OCR结果路径"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE receive_documents 
                    SET ocr_result_path = ?
                    WHERE id = ?
                """, (ocr_path, document_id))
                conn.commit()
                return True, "更新成功"
        except Exception as e:
            return False, f"更新失败: {str(e)}"
        
    def update_document(self, document_id, data):
        """更新公文信息"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建更新语句
                set_clause = ", ".join([f"{key} = ?" for key in data.keys()])
                values = list(data.values())
                values.append(document_id)
                
                cursor.execute(f"""
                    UPDATE receive_documents 
                    SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, values)
                
                conn.commit()
                return True, "公文更新成功"
        except Exception as e:
            return False, f"更新公文失败: {str(e)}"    
        
    def get_receive_document_by_id(self, document_id):
        """根据ID获取收文文档"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM receive_documents WHERE id = ?", (document_id,))
                row = cursor.fetchone()
                
                if row:
                    # 转换为字典
                    document = dict(row)
                    
                    # 处理日期字段
                    date_fields = ['received_date', 'created_at', 'updated_at']
                    for field in date_fields:
                        if field in document and document[field]:
                            try:
                                if isinstance(document[field], str):
                                    # 尝试解析日期字符串
                                    document[field] = datetime.fromisoformat(document[field].replace('Z', '+00:00'))
                            except:
                                pass
                    
                    return True, "获取成功", document
                else:
                    return False, f"未找到ID为{document_id}的文档", None
        except Exception as e:
            return False, f"查询文档失败: {str(e)}", None
        
    def get_circulation_by_id(self, circ_id):
        """根据ID获取流转记录"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT cr.*, 
                        u1.username as current_holder_name,
                        u2.username as borrow_requester_name,
                        u3.username as created_by_name
                    FROM circulation_records cr
                    LEFT JOIN users u1 ON cr.current_holder_id = u1.id
                    LEFT JOIN users u2 ON cr.borrow_requester_id = u2.id
                    LEFT JOIN users u3 ON cr.created_by = u3.id
                    WHERE cr.id = ?
                """, (circ_id,))
                
                row = cursor.fetchone()
                if row:
                    # 转换为字典
                    record = dict(row)
                    
                    # 调试输出
                    print(f"[DEBUG] 数据库查询返回的记录: {record}")
                    
                    return True, "查询成功", record
                else:
                    return False, f"未找到流转记录 ID: {circ_id}", None
        except Exception as e:
            print(f"[ERROR] 查询失败: {e}")
            return False, f"查询失败: {e}", None
        
    def get_document_count_by_date_range(self, table_name, start_date, end_date):
        """获取指定日期范围内的文档数量"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    SELECT COUNT(*) as count 
                    FROM {table_name} 
                    WHERE created_at BETWEEN ? AND ?
                """, (start_date, end_date))
                row = cursor.fetchone()
                return row['count'] if row and row['count'] is not None else 0
        except Exception as e:
            print(f"统计{table_name}失败: {e}")
            return 0    
        
# 导出
__all__ = ['DatabaseManager']
