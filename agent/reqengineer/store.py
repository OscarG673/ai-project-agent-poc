"""In-memory storage for generated requirements and embeddings."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from uuid import uuid4

from .agent import ConversationMessage, Requirement


@dataclass(frozen=True)
class StoredRequirement:
    id: str
    name: str
    description: str
    priority: str
    status: str

    @classmethod
    def from_requirement(cls, requirement: Requirement) -> StoredRequirement:
        return cls(
            id=f"req_{uuid4().hex[:12]}",
            name=requirement.name,
            description=requirement.description,
            priority=requirement.priority,
            status=requirement.status,
        )


@dataclass(frozen=True)
class StoredEmbedding:
    requirement_id: str
    model: str
    dimensions: int
    vector: list[float]


@dataclass(frozen=True)
class Draft:
    id: str
    original_text: str
    requirement_ids: list[str]
    status: str


@dataclass(frozen=True)
class ChatSession:
    id: str
    draft_id: str | None = None


class InMemoryStore:
    def __init__(self) -> None:
        self._requirements: dict[str, StoredRequirement] = {}
        self._embeddings: dict[str, StoredEmbedding] = {}
        self._drafts: dict[str, Draft] = {}
        self._sessions: dict[str, ChatSession] = {}
        self._messages: dict[str, list[ConversationMessage]] = {}
        self._lock = Lock()

    def save_requirements(self, requirements: list[Requirement]) -> list[StoredRequirement]:
        stored = [StoredRequirement.from_requirement(requirement) for requirement in requirements]
        with self._lock:
            for requirement in stored:
                self._requirements[requirement.id] = requirement
        return stored

    def get_requirement(self, requirement_id: str) -> StoredRequirement | None:
        with self._lock:
            return self._requirements.get(requirement_id)

    def create_session(self) -> ChatSession:
        session = ChatSession(id=f"session_{uuid4().hex[:12]}")
        with self._lock:
            self._sessions[session.id] = session
            self._messages[session.id] = []
        return session

    def get_session(self, session_id: str) -> ChatSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def append_message(self, session_id: str, message: ConversationMessage) -> None:
        with self._lock:
            self._messages.setdefault(session_id, []).append(message)

    def get_messages(self, session_id: str) -> list[ConversationMessage]:
        with self._lock:
            return list(self._messages.get(session_id, []))

    def create_draft(self, original_text: str, requirements: list[Requirement]) -> tuple[Draft, list[StoredRequirement]]:
        stored_requirements = [StoredRequirement.from_requirement(requirement) for requirement in requirements]
        draft = Draft(
            id=f"draft_{uuid4().hex[:12]}",
            original_text=original_text,
            requirement_ids=[requirement.id for requirement in stored_requirements],
            status="pending",
        )
        with self._lock:
            for requirement in stored_requirements:
                self._requirements[requirement.id] = requirement
            self._drafts[draft.id] = draft
        return draft, stored_requirements

    def attach_draft_to_session(self, session_id: str, draft_id: str) -> ChatSession | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            updated = ChatSession(id=session.id, draft_id=draft_id)
            self._sessions[session_id] = updated
            return updated

    def get_draft(self, draft_id: str) -> Draft | None:
        with self._lock:
            return self._drafts.get(draft_id)

    def get_draft_requirements(self, draft_id: str) -> list[StoredRequirement] | None:
        with self._lock:
            draft = self._drafts.get(draft_id)
            if draft is None:
                return None
            requirements = []
            for requirement_id in draft.requirement_ids:
                requirement = self._requirements.get(requirement_id)
                if requirement is not None:
                    requirements.append(requirement)
            return requirements

    def replace_draft_requirements(
        self,
        draft_id: str,
        requirements: list[Requirement],
    ) -> tuple[Draft, list[StoredRequirement]] | None:
        stored_requirements = [StoredRequirement.from_requirement(requirement) for requirement in requirements]
        with self._lock:
            draft = self._drafts.get(draft_id)
            if draft is None:
                return None
            updated_draft = Draft(
                id=draft.id,
                original_text=draft.original_text,
                requirement_ids=[requirement.id for requirement in stored_requirements],
                status="pending",
            )
            for requirement in stored_requirements:
                self._requirements[requirement.id] = requirement
            self._drafts[draft_id] = updated_draft
            return updated_draft, stored_requirements

    def approve_draft(self, draft_id: str) -> tuple[Draft, list[StoredRequirement]] | None:
        with self._lock:
            draft = self._drafts.get(draft_id)
            if draft is None:
                return None

            approved_requirements: list[StoredRequirement] = []
            for requirement_id in draft.requirement_ids:
                requirement = self._requirements.get(requirement_id)
                if requirement is None:
                    continue
                approved = StoredRequirement(
                    id=requirement.id,
                    name=requirement.name,
                    description=requirement.description,
                    priority=requirement.priority,
                    status="approved",
                )
                self._requirements[requirement_id] = approved
                approved_requirements.append(approved)

            approved_draft = Draft(
                id=draft.id,
                original_text=draft.original_text,
                requirement_ids=draft.requirement_ids,
                status="approved",
            )
            self._drafts[draft_id] = approved_draft
            return approved_draft, approved_requirements

    def save_embedding(
        self,
        requirement_id: str,
        model: str,
        vector: list[float],
    ) -> StoredEmbedding:
        embedding = StoredEmbedding(
            requirement_id=requirement_id,
            model=model,
            dimensions=len(vector),
            vector=vector,
        )
        with self._lock:
            self._embeddings[requirement_id] = embedding
        return embedding
