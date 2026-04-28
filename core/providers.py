import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProviderConfig:
    name: str = ""
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    max_tokens: int = 16000
    temperature: float = 0.1
    fallback_models: list = field(default_factory=list)


MODELSCOPE_FALLBACK_MODELS = [
    "deepseek-ai/DeepSeek-V4-Pro",
    "ZhipuAI/GLM-5",
    "moonshotai/Kimi-K2.5",
    "deepseek-ai/DeepSeek-V3.2",
    "deepseek-ai/DeepSeek-R1-0528",
    "Qwen/Qwen3-Coder-480B-A35B-Instruct",
    "ZhipuAI/GLM-4.7:DashScope",
]

PROVIDERS: dict[str, ProviderConfig] = {
    "openai": ProviderConfig(
        name="openai",
        base_url="https://api.openai.com/v1",
        api_key="",
        model="gpt-4o",
    ),
    "deepseek": ProviderConfig(
        name="deepseek",
        base_url="https://api.deepseek.com",
        api_key="",
        model="deepseek-chat",
    ),
    "zhipu": ProviderConfig(
        name="zhipu",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        api_key="",
        model="glm-4-plus",
    ),
    "moonshot": ProviderConfig(
        name="moonshot",
        base_url="https://api.moonshot.cn/v1",
        api_key="",
        model="moonshot-v1-128k",
    ),
    "qwen": ProviderConfig(
        name="qwen",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="",
        model="qwen-max",
    ),
    "baichuan": ProviderConfig(
        name="baichuan",
        base_url="https://api.baichuan-ai.com/v1",
        api_key="",
        model="Baichuan4",
    ),
    "yi": ProviderConfig(
        name="yi",
        base_url="https://api.lingyiwanwu.com/v1",
        api_key="",
        model="yi-large",
    ),
    "ollama": ProviderConfig(
        name="ollama",
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        model="llama3",
    ),
    "siliconflow": ProviderConfig(
        name="siliconflow",
        base_url="https://api.siliconflow.cn/v1",
        api_key="",
        model="Qwen/Qwen2.5-72B-Instruct",
    ),
    "modelscope": ProviderConfig(
        name="modelscope",
        base_url="https://api-inference.modelscope.cn/v1",
        api_key="",
        model="ZhipuAI/GLM-5.1",
        max_tokens=32768,
        temperature=0.7,
        fallback_models=MODELSCOPE_FALLBACK_MODELS,
    ),
    "azure": ProviderConfig(
        name="azure",
        base_url="",
        api_key="",
        model="gpt-4o",
    ),
}


def get_provider(name: str) -> ProviderConfig:
    if name not in PROVIDERS:
        available = ", ".join(PROVIDERS.keys())
        raise ValueError(f"Unknown provider '{name}'. Available: {available}")
    return ProviderConfig(**PROVIDERS[name].__dict__)


def resolve_config(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    config_file: Optional[str] = None,
) -> ProviderConfig:
    if config_file:
        file_config = _load_config_file(config_file)
        provider = provider or file_config.get("provider")
        model = model or file_config.get("model")
        api_key = api_key or file_config.get("api_key")
        base_url = base_url or file_config.get("base_url")
        max_tokens = max_tokens or file_config.get("max_tokens")
        temperature = temperature or file_config.get("temperature")

    if provider:
        config = get_provider(provider)
    else:
        config = ProviderConfig()

    config.model = model or config.model or os.getenv("LLM_MODEL", "gpt-4o")
    config.api_key = (
        api_key
        or config.api_key
        or os.getenv("LLM_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    )
    config.base_url = (
        base_url
        or config.base_url
        or os.getenv("LLM_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or ""
    )
    config.max_tokens = max_tokens or config.max_tokens
    config.temperature = temperature if temperature is not None else config.temperature

    if not config.api_key:
        raise ValueError(
            "API key is required. Provide it via:\n"
            "  - CLI: --api-key\n"
            "  - Config file: api_key field\n"
            "  - Environment: LLM_API_KEY or OPENAI_API_KEY"
        )

    return config


def _load_config_file(filepath: str) -> dict:
    import json
    from pathlib import Path

    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")
    return json.loads(path.read_text(encoding="utf-8"))
