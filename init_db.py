#!/usr/bin/env python3
"""
数据库初始化脚本
用于创建数据库表结构和初始化数据
"""
from app import app, db
from models import User, Novel, Chapter, Comment, UserNovel
from datetime import datetime
import os

def create_tables():
    """创建数据库表"""
    with app.app_context():
        # 删除所有表（如果存在）
        db.drop_all()
        
        # 创建所有表
        db.create_all()
        
        print("✅ 数据库表创建成功")

def create_admin_user():
    """创建管理员用户"""
    with app.app_context():
        # 检查管理员是否已存在
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@taletap.org',
                password='admin123'  # 实际使用时应该加密
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ 管理员用户创建成功")
        else:
            print("ℹ️  管理员用户已存在")

def create_sample_novels():
    """创建示例小说数据"""
    with app.app_context():
        # 检查是否已有小说数据
        if Novel.query.count() > 0:
            print("ℹ️  小说数据已存在，跳过创建")
            return
        
        # 创建示例小说
        novels = [
            {
                'title': 'The Dragon\'s Legacy',
                'description': 'An epic fantasy tale of dragons, magic, and ancient prophecies.',
                'category': 'Fantasy',
                'author': 'Elena Stormwind',
                'cover_image': 'cover_fantasy.jpg',
                'rating': 4.5,
                'status': 'ongoing'
            },
            {
                'title': 'Hearts in Bloom',
                'description': 'A heartwarming romance set in a small coastal town.',
                'category': 'Romance',
                'author': 'Sarah Mitchell',
                'cover_image': 'cover_romance.jpg',
                'rating': 4.2,
                'status': 'completed'
            }
        ]
        
        for novel_data in novels:
            novel = Novel(**novel_data)
            db.session.add(novel)
        
        db.session.commit()
        print("✅ 示例小说数据创建成功")

def create_sample_chapters():
    """创建示例章节数据"""
    with app.app_context():
        # 为每本小说创建几个章节
        novels = Novel.query.all()
        
        for novel in novels:
            for i in range(1, 6):  # 创建5个章节
                chapter = Chapter(
                    novel_id=novel.id,
                    title=f'Chapter {i}: The Beginning',
                    content=f'This is the content of chapter {i} for {novel.title}. ' * 50
                )
                db.session.add(chapter)
        
        db.session.commit()
        print("✅ 示例章节数据创建成功")

def init_database():
    """完整的数据库初始化流程"""
    print("开始初始化数据库...")
    
    # 确保数据库文件存在
    if not os.path.exists('site.db'):
        open('site.db', 'a').close()
    
    try:
        create_tables()
        create_admin_user()
        create_sample_novels()
        create_sample_chapters()
        print("🎉 数据库初始化完成！")
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")

if __name__ == "__main__":
    init_database()
