# auth/authenticator.py
"""
用户认证模块
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from database import DatabaseManager

class Authenticator:
    """用户认证类"""
    
    def __init__(self, db_manager=None):
        self.db_manager = db_manager or DatabaseManager()
        self.current_user = None
    
    def login(self, username, password):
        """用户登录"""
        success, message, user_info = self.db_manager.authenticate_user(username, password)
        
        if success:
            self.current_user = user_info
            return True, message, user_info
        else:
            return False, message, None
    
    def logout(self):
        """用户注销"""
        self.current_user = None
        return True, "注销成功"
    
    def get_current_user(self):
        """获取当前登录用户"""
        return self.current_user
    
    def is_authenticated(self):
        """检查是否已认证"""
        return self.current_user is not None
    
    def is_admin(self):
        """检查是否是管理员"""
        return self.current_user and self.current_user.get('role') == 'admin'
    
    def has_permission(self, required_role='user'):
        """检查是否有指定权限"""
        if not self.current_user:
            return False
        
        # 权限层级
        role_hierarchy = {
            'user': 1,
            'manager': 2,
            'admin': 3
        }
        
        user_role = self.current_user.get('role', 'user')
        user_level = role_hierarchy.get(user_role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        
        return user_level >= required_level
    
    def change_password(self, old_password, new_password):
        """修改密码"""
        if not self.current_user:
            return False, "用户未登录"
        
        with self.db_manager.session_scope() as session:
            user = session.query(self.db_manager.User).filter_by(
                id=self.current_user['id']
            ).first()
            
            if not user:
                return False, "用户不存在"
            
            # 验证旧密码
            if not self.db_manager.verify_password(old_password, user.password_hash):
                return False, "原密码错误"
            
            # 更新密码
            user.password_hash = self.db_manager.hash_password(new_password)
            session.add(user)
            
            return True, "密码修改成功"
    
    def create_session_token(self, expires_hours=24):
        """创建会话令牌（简化版）"""
        if not self.current_user:
            return None
        
        token = secrets.token_urlsafe(32)
        expires = datetime.now() + timedelta(hours=expires_hours)
        
        # 这里可以保存到数据库，简化版本直接返回
        return {
            'token': token,
            'user_id': self.current_user['id'],
            'expires': expires
        }