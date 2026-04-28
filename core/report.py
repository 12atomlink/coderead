import json
from pathlib import Path
from typing import Any


def generate_report(data: dict) -> str:
    parts = []

    meta = data.get("meta", {})
    repo_name = meta.get("repo_name", "Unknown")
    analyzed_at = meta.get("analyzed_at", "N/A")

    parts.append(f"# {repo_name} 项目分析报告\n")
    parts.append(f"> 生成时间：{analyzed_at}\n")

    parts.append(_render_structure(data))
    parts.append(_render_behavior(data))
    parts.append(_render_intent(data))
    parts.append(_render_tradeoff(data))
    parts.append(_render_review(data))

    return "\n".join(parts)


def _render_structure(data: dict) -> str:
    structure = data.get("structure", {})
    if not structure:
        return ""

    parts = ["\n---\n\n## 一、项目结构\n"]

    modules = structure.get("modules", [])
    if modules:
        parts.append(f"\n### 模块概览（共 {len(modules)} 个）\n")
        parts.append("| 模块 | 路径 | 类型 | 说明 |")
        parts.append("|------|------|------|------|")
        for m in modules:
            name = m.get("name", "")
            path = m.get("path", "")
            mtype = m.get("type", "")
            desc = m.get("description", "").replace("|", "\\|")[:80]
            parts.append(f"| {name} | `{path}` | {mtype} | {desc} |")

    deps = structure.get("dependencies", [])
    if deps:
        parts.append(f"\n### 模块依赖关系（共 {len(deps)} 条）\n")
        for d in deps:
            from_m = d.get("from", "")
            to_m = d.get("to", "")
            dtype = d.get("type", "")
            parts.append(f"- **{from_m}** → **{to_m}**（{dtype}）")

    entries = structure.get("entry_points", [])
    if entries:
        parts.append(f"\n### 入口点\n")
        for e in entries:
            name = e.get("name", e.get("path", ""))
            desc = e.get("description", "")
            parts.append(f"- **{name}**：{desc}")

    confidence = structure.get("confidence")
    if confidence is not None:
        parts.append(f"\n> 置信度：{confidence:.0%}")

    return "\n".join(parts)


def _render_behavior(data: dict) -> str:
    behavior = data.get("behavior", {})
    if not behavior:
        return ""

    parts = ["\n---\n\n## 二、执行流分析\n"]

    flows = behavior.get("flows", [])
    if flows:
        parts.append(f"\n### 核心执行流程（共 {len(flows)} 个）\n")
        for i, f in enumerate(flows, 1):
            name = f.get("name", f"流程 {i}")
            desc = f.get("description", "")
            trigger = f.get("trigger", "")
            steps = f.get("steps", [])

            parts.append(f"\n#### {i}. {name}\n")
            if trigger:
                parts.append(f"- **触发条件**：{trigger}")
            if desc:
                parts.append(f"- **说明**：{desc}")
            if steps:
                parts.append(f"- **执行步骤**：")
                for j, s in enumerate(steps, 1):
                    if isinstance(s, dict):
                        action = s.get("action", s.get("name", s.get("step", "")))
                        component = s.get("component", "")
                        if action and component:
                            parts.append(f"  {j}. {action}（{component}）")
                        elif action:
                            parts.append(f"  {j}. {action}")
                        else:
                            parts.append(f"  {j}. {s}")
                    else:
                        parts.append(f"  {j}. {s}")

    data_flows = behavior.get("data_flow", [])
    if data_flows:
        parts.append(f"\n### 数据流（共 {len(data_flows)} 条）\n")
        for df in data_flows:
            name = df.get("name", "")
            source = df.get("source", "")
            sink = df.get("sink", "")
            parts.append(f"- **{name}**：`{source}` → `{sink}`")

    control_flows = behavior.get("control_flow", [])
    if control_flows:
        parts.append(f"\n### 控制流（共 {len(control_flows)} 条）\n")
        for cf in control_flows:
            name = cf.get("name", "")
            ctype = cf.get("type", "")
            desc = cf.get("description", "")
            parts.append(f"- **{name}**（{ctype}）：{desc}")

    confidence = behavior.get("confidence")
    if confidence is not None:
        parts.append(f"\n> 置信度：{confidence:.0%}")

    return "\n".join(parts)


