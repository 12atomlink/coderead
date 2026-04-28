# coderead 改进计划

> 核心问题：当前系统将所有理解工作外包给 LLM，没有静态分析兜底，输出是文字列表而非可视化图表，导致两个根本缺陷：分析质量取决于模型能力，且在大型仓库上核心实现文件进不来。

---

## 能力差距评估

当前系统擅长回答 **WHAT**（项目有哪些模块、整体流程是什么），不擅长回答 **HOW**（某个机制内部怎么实现的）。

| 用户问题 | 当前输出能否回答 | 根因 |
|----------|----------------|------|
| 入口在哪、主流程是什么 | 部分（文字步骤，无图） | 缺少流程图输出 |
| 项目分几层、模块关系 | 部分（表格，无可视化） | 缺少架构图输出 |
| agentloop 怎么实现 | 基本不能（1/10） | 核心实现文件未进入分析 |
| 会话数据怎么存 | 基本不能 | 同上 |
| 系统提示词怎么加 | 基本不能 | 同上 |

---

## 问题地图

```
现状：原始文件 ──(截取前50个，按文件系统顺序)──> LLM ──> 文字列表输出
                        ↑
              入口文件、配置文件、前端文件占满了槽位
              核心引擎实现文件（agent/session/tool）进不来
              输出是表格和步骤列表，没有图表

目标：原始文件 ──(入口链追踪 + 分块)──> 核心实现文件优先 ──> LLM ──> 图表 + 文字
                                                                  ↑
                                                         Mermaid 架构图
                                                         Mermaid 流程图
                                                         按子系统深度分析
```

---

## P1 — 高优先级

### 1. 🆕 图表生成（Mermaid 流程图 + 架构图）

**解决问题**：用户需求 1（主函数流程图）、需求 2（架构图）

**现状**：behavior agent 输出文字步骤列表，structure agent 输出模块表格，读者需要在脑中重建图。

**改进方案**

- **structure agent**：在 JSON 输出中增加 `architecture_diagram` 字段，要求模型生成 Mermaid `graph TD` 架构图，表达模块分层和依赖方向
- **behavior agent**：在每个 flow 中增加 `mermaid` 字段，要求模型生成 Mermaid `flowchart TD` 流程图
- **report.py**：在 Markdown 渲染时将 Mermaid 代码块直接嵌入，GitHub / Obsidian / VSCode Preview 原生支持渲染

**影响文件**：`prompts/structure.md`、`prompts/behavior.md`、`core/context.py`、`core/report.py`

**实现复杂度**：低（纯 prompt 和渲染层改动，不依赖其他改进）

**可立即用现有 JSON 验证**：对已有分析结果重新 `python core/report.py` 即可看效果

---

### 2. 🆕 入口链追踪式文件选择

**解决问题**：用户需求 3（agentloop / 会话存储 / 系统提示词）的根本前提

**现状**：50 文件槽位被入口文件、前端文件、配置文件占满，核心引擎实现文件（`agent/`、`session/`、`tool/`）进不来。原有的"按 import 频率选文件"无法解决这个问题——核心实现文件往往是被调用者，import 频率反而低。

**改进方案**

从入口点出发，沿调用链向内追踪，优先选取实现层文件：

```
第一步：识别入口点
  - 扫描 main.py / index.ts / cmd/ / cli/ 等模式
  - 读取 package.json 的 bin/main 字段

第二步：沿 import 向内追踪（深度优先，最多 3 层）
  - 入口 → 直接依赖 → 直接依赖的依赖
  - 优先选取体积适中（5-50KB）的实现文件
  - 跳过测试文件、类型声明、vendor

第三步：补充覆盖
  - 剩余槽位按 import 频率补充
```

**影响文件**：`core/loader.py`（新增 `get_files_by_entry_chain()` 方法）

**实现复杂度**：中（Python 用 `ast` 解析 import，TS/JS 用正则，需处理相对路径解析）

---

### 3. ↑ 大型仓库分块分析（从 P2 升级）

**解决问题**：用户需求 3 的前提条件，对 monorepo 必要

**现状**：50 文件硬截断，对 opencode 这类 monorepo，`packages/opencode/src/` 的内部文件永远进不来，不是优化问题，是前提条件。

**改进方案**

按顶层目录/包边界分块，每块独立走 structure + behavior 分析，最后汇总：

```
monorepo/
├── packages/opencode/  → 独立深度分析（最重要，优先）
├── packages/app/       → 独立分析
└── github/             → 独立分析
                          ↓
                    跨包关系汇总（narrative + tradeoff）
```

用户可配置分析优先级：`--focus packages/opencode` 让该包优先分配 token 预算。

