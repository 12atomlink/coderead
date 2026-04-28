# 🧠 Project Analyzer v1

## 1. 🎯 Goal（目标）

构建一个系统，用于**结构化理解任意代码仓库**。

该系统的核心目标不是生成代码，而是：

* 理解项目结构（Structure）
* 分析执行流程（Behavior）
* 推断设计意图（Intent）
* 评估设计权衡（Trade-off）

最终输出为一个：

> ✅ 可读
> ✅ 可验证
> ✅ 可修正
> ✅ 可扩展

的**认知文档（Cognitive Document）**

---

## 2. 🧩 Core Principles（核心原则）

### 2.1 Progressive Reasoning（递进式认知）

分析必须严格分阶段进行：

1. Structure（结构）
2. Behavior（行为）
3. Intent（意图）
4. Trade-off（权衡）

约束：

* 不允许跳过阶段
* 每一步必须依赖上一步结果
* 不允许一次性“总结全部”

---

### 2.2 Externalized Cognition（外部化认知）

所有推理结果必须写入统一文档：

* 不允许仅在模型内部推理
* 所有结论必须结构化存储
* 所有结果必须可供后续步骤读取

---

### 2.3 Evidence-Based Reasoning（基于证据）

所有结论必须满足以下之一：

* 引用具体代码（文件 / 函数 / 模块）
* 或明确标记为“推测（Hypothesis）”

禁止：

* 无依据的推断
* 模糊描述（如“可能是…”但无解释）

---

### 2.4 Self-Correctable System（可纠错）

系统必须具备：

* 置信度标记（confidence）
* 错误检测能力
* 局部重分析能力（rerun）

---

## 3. 🏗️ System Architecture（系统结构）

### 3.1 Pipeline（分析流水线）

```
Structure → Behavior → Intent → Trade-off → Reviewer
```

说明：

* 每一步必须读取 Shared Document
* 每一步必须写回 Shared Document

---

### 3.2 Shared Document（核心数据结构）

统一 JSON 结构如下：

```json
{
  "meta": {
    "repo_name": "",
    "analyzed_at": "",
    "version": "v1"
  },
  "structure": {
    "modules": [],
    "dependencies": [],
    "entry_points": [],
    "confidence": 0.0,
    "evidence": []
  },
  "behavior": {
    "flows": [],
    "data_flow": [],
    "control_flow": [],
    "confidence": 0.0,
    "evidence": []
  },
  "intent": {
    "design_goals": [],
    "architectural_patterns": [],
    "assumptions": [],
    "confidence": 0.0,
    "evidence": []
  },
  "tradeoff": {
    "pros": [],
    "cons": [],
    "alternatives": [],
    "risks": [],
    "confidence": 0.0
  },
  "review": {
    "issues": [],
    "inconsistencies": [],
    "low_confidence_areas": [],
    "suggestions": []
  }
}
```

---

### 3.3 Agents（最小 Agent 集合）

#### 1. Structure Agent

职责：

* 分析项目模块划分
* 提取依赖关系
* 找到入口点（main / CLI / API）

输入：

* 代码仓库
* 空或已有 document

输出：

* document.structure

---

#### 2. Behavior Agent

职责：

* 分析执行流程（input → process → output）
* 描述关键调用链

依赖：

* structure

输出：

* document.behavior

---

#### 3. Intent Agent

职责：

* 推断设计目标
* 识别架构模式（如 MVC、Agent-based 等）

依赖：

* structure + behavior

输出：

* document.intent

---

#### 4. Trade-off Agent

职责：

* 分析优缺点
* 推断设计权衡
* 提出替代方案

依赖：

* intent

输出：

* document.tradeoff

---

#### 5. Reviewer Agent（关键）

职责：

* 检查前面所有内容
* 发现矛盾
* 检测无证据结论
* 标记低置信度部分

输出：

* document.review

---

## 4. ⚙️ Execution Flow（执行流程）

```
1. 加载代码仓库
2. 初始化 Shared Document
3. 执行 Structure Agent
4. 执行 Behavior Agent
5. 执行 Intent Agent
6. 执行 Trade-off Agent
7. 执行 Reviewer Agent
8. 输出最终 JSON / Markdown
```

---

## 5. 🧠 Agent Prompt 规范（重要）

每个 Agent 必须遵守：

### 输入必须包含：

* 当前 Shared Document
* 明确任务说明

### 输出必须：

* 只更新自己负责的字段
* 不修改其他字段
* 提供 evidence（引用代码路径）
* 提供 confidence（0~1）

---

## 6. ⚠️ Constraints（强约束）

* 不允许跳过 pipeline
* 不允许修改非职责字段
* 不允许输出非结构化内容
* 不允许生成无证据结论
* 不允许假设不存在的代码结构

---

## 7. 🚫 Non-Goals（当前不做）

为了控制复杂度，本阶段不实现：

* 多 Agent 并行执行
* 长期 Memory 系统
* 自动代码执行
* 自动修复代码
* UI 可视化界面

---

## 8. 🧪 MVP Scope（最小可行实现）

第一阶段必须完成：

* [ ] Repo Loader（读取文件结构）
* [ ] Shared Document（JSON 文件）
* [ ] 4 个核心 Agent（Prompt 实现）
* [ ] 1 个 Reviewer Agent
* [ ] CLI 工具（输入 repo → 输出分析结果）

---

## 9. 📂 Suggested Project Structure（建议目录结构）

```
project-analyzer/
├── agents/
│   ├── structure_agent.py
│   ├── behavior_agent.py
│   ├── intent_agent.py
│   ├── tradeoff_agent.py
│   └── reviewer_agent.py
├── core/
│   ├── pipeline.py
│   ├── context.py
│   └── loader.py
├── prompts/
│   ├── structure.txt
│   ├── behavior.txt
│   ├── intent.txt
│   ├── tradeoff.txt
│   └── reviewer.txt
├── output/
│   └── analysis.json
├── main.py
└── CLAUDE.md
```

---

## 10. 🧭 Future Direction（未来方向）

（不在当前实现范围）

* 支持对话式查询（Chat over analysis）
* 支持局部重分析（rerun agent）
* 引入置信度传播机制
* 多假设推理（Hypothesis system）
* 可视化结构图
* Memory / Learning 能力

---

## 11. 🧠 Design Philosophy（设计哲学）

本系统的核心不是“分析代码”，而是：

> 构建一个**可被检查、可被修正、可持续演进的认知过程**

---

## 12. 📌 Instructions for Claude Code

在实现本项目时，请遵循：

1. 优先实现最小可运行版本（MVP）
2. 不要过度设计（Avoid over-engineering）
3. 每个模块必须职责单一
4. 每个 Agent 必须可独立测试
5. 优先保证结构清晰，而不是功能复杂

如果遇到不确定的设计：

> 👉 优先选择：简单 + 可运行 + 可扩展

---

## 13. 🚀 How to Start

请按以下步骤执行：

1. 先设计项目目录结构
2. 实现 Repo Loader
3. 定义 Shared Document 数据结构
4. 实现 Structure Agent
5. 逐步实现后续 Agent
6. 最后实现 Pipeline 串联

---

**最终目标：构建一个可靠的“代码理解系统”，而不是一个“生成文本的工具”。**
