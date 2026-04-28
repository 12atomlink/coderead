import json

from agents.base import BaseAgent
from core.context import SharedDocument
from core.llm import LLMClient


class TradeoffAgent(BaseAgent):
    agent_name = "tradeoff"
    prompt_file = "tradeoff.md"
    output_section = "tradeoff"

    def __init__(self, llm: LLMClient):
        super().__init__(llm)

    def build_user_prompt(
        self,
        document: SharedDocument,
        repo_summary: dict,
        file_tree: dict,
        file_contents: list[dict],
    ) -> str:
        structure_analysis = document.get_structure()
        behavior_analysis = document.get_behavior()
        intent_analysis = document.get_intent()
        return (
            f"### Structure Analysis\n"
            f"{json.dumps(structure_analysis, indent=2, ensure_ascii=False)}\n\n"
            f"### Behavior Analysis\n"
            f"{json.dumps(behavior_analysis, indent=2, ensure_ascii=False)}\n\n"
            f"### Intent Analysis\n"
            f"{json.dumps(intent_analysis, indent=2, ensure_ascii=False)}\n\n"
            f"### File Contents\n"
            f"{self._format_file_contents(file_contents)}"
        )
