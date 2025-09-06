#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小说批量导入模块
支持中文和英文小说的自动解析和批量导入
作者: Assistant
"""

import re
import os
import hashlib
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class Language(Enum):
    CHINESE = "zh"
    ENGLISH = "en"
    UNKNOWN = "unknown"


@dataclass
class ChapterInfo:
    """章节信息数据类"""
    title: str
    content: str
    chapter_number: Optional[int] = None


@dataclass
class NovelInfo:
    """小说信息数据类"""
    title: str
    author: str
    description: str
    language: Language
    category: str
    chapters: List[ChapterInfo]


class NovelImporter:
    """小说导入器主类"""
    
    def __init__(self):
        self.chinese_chapter_patterns = [
            r'第([0-9一二三四五六七八九十百千万]+)章[\s\u3000]*(.+?)(?=\n|$)',  # 第X章 标题
            r'第([0-9]+)回[\s\u3000]*(.+?)(?=\n|$)',  # 第X回 标题
            r'(序章|楔子|后记|结局|大结局|终章|尾声)[\s\u3000]*(.*)(?=\n|$)',  # 特殊章节
            r'([0-9]+)[\s\u3000]*\.[\s\u3000]*(.+?)(?=\n|$)',  # 1. 标题
        ]
        
        self.english_chapter_patterns = [
            r'Chapter\s+(\d+)[\s:]*(.+?)(?=\n|$)',  # Chapter X: Title
            r'CHAPTER\s+(\d+)[\s:]*(.+?)(?=\n|$)',  # CHAPTER X: Title
            r'Ch\.?\s*(\d+)[\s:]*(.+?)(?=\n|$)',  # Ch. X: Title
            r'(\d+)\.?\s+(.+?)(?=\n|$)',  # 1. Title
            r'(Prologue|Epilogue|Preface|Afterword)[\s:]*(.*)(?=\n|$)',  # 特殊章节
        ]
    
    def detect_language(self, text: str) -> Language:
        """检测文本语言"""
        # 统计中文字符
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        # 统计英文单词
        english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))
        
        total_chars = len(text.replace(' ', '').replace('\n', ''))
        
        if total_chars == 0:
            return Language.UNKNOWN
        
        chinese_ratio = chinese_chars / total_chars
        
        if chinese_ratio > 0.3:  # 中文字符超过30%认为是中文
            return Language.CHINESE
        elif english_words > chinese_chars * 2:  # 英文单词数量是中文字符2倍以上
            return Language.ENGLISH
        else:
            return Language.UNKNOWN
    
    def extract_novel_metadata(self, content: str) -> Dict[str, str]:
        """提取小说元数据"""
        metadata = {
            'title': '',
            'author': '',
            'description': '',
            'category': ''
        }
        
        # 中文格式的元数据提取
        title_match = re.search(r'『(.+?)/作者:(.+?)』', content)
        if title_match:
            metadata['title'] = title_match.group(1).strip()
            metadata['author'] = title_match.group(2).strip()
        
        # 增强的简介提取 - 支持多种格式
        intro_patterns = [
            # 格式1: 『内容简介: ... 』
            r'『内容简介[\s\u3000]*[:：]\s*(.*?)』',
            # 格式2: 内容简介: ... (无书名号)
            r'内容简介[\s\u3000]*[:：]\s*(.*?)(?=\n\n|\n-{3,}|\n第)',
            # 格式3: 简介: ...
            r'简介[\s\u3000]*[:：]\s*(.*?)(?=\n\n|\n-{3,}|\n第)',
            # 格式4: 【简介】...
            r'【简介】\s*(.*?)(?=\n\n|\n-{3,}|\n第)',
        ]
        
        for pattern in intro_patterns:
            intro_match = re.search(pattern, content, re.DOTALL)
            if intro_match:
                raw_description = intro_match.group(1).strip()
                # 清理简介内容
                metadata['description'] = self._clean_description(raw_description)
                break
        
        # 英文格式的元数据提取
        if not metadata['title']:
            title_match = re.search(r'Title:\s*(.+?)(?:\n|Author)', content, re.IGNORECASE)
            if title_match:
                metadata['title'] = title_match.group(1).strip()
        
        if not metadata['author']:
            author_match = re.search(r'Author:\s*(.+?)(?:\n|$)', content, re.IGNORECASE)
            if author_match:
                metadata['author'] = author_match.group(1).strip()
        
        if not metadata['description']:
            desc_match = re.search(r'(Summary|Description):\s*(.*?)(?:\n\n|\nChapter)', content, re.DOTALL | re.IGNORECASE)
            if desc_match:
                metadata['description'] = desc_match.group(2).strip()
        
        return metadata
    
    def _clean_description(self, description: str) -> str:
        """清理简介内容"""
        if not description:
            return description
        
        # 移除多余的换行和空白字符
        description = re.sub(r'[\s\u3000]+', ' ', description)
        
        # 移除首尾的特殊符号
        description = description.strip('　\n\r\t ')
        
        # 处理段落分隔，将多个空格替换为段落分隔
        description = re.sub(r'\s{3,}', '\n\n', description)
        
        # 移除HTML标签（如果有）
        description = re.sub(r'<[^>]+>', '', description)
        
        # 限制长度（可选）
        if len(description) > 1000:
            description = description[:1000] + '...'
        
        return description.strip()
    
    def clean_content(self, text: str, language: Language) -> str:
        """清理文本内容"""
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        
        # 移除常见的无用内容
        unwanted_patterns = [
            r'</p>',
            r'更多电子书请访问.*',
            r'爱下电子书.*',
            r'简体:https?://.*',
            r'繁体:https?://.*',
            r'E-mail:.*',
            r'------.*?-------',
            r'『.*?连载中.*?』',
            r'www\..*\.com',
            r'http[s]?://.*',
        ]
        
        for pattern in unwanted_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # 移除多余的空行
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 移除行首行尾空白
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(line for line in lines if line)
        
        return text.strip()
    
    def split_chapters(self, content: str, language: Language) -> List[ChapterInfo]:
        """分割章节"""
        chapters = []
        
        # 根据语言选择对应的模式
        if language == Language.CHINESE:
            patterns = self.chinese_chapter_patterns
        else:
            patterns = self.english_chapter_patterns
        
        lines = content.split('\n')
        current_chapter = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检查是否是章节标题
            is_chapter_title = False
            for pattern in patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    # 保存上一章节
                    if current_chapter:
                        content_text = '\n'.join(current_content).strip()
                        if content_text:  # 只有内容不为空才添加
                            chapters.append(ChapterInfo(
                                title=current_chapter,
                                content=content_text,
                                chapter_number=len(chapters) + 1
                            ))
                    
                    # 开始新章节
                    current_chapter = line
                    current_content = []
                    is_chapter_title = True
                    break
            
            # 如果不是章节标题且有当前章节，则添加到内容中
            if not is_chapter_title and current_chapter:
                # 跳过一些无用的行
                if (line and 
                    not line.startswith('</p>') and 
                    not line.startswith('更多电子书') and
                    not line.startswith('www.') and
                    len(line) > 1):
                    current_content.append(line)
        
        # 保存最后一章
        if current_chapter and current_content:
            content_text = '\n'.join(current_content).strip()
            if content_text:
                chapters.append(ChapterInfo(
                    title=current_chapter,
                    content=content_text,
                    chapter_number=len(chapters) + 1
                ))
        
        return chapters
    
    def validate_chapters(self, chapters: List[ChapterInfo]) -> List[str]:
        """验证章节数据"""
        issues = []
        
        if not chapters:
            issues.append("未检测到任何章节")
            return issues
        
        for i, chapter in enumerate(chapters):
            # 检查章节标题
            if not chapter.title or len(chapter.title.strip()) == 0:
                issues.append(f"第{i+1}章缺少标题")
            
            # 检查章节内容长度
            if not chapter.content or len(chapter.content.strip()) < 50:
                issues.append(f"第{i+1}章({chapter.title})内容过短")
            
            # 检查内容是否过长（可能是分章失败）
            if len(chapter.content) > 50000:  # 5万字符
                issues.append(f"第{i+1}章({chapter.title})内容过长，可能需要进一步分割")
        
        return issues
    
    def process_novel_file(self, file_path: str, encoding: str = 'utf-8') -> Tuple[NovelInfo, List[str]]:
        """处理小说文件"""
        try:
            # 读取文件
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            for enc in ['gbk', 'gb2312', 'utf-8-sig']:
                try:
                    with open(file_path, 'r', encoding=enc) as f:
                        content = f.read()
                        encoding = enc
                        break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError(f"无法读取文件 {file_path}，请检查文件编码")
        
        # 检测语言
        language = self.detect_language(content)
        
        # 提取元数据
        metadata = self.extract_novel_metadata(content)
        
        # 清理内容
        cleaned_content = self.clean_content(content, language)
        
        # 分割章节
        chapters = self.split_chapters(cleaned_content, language)
        
        # 验证章节
        issues = self.validate_chapters(chapters)
        
        # 构建小说信息
        novel_info = NovelInfo(
            title=metadata.get('title', '未知标题'),
            author=metadata.get('author', '未知作者'),
            description=metadata.get('description', '暂无描述'),
            language=language,
            category=metadata.get('category', '其他'),
            chapters=chapters
        )
        
        return novel_info, issues
    
    def translate_novel_simple(self, novel_info: NovelInfo, custom_prompt: str = None, prompt_type: str = "novel_general") -> NovelInfo:
        """简单免费翻译小说（使用Google翻译免费版）"""
        if novel_info.language != Language.CHINESE:
            return novel_info
            
        try:
            from googletrans import Translator
            translator = Translator()
            
            # 加载提示词系统
            try:
                from translation_prompts import PromptManager, PromptType
                prompt_manager = PromptManager()
                use_advanced_prompts = True
                print(f"开始翻译小说... (使用{prompt_type}提示词)")
            except ImportError:
                use_advanced_prompts = False
                print("开始翻译小说... (使用基础翻译)")
            
            # 翻译基本信息
            try:
                if custom_prompt:
                    # 使用自定义提示词翻译标题
                    title_with_prompt = f"{custom_prompt}\n\n请翻译标题: {novel_info.title}"
                    title_result = translator.translate(title_with_prompt, src='zh-cn', dest='en')
                    translated_title = title_result.text.replace(custom_prompt, "").strip()
                else:
                    title_result = translator.translate(novel_info.title, src='zh-cn', dest='en')
                    translated_title = title_result.text
            except:
                translated_title = novel_info.title
                
            try:
                if custom_prompt:
                    # 使用自定义提示词翻译描述
                    desc_with_prompt = f"{custom_prompt}\n\n请翻译描述: {novel_info.description}"
                    desc_result = translator.translate(desc_with_prompt, src='zh-cn', dest='en')
                    translated_description = desc_result.text.replace(custom_prompt, "").strip()
                else:
                    desc_result = translator.translate(novel_info.description, src='zh-cn', dest='en')
                    translated_description = desc_result.text
            except:
                translated_description = novel_info.description
            
            # 翻译章节
            translated_chapters = []
            for i, chapter in enumerate(novel_info.chapters):
                print(f"翻译第{i+1}/{len(novel_info.chapters)}章...")
                try:
                    # 翻译标题
                    if custom_prompt:
                        title_with_prompt = f"{custom_prompt}\n\n请翻译章节标题: {chapter.title}"
                        title_trans = translator.translate(title_with_prompt, src='zh-cn', dest='en')
                        translated_title = title_trans.text.replace(custom_prompt, "").strip()
                    else:
                        title_trans = translator.translate(chapter.title, src='zh-cn', dest='en')
                        translated_title = title_trans.text
                    
                    # 分段翻译内容（避免内容过长）
                    content = chapter.content
                    if len(content) > 800:  # 为提示词预留空间，减少单次翻译长度
                        # 分成多段
                        chunk_size = 800 if custom_prompt else 1000
                        chunks = [content[j:j+chunk_size] for j in range(0, len(content), chunk_size)]
                        translated_chunks = []
                        
                        for chunk in chunks:
                            try:
                                if custom_prompt:
                                    chunk_with_prompt = f"{custom_prompt}\n\n请翻译: {chunk}"
                                    chunk_trans = translator.translate(chunk_with_prompt, src='zh-cn', dest='en')
                                    translated_chunk = chunk_trans.text.replace(custom_prompt, "").strip()
                                else:
                                    chunk_trans = translator.translate(chunk, src='zh-cn', dest='en')
                                    translated_chunk = chunk_trans.text
                                translated_chunks.append(translated_chunk)
                            except:
                                translated_chunks.append(chunk)  # 失败时保持原文
                                
                        translated_content = ' '.join(translated_chunks)
                    else:
                        if custom_prompt:
                            content_with_prompt = f"{custom_prompt}\n\n请翻译: {content}"
                            content_trans = translator.translate(content_with_prompt, src='zh-cn', dest='en')
                            translated_content = content_trans.text.replace(custom_prompt, "").strip()
                        else:
                            content_trans = translator.translate(content, src='zh-cn', dest='en')
                            translated_content = content_trans.text
                    
                    translated_chapters.append(ChapterInfo(
                        title=translated_title,
                        content=translated_content,
                        chapter_number=chapter.chapter_number
                    ))
                    
                    # 避免请求过快
                    import time
                    time.sleep(0.5)  # 每次翻译间隔0.5秒
                    
                except Exception as e:
                    print(f"翻译第{i+1}章失败: {e}")
                    # 翻译失败时保持原文
                    translated_chapters.append(chapter)
            
            print("翻译完成!")
            return NovelInfo(
                title=translated_title,
                author=novel_info.author,  # 作者名不翻译
                description=translated_description,
                language=Language.ENGLISH,
                category=self._translate_category(novel_info.category),
                chapters=translated_chapters
            )
            
        except ImportError:
            print("googletrans未安装，请运行: pip install googletrans==4.0.0-rc1")
            return novel_info
        except Exception as e:
            print(f"翻译失败: {e}")
            return novel_info
    
    def _translate_category(self, category: str) -> str:
        """翻译分类名称"""
        category_mapping = {
            '玄幻': 'Fantasy',
            '言情': 'Romance', 
            '科幻': 'Sci-Fi',
            '悬疑': 'Mystery',
            '惊悚': 'Thriller',
            '历史': 'Historical',
            '军事': 'Military',
            '都市': 'Urban',
            '网游': 'Gaming'
        }
        return category_mapping.get(category, 'Fantasy')

    def generate_preview_data(self, novel_info: NovelInfo) -> Dict:
        """生成预览数据"""
        return {
            'title': novel_info.title,
            'author': novel_info.author,
            'description': novel_info.description,
            'language': novel_info.language.value,
            'chapter_count': len(novel_info.chapters),
            'total_words': sum(len(ch.content) for ch in novel_info.chapters),
            'first_chapters': [
                {
                    'title': ch.title,
                    'content_preview': ch.content[:200] + '...' if len(ch.content) > 200 else ch.content,
                    'word_count': len(ch.content)
                }
                for ch in novel_info.chapters[:5]  # 预览前5章
            ]
        }


class DatabaseImporter:
    """数据库导入器"""
    
    def __init__(self, db_session):
        self.db = db_session
    
    def import_novel_to_database(self, novel_info: NovelInfo, cover_image: str = None) -> int:
        """将小说数据导入到数据库"""
        from models import Novel, Chapter
        
        # 创建小说记录
        novel = Novel(
            title=novel_info.title,
            author=novel_info.author,
            description=novel_info.description,
            cover_image=cover_image or 'cover_fantasy.jpg',
            category=self._map_category(novel_info.category, novel_info.language)
        )
        
        self.db.session.add(novel)
        self.db.session.flush()  # 获取novel.id
        
        # 批量创建章节记录
        chapters_to_add = []
        for chapter_info in novel_info.chapters:
            chapter = Chapter(
                novel_id=novel.id,
                title=chapter_info.title,
                content=chapter_info.content
            )
            chapters_to_add.append(chapter)
        
        # 批量插入章节
        self.db.session.add_all(chapters_to_add)
        self.db.session.commit()
        
        return novel.id
    
    def _map_category(self, category: str, language: Language) -> str:
        """映射分类名称"""
        if language == Language.CHINESE:
            category_mapping = {
                '玄幻': 'Fantasy',
                '言情': 'Romance',
                '科幻': 'Sci-Fi',
                '悬疑': 'Mystery',
                '惊悚': 'Thriller',
                '历史': 'Historical',
                '军事': 'Military',
                '都市': 'Urban',
                '网游': 'Gaming'
            }
            return category_mapping.get(category, 'Fantasy')
        else:
            # 英文分类直接使用
            return category.title() if category else 'Fantasy'


# 使用示例
if __name__ == "__main__":
    # 测试代码
    importer = NovelImporter()
    
    # 处理小说文件
    try:
        novel_info, issues = importer.process_novel_file("test_novel.txt")
        
        print(f"小说标题: {novel_info.title}")
        print(f"作者: {novel_info.author}")
        print(f"语言: {novel_info.language}")
        print(f"章节数: {len(novel_info.chapters)}")
        
        if issues:
            print("发现问题:")
            for issue in issues:
                print(f"  - {issue}")
        
        # 生成预览数据
        preview = importer.generate_preview_data(novel_info)
        print(f"总字数: {preview['total_words']}")
        
    except Exception as e:
        print(f"处理失败: {e}")
