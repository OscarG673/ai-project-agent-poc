"""Command-line interface for ReqEngineer."""

from __future__ import annotations

import argparse
import json
import sys

from .agent import RequirementsAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reqengineer",
        description="Turn a rough product idea into a requirements draft.",
    )
    parser.add_argument(
        "idea",
        nargs="*",
        help="Product idea or workflow description. If omitted, stdin is used.",
    )
    parser.add_argument(
        "--model",
        help="OpenAI-compatible model name. Defaults to EXO_MODEL.",
    )
    parser.add_argument(
        "--base-url",
        help="OpenAI-compatible API base URL. Defaults to EXO_BASE_URL.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        help="Sampling temperature. Defaults to REQENGINEER_TEMPERATURE or 0.2.",
    )
    parser.add_argument(
        "--review-iterations",
        type=int,
        help="Draft critique/revision passes. Defaults to REQENGINEER_REVIEW_ITERATIONS or 1.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    prompt = " ".join(args.idea).strip()
    if not prompt and not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()

    agent = RequirementsAgent()
    config = agent.config
    if (
        args.model
        or args.base_url
        or args.temperature is not None
        or args.review_iterations is not None
    ):
        from .agent import AgentConfig

        config = AgentConfig(
            base_url=args.base_url or config.base_url,
            model=args.model or config.model,
            temperature=args.temperature
            if args.temperature is not None
            else config.temperature,
            timeout_seconds=config.timeout_seconds,
            review_iterations=args.review_iterations
            if args.review_iterations is not None
            else config.review_iterations,
        )
        agent = RequirementsAgent(config)

    try:
        result = agent.run(prompt)
    except ValueError as error:
        parser.error(str(error))
    except RuntimeError as error:
        print(f"reqengineer: {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "requirements": [requirement.__dict__ for requirement in result.requirements],
                "agent_steps": [step.__dict__ for step in result.steps],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
