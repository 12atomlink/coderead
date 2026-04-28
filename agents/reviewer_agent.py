import json

from agents.base import BaseAgent
from core.context import SharedDocument
from core.llm import LLMClient


class ReviewerAgent(BaseAgent):
    agent_name = "reviewer"
    prompt_file = "reviewer.md"
    output_section = "review"

    def __init__(self, llm: LLMClient):
        super().__init__(llm)

    def build_user_prompt(
        self,
        document: SharedDocument,
        repo_summary: dict,
        file_tree: dict,
        file_contents: list[dict],
    ) -> str:
        full_document = document.data
        return (
            f"### Complete Analysis Document\n"
            f"{json.dumps(full_document, indent=2, ensure_ascii=False)}\n\n"
            f"### File Contents\n"
            f"{self._format_file_contents(file_contents)}"
        )