def _render_intent(data: dict) -> str:
    intent = data.get("intent", {})
    if not intent:
        return ""

    parts = ["\n---\n\n## 三、设计意图\n"]

    goals = intent.get("design_goals", [])
    if goals:
        parts.append(f"\n### 设计目标（共 {len(goals)} 个）\n")
        for g in goals:
            goal = g.get("goal", "")
            evidence = g.get("evidence", "")
            hypothesis = g.get("hypothesis", False)
            tag = " 🔍*假设*" if hypothesis else ""
            parts.append(f"- **{goal}**{tag}")
            if evidence:
                parts.append(f"  - 依据：{evidence}")

    patterns = intent.get("architectural_patterns", [])
    if patterns:
        parts.append(f"\n### 架构模式（共 {len(patterns)} 个）\n")
        for p in patterns:
            pattern = p.get("pattern", "")
            desc = p.get("description", "")
            parts.append(f"- **{pattern}**：{desc}")

    assumptions = intent.get("assumptions", [])
    if assumptions:
        parts.append(f"\n### 设计假设（共 {len(assumptions)} 个）\n")
        for a in assumptions:
            assumption = a.get("assumption", "")
            hypothesis = a.get("hypothesis", False)
            tag = " 🔍*假设*" if hypothesis else ""
            parts.append(f"- {assumption}{tag}")

    confidence = intent.get("confidence")
    if confidence is not None:
        parts.append(f"\n> 置信度：{confidence:.0%}")

    return "\n".join(parts)


def _render_tradeoff(data: dict) -> str:
    tradeoff = data.get("tradeoff", {})
    if not tradeoff:
        return ""

    parts = ["\n---\n\n## 四、权衡分析\n"]

    pros = tradeoff.get("pros", [])
    if pros:
        parts.append(f"\n### ✅ 优势（共 {len(pros)} 个）\n")
        for p in pros:
            pro = p.get("pro", "")
            evidence = p.get("evidence", "")
            parts.append(f"- **{pro}**")
            if evidence:
                parts.append(f"  - 依据：{evidence}")

    cons = tradeoff.get("cons", [])
    if cons:
        parts.append(f"\n### ❌ 劣势（共 {len(cons)} 个）\n")
        for c in cons:
            con = c.get("con", "")
            evidence = c.get("evidence", "")
            parts.append(f"- **{con}**")
            if evidence:
                parts.append(f"  - 依据：{evidence}")

    alternatives = tradeoff.get("alternatives", [])
    if alternatives:
        parts.append(f"\n### 🔄 备选方案（共 {len(alternatives)} 个）\n")
        for a in alternatives:
            alt = a.get("alternative", "")
            trade_off = a.get("trade_off", "")
            feasibility = a.get("feasibility", "")
            parts.append(f"- **{alt}**")
            if trade_off:
                parts.append(f"  - 代价：{trade_off}")
            if feasibility:
                parts.append(f"  - 可行性：{feasibility}")

    risks = tradeoff.get("risks", [])
    if risks:
        parts.append(f"\n### ⚠️ 风险（共 {len(risks)} 个）\n")
        for r in risks:
            risk = r.get("risk", "")
            severity = r.get("severity", "")
            evidence = r.get("evidence", "")
            severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                str(severity).lower(), "⚪"
            )
            parts.append(f"- {severity_icon} **{risk}**（严重度：{severity}）")
            if evidence:
                parts.append(f"  - 依据：{evidence}")

    confidence = tradeoff.get("confidence")
    if confidence is not None:
        parts.append(f"\n> 置信度：{confidence:.0%}")

    return "\n".join(parts)


