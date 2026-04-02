# init_database.py
"""
初始化数据库脚本
"""

import sys
import os
from database import DatabaseManager

def main():
    print("公文智能管理系统 - 数据库初始化")
    print("=" * 60)
    
    try:
        # 初始化数据库
        db_manager = DatabaseManager()
        
        print("✅ 数据库初始化完成！")
        print(f"   数据库位置: data/database/documents.db")
        
        print("\n📋 默认登录信息:")
        print("   用户名: admin")
        print("   密码: 123456")
        print("\n⚠️  首次登录后请立即修改密码！")
        
        # 测试数据库连接
        from sqlalchemy import text
        with db_manager.session_scope() as session:
            result = session.execute(text("SELECT COUNT(*) FROM users"))
            user_count = result.fetchone()[0]
            print(f"\n📊 数据库状态: 共有 {user_count} 个用户")
            
            result = session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result.fetchall()]
            print(f"   表结构: {', '.join(tables)}")
        
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
