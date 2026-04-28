import json

from agents.base import BaseAgent
from core.context import SharedDocument
from core.llm import LLMClient


class NarrativeAgent(BaseAgent):
    agent_name = "narrative"
    prompt_file = "narrative.md"
    output_section = "narrative"

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
            f"### 仓库概要\n"
            f"{json.dumps(repo_summary, indent=2, ensure_ascii=False)}\n\n"
            f"### 完整分析结果\n"
            f"{document.to_context_string()}\n\n"
            f"### 文件内容（前30个）\n"
            f"{self._format_file_contents(file_contents, max_files=30)}"
        )
