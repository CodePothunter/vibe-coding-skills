#!/usr/bin/env python3
"""
Mermaid代码兼容性修复脚本

针对mermaid-cli旧版本的解析限制，自动修复以下问题：
1. 移除<br>或<br/>等HTML标签
2. 替换特殊字符 / \ | 为空格（这些字符可能被误解析）
3. 确保节点标签使用纯文本（支持多种节点形状）
4. 修复箭头标签中的特殊字符
5. 修复subgraph标题中的特殊字符
6. 将中文引号转为英文引号
7. 检测空节点标签并报告警告

支持的节点形状：
  - [...]   方括号（矩形）
  - (...)   圆角矩形
  - {...}   菱形
  - ([...]) 体育场形
  - ((...)) 圆形

使用方法：
    python fix_mermaid.py <input_file> [output_file]

如果不指定output_file，将直接覆盖原文件
"""

import re
import sys
import os


def _sanitize_label(label):
    """对标签内容执行统一的特殊字符清理"""
    # 移除 <br> 标签
    label = re.sub(r'<br\s*/?>', ' ', label, flags=re.IGNORECASE)
    # / 可能被解析为路径
    label = label.replace('/', ' ')
    # \ 可能被解析为转义
    label = label.replace('\\', ' ')
    # | 可能被解析为管道
    label = label.replace('|', ' ')
    # ( ) 可能影响节点定义 —— 转为全角
    label = label.replace('(', '（')
    label = label.replace(')', '）')
    # 中文引号转英文
    label = label.replace('\u201c', '"').replace('\u201d', '"')
    label = label.replace('\u2018', "'").replace('\u2019', "'")
    # 清理多余空格
    label = ' '.join(label.split())
    return label


def fix_mermaid_code(line):
    """
    修复单行mermaid代码中的兼容性问题
    """
    original_line = line

    # 修复0: 移除<br>或<br/>标签（全局，包括非标签区域）
    line = re.sub(r'<br\s*/?>', ' ', line, flags=re.IGNORECASE)

    # 修复1: 中文引号转英文引号（全行）
    line = line.replace('\u201c', '"').replace('\u201d', '"')
    line = line.replace('\u2018', "'").replace('\u2019', "'")

    # 修复2: subgraph 标题修复
    # 匹配 "subgraph 标题文字" 行
    m = re.match(r'^(\s*subgraph\s+)(.*)', line)
    if m:
        prefix = m.group(1)
        title = m.group(2)
        title = title.replace('/', ' ').replace('\\', ' ').replace('|', ' ')
        title = ' '.join(title.split())
        line = prefix + title
        return line, original_line

    # 修复3: 箭头标签修复
    # 匹配 -->|文字|、-.->|文字|、==>|文字| 等模式
    def fix_arrow_label(match):
        prefix = match.group(1)   # e.g. "-->|" 的 "-->"
        label = match.group(2)    # 箭头标签文字
        # 清理标签内的特殊字符（但不清理管道符，因为外层 | 是分隔符）
        label = re.sub(r'<br\s*/?>', ' ', label, flags=re.IGNORECASE)
        label = label.replace('/', ' ').replace('\\', ' ')
        label = label.replace('\u201c', '"').replace('\u201d', '"')
        label = label.replace('\u2018', "'").replace('\u2019', "'")
        label = ' '.join(label.split())
        return f'{prefix}|{label}|'

    line = re.sub(r'(-+\.?-+>|=+>)\|([^|]*)\|', fix_arrow_label, line)

    # 修复4: 节点标签修复 —— 按从特殊到一般的顺序处理

    # 4a: 体育场形 ([...])
    def fix_stadium_label(match):
        label = _sanitize_label(match.group(1))
        return f'([{label}])'

    line = re.sub(r'\(\[([^\]]*)\]\)', fix_stadium_label, line)

    # 4b: 圆形 ((...))
    def fix_circle_label(match):
        label = _sanitize_label(match.group(1))
        # 圆形标签内不转换括号为全角（因为外层已经是双括号）
        return f'(({label}))'

    line = re.sub(r'\(\(([^)]*(?:\)[^)])*)\)\)', fix_circle_label, line)
    # 更简单的匹配：找到 (( 开头，匹配到 )) 结束
    # 重新用一个更稳健的方式
    def fix_circle_labels_in_line(line):
        result = []
        i = 0
        while i < len(line):
            if i + 1 < len(line) and line[i] == '(' and line[i+1] == '(':
                # 找到 (( ，寻找对应的 ))
                j = line.find('))', i + 2)
                if j != -1:
                    inner = line[i+2:j]
                    inner = re.sub(r'<br\s*/?>', ' ', inner, flags=re.IGNORECASE)
                    inner = inner.replace('/', ' ').replace('\\', ' ').replace('|', ' ')
                    inner = inner.replace('\u201c', '"').replace('\u201d', '"')
                    inner = inner.replace('\u2018', "'").replace('\u2019', "'")
                    inner = ' '.join(inner.split())
                    result.append(f'(({inner}))')
                    i = j + 2
                else:
                    result.append(line[i])
                    i += 1
            else:
                result.append(line[i])
                i += 1
        return ''.join(result)

    line = fix_circle_labels_in_line(line)

    # 4c: 菱形 {...}
    def fix_diamond_label(match):
        label = _sanitize_label(match.group(1))
        return '{' + label + '}'

    line = re.sub(r'\{([^}]+)\}', fix_diamond_label, line)

    # 4d: 方括号 [...] （最后处理，避免与体育场形冲突）
    def fix_square_label(match):
        label = _sanitize_label(match.group(1))
        return f'[{label}]'

    line = re.sub(r'\[([^\]]+)\]', fix_square_label, line)

    # 4e: 圆角矩形 (...)
    # 需要避免匹配已处理的 ((...)) 和 ([...])
    # 只匹配单层括号且内容不以 ( 或 [ 开头
    def fix_round_label(match):
        inner = match.group(1)
        # 跳过已经是 ((...)) 或 ([...]) 的部分
        if inner.startswith('(') or inner.startswith('['):
            return match.group(0)
        label = _sanitize_label(inner)
        return f'({label})'

    line = re.sub(r'\(([^)]+)\)', fix_round_label, line)

    return line, original_line