**影响文件**：`core/pipeline.py`（新增 `ChunkedPipeline`）、`core/loader.py`、`main.py`（新增 `--focus` 参数）

**实现复杂度**：高

---

### 4. 文件内容摘要化（原 P1-2）

**解决问题**：分块后每块仍可覆盖更多文件，提升分析深度

**现状**：原始文件全文送入 LLM，每个文件平均几十 KB，token 大量浪费在实现细节上。

**改进方案**

用 Python `ast` 提取类签名 + 函数签名 + docstring，压缩 80% token：

```python
# 原始（500 行） → 摘要（20 行）
class AgentManager:
    """Manages agent lifecycle and execution."""
    def run(session_id: str, prompt: str) -> AsyncGenerator[Event, None]: ...
    def stop(session_id: str) -> None: ...
```

对非 Python 文件（TS/JS/Go）降级为正则提取函数签名。

**影响文件**：`core/loader.py`、各 agent 的 `build_user_prompt()`

**实现复杂度**：中

---

## P2 — 中优先级

### 5. Import 依赖图预计算（原 P1-3）

**解决问题**：支撑入口链追踪（P1-2 的基础设施）、同时让 structure agent 的依赖分析从"模型猜测"变为"程序确定 + 模型解释"

**改进方案**

用 `ast` / 正则扫描全量 import，生成依赖图传给 structure agent：

```json
{
  "import_graph": {
    "core/pipeline.py": ["agents/structure_agent", "core/llm", "core/context"],
    "agents/base.py": ["core/context", "core/llm"]
  },
  "import_frequency": { "core/llm": 6, "core/context": 5 }
}
```

**影响文件**：`core/loader.py`、`prompts/structure.md`、`agents/structure_agent.py`

**实现复杂度**：中

---

### 6. Agent 上下文按需裁剪（原 P2-4）

**解决问题**：降低每次 LLM 调用成本，提升分析焦点

| Agent | 当前 | 优化后 |
|-------|------|--------|
| structure | 全量文件 | 全量摘要 |
| behavior | 全量文件 | 入口 + 高频文件 |
| intent | 全量文件 | 配置 + 架构层文件 |
| tradeoff | 全量文件 | 仅前三轮分析结果 |
| reviewer | 全量文件 | 仅分析文档 |
| narrative | 全量文件 | 仅分析文档 |

**影响文件**：各 agent 的 `build_user_prompt()`

**实现复杂度**：低

---

## P3 — 低优先级

### 7. Reviewer 事实校验（原 P2-5）

程序化验证分析结论中引用的文件路径和函数名是否真实存在，消除幻觉路径引用。

**实现复杂度**：中

---

### 8. 多语言静态分析适配（原 P3-7）

为 TypeScript/JavaScript、Go、Java 添加精确 AST 解析，替代当前的正则降级方案。

**实现复杂度**：高（每种语言独立实现）

---

### 9. 增量分析（原 P3-8）

基于 git diff，只对变更文件重新分析，适合持续维护场景。

**实现复杂度**：高

---

## 实施路线

```
第一阶段：让输出可视化（改动最小，可立即验证）
  └── P1-1 图表生成（Mermaid）← 可用现有 JSON 直接验证

第二阶段：让核心文件进来（解决 HOW 类问题的根本）
  └── P1-2 入口链追踪式文件选择
  └── P2-5 Import 依赖图（P1-2 的基础设施，先做）

第三阶段：支持大型仓库
  └── P1-3 分块分析
  └── P1-4 文件内容摘要化

第四阶段：降本提质
  └── P2-6 Agent 上下文裁剪
  └── P3-7 Reviewer 事实校验
```

---

## 各改进项总览

| # | 改进项 | 优先级 | 复杂度 | 直接解决 |
|---|--------|--------|--------|---------|
| 1 | 🆕 Mermaid 图表生成 | P1 | 低 | 需求 1、2（流程图、架构图） |
| 2 | 🆕 入口链追踪文件选择 | P1 | 中 | 需求 3（核心机制分析） |
| 3 | ↑ 大型仓库分块 | P1 | 高 | 需求 3 的前提 |
| 4 | 文件内容摘要化 | P1 | 中 | 覆盖更多文件 |
| 5 | Import 依赖图预计算 | P2 | 中 | 支撑入口链追踪 |
| 6 | Agent 上下文裁剪 | P2 | 低 | 降低成本 |
| 7 | Reviewer 事实校验 | P3 | 中 | 消除幻觉引用 |
| 8 | 多语言静态分析 | P3 | 高 | 非 Python 仓库质量 |
| 9 | 增量分析 | P3 | 高 | 持续维护场景 |
