# coderead

用廉价模型对任意代码仓库生成结构化"认知地图"，供人类阅读和 AI 工具复用。

---

## 它解决什么问题

拿到一个陌生仓库时，README 只告诉你"这是什么"，不告诉你"为什么这么设计"、"各模块如何协作"、"我想二开从哪里入手"。

手动阅读代码费时，直接问 LLM 又因为没有上下文而回答不准。

coderead 的做法：**离线跑一次，把项目理解固化成文档**，之后人和 AI 都可以直接复用，不用每次重新分析。

---

## 核心用途

**1. 快速熟悉陌生项目**
生成覆盖模块结构、执行流、设计意图、权衡分析的 Markdown 报告，比读 README 深，比自己读代码快。

**2. 二次开发 / 代码移植**
分析模块依赖边界，帮你判断"移植这个功能需要带走哪些依赖"、"扩展这个模块从哪里切入"。

**3. 生成可复用的项目上下文**
输出的 `.md` 可以直接作为 `CLAUDE.md` 注入 Claude Code、Cursor 等 AI 工具，让后续所有对话都基于这份理解，不用重复解释项目背景。

---

## 与 Claude Code `/init` 的区别

| | coderead | Claude Code `/init` |
|---|---|---|
| 模型依赖 | 任意 OpenAI 兼容模型（deepseek、qwen、ollama…） | 需要 Anthropic API |
| 分析深度 | 执行流、设计意图、权衡分析 | 操作指南（命令、约定） |
| 适用场景 | 陌生仓库，无需开发环境 | 已在项目内工作 |
| 成本 | 低（可用免费/本地模型） | 按 Claude API 计费 |

两者互补：**coderead 负责"理解项目是什么"，`/init` 负责"在项目里怎么工作"**。推荐先用 coderead 生成认知地图，再用 `/init` 补充开发操作细节。

---

## 快速开始

```bash
# 安装依赖
uv sync

# 分析一个仓库
uv run python main.py ./path/to/repo --provider deepseek --api-key sk-xxx

# 使用配置文件
uv run python main.py ./path/to/repo --config llm-config.json

# 只分析 monorepo 的某个子目录
uv run python main.py ./monorepo --focus packages/core --provider deepseek
```

输出：
- `output/analysis.md` — 人类可读的分析报告（可直接用作 CLAUDE.md）
- `output/analysis.json` — 结构化数据，可供工具链复用

支持断点续跑（`--resume`）和从指定步骤重跑（`--from-step`）。完整参数见 [CLAUDE.md](CLAUDE.md)。

---

## 支持的 LLM 提供商

deepseek · qwen · moonshot · siliconflow · modelscope · zhipu · baichuan · yi · openai · azure · ollama（本地）

优先推荐 deepseek 或 qwen——成本低，中文理解好，输出质量稳定。

---

## 工作原理

1. **文件选择**：从入口文件出发，沿 import 链 BFS 扩散，优先选取最核心的代码，其余文件压缩为签名摘要，最终控制在 token 预算内
2. **顺序推理链**：6 个 agent 依次分析，每步结果传递给下一步，逐层积累理解
   - structure → behavior → intent → tradeoff → reviewer → narrative
3. **输出**：JSON + Markdown，Markdown 内嵌 Mermaid 架构图和流程图
