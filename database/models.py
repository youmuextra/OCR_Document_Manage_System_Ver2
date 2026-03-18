# database/models.py
"""
数据库模型定义
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import os
import enum

# 创建基础类
Base = declarative_base()

# 枚举定义
class DocumentType(enum.Enum):
    """文档类型枚举"""
    RECEIVE = "收文"  # 收文
    SEND = "发文"    # 发文

class CirculationType(enum.Enum):
    """流转类型枚举"""
    HANDOVER = "交接"  # 交接
    BORROW = "借阅"    # 借阅
    OTHER = "其他"     # 其他

class CirculationStatus(enum.Enum):
    """流转状态枚举"""
    PENDING = "待确认"  # 待确认
    CIRCULATING = "流转中"  # 流转中
    BORROWED = "已借出"  # 已借出
    RETURNED = "已归还"  # 已归还
    COMPLETED = "已完成"  # 已完成

class User(Base):
    """用户表"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)  # 存储哈希密码
    real_name = Column(String(50))
    department = Column(String(100))
    position = Column(String(50))  # 职位
    role = Column(String(20), default='user')  # user, admin, manager
    email = Column(String(100))
    phone = Column(String(20))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime)
    
    # 关系
    created_documents = relationship("Document", back_populates="creator", foreign_keys="Document.created_by")
    sent_documents = relationship("SendDocument", back_populates="sender")
    received_documents = relationship("ReceiveDocument", back_populates="receiver_user")
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"

class Document(Base):
    """公文基表（抽象类）"""
    __tablename__ = 'documents'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_type = Column(String(20), nullable=False)  # 文档类型：receive, send
    
    # 公共字段
    document_no = Column(String(50), unique=True, index=True)  # 文号
    title = Column(String(500), nullable=False, index=True)  # 标题
    issuing_unit = Column(String(200), index=True)  # 发文单位
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)  # 创建人
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    status = Column(String(20), default='正常')  # 状态
    remarks = Column(Text)  # 备注
    
    # 关系
    creator = relationship("User", foreign_keys=[created_by])
    
    __mapper_args__ = {
        'polymorphic_on': document_type,
        'polymorphic_identity': 'document'
    }
    
    def __repr__(self):
        return f"<Document(id={self.id}, type='{self.document_type}', title='{self.title[:20]}...')>"

class ReceiveDocument(Document):
    """收文表"""
    __tablename__ = 'receive_documents'
    
    id = Column(Integer, ForeignKey('documents.id'), primary_key=True)
    
    # 收文特有字段
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # 经办人
    security_level = Column(String(20), default='普通')  # 密级
    urgency_level = Column(String(20), default='普通')  # 紧急程度
    copies = Column(Integer, default=1)  # 份数
    received_date = Column(DateTime, default=datetime.now, index=True)  # 收文日期
    storage_location = Column(String(200))  # 存放位置
    original_file_path = Column(String(500))  # 原文文件路径
    ocr_result_path = Column(String(500))  # OCR结果路径
    thumbnail_path = Column(String(500))  # 缩略图路径
    content_summary = Column(Text)  # 内容摘要
    keywords = Column(String(200))  # 关键词
    receiver = Column(String(100))  # 收文人
    
    # 关系
    receiver_user = relationship("User", foreign_keys=[user_id])
    
    __mapper_args__ = {
        'polymorphic_identity': 'receive'
    }

class SendDocument(Document):
    """发文表"""
    __tablename__ = 'send_documents'
    
    id = Column(Integer, ForeignKey('documents.id'), primary_key=True)
    
    # 发文特有字段
    send_to_unit = Column(String(200), nullable=False)  # 发往单位
    processor = Column(String(100), nullable=False)  # 经办人
    send_date = Column(DateTime, default=datetime.now, index=True)  # 发文日期
    send_status = Column(String(20), default='已发文')  # 发文状态
    
    # 关系
    sender = relationship("User", foreign_keys=[Document.created_by])
    
    __mapper_args__ = {
        'polymorphic_identity': 'send'
    }

class CirculationRecord(Base):
    """流转记录表"""
    __tablename__ = 'circulation_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, nullable=False)  # 文档ID
    document_type = Column(String(20), nullable=False)  # 文档类型：receive, send
    circulation_type = Column(String(20), nullable=False)  # 流转类型：handover, borrow, other
    next_node_unit = Column(String(200))  # 下一节点单位
    next_node_person = Column(String(100))  # 下一节点人员
    current_holder_id = Column(Integer, ForeignKey('users.id'))  # 当前持有人
    borrow_requester_id = Column(Integer, ForeignKey('users.id'))  # 借阅申请人
    borrow_date = Column(DateTime)  # 借阅日期
    due_date = Column(DateTime)  # 应归还日期
    return_date = Column(DateTime)  # 实际归还日期
    status = Column(String(20), default='待确认')  # 流转状态
    remarks = Column(Text)  # 备注
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)  # 创建人
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    current_holder = relationship("User", foreign_keys=[current_holder_id])
    borrow_requester = relationship("User", foreign_keys=[borrow_requester_id])
    creator = relationship("User", foreign_keys=[created_by])
    
    def __repr__(self):
        return f"<CirculationRecord(id={self.id}, type='{self.circulation_type}', status='{self.status}')>"

class DocumentLog(Base):
    """公文操作日志表"""
    __tablename__ = 'document_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, nullable=False, index=True)
    document_type = Column(String(20), nullable=False)  # 文档类型
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    action = Column(String(50), nullable=False)  # 操作类型
    action_details = Column(Text)  # 操作详情
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    created_at = Column(DateTime, default=datetime.now, index=True)
    
    # 关系
    user = relationship("User", foreign_keys=[user_id])
    
    def __repr__(self):
        return f"<DocumentLog(id={self.id}, action='{self.action}')>"

class SystemConfig(Base):
    """系统配置表"""
    __tablename__ = 'system_configs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(100), unique=True, nullable=False, index=True)
    config_value = Column(Text)
    config_type = Column(String(20), default='string')  # string, int, float, bool, json
    description = Column(String(200))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<SystemConfig(key='{self.config_key}', value='{self.config_value[:30]}...')>"