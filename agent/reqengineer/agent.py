"""Core requirements engineering agent."""

from __future__ import annotations

import os
import urllib.error
import urllib.request
import json
from dataclasses import asdict, dataclass
from typing import Literal


SYSTEM_PROMPT = """\
You are ReqEngineer, an AI requirements engineering agent.
Turn rough product ideas into clear, testable requirement records.
Return only valid JSON. Do not include markdown, commentary, or code fences.
"""

Priority = Literal["low", "medium", "high"]
Status = Literal["pending", "approved", "discarded"]


@dataclass(frozen=True)
class Requirement:
    name: str
    description: str
    priority: Priority
    status: Status


@dataclass(frozen=True)
class AgentStep:
    name: str
    summary: str


@dataclass(frozen=True)
class AgentResult:
    requirements: list[Requirement]
    steps: list[AgentStep]


@dataclass(frozen=True)
class ConversationMessage:
    role: Literal["user", "assistant", "tool"]
    content: str


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, object]


@dataclass(frozen=True)
class ChatTurn:
    reply: str
    tool_calls: list[ToolCall]


@dataclass(frozen=True)
class AgentConfig:
    """Runtime configuration for an OpenAI-compatible chat backend."""

    base_url: str = "http://192.168.10.68:52415/v1"
    model: str | None = None
    temperature: float = 0.2
    timeout_seconds: int = 300
    review_iterations: int = 0

    @classmethod
    def from_env(cls) -> AgentConfig:
        return cls(
            base_url=os.getenv("EXO_BASE_URL", cls.base_url),
            model=os.getenv("EXO_MODEL", "mlx-community/gpt-oss-20b-MXFP4-Q8"),
            temperature=float(os.getenv("REQENGINEER_TEMPERATURE", "0.2")),
            timeout_seconds=int(os.getenv("REQENGINEER_TIMEOUT_SECONDS", "300")),
            review_iterations=int(os.getenv("REQENGINEER_REVIEW_ITERATIONS", "0")),
        )


