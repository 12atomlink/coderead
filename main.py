import argparse
import sys

from core.llm import LLMClient
from core.pipeline import AGENT_NAMES, Pipeline
from core.providers import PROVIDERS


def main():
    provider_names = ", ".join(PROVIDERS.keys())
    step_names = ", ".join(AGENT_NAMES)

    parser = argparse.ArgumentParser(
        description="Project Analyzer v1 - Structured code repository understanding",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  # Basic usage
  python main.py ./my-project --provider deepseek --api-key sk-xxx

  # Resume from interrupted run (skip completed steps)
  python main.py ./my-project --provider deepseek --resume

  # Start from a specific step
  python main.py ./my-project --provider deepseek --from-step behavior

  # Use config file
  python main.py ./my-project --config llm-config.json

  # Use local Ollama
  python main.py ./my-project --provider ollama --model llama3

Available providers: {provider_names}
Available steps: {step_names}
""",
    )
    parser.add_argument(
        "repo_path", nargs="?", help="Path to the repository to analyze"
    )
    parser.add_argument(
        "-o",
        "--output",
        default="output/analysis.json",
        help="Output file path (default: output/analysis.json)",
    )
    parser.add_argument(
        "-p",
        "--provider",
        default=None,
        help=f"LLM provider preset ({provider_names})",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="LLM model name (overrides provider default)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="LLM API key (overrides provider default and env var)",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="LLM API base URL (overrides provider default and env var)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Max tokens for LLM response (default: 16000)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="LLM temperature (default: 0.1)",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=None,
        help="Path to LLM config JSON file",
    )
    parser.add_argument(
        "--no-intermediate",
        action="store_true",
        help="Don't save intermediate results for each agent",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from previous run, skip completed steps",
    )
    parser.add_argument(
        "--from-step",
        default=None,
        help=f"Start from a specific step ({step_names})",
    )
    parser.add_argument(
        "--list-providers",
        action="store_true",
        help="List all available provider presets and exit",
    )
    parser.add_argument(
        "--focus",
        default=None,
        metavar="SUBDIR",
        help="Focus analysis on a subdirectory (e.g. packages/opencode). "
             "Files in this path get 70%% of the file slots, rest get 30%%.",
    )

    args = parser.parse_args()

    if args.list_providers:
        print("Available LLM provider presets:\n")
        for name, cfg in PROVIDERS.items():
            print(
                f"  {name:12s}  base_url={cfg.base_url or '(required)'}  model={cfg.model}"
            )
        sys.exit(0)

    if not args.repo_path:
        parser.error("repo_path is required")

    if args.resume and args.no_intermediate:
        parser.error(
            "--resume requires intermediate results, cannot use with --no-intermediate"
        )

    try:
        llm = LLMClient(
            provider=args.provider,
            model=args.model,
            api_key=args.api_key,
            base_url=args.base_url,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            config_file=args.config,
        )
        print(f"🤖 LLM: {llm}")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    pipeline = Pipeline(llm)

    try:
        document = pipeline.run(
            repo_path=args.repo_path,
            output_path=args.output,
            save_intermediate=not args.no_intermediate,
            resume=args.resume,
            from_step=args.from_step,
            focus_path=args.focus,
        )
        print(f"\n✅ Analysis complete!")
        print(f"📄 Output: {args.output}")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error during analysis: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
