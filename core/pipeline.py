import json
import shutil
import time
from pathlib import Path
from typing import Optional

from agents.behavior_agent import BehaviorAgent
from agents.intent_agent import IntentAgent
from agents.narrative_agent import NarrativeAgent
from agents.reviewer_agent import ReviewerAgent
from agents.structure_agent import StructureAgent
from agents.tradeoff_agent import TradeoffAgent
from core.context import SharedDocument
from core.llm import LLMClient
from core.loader import RepoLoader
from core.report import save_report, save_step_report

AGENT_NAMES = ["structure", "behavior", "intent", "tradeoff", "reviewer", "narrative"]


class StepTracker:
    def __init__(self):
        self.steps: list[dict] = []
        self._start_time: Optional[float] = None

    def start_step(self, name: str, index: int, total: int, skipped: bool = False):
        self._start_time = time.time()
        status = "SKIPPED (resume)" if skipped else "RUNNING"
        print(f"\n{'='*60}")
        print(f"  Step {index + 1}/{total}: {name}  [{status}]")
        print(f"{'='*60}")

    def end_step(self, name: str, skipped: bool = False):
        elapsed = time.time() - self._start_time if self._start_time else 0
        status = "SKIPPED" if skipped else "DONE"
        step_info = {
            "name": name,
            "status": status,
            "elapsed_seconds": round(elapsed, 2),
        }
        self.steps.append(step_info)
        if not skipped:
            print(f"  ⏱  {name} completed in {elapsed:.1f}s")
        return step_info

    def print_summary(self):
        print(f"\n{'='*60}")
        print("  Pipeline Summary")
        print(f"{'='*60}")
        total_time = 0.0
        for s in self.steps:
            icon = "⏭️ " if s["status"] == "SKIPPED" else "✅"
            print(
                f"  {icon} {s['name']:12s}  {s['status']:8s}  {s['elapsed_seconds']:.1f}s"
            )
            total_time += s["elapsed_seconds"]
        print(f"  {'─'*40}")
        print(f"  {'TOTAL':12s}  {'':8s}  {total_time:.1f}s")
        print(f"{'='*60}")


class Pipeline:
    def __init__(self, llm: LLMClient):
        self.llm = llm
        self.agents = [
            StructureAgent(llm),
            BehaviorAgent(llm),
            IntentAgent(llm),
            TradeoffAgent(llm),
            ReviewerAgent(llm),
            NarrativeAgent(llm),
        ]

    def run(
        self,
        repo_path: str,
        output_path: Optional[str] = None,
        save_intermediate: bool = True,
        resume: bool = False,
        from_step: Optional[str] = None,
        focus_path: Optional[str] = None,
    ) -> SharedDocument:
        tracker = StepTracker()

        print(f"[Pipeline] Loading repository: {repo_path}")
        if focus_path:
            print(f"[Pipeline] Focus: {focus_path} (70% slot priority)")
        loader = RepoLoader(repo_path, focus_path=focus_path)
        repo_summary = loader.get_summary()
        file_tree = loader.get_tree()
        file_contents = loader.get_files_ranked(max_files=50)
        print(f"[Pipeline] Found {repo_summary['total_files']} files total, selected {len(file_contents)} by entry-chain ranking")

        intermediate_dir = None
        if output_path and save_intermediate:
            intermediate_dir = Path(output_path).parent / "intermediate"

        if not resume:
            self._backup_existing(output_path, intermediate_dir)
        else:
            if intermediate_dir:
                intermediate_dir.mkdir(parents=True, exist_ok=True)

        document = SharedDocument(repo_name=repo_summary["repo_name"])

        if resume and intermediate_dir:
            document = self._load_existing_results(document, intermediate_dir)
            print(f"[Pipeline] Resume mode: loaded existing results")

        from_index = 0
        if from_step:
            if from_step not in AGENT_NAMES:
                raise ValueError(
                    f"Unknown step '{from_step}'. Available: {', '.join(AGENT_NAMES)}"
                )
            from_index = AGENT_NAMES.index(from_step)
            print(f"[Pipeline] Starting from step: {from_step} (index {from_index})")

        for i, agent in enumerate(self.agents):
            if i < from_index:
                tracker.start_step(agent.agent_name, i, len(self.agents), skipped=True)
                tracker.end_step(agent.agent_name, skipped=True)
                continue

            if resume and intermediate_dir:
                intermediate_file = intermediate_dir / f"{agent.agent_name}.json"
                if intermediate_file.exists():
                    existing = self._load_intermediate(intermediate_file)
                    if existing:
                        document.update_section(agent.output_section, existing)
                        tracker.start_step(
                            agent.agent_name, i, len(self.agents), skipped=True
                        )
                        tracker.end_step(agent.agent_name, skipped=True)
                        continue

            tracker.start_step(agent.agent_name, i, len(self.agents))

            try:
                document = agent.run(
                    document=document,
                    repo_summary=repo_summary,
                    file_tree=file_tree,
                    file_contents=file_contents,
                )
            except Exception as e:
                tracker.end_step(agent.agent_name)
                print(f"[Pipeline] ❌ ERROR in {agent.agent_name}: {e}")
                if save_intermediate and intermediate_dir:
                    error_file = intermediate_dir / f"{agent.agent_name}_error.json"
                    error_info = {
                        "agent": agent.agent_name,
                        "error": str(e),
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "completed_steps": [
                            s["name"] for s in tracker.steps if s["status"] == "DONE"
                        ],
                    }
                    error_file.write_text(
                        json.dumps(error_info, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    print(f"[Pipeline] Error info saved to {error_file}")
                    print(f"[Pipeline] Use --resume to continue from this point")
                raise

            tracker.end_step(agent.agent_name)

            if save_intermediate and intermediate_dir:
                intermediate_file = intermediate_dir / f"{agent.agent_name}.json"
                document.save(str(intermediate_file))
                print(f"[Pipeline] 💾 Intermediate saved: {intermediate_file}")

                step_data = document.to_dict().get(agent.agent_name, {})
                if step_data:
                    step_md_path = intermediate_dir / f"{agent.agent_name}.md"
                    save_step_report(
                        agent.agent_name,
                        step_data,
                        step_md_path,
                        meta=document.to_dict().get("meta"),
                    )
                    print(f"[Pipeline] 📝 Step report saved: {step_md_path}")

            if output_path:
                document.save(output_path)
                report_path = str(output_path).replace(".json", ".md")
                save_report(document.to_dict(), report_path)

        tracker.print_summary()
        return document

    def _backup_existing(
        self,
        output_path: Optional[str],
        intermediate_dir: Optional[Path],
    ):
        has_existing = False

        if intermediate_dir and intermediate_dir.exists():
            if any(intermediate_dir.iterdir()):
                has_existing = True

        if output_path:
            output_file = Path(output_path)
            if output_file.exists():
                has_existing = True
            report_file = output_file.with_suffix(".md")
            if report_file.exists():
                has_existing = True

        if not has_existing:
            if intermediate_dir:
                intermediate_dir.mkdir(parents=True, exist_ok=True)
            return

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_dir = (
            intermediate_dir.parent / "backup" / timestamp
            if intermediate_dir
            else Path("output") / "backup" / timestamp
        )
        backup_dir.mkdir(parents=True, exist_ok=True)

        if intermediate_dir and intermediate_dir.exists():
            for f in intermediate_dir.iterdir():
                if f.is_file():
                    shutil.copy2(f, backup_dir / f.name)

        if output_path:
            output_file = Path(output_path)
            if output_file.exists():
                shutil.copy2(output_file, backup_dir / output_file.name)
            report_file = output_file.with_suffix(".md")
            if report_file.exists():
                shutil.copy2(report_file, backup_dir / report_file.name)

        print(f"[Pipeline] 📦 Existing results backed up to: {backup_dir}")

        if intermediate_dir and intermediate_dir.exists():
            for f in intermediate_dir.iterdir():
                if f.is_file():
                    f.unlink()

        if output_path:
            output_file = Path(output_path)
            if output_file.exists():
                output_file.unlink()
            report_file = output_file.with_suffix(".md")
            if report_file.exists():
                report_file.unlink()

        if intermediate_dir:
            intermediate_dir.mkdir(parents=True, exist_ok=True)

    def _load_existing_results(
        self, document: SharedDocument, intermediate_dir: Path
    ) -> SharedDocument:
        for agent_name in AGENT_NAMES:
            intermediate_file = intermediate_dir / f"{agent_name}.json"
            existing = self._load_intermediate(intermediate_file)
            if existing:
                document.update_section(agent_name, existing)
                print(f"[Pipeline]   Loaded: {agent_name}")
        return document

    def _load_intermediate(self, filepath: Path) -> Optional[dict]:
        if not filepath.exists():
            return None
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            if isinstance(data, dict) and len(data) > 0:
                return data
        except (json.JSONDecodeError, Exception):
            pass
        return None
