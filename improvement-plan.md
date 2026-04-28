# coderead 改进计划

> 核心问题：当前系统将所有理解工作外包给 LLM，没有静态分析兜底，导致分析质量完全取决于模型能力，且在大型仓库上容易失效。

---

## 问题地图

```
现状：原始文件 ──(截取前50个)──> LLM ──> 分析结果
                                  ↑
                         模型需独立完成：
                         - 依赖关系推断
                         - 调用链追踪
                         - 重要文件判断
                         - 设计意图推断

目标：原始文件 ──(静态预处理)──> 结构化摘要 ──> LLM ──> 分析结果
                   ↑                              ↑
           AST / import图                 更小、更准、更稳定的输入
           函数签名提取
           重要性评分
```

---

## P1 — 高优先级（先做这三个，收益最大）

### 1. 智能文件选择

**现状问题**

`base.py:69` 硬截取前 50 个文件，按文件系统顺序排列。超过 50 个文件的仓库，重要文件可能直接被丢弃。

**改进方案**

在 `RepoLoader` 中加入文件重要性评分，综合以下维度排序后再截取：

| 维度 | 权重 | 实现方式 |
|------|------|----------|
| 被其他文件 import 的次数 | 高 | 全量扫描 import 语句统计 |
| 文件名语义（main/core/base/engine/app） | 高 | 关键词列表匹配 |
| 文件体积（过大/过小均降权） | 中 | 5KB–50KB 区间优先 |
| 目录层级（越浅越重要） | 中 | 路径深度计算 |
| 是否为入口点（if __main__、CLI 注册） | 高 | 简单文本扫描 |

**影响文件**：`core/loader.py`

**预期收益**：确保关键文件始终进入分析，对中大型仓库效果尤其明显。

**实现复杂度**：低（纯 Python，不依赖外部库）

---

### 2. 文件内容摘要化

**现状问题**

每个 agent 都接收原始文件全文。一个 500 行的文件中，LLM 真正需要的信息可能只有类签名和函数定义，其余是实现细节。大量 token 被浪费在 LLM 不需要精读的内容上，同时压缩了可分析的文件数量。

**改进方案**

在送给 LLM 前，用 Python `ast` 模块将文件内容转换为结构化摘要：

```
原始文件（500行）→ 摘要（30行）
─────────────────────────────────
class Pipeline:
    """Orchestrates agent execution."""

    def run(repo_path, output_path, resume) -> SharedDocument: ...
    def _backup_existing(output_path, intermediate_dir): ...
    def _load_intermediate(filepath) -> Optional[dict]: ...
```

对非 Python 文件（JS/TS/Go 等）降级为基于正则的签名提取。

**影响文件**：`core/loader.py`（新增 `get_file_summaries()` 方法），各 agent 的 `build_user_prompt()`

**预期收益**：
- 单文件 token 消耗降低 80%
- 可分析文件数从 50 个提升到 150–200 个
- 减少模型"淹没在实现细节里"的问题

**实现复杂度**：中（Python 文件用 `ast`，其他语言用正则降级）

---

### 3. Import 依赖图预计算

**现状问题**

structure agent 需要从原始代码中自己推断模块依赖关系，这是典型的"让模型做本可以用程序精确完成的事"。模型推断的依赖可能有遗漏或幻觉，且 reviewer 无法校验。

**改进方案**

在 `RepoLoader` 中加入静态 import 分析，生成精确的依赖图，直接传给 structure agent：

```json
{
  "import_graph": {
    "core/pipeline.py": ["agents/structure_agent", "agents/behavior_agent", "core/llm", "core/context"],
    "agents/base.py": ["core/context", "core/llm"],
    ...
  },
  "import_frequency": {
    "core/llm": 6,
    "core/context": 5,
    ...
  }
}
```

structure agent 的 prompt 改为：基于已知依赖图，解释每条依赖的语义含义，而不是自己推断依赖关系。

**影响文件**：`core/loader.py`，`prompts/structure.md`，`agents/structure_agent.py`

**预期收益**：
- 依赖关系从"模型猜测"变为"程序确定 + 模型解释"
- structure 分析结果更准确，后续所有 agent 的分析质量连带提升
- 消除这一维度的幻觉风险

**实现复杂度**：中（Python 用 `ast.parse`，其他语言用正则扫描 import/require/use 语句）

---

## P2 — 中优先级

### 4. Agent 上下文按需裁剪

**现状问题**

behavior、intent、tradeoff agent 都把完整 `file_contents`（最多 50 个文件）传入。实际上：
- behavior agent 主要需要"高频被调用"的文件
- intent agent 主要需要配置、架构层文件
- tradeoff agent 更多依赖已完成的前三轮分析，而非原始代码

这导致每次 LLM 调用的 context 都接近上限，模型注意力被分散。

**改进方案**

根据每个 agent 的分析目标，定义不同的文件过滤策略：