class RequirementsAgent:
    """Agent that drafts requirement artifacts from a product prompt."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or AgentConfig.from_env()

    def run(self, prompt: str) -> AgentResult:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("Prompt cannot be empty.")
        if not self.config.model:
            raise ValueError("Model is required. Set EXO_MODEL or pass model in the request.")

        steps: list[AgentStep] = []
        requirements = self._draft_requirements(prompt)
        steps.append(
            AgentStep(
                name="draft_requirements",
                summary=f"Generated {len(requirements)} candidate requirements from user text.",
            )
        )

        for iteration in range(max(0, self.config.review_iterations)):
            critique = self._critique_requirements(prompt, requirements)
            issue_count = len(critique.get("issues", [])) if isinstance(critique.get("issues"), list) else 0
            steps.append(
                AgentStep(
                    name="critique_requirements",
                    summary=f"Review pass {iteration + 1} found {issue_count} issue(s).",
                )
            )

            requirements = self._revise_requirements(prompt, requirements, critique)
            steps.append(
                AgentStep(
                    name="revise_requirements",
                    summary=f"Review pass {iteration + 1} produced {len(requirements)} final requirements.",
                )
            )

        return AgentResult(requirements=requirements, steps=steps)

    def revise(
        self,
        original_text: str,
        requirements: list[Requirement],
        observations: str,
    ) -> AgentResult:
        original_text = original_text.strip()
        observations = observations.strip()
        if not original_text:
            raise ValueError("Original text cannot be empty.")
        if not observations:
            raise ValueError("Observations cannot be empty.")
        if not requirements:
            raise ValueError("Requirements cannot be empty.")
        if not self.config.model:
            raise ValueError("Model is required. Set EXO_MODEL or pass model in the request.")

        revised = self._revise_from_observations(original_text, requirements, observations)
        return AgentResult(
            requirements=revised,
            steps=[
                AgentStep(
                    name="revise_from_user_observations",
                    summary=f"Revised {len(revised)} requirements from user observations.",
                )
            ],
        )

    def chat(self, messages: list[ConversationMessage]) -> ChatTurn:
        if not messages:
            raise ValueError("Conversation cannot be empty.")
        if not self.config.model:
            raise ValueError("Model is required. Set EXO_MODEL or pass model in the request.")

        content = self._chat_json(self._build_chat_prompt(messages))
        return self._parse_chat_turn(content)

    def _draft_requirements(self, prompt: str) -> list[Requirement]:
        content = self._chat_json(self._build_draft_prompt(prompt))
        return self._parse_requirements(content)

    def _critique_requirements(self, prompt: str, requirements: list[Requirement]) -> dict[str, object]:
        content = self._chat_json(self._build_critique_prompt(prompt, requirements))
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Model returned invalid critique JSON: {content}") from error
        if not isinstance(parsed, dict):
            raise RuntimeError("Model critique response must be a JSON object.")
        if "issues" not in parsed or not isinstance(parsed["issues"], list):
            raise RuntimeError("Model critique response must include an issues array.")
        return parsed

    def _revise_requirements(
        self,
        prompt: str,
        requirements: list[Requirement],
        critique: dict[str, object],
    ) -> list[Requirement]:
        content = self._chat_json(self._build_revision_prompt(prompt, requirements, critique))
        return self._parse_requirements(content)

    def _revise_from_observations(
        self,
        original_text: str,
        requirements: list[Requirement],
        observations: str,
    ) -> list[Requirement]:
        content = self._chat_json(
            self._build_observation_revision_prompt(original_text, requirements, observations)
        )
        return self._parse_requirements(content)

    def _chat_json(self, user_prompt: str) -> str:
        payload = {
            "model": self.config.model,
            "stream": False,
            "temperature": self.config.temperature,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        }

        request = urllib.request.Request(
            url=f"{self.config.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Model request failed with HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"Model request failed: {error.reason}") from error
        except TimeoutError as error:
            raise RuntimeError(
                f"Model request timed out after {self.config.timeout_seconds} seconds"
            ) from error

        try:
            return body["choices"][0]["message"]["content"].strip()
        except (KeyError, TypeError) as error:
            raise RuntimeError(f"Unexpected model response: {body}") from error

    def _parse_requirements(self, content: str) -> list[Requirement]:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Model returned invalid JSON: {content}") from error

        if isinstance(parsed, dict):
            raw_requirements = parsed.get("requirements")
        else:
            raw_requirements = parsed

        if not isinstance(raw_requirements, list):
            raise RuntimeError("Model response must be a JSON array or an object with a requirements array.")

        requirements: list[Requirement] = []
        for index, item in enumerate(raw_requirements, start=1):
            if not isinstance(item, dict):
                raise RuntimeError(f"Requirement {index} must be an object.")

            name = item.get("name")
            description = item.get("description")
            priority = item.get("priority")
            status = item.get("status")

            if not isinstance(name, str) or not name.strip():
                raise RuntimeError(f"Requirement {index} is missing a non-empty name.")
            if not isinstance(description, str) or not description.strip():
                raise RuntimeError(f"Requirement {index} is missing a non-empty description.")
            if priority not in {"low", "medium", "high"}:
                raise RuntimeError(f"Requirement {index} has invalid priority: {priority!r}.")
            if status not in {"pending", "approved", "discarded"}:
                raise RuntimeError(f"Requirement {index} has invalid status: {status!r}.")

            requirements.append(
                Requirement(
                    name=name.strip(),
                    description=description.strip(),
                    priority=priority,
                    status=status,
                )
            )

        if not requirements:
            raise RuntimeError("Model response did not include any requirements.")

        return requirements

    def _parse_chat_turn(self, content: str) -> ChatTurn:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Model returned invalid chat JSON: {content}") from error

        if not isinstance(parsed, dict):
            raise RuntimeError("Model chat response must be a JSON object.")

        reply = parsed.get("reply")
        if not isinstance(reply, str) or not reply.strip():
            raise RuntimeError("Model chat response must include a non-empty reply.")

        raw_tool_calls = parsed.get("tool_calls", [])
        if not isinstance(raw_tool_calls, list):
            raise RuntimeError("Model chat response tool_calls must be an array.")

        tool_calls: list[ToolCall] = []
        for index, raw_tool_call in enumerate(raw_tool_calls, start=1):
            if not isinstance(raw_tool_call, dict):
                raise RuntimeError(f"Tool call {index} must be an object.")
            name = raw_tool_call.get("name")
            arguments = raw_tool_call.get("arguments", {})
            if name != "create_requirements_from_conversation":
                raise RuntimeError(f"Unsupported tool call: {name!r}.")
            if not isinstance(arguments, dict):
                raise RuntimeError(f"Tool call {index} arguments must be an object.")
            tool_calls.append(ToolCall(name=name, arguments=arguments))

        return ChatTurn(reply=reply.strip(), tool_calls=tool_calls)

    @staticmethod
    def _requirements_to_json(requirements: list[Requirement]) -> str:
        return json.dumps(
            {"requirements": [asdict(requirement) for requirement in requirements]},
            indent=2,
        )

    @staticmethod
    def _build_draft_prompt(prompt: str) -> str:
        return f"""\
Create a concise set of requirements for this product idea:

{prompt}

