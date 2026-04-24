# Citation Review Crew

[English](README.md) | **中文**

基于 CrewAI 的学术论文引用审查工具。自动检测引用错配、搜索正确替代文献、检查引用格式规范。

## 功能

1. **审查阶段** (`crewai run`)：读取论文 (.docx) 和 Zotero 文献元数据，生成审查报告
2. **修正阶段** (`uv run fix`)：基于审查报告自动搜索替代文献、修正作者名、检查格式

## 核心特性

- **智能输入压缩**：仅提取含引用标记 `[N]` 的段落（~5倍压缩）
- **多 API 学术搜索**：OpenAlex + Semantic Scholar + PubMed + CrossRef
- **Python 预搜索 + AI 验证**：免费 API 批量搜索（~10秒）+ AI 并行验证（~2分钟）
- **容错设计**：每个 Crew 独立 try/except
- **Zotero 集成**：自动导入替代文献并打标签

## 快速开始

```bash
uv tool install crewai
git clone https://github.com/ChristinaSaikoy/citation-review-crew.git
cd citation-review-crew
cp .env.example .env  # 填入 API Key
uv sync

# 审查
uv run crewai run

# 修正
uv run fix
```

## 自定义

- **引用格式**：修改 `tasks.yaml` 中的格式规则
- **模型**：在 `.env` 中设置 `OPENAI_MODEL_NAME` 和 `OPENAI_MODEL_NAME_LIGHT`

## 许可证

MIT
