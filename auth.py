# auth.py
"""
认证管理器
"""

class Authenticator:
    """认证管理器"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.current_user = None
    
    def login(self, username, password):
        """用户登录"""
        return self.db_manager.authenticate_user(username, password)
    
    def logout(self):
        """用户登出"""
        self.current_user = None
    
    def is_authenticated(self):
        """检查是否已认证"""
        return self.current_user is not None
    
    def get_current_user(self):
        """获取当前用户"""
        return self.current_user