#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAQ处理工具函数
专门处理FAQ相关的HTML结构识别和美化
"""

from bs4 import BeautifulSoup, Tag


def is_faq_item(li: Tag) -> bool:
    """检查是否为FAQ项结构"""
    # 检查是否有icon和div结构
    has_icon = li.find('i', class_='icon icon-plus')
    has_div = li.find('div')

    if has_icon and has_div:
        # 检查div内是否有a标签（问题）和section标签（答案）
        div = li.find('div')
        has_question = div.find('a')
        has_answer = div.find('section')

        return bool(has_question and has_answer)

    return False


def process_faq_item(li: Tag, new_li: Tag, soup: BeautifulSoup):
    """处理FAQ项，提取问题和答案，使用美化的HTML结构"""
    div = li.find('div')
    if not div:
        return

    # 提取问题
    question_a = div.find('a')
    if question_a:
        question_text = question_a.get_text(strip=True)
        if question_text:
            # 创建问题div容器
            question_div = soup.new_tag('div', **{'class': 'faq-question'})
            question_div.string = question_text
            new_li.append(question_div)

    # 提取答案
    answer_section = div.find('section')
    if answer_section:
        answer_text = answer_section.get_text(strip=True)
        if answer_text:
            # 创建答案div容器
            answer_div = soup.new_tag('div', **{'class': 'faq-answer'})
            answer_div.string = answer_text
            new_li.append(answer_div)


def extract_qa_content(soup: BeautifulSoup) -> str:
    """提取Q&A内容以及支持和服务级别协议内容"""
    print("🔍 提取Q&A内容...")
    
    qa_sections = []
    
    # 查找常见问题部分
    faq_keywords = ['常见问题', 'faq', 'frequently asked questions', '问题解答']
    
    for keyword in faq_keywords:
        # 查找包含关键词的标题
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'], 
                                string=lambda text: text and keyword.lower() in text.lower())
        
        for heading in headings:
            # 查找标题后的内容
            content_element = heading.find_next_sibling()
            
            if content_element:
                qa_text = content_element.get_text(strip=True)
                if qa_text and len(qa_text) > 50:  # 过滤过短的内容
                    qa_sections.append({
                        'section': keyword,
                        'content': qa_text[:1000]  # 限制长度
                    })
    
    # 查找支持相关内容
    support_keywords = ['支持', 'support', '服务级别协议', 'sla', 'service level']
    
    for keyword in support_keywords:
        elements = soup.find_all(string=lambda text: text and keyword.lower() in text.lower())
        
        for element in elements[:3]:  # 限制数量
            parent = element.parent
            if parent:
                support_text = parent.get_text(strip=True)
                if support_text and len(support_text) > 30:
                    qa_sections.append({
                        'section': keyword,
                        'content': support_text[:500]
                    })
    
    # 合并所有Q&A内容
    if qa_sections:
        combined_qa = '\n\n'.join([f"## {section['section']}\n{section['content']}" 
                                  for section in qa_sections[:5]])  # 限制为前5个
        print(f"  ✓ 提取了 {len(qa_sections)} 个Q&A部分")
        return combined_qa
    else:
        print("  ⚠ 未找到Q&A内容")
        return ""