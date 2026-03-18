
import sqlite3
import os

def fix_database():
    db_path = "data/documents.db"
    
    if not os.path.exists(db_path):
        print("❌ 数据库文件不存在")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查document_logs表
        cursor.execute("PRAGMA table_info(document_logs)")
        columns = cursor.fetchall()
        
        has_document_type = any(col[1] == 'document_type' for col in columns)
        
        if not has_document_type:
            print("添加document_type列...")
            cursor.execute("ALTER TABLE document_logs ADD COLUMN document_type TEXT")
            cursor.execute("UPDATE document_logs SET document_type = 'receive' WHERE document_type IS NULL")
            print("✅ 已添加document_type列")
        else:
            print("✅ document_type列已存在")
        
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    fix_database()