Return JSON with this exact shape:
{{
  "requirements": [
    {{
      "name": "Short requirement name",
      "description": "One clear, testable requirement statement.",
      "priority": "high",
      "status": "pending"
    }}
  ]
}}

Rules:
- Return 5 to 10 requirements.
- Use priority values only: "low", "medium", "high".
- Use status values only: "pending", "approved", "discarded".
- Set every generated requirement status to "pending".
- Do not include assumptions, open questions, markdown, or extra keys.
"""

    def _build_critique_prompt(self, prompt: str, requirements: list[Requirement]) -> str:
        return f"""\
Review these candidate requirements for ambiguity, duplicates, missing core behavior,
untestable wording, and misplaced priority.

Original user text:
{prompt}

Candidate requirements:
{self._requirements_to_json(requirements)}

Return JSON with this exact shape:
{{
  "issues": [
    {{
      "requirement_name": "Requirement name or global",
      "severity": "medium",
      "problem": "What is wrong.",
      "recommendation": "How to fix it."
    }}
  ]
}}

Rules:
- Use severity values only: "low", "medium", "high".
- Return an empty issues array if the requirements are already clear, complete, and testable.
- Return only JSON.
"""

    def _build_revision_prompt(
        self,
        prompt: str,
        requirements: list[Requirement],
        critique: dict[str, object],
    ) -> str:
        return f"""\
Revise the candidate requirements using the critique.

Original user text:
{prompt}

Candidate requirements:
{self._requirements_to_json(requirements)}

Critique:
{json.dumps(critique, indent=2)}

Return JSON with this exact shape:
{{
  "requirements": [
    {{
      "name": "Short requirement name",
      "description": "One clear, testable requirement statement.",
      "priority": "high",
      "status": "pending"
    }}
  ]
}}

Rules:
- Return 5 to 10 requirements.
- Use priority values only: "low", "medium", "high".
- Use status values only: "pending", "approved", "discarded".
- Set every generated requirement status to "pending".
- Remove duplicate requirements.
- Make every description testable.
- Return only JSON.
"""

    def _build_observation_revision_prompt(
        self,
        original_text: str,
        requirements: list[Requirement],
        observations: str,
    ) -> str:
        return f"""\
Revise the current draft requirements using the user's observations.

Original user text:
{original_text}

Current draft requirements:
{self._requirements_to_json(requirements)}

User observations:
{observations}

Return JSON with this exact shape:
{{
  "requirements": [
    {{
      "name": "Short requirement name",
      "description": "One clear, testable requirement statement.",
      "priority": "high",
      "status": "pending"
    }}
  ]
}}

Rules:
- Return 5 to 10 requirements.
- Use priority values only: "low", "medium", "high".
- Use status values only: "pending", "approved", "discarded".
- Set revised requirements status to "pending".
- Apply only the user's actionable observations.
- Preserve good existing requirements when they still fit.
- Remove duplicate requirements.
- Make every description testable.
- Return only JSON.
"""

    @staticmethod
    def _conversation_to_json(messages: list[ConversationMessage]) -> str:
        return json.dumps(
            {"messages": [asdict(message) for message in messages]},
            indent=2,
        )

    def _build_chat_prompt(
        self,
        messages: list[ConversationMessage],
    ) -> str:
        return f"""\
You are the conversational front end for a requirements engineering workflow.
The user is chatting naturally. They may be brainstorming, asking unrelated
questions, clarifying scope, or deciding that the conversation is ready to turn
into structured requirements.

Available backend tool:
- create_requirements_from_conversation: creates structured requirements from
  the conversation so far. Use this only when the user explicitly asks to create,
  generate, draft, or proceed with requirements, or clearly confirms that the
  gathered scope is correct.

Conversation so far:
{self._conversation_to_json(messages)}

Return JSON with this exact shape:
{{
  "reply": "A natural-language assistant message for the chat UI.",
  "tool_calls": []
}}

Tool rules:
- Do not call the tool for a first product idea by itself. Discuss it and ask a
  useful follow-up question.
- Do not call the tool for greetings, unrelated questions, sports facts, or vague
  messages.
- Call create_requirements_from_conversation when the user says things like
  "create the requirements", "generate requirements", "go ahead", "yes that's it",
  "that looks good", or "proceed".
- If you call a tool, include:
  "tool_calls": [
    {{"name": "create_requirements_from_conversation", "arguments": {{}}}}
  ]

Reply rules:
- Keep the reply conversational.
- Ask one focused follow-up question when the scope is still being gathered.
- For unrelated questions, answer briefly if possible, then steer back to the
  requirements discussion. If you do not have enough context, say so.
- Match the user's language when practical. If the user writes in Spanish, reply in Spanish.
- Return only JSON.
"""
