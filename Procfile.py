#!/usr/bin/env python3
"""
Procfile配置文件
用于部署配置和进程管理
"""

# Web服务器配置
web_config = {
    'port': 5000,
    'host': '0.0.0.0',
    'workers': 2,
    'timeout': 30
}

# 数据库配置
db_config = {
    'database_url': 'sqlite:///site.db',
    'pool_size': 10,
    'max_overflow': 20
}

# 静态文件配置
static_config = {
    'static_folder': 'static',
    'static_url_path': '/static'
}

# 日志配置
logging_config = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
}

if __name__ == "__main__":
    print("Procfile配置加载完成")
    print(f"Web配置: {web_config}")
    print(f"数据库配置: {db_config}")
