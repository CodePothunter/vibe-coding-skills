# Vibe Coding Skills

A curated collection of Claude Code skills for context engineering, agent development, and creative workflows.

```
                    ╭──────────────────────────────────╮
                    │   19 Skills · 7 Categories       │
                    │   Context · Agents · Creative    │
                    ╰──────────────────────────────────╯
```

---

## Skills Directory

### Context Engineering

Master the art of managing context in LLM-powered systems.

| Skill | Description |
|-------|-------------|
| [context-fundamentals](./context-fundamentals/) | Understand context components, mechanics, and constraints. Foundation for all other context skills. |
| [context-optimization](./context-optimization/) | Extend effective context capacity through compaction, observation masking, KV-cache optimization, and partitioning. |
| [context-compression](./context-compression/) | Design compression strategies for long-running sessions. Anchored summarization, tokens-per-task optimization. |
| [context-degradation](./context-degradation/) | Recognize and mitigate degradation patterns: lost-in-middle, context poisoning, distraction, and clash. |

### Agent Development

Build robust and efficient agent systems.

| Skill | Description |
|-------|-------------|
| [memory-systems](./memory-systems/) | Design memory architectures from simple file storage to temporal knowledge graphs. Persist state across sessions. |
| [tool-design](./tool-design/) | Create tools agents can use effectively. Includes consolidation principle and architectural reduction patterns. |
| [multi-agent-patterns](./multi-agent-patterns/) | Design multi-agent architectures: supervisor, swarm, and hierarchical patterns. Context isolation strategies. |

### Quality & Evaluation

Build reliable evaluation frameworks for AI systems.

| Skill | Description |
|-------|-------------|
| [evaluation](./evaluation/) | Build evaluation frameworks with multi-dimensional rubrics, LLM-as-judge, and continuous monitoring. |
| [advanced-evaluation](./advanced-evaluation/) | Master direct scoring, pairwise comparison, rubric generation, and bias mitigation techniques. |

### Project & Product

From ideation to deployment.

| Skill | Description |
|-------|-------------|
| [project-development](./project-development/) | Design LLM-powered projects. Task-model fit, pipeline architecture, and agent-assisted development. |
| [product-validation](./product-validation/) | 产品创意验证流程。竞品分析、差异化评估、商业模式验证。帮助快速做出"做/不做"决定。 |
| [opportunity-hunter](./opportunity-hunter/) | 商业机会发现。通过热门事件、高下载低评分应用、社交媒体呼声三种方法挖掘产品方向。 |

### Creative

Transform ideas into beautiful artifacts.

| Skill | Description |
|-------|-------------|
| [canvas-design](./canvas-design/) | Create museum-quality visual art in .png and .pdf. Design philosophy creation + canvas expression. |
| [year-book](./year-book/) | 将年度日志转换为精美的 LaTeX 书籍。主题提炼、章节组织、Overleaf 兼容模板。 |

### Document Manipulation

Programmatic document processing and generation.

| Skill | Description |
|-------|-------------|
| [pdf](./pdf/) | PDF manipulation toolkit: extract text/tables, create PDFs, merge/split, handle forms. |
| [docx](./docx/) | Comprehensive Word document manipulation: create, edit, tracked changes, comments, formatting. |
| [pptx](./pptx/) | Presentation creation and editing: layouts, slides, speaker notes, HTML-to-PPTX conversion. |

### Developer Tools

Streamline development workflows.

| Skill | Description |
|-------|-------------|
| [git-commit-format](./git-commit-format/) | Git 提交信息格式规范。Emoji+中文类别格式，确保提交信息专业、简洁、一致。 |
| [skill-creator](./skill-creator/) | Meta-skill for creating new skills. Design specialized tools with knowledge and workflows. |

---

## Skill Structure

Each skill follows a consistent structure:

```
skill-name/
├── SKILL.md              # Main skill document
├── references/           # Deep-dive reference materials
│   └── *.md
└── scripts/              # Example implementations
    └── *.py
```

## Usage

These skills are designed for [Claude Code](https://claude.com/claude-code). Add them to your `~/.claude/skills/` directory.

Skills activate based on context. For example:
- Ask about context limits → `context-fundamentals` activates
- Design an agent system → `multi-agent-patterns` activates
- Create visual art → `canvas-design` activates

## License

Individual skills may have their own licenses. Check each skill's directory for details.

---

<p align="center">
  <sub>Built with Claude Code</sub>
</p>
