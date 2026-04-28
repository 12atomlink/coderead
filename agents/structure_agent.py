import json

from agents.base import BaseAgent
from core.context import SharedDocument
from core.llm import LLMClient


class StructureAgent(BaseAgent):
    agent_name = "structure"
    prompt_file = "structure.md"
    output_section = "structure"

    def __init__(self, llm: LLMClient):
        super().__init__(llm)

    def build_user_prompt(
        self,
        document: SharedDocument,
        repo_summary: dict,
        file_tree: dict,
        file_contents: list[dict],
    ) -> str:
        return (
            f"### Repository Summary\n"
            f"{json.dumps(repo_summary, indent=2, ensure_ascii=False)}\n\n"
            f"### File Tree\n"
            f"{json.dumps(file_tree, indent=2, ensure_ascii=False)}\n\n"
            f"### File Contents\n"
            f"{self._format_file_contents(file_contents)}"
        )
