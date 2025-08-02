from app import app, db
from models import Novel, Chapter, User
from werkzeug.security import generate_password_hash

with app.app_context():
    db.drop_all()
    db.create_all()

    # 添加测试用户
    user1 = User(username="testuser", password=generate_password_hash("password123"))
    user2 = User(username="admin", password=generate_password_hash("admin123"))
    db.session.add_all([user1, user2])

    # 添加小说和章节
    novel1 = Novel(
        title="Transmigration: Defying Fate for Immortality",
        description="Yang Zaochen travels through time and is reborn into a different world. At the beginning, I found a stunning beauty. Millions of years ago, an old monster came with a big gift package to steal it.",
        cover_image="Domineering.png",
        category="奇幻"
    )
    novel2 = Novel(
        title="倾城之恋",
        description="一段缠绵悱恻的现代言情故事，描绘都市中的爱情与抉择。",
        cover_image="Domineering.png",
        category="言情"
    )
    db.session.add_all([novel1, novel2])

    # 为黑暗森林添加章节
    chapter1_1 = Chapter(
        novel=novel1,
        title="Chapter 1: Time Travel Rebirth",
        content="在神秘的魔法森林中，英雄艾伦开始了冒啊达瓦达瓦达瓦达瓦达瓦低洼地我去达瓦达瓦德瓦达达娃哒哒哒伟大的险……（约500字内容）。"
    )
    chapter1_2 = Chapter(
        novel=novel1,
        title="第二章：暗影初现",
        content="黑暗势力逐渐浮现，艾伦面临第一次考验……（约500字内容）。"
    )

    # 为倾城之恋添加章节
    chapter2_1 = Chapter(
        novel=novel2,
        title="第一章：初遇",
        content="林若曦在咖啡馆偶遇了神秘男子顾辰……（约500字内容）。"
    )
    chapter2_2 = Chapter(
        novel=novel2,
        title="第二章：心动",
        content="一次意外的相遇，让两人心动不已……（约500字内容）。"
    )
    db.session.add_all([chapter1_1, chapter1_2, chapter2_1, chapter2_2])

    db.session.commit()
    print("数据库已初始化，包含多本小说、章节和用户测试数据！")