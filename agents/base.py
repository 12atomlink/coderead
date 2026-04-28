import json
from pathlib import Path
from typing import Any, Optional

from core.context import SharedDocument
from core.llm import LLMClient, LLMResponseError

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class BaseAgent:
    agent_name: str = "base"
    prompt_file: str = ""
    output_section: str = ""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def load_prompt(self) -> str:
        prompt_path = PROMPTS_DIR / self.prompt_file
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
        return prompt_path.read_text(encoding="utf-8")

    def build_user_prompt(
        self,
        document: SharedDocument,
        repo_summary: dict,
        file_tree: dict,
        file_contents: list[dict],
    ) -> str:
        raise NotImplementedError

    def run(
        self,
        document: SharedDocument,
        repo_summary: dict,
        file_tree: dict,
        file_contents: list[dict],
    ) -> SharedDocument:
        system_prompt = self.load_prompt()
        user_prompt = self.build_user_prompt(document, repo_summary, file_tree, file_contents)

        print(f"[{self.agent_name}] Calling LLM (model={self.llm.model})...")
        try:
            result = self.llm.chat_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except LLMResponseError as e:
            print(f"[{self.agent_name}] ❌ LLM response error: {e}")
            if e.raw_response:
                debug_file = Path("output") / "debug" / f"{self.agent_name}_raw_response.txt"
                debug_file.parent.mkdir(parents=True, exist_ok=True)
                debug_file.write_text(e.raw_response, encoding="utf-8")
                print(f"[{self.agent_name}] Raw response saved to: {debug_file}")
            raise
        print(f"[{self.agent_name}] LLM response received.")

        self._validate_result(result)
        document.update_section(self.output_section, result)

        return document

    def _validate_result(self, result: dict):
        if not isinstance(result, dict):
            raise ValueError(f"[{self.agent_name}] Result must be a dict, got {type(result)}")

    def _format_file_contents(self, file_contents: list[dict], max_files: int = 50) -> str:
        parts = []
        for f in file_contents[:max_files]:
            parts.append(f"### {f['path']}\n```\n{f['content']}\n```")
        if len(file_contents) > max_files:
            parts.append(f"\n... and {len(file_contents) - max_files} more files")
        return "\n\n".join(parts)

    def _format_json_section(self, data: Any) -> str:
        return json.dumps(data, indent=2, ensure_ascii=False)