def detect_empty_nodes(line, line_num):
    """检测空标签节点"""
    warnings = []
    # 检测 A[], B(), C{}, D([]), E(())
    empty_patterns = [
        (r'\b\w+\[\]', '方括号'),
        (r'\b\w+\(\)', '圆角矩形'),
        (r'\b\w+\{\}', '菱形'),
        (r'\b\w+\(\[\]\)', '体育场形'),
        (r'\b\w+\(\(\)\)', '圆形'),
    ]
    for pattern, shape_name in empty_patterns:
        matches = re.findall(pattern, line)
        for m in matches:
            warnings.append({
                'line': line_num,
                'type': 'empty_node',
                'node': m,
                'shape': shape_name,
                'message': f'空标签节点 {m}（{shape_name}），请添加标签内容'
            })
    return warnings


def validate_and_fix_mermaid(markdown_text, verbose=True):
    """
    检查并修复markdown文本中的mermaid代码兼容性问题

    Args:
        markdown_text: 输入的markdown文本
        verbose: 是否打印修复信息

    Returns:
        tuple: (修复后的文本, 问题列表)
    """
    lines = markdown_text.split('\n')
    fixed_lines = []
    issues_found = []
    warnings = []

    in_mermaid = False
    mermaid_start_line = 0

    for i, line in enumerate(lines, 1):
        # 检测mermaid代码块开始
        if line.strip().startswith('```mermaid'):
            in_mermaid = True
            mermaid_start_line = i
            fixed_lines.append(line)
            continue

        # 检测mermaid代码块结束
        elif in_mermaid and line.strip().startswith('```'):
            in_mermaid = False
            fixed_lines.append(line)
            continue

        # 处理mermaid代码块内的行
        if in_mermaid:
            # 检测空节点
            empty_warnings = detect_empty_nodes(line, i)
            warnings.extend(empty_warnings)

            fixed_line, original_line = fix_mermaid_code(line)

            if fixed_line != original_line:
                issues_found.append({
                    'line': i,
                    'original': original_line.strip(),
                    'fixed': fixed_line.strip()
                })

            fixed_lines.append(fixed_line)
        else:
            fixed_lines.append(line)

    if verbose:
        if issues_found:
            print(f"✓ 检测到 {len(issues_found)} 个mermaid兼容性问题并已修复：")
            for issue in issues_found[:10]:  # 只显示前10个
                print(f"  行{issue['line']}: {issue['original'][:60]}...")
                print(f"    → {issue['fixed'][:60]}...")
            if len(issues_found) > 10:
                print(f"  ... 还有 {len(issues_found) - 10} 个问题")

        if warnings:
            print(f"\n⚠ 检测到 {len(warnings)} 个警告：")
            for w in warnings:
                print(f"  行{w['line']}: {w['message']}")

    return '\n'.join(fixed_lines), issues_found + warnings


def main():
    if len(sys.argv) < 2:
        print("使用方法: python fix_mermaid.py <input_file> [output_file]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file

    if not os.path.exists(input_file):
        print(f"错误: 文件不存在: {input_file}")
        sys.exit(1)

    # 读取输入文件
    print(f"读取文件: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检测并修复mermaid代码
    fixed_content, issues = validate_and_fix_mermaid(content)

    # 写入输出文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(fixed_content)

    fixes = [i for i in issues if i.get('fixed') is not None]
    warns = [i for i in issues if i.get('type') == 'empty_node']

    if fixes or warns:
        parts = []
        if fixes:
            parts.append(f"修复 {len(fixes)} 个问题")
        if warns:
            parts.append(f"{len(warns)} 个警告")
        print(f"✓ 完成，{'，'.join(parts)}")
    else:
        print("✓ 未发现兼容性问题，文件无需修改")

    print(f"输出文件: {output_file}")


if __name__ == '__main__':
    main()
