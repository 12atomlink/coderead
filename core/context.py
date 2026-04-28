import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


def create_empty_document(repo_name: str = "") -> dict:
    return {
        "meta": {
            "repo_name": repo_name,
            "analyzed_at": datetime.now().isoformat(),
            "version": "v1",
        },
        "structure": {
            "modules": [],
            "dependencies": [],
            "entry_points": [],
            "confidence": 0.0,
            "evidence": [],
        },
        "behavior": {
            "flows": [],
            "data_flow": [],
            "control_flow": [],
            "confidence": 0.0,
            "evidence": [],
        },
        "intent": {
            "design_goals": [],
            "architectural_patterns": [],
            "assumptions": [],
            "confidence": 0.0,
            "evidence": [],
        },
        "tradeoff": {
            "pros": [],
            "cons": [],
            "alternatives": [],
            "risks": [],
            "confidence": 0.0,
        },
        "review": {
            "issues": [],
            "inconsistencies": [],
            "low_confidence_areas": [],
            "suggestions": [],
        },
    }


class SharedDocument:
    def __init__(self, data: Optional[dict] = None, repo_name: str = ""):
        if data is not None:
            self._data = data
        else:
            self._data = create_empty_document(repo_name)

    @property
    def data(self) -> dict:
        return self._data

    def get_section(self, section: str) -> Any:
        return self._data.get(section, {})

    def update_section(self, section: str, value: Any):
        self._data[section] = value

    def get_meta(self) -> dict:
        return self._data.get("meta", {})

    def get_structure(self) -> dict:
        return self._data.get("structure", {})

    def get_behavior(self) -> dict:
        return self._data.get("behavior", {})

    def get_intent(self) -> dict:
        return self._data.get("intent", {})

    def get_tradeoff(self) -> dict:
        return self._data.get("tradeoff", {})

    def get_review(self) -> dict:
        return self._data.get("review", {})

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self._data, indent=indent, ensure_ascii=False)

    def save(self, filepath: str):
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, filepath: str) -> "SharedDocument":
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Document file not found: {filepath}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(data=data)

    def to_context_string(self) -> str:
        sections = []
        for key, value in self._data.items():
            if key == "meta":
                continue
            section_json = json.dumps(value, indent=2, ensure_ascii=False)
            sections.append(f"## {key.upper()}\n{section_json}")
        return "\n\n".join(sections)