| Agent | 文件策略 |
|-------|---------|
| structure | 全量摘要（受益于完整视图） |
| behavior | 入口文件 + 高 import 频率文件 |
| intent | 配置文件 + 架构层文件 + 摘要 |
| tradeoff | 仅使用前三轮分析结果，不传文件 |
| reviewer | 仅使用完整分析文档，不传文件 |
| narrative | 同 reviewer |

**影响文件**：各 agent 的 `build_user_prompt()`

**预期收益**：降低每次 LLM 调用成本，减少无关信息干扰，提升各 agent 分析焦点。

**实现复杂度**：低（只改各 agent 的 prompt 构建逻辑）

---

### 5. Reviewer 事实校验层

**现状问题**

reviewer agent 目前只做内部逻辑一致性检查（分析结论之间是否矛盾），无法发现事实性错误，例如：
- structure 分析引用了不存在的文件路径
- behavior 分析引用了实际不存在的函数名
- 置信度评分与证据数量不匹配

**改进方案**

在 reviewer agent 运行前，加一个程序化的事实校验步骤（不调用 LLM）：

```python
def verify_facts(document: SharedDocument, repo_path: str) -> list[str]:
    issues = []
    # 检查所有引用的文件路径是否存在
    for module in document.get_structure().get("modules", []):
        if not Path(repo_path, module["path"]).exists():
            issues.append(f"引用路径不存在: {module['path']}")
    # 检查引用的函数名是否在代码中出现
    ...
    return issues
```

将校验结果作为附加上下文传给 reviewer agent，让它聚焦于解释和修复建议，而不是重新发现问题。

**影响文件**：新增 `core/verifier.py`，`core/pipeline.py`，`agents/reviewer_agent.py`

**预期收益**：从根本上杜绝幻觉路径引用，提高分析可信度。

**实现复杂度**：中

---

### 6. 大型仓库分块策略

**现状问题**

对于超过 200 个文件的仓库，当前方案完全失效——大量文件被截断，分析结果失去代表性。

**改进方案**

按目录模块分块，每块独立分析后汇总：

```
大型仓库
├── frontend/   → 独立分析 → frontend 摘要
├── backend/    → 独立分析 → backend 摘要
└── shared/     → 独立分析 → shared 摘要
                              ↓
                        跨模块汇总分析
```

**影响文件**：`core/pipeline.py`（新增 `ChunkedPipeline`），`core/loader.py`

**预期收益**：支持企业级大型仓库，打破 50 文件上限的根本限制。

**实现复杂度**：高（需要设计汇总策略，token 消耗增加）

---

## P3 — 低优先级（有余力再做）

### 7. 多语言静态分析适配

当前 import 图和签名提取只对 Python 有精确实现，其他语言降级为正则。可以逐步为 TypeScript/JavaScript（用 `@babel/parser`）、Go（用 `go/parser`）、Java（用 `javalang`）添加精确 AST 解析。

**实现复杂度**：高（每种语言独立实现）

---

### 8. 分析结果增量更新

基于 git diff，只对变更的文件重新分析，其余复用上次结果。对于持续维护的项目（每周跑一次分析）价值较高。

**实现复杂度**：高（需要文件级别的结果缓存和合并策略）

---

## 实施路线建议

```
第一阶段（降低模型依赖的基础）
  └── P1-1 智能文件选择        ← 改动最小，收益最快
  └── P1-3 Import 依赖图预计算 ← 与文件选择共享基础设施

第二阶段（提升分析深度）
  └── P1-2 文件内容摘要化      ← 依赖语言适配决策
  └── P2-4 Agent 上下文裁剪   ← 依赖摘要化完成后再做

第三阶段（质量保障）
  └── P2-5 Reviewer 事实校验  ← 依赖前两阶段建立的基础设施

第四阶段（规模化）
  └── P2-6 大型仓库分块策略
  └── P3-7/8 按需扩展
```

---

## 各改进项总览

| # | 改进项 | 优先级 | 复杂度 | 主要收益 |
|---|--------|--------|--------|---------|
| 1 | 智能文件选择 | P1 | 低 | 关键文件不再被截断 |
| 2 | 文件内容摘要化 | P1 | 中 | 覆盖文件数 3x，token 消耗降低 |
| 3 | Import 依赖图预计算 | P1 | 中 | 依赖分析从猜测变为事实 |
| 4 | Agent 上下文裁剪 | P2 | 低 | 降低成本，提升焦点 |
| 5 | Reviewer 事实校验 | P2 | 中 | 消除路径/函数名幻觉 |
| 6 | 大型仓库分块 | P2 | 高 | 支持 200+ 文件仓库 |
| 7 | 多语言静态分析 | P3 | 高 | 提升非 Python 仓库质量 |
| 8 | 增量更新 | P3 | 高 | 持续维护场景提速 |
