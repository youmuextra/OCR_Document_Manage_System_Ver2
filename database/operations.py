# database/operations.py
"""
统一的数据库管理器
包含发文、收文、流转等所有功能
"""

import sqlite3
from contextlib import contextmanager
import hashlib
from datetime import datetime, timedelta
import os
import json
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


        # 创建固定年份（由管理员设置）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                config_key TEXT PRIMARY KEY,
                config_value TEXT
            )
        """)
        # 插入默认年份（如果不存在）
        cursor.execute("INSERT OR IGNORE INTO system_config (config_key, config_value) VALUES ('working_year', '2025')")



        # 创建users表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                real_name TEXT,
                department TEXT,
                position TEXT,
                role TEXT DEFAULT 'user',  -- 'user' 或 'admin'
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

        # TODO 处理收文之后的取件人信息
        try:
            cursor.execute("PRAGMA table_info(receive_documents)")
            cols = [row[1] for row in cursor.fetchall()]
            if 'receiver_info' not in cols:
                cursor.execute("ALTER TABLE receive_documents ADD COLUMN receiver_info TEXT DEFAULT ''")
                print("✅ 已为 receive_documents 补充 receiver_info 字段")
        except Exception as e:
            print(f"⚠️ 补充字段失败: {e}")
        
        conn.commit()
        conn.close()
        
        print(f"✅ 数据库初始化完成: {self.db_path}")
    
    def hash_password(self, password):
        """密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()

    # ============================================================================================ #
    def set_working_year(self, year: str):
        """管理员设置全局工作年份"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO system_config (config_key, config_value)
                VALUES ('working_year', ?)
            """, (str(year),))
            conn.commit()
            return True

    # ============================================================================================ #
    
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
    
    def authenticate_user(self, username, password):
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

    # ============================================================================================ #
    def _generate_next_doc_no(self, document_type_name: str) -> str:
        """
        TODO 生成下一个文号
        :param document_type_name: 用户选择的文种，如 '政府文件', '内部通知'
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. 获取管理员设置的当前工作年份
            cursor.execute("SELECT config_value FROM system_config WHERE config_key = 'working_year'")
            row = cursor.fetchone()
            working_year = row['config_value'] if row else str(datetime.now().year)

            # 2. 匹配当前文种和年份的已有最大编号
            # 假设文号存储格式为: 文种〔2025〕01号
            pattern = f"{document_type_name}〔{working_year}〕%"
            cursor.execute("""
                SELECT document_no FROM receive_documents 
                WHERE document_no LIKE ? 
                ORDER BY document_no DESC LIMIT 1
            """, (pattern,))

            last_doc = cursor.fetchone()

            if last_doc:
                # 提取序号：从 "文种〔2025〕05号" 中提取 "05"
                import re
                last_no_str = last_doc['document_no']
                match = re.search(r'〕(\d+)号', last_no_str)
                if match:
                    next_val = int(match.group(1)) + 1
                else:
                    next_val = 1
            else:
                # 该文种在该年份的第一份文件
                next_val = 1

            # 3. 格式化为两位数（01, 02...），如果超过99会自动变为三位数
            return f"{document_type_name}〔{working_year}〕{next_val:02d}号"
    # ============================================================================================ #
    
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
                'remarks': 'remarks',
                'receiver_info': 'receiver_info'
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

    def update_document_receiver(self, doc_id: int, receiver_info: str, user_id: int):
        """
            TODO 专门用于更新取件人信息的接口
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    UPDATE receive_documents 
                    SET receiver_info = ?, updated_at = ? 
                    WHERE id = ?
                """, (receiver_info, datetime.now(), doc_id))

                # 记录到日志中，方便追溯
                cursor.execute("""
                    INSERT INTO document_logs 
                    (document_id, document_type, user_id, action, action_details, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (doc_id, 'receive', user_id, 'update_receiver', f'录入取件人: {receiver_info}', datetime.now()))

                conn.commit()
                return cursor.rowcount > 0, "取件人信息更新成功"
            except Exception as e:
                return False, f"录入失败: {e}"


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
            
            # # 检查文号是否已存在
            # if send_data.get('document_no'):
            #     cursor.execute("SELECT id FROM send_documents WHERE document_no = ?",
            #                  (send_data.get('document_no'),))
            #     if cursor.fetchone():
            #         return False, "文号已存在", None

            # TODO 自动设置文号
            doc_type = send_data.get('document_type', '公文')  # 默认分类
            send_data['document_no'] = self._generate_next_doc_no(doc_type)


            # 验证必填字段
            if not send_data.get('title'):
                return False, "标题不能为空", None
            if not send_data.get('send_to_unit'):
                return False, "发往单位不能为空", None
            if not send_data.get('m_level'):
                return False, "M级不能为空", None
            if not send_data.get('processor'):
                return False, "经办人不能为空", None
            
            # 准备插入数据
            columns = [
                'document_no', 'title', 'issuing_unit', 'send_to_unit', 
                'm_level', 'processor', 'send_date', 'send_status', 'remarks',
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

                # 同步更新原始文档状态：发起后先“待确认”，领取确认后再进入已流转/已借出
                doc_status = '待确认'
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
                    CASE WHEN cr.document_type = 'receive' THEN rd.title ELSE sd.title END as title
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