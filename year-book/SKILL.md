---
name: year-book
description: 将个人年度日志转换为精美的年记书籍。支持从 Markdown 日志生成 LaTeX 书籍格式，包含主题提炼、章节组织、引用样式等。适用于 Overleaf 在线编译。当用户想要把日记/日志整理成书、创建年度回顾、生成年记时使用此技能。
---

# 年记书籍生成技能

将个人日志转换为精美的 LaTeX 书籍，适合打印或电子阅读。

## 工作流程

### 第一步：阅读和分析日志

1. 分块读取日志文件（如文件过大，每次读取 800 行）
2. 提取关键主题和素材：
   - 健康与身体变化
   - 工作与创作
   - 家庭与育儿
   - 生活仪式感与微幸福
   - 重要里程碑事件
3. 记录具体日期和引用内容

### 第二步：设计书籍结构

典型结构：
- 序言：年度总览，点明核心主题
- 第一章至第四章：按主题组织内容
- 尾声：年度总结与展望
- 附录（可选）：给特定读者的话

### 第三步：生成 Markdown 初稿

先生成 Markdown 格式的书稿，便于预览和修改。使用 `>` 引用块标记日志原文。

### 第四步：转换为 LaTeX

使用以下 Overleaf 兼容模板：

```latex
\documentclass[11pt,a5paper,openany]{book}

% ==================== 基础包 ====================
\usepackage[UTF8, heading=true, fontset=none]{ctex}
\usepackage{fontspec}
\usepackage{xeCJK}
\usepackage{geometry}
\usepackage{graphicx}
\usepackage{xcolor}
\usepackage{titlesec}
\usepackage{titletoc}
\usepackage{fancyhdr}
\usepackage{enumitem}
\usepackage{booktabs}
\usepackage{array}
\usepackage{longtable}
\usepackage{setspace}
\usepackage{indentfirst}
\usepackage{hyperref}

% ==================== 页面设置 ====================
\geometry{
    a5paper,
    inner=20mm,
    outer=15mm,
    top=20mm,
    bottom=20mm,
    headheight=14pt
}

% ==================== 字体设置 ====================
% Overleaf 兼容：使用 Noto CJK 字体
\setCJKmainfont{Noto Serif CJK SC}
\setCJKsansfont{Noto Sans CJK SC}
\setCJKmonofont{Noto Sans Mono CJK SC}

% 定义楷体命令（用于引用）- 使用霞鹜文楷
\newCJKfontfamily\kaiti{LXGW WenKai}

% ==================== 颜色定义 ====================
\definecolor{chaptercolor}{RGB}{70, 70, 70}
\definecolor{quotecolor}{RGB}{100, 100, 100}
\definecolor{quotebg}{RGB}{248, 248, 248}
\definecolor{datecolor}{RGB}{128, 128, 128}

% ==================== 引用环境（楷体） ====================
\usepackage{tcolorbox}
\tcbuselibrary{skins,breakable}

\newtcolorbox{myquote}{
    enhanced,
    breakable,
    colback=quotebg,
    colframe=quotebg,
    boxrule=0pt,
    left=10pt,
    right=10pt,
    top=8pt,
    bottom=8pt,
    before skip=10pt,
    after skip=10pt,
    borderline west={3pt}{0pt}{quotecolor},
    fontupper=\kaiti\color{quotecolor}
}

% ==================== 章节标题设置 ====================
\ctexset{
    chapter = {
        format = \huge\bfseries\centering,
        nameformat = {},
        titleformat = {},
        number = \chinese{chapter},
        name = {第,章},
        aftername = \quad,
        beforeskip = 20pt,
        afterskip = 30pt,
    },
    section = {
        format = \Large\bfseries,
        beforeskip = 15pt,
        afterskip = 10pt,
    },
    subsection = {
        format = \large\bfseries,
        beforeskip = 10pt,
        afterskip = 8pt,
    }
}

% ==================== 页眉页脚 ====================
\pagestyle{fancy}
\fancyhf{}
\fancyhead[LE,RO]{\thepage}
\fancyhead[RE]{\leftmark}
\fancyhead[LO]{\rightmark}
\renewcommand{\headrulewidth}{0.4pt}

\fancypagestyle{plain}{
    \fancyhf{}
    \fancyfoot[C]{\thepage}
    \renewcommand{\headrulewidth}{0pt}
}

% ==================== 超链接设置 ====================
\hypersetup{
    colorlinks=true,
    linkcolor=chaptercolor,
    urlcolor=chaptercolor,
    bookmarks=true,
    bookmarksopen=true
}

% ==================== 行距设置 ====================
\setstretch{1.5}
\setlength{\parindent}{2em}

% ==================== 日期标记命令 ====================
\newcommand{\diarydate}[1]{%
    \par\noindent\textcolor{datecolor}{\small #1}\par\vspace{3pt}%
}

\begin{document}

% 标题页、目录、正文内容...

\end{document}
```

## Overleaf 字体选项

根据 Overleaf 可用字体选择：

**正文字体（宋体类）：**
- `Noto Serif CJK SC` - 思源宋体（推荐）
- `AR PL SungtiL GB` - 文鼎宋体
- `FandolSong` - Fandol 宋体

**标题字体（黑体类）：**
- `Noto Sans CJK SC` - 思源黑体
- `FandolHei` - Fandol 黑体
- `WenQuanYi Micro Hei` - 文泉驿微米黑

**引用字体（楷体类）：**
- `LXGW WenKai` - 霞鹜文楷（推荐，最美观）
- `AR PL UKai CN` - 文鼎楷体
- `FandolKai` - Fandol 楷体
- `cwTeXKai` - cwTeX 楷体

## 关键技术点

1. **ctex 配置**：使用 `fontset=none` 禁用自动字体检测，避免在 Overleaf 上报错
2. **字体加载顺序**：先加载 `fontspec` 和 `xeCJK`，再使用 `\setCJKmainfont` 等命令
3. **引用样式**：使用 `tcolorbox` 的 `breakable` 选项支持跨页，`borderline west` 创建左侧竖线
4. **编译器**：必须使用 XeLaTeX

## 写作风格建议

- 保持个人叙事风格，第一人称
- 日志原文用引用块，保持真实感
- 适当添加反思和串联
- 章节之间有过渡，形成完整叙事
- 结尾留有余韵，展望未来