def _render_review(data: dict) -> str:
    review = data.get("review", {})
    if not review:
        return ""

    parts = ["\n---\n\n## 五、审查与建议\n"]

    issues = review.get("issues", [])
    if issues:
        parts.append(f"\n### 🐛 发现的问题（共 {len(issues)} 个）\n")
        for i, issue in enumerate(issues, 1):
            desc = issue.get("issue", "")
            section = issue.get("section", "")
            severity = issue.get("severity", "")
            suggestion = issue.get("suggestion", "")
            severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                str(severity).lower(), "⚪"
            )
            parts.append(
                f"{i}. {severity_icon} **{desc}**（来源：{section}，严重度：{severity}）"
            )
            if suggestion:
                parts.append(f"   - 建议：{suggestion}")

    inconsistencies = review.get("inconsistencies", [])
    if inconsistencies:
        parts.append(f"\n### ⚡ 不一致之处（共 {len(inconsistencies)} 个）\n")
        for inc in inconsistencies:
            desc = inc.get("inconsistency", "")
            sections = inc.get("sections", "")
            resolution = inc.get("resolution", "")
            parts.append(f"- **{desc}**（涉及：{sections}）")
            if resolution:
                parts.append(f"  - 修复建议：{resolution}")

    low_conf = review.get("low_confidence_areas", [])
    if low_conf:
        parts.append(f"\n### 🔍 低置信度区域（共 {len(low_conf)} 个）\n")
        for lc in low_conf:
            area = lc.get("area", "")
            reason = lc.get("reason", "")
            suggestion = lc.get("suggestion", "")
            parts.append(f"- **{area}**：{reason}")
            if suggestion:
                parts.append(f"  - 建议：{suggestion}")

    suggestions = review.get("suggestions", [])
    if suggestions:
        parts.append(f"\n### 💡 改进建议（共 {len(suggestions)} 个）\n")
        for s in suggestions:
            suggestion = s.get("suggestion", "")
            priority = s.get("priority", "")
            rationale = s.get("rationale", "")
            priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                str(priority).lower(), "⚪"
            )
            parts.append(f"- {priority_icon} **{suggestion}**（优先级：{priority}）")
            if rationale:
                parts.append(f"  - 理由：{rationale}")

    return "\n".join(parts)


STEP_RENDERERS = {
    "structure": _render_structure,
    "behavior": _render_behavior,
    "intent": _render_intent,
    "tradeoff": _render_tradeoff,
    "review": _render_review,
}

STEP_TITLES = {
    "structure": "项目结构",
    "behavior": "执行流分析",
    "intent": "设计意图",
    "tradeoff": "权衡分析",
    "review": "审查与建议",
}


def generate_step_report(
    step_name: str, step_data: dict, meta: dict | None = None
) -> str:
    renderer = STEP_RENDERERS.get(step_name)
    if not renderer:
        return ""

    title = STEP_TITLES.get(step_name, step_name)
    parts = [f"# {title}\n"]

    if meta:
        repo_name = meta.get("repo_name", "Unknown")
        analyzed_at = meta.get("analyzed_at", "N/A")
        parts.append(f"> 项目：{repo_name} ｜ 生成时间：{analyzed_at}\n")

    single_data = {step_name: step_data}
    content = renderer(single_data)
    if content:
        content = content.replace("\n---\n\n", "")
        parts.append(content)

    confidence = step_data.get("confidence")
    if confidence is not None:
        parts.append(f"\n> 置信度：{confidence:.0%}")

    return "\n".join(parts)


def save_report(data: dict, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    report = generate_report(data)
    output_path.write_text(report, encoding="utf-8")
    return output_path


def save_step_report(
    step_name: str, step_data: dict, output_path: str | Path, meta: dict | None = None
) -> Path:
    output_path = Path(output_path)
    report = generate_step_report(step_name, step_data, meta)
    if report:
        output_path.write_text(report, encoding="utf-8")
    return output_path


if __name__ == "__main__":
    import sys

    json_path = sys.argv[1] if len(sys.argv) > 1 else "output/analysis.json"
    output_path = (
        sys.argv[2] if len(sys.argv) > 2 else json_path.replace(".json", ".md")
    )

    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    result = save_report(data, output_path)
    print(f"✅ Report saved to: {result}")
