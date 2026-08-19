"""Provider-neutral AI vision client used for plant identification and care."""

import base64
import json
import logging
import re
import time
from dataclasses import dataclass

import httpx

from app.languages import DEFAULT_LANGUAGE, language_name
from app.species_names import override_common_name

LOG = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a houseplant identification assistant. Given a photo, respond with STRICT JSON only, "
    "no prose, no markdown fences, matching this shape exactly: "
    '{"candidates": [{"scientific_name": str, "common_name": str, "confidence": float between 0 and 1}]}. '
    "Always return 3 candidates ordered by descending confidence, even if you are confident about the top "
    "one: include the 2 next most plausible alternative species (lower confidence is fine) so the user has "
    "options to pick from. Only return fewer than 3 if you genuinely cannot think of any other plausible "
    "species. "
    "scientific_name must stay in Latin; common_name must be written in __LANGUAGE_NAME__."
)

# Perenual's text search is English-only, so a species name typed in the
# deployment's configured non-English language finds nothing there. This is a
# text-only counterpart to identify_species (same response shape) that resolves
# a possibly foreign-language plant name to real species.
_NAME_RESOLVE_SYSTEM_PROMPT = (
    "You are a houseplant identification assistant. The user will give you the name of a houseplant, "
    "possibly written in a language other than English. Respond with STRICT JSON only, no prose, no "
    "markdown fences, matching this shape exactly: "
    '{"candidates": [{"scientific_name": str, "common_name": str, "confidence": float between 0 and 1}]}. '
    "Resolve the name to real houseplant species even if it isn't written in Latin/English. "
    "Always return up to 3 candidates ordered by descending confidence: if the name is ambiguous or could "
    "refer to more than one species, include those alternatives (lower confidence is fine) rather than only "
    "the single best guess. "
    "scientific_name must stay in Latin; common_name must be written in __LANGUAGE_NAME__."
)

_CARE_SYSTEM_PROMPT = (
    "You are a houseplant care assistant. Given a plant's scientific or common name, respond with STRICT "
    "JSON only, no prose, no markdown fences, matching this shape exactly: "
    '{"watering_interval_days": int, "light": str, "soil": str, "notes": str, '
    '"seasonal_profile": one of "tropical", "succulent", "mediterranean", "temperate"}. '
    "watering_interval_days must be a plain integer and seasonal_profile must stay one of the English enum "
    "values listed above; light, soil, and notes are free text describing sunlight needs, soil/potting mix, "
    "and any other care tips, and must be written in __LANGUAGE_NAME__."
)

_DIAGNOSE_SYSTEM_PROMPT = (
    "You are a houseplant health assistant. Given a photo of a houseplant (species: __SPECIES_NAME__), "
    "look for visible signs of trouble — yellowing/browning leaves, wilting, spots, pests, mold, leggy growth, "
    "etc. Respond with STRICT JSON only, no prose, no markdown fences, matching this shape exactly: "
    '{"healthy": bool, "issues": [{"issue": str, "suggestion": str}]}. '
    "Set healthy to true and return an empty issues list only if the plant looks visibly fine. Otherwise list "
    "each distinct issue you can identify with a concrete, actionable suggestion for fixing it. Both issue and "
    "suggestion must be written in __LANGUAGE_NAME__."
)


class AiVisionError(Exception):
    """Raised when the AI response cannot be parsed into species candidates."""


class AiCareDataError(Exception):
    """Raised when the AI response cannot be parsed into care data."""


class AiDiagnoseError(Exception):
    """Raised when the AI response cannot be parsed into a diagnosis."""


class AiUnavailableError(Exception):
    """Raised when the circuit breaker is tripped and calls should fail fast."""


@dataclass(frozen=True)
class SpeciesCandidate:
    scientific_name: str
    common_name: str | None
    confidence: float


@dataclass(frozen=True)
class DiagnoseIssue:
    issue: str
    suggestion: str


@dataclass(frozen=True)
class DiagnoseResult:
    healthy: bool
    issues: list[DiagnoseIssue]


def _extract_json(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise AiVisionError(f"Could not parse JSON from AI response: {content!r}")


def _parse_candidates(content: str, *, language: str = DEFAULT_LANGUAGE) -> list[SpeciesCandidate]:
    parsed = _extract_json(content)
    return [
        SpeciesCandidate(
            scientific_name=c["scientific_name"],
            common_name=override_common_name(c["scientific_name"], c.get("common_name"), language),
            confidence=c["confidence"],
        )
        for c in parsed.get("candidates", [])
    ]


class AiVisionClient:
    def __init__(
        self,
        *,
        api_style: str,
        base_url: str,
        api_key: str,
        model: str,
        api_version: str,
        timeout: float = 15.0,
        http_client: httpx.AsyncClient | None = None,
        failure_threshold: int = 2,
        cooldown_seconds: float = 300.0,
    ) -> None:
        self._api_style = api_style
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._api_version = api_version
        self._timeout = timeout
        # A shared, injected client (see app.main) reuses TCP/TLS connections
        # across requests instead of paying a fresh handshake per call; each
        # instance falls back to owning a private client (e.g. in tests) when
        # none is supplied.
        self._client = http_client or httpx.AsyncClient()
        # Circuit breaker (same shape as app.clients.perenual.PerenualClient):
        # after `failure_threshold` consecutive failures/timeouts across any of
        # identify_species/resolve_species_by_name/describe_care, skip the
        # network call entirely for `cooldown_seconds` and fail fast instead.
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._consecutive_failures = 0
        self._skip_until: float | None = None

    def _should_skip(self) -> bool:
        return self._skip_until is not None and time.monotonic() < self._skip_until

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._skip_until = None

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._failure_threshold:
            self._skip_until = time.monotonic() + self._cooldown_seconds

    def _build_request(self, messages: list[dict]) -> tuple[str, dict[str, str], dict[str, str], dict]:
        if self._api_style == "openai":
            return (
                f"{self._base_url}/chat/completions",
                {},
                {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
                {"model": self._model, "messages": messages, "temperature": 0},
            )
        if self._api_style == "azure-openai":
            if not self._api_version:
                raise ValueError("AI_API_VERSION must be set when AI_API_STYLE=azure-openai")
            return (
                f"{self._base_url}/openai/deployments/{self._model}/chat/completions",
                {"api-version": self._api_version},
                {"api-key": self._api_key, "Content-Type": "application/json"},
                {"messages": messages, "temperature": 0},
            )
        raise ValueError(f"Unsupported AI_API_STYLE: {self._api_style!r}")

    async def _post_chat_completion(self, messages: list[dict]) -> str:
        if self._should_skip():
            LOG.info("Skipping AI call — recently failing (model=%s)", self._model)
            raise AiUnavailableError(f"AI model {self._model!r} has been failing recently; skipping call")

        url, params, headers, payload = self._build_request(messages)

        # Timed + logged at INFO (see app.asgi's logging.basicConfig) since
        # provider latency is the prime suspect whenever plant identification is
        # slow — see TODO.md "Speed up plant identification further".
        start = time.monotonic()
        try:
            response = await self._client.post(
                url,
                params=params,
                headers=headers,
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            LOG.info(
                "AI chat completion failed after %.2fs (model=%s)",
                time.monotonic() - start,
                self._model,
                exc_info=True,
            )
            self._record_failure()
            raise
        self._record_success()
        LOG.info("AI chat completion took %.2fs (model=%s)", time.monotonic() - start, self._model)
        return response.json()["choices"][0]["message"]["content"]

    async def identify_species(
        self, *, image_bytes: bytes, mime_type: str, language: str = DEFAULT_LANGUAGE
    ) -> list[SpeciesCandidate]:
        b64_image = base64.b64encode(image_bytes).decode("ascii")
        system_prompt = _SYSTEM_PROMPT.replace("__LANGUAGE_NAME__", language_name(language))

        content = await self._post_chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Identify this houseplant species."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_image}"}},
                    ],
                },
            ]
        )
        return _parse_candidates(content, language=language)

    async def resolve_species_by_name(self, query: str, *, language: str = DEFAULT_LANGUAGE) -> list[SpeciesCandidate]:
        """Resolves a typed plant name to real species names."""
        system_prompt = _NAME_RESOLVE_SYSTEM_PROMPT.replace("__LANGUAGE_NAME__", language_name(language))

        content = await self._post_chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Plant name: {query}"},
            ]
        )
        return _parse_candidates(content, language=language)

    async def describe_care(self, species_name: str, *, language: str = DEFAULT_LANGUAGE) -> dict:
        """Returns watering interval and localized care guidance for a species."""
        system_prompt = _CARE_SYSTEM_PROMPT.replace("__LANGUAGE_NAME__", language_name(language))
        content = await self._post_chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Care guidance for: {species_name}"},
            ]
        )
        try:
            return _extract_json(content)
        except AiVisionError as exc:
            raise AiCareDataError(str(exc)) from exc

    async def diagnose_plant(
        self, *, image_bytes: bytes, mime_type: str, species_name: str | None = None, language: str = DEFAULT_LANGUAGE
    ) -> DiagnoseResult:
        """Returns visible plant issues and concrete suggested fixes."""
        b64_image = base64.b64encode(image_bytes).decode("ascii")
        system_prompt = _DIAGNOSE_SYSTEM_PROMPT.replace("__LANGUAGE_NAME__", language_name(language)).replace(
            "__SPECIES_NAME__", species_name or "unknown species"
        )

        content = await self._post_chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Diagnose any visible issues with this houseplant."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_image}"}},
                    ],
                },
            ]
        )
        try:
            parsed = _extract_json(content)
            return DiagnoseResult(
                healthy=bool(parsed.get("healthy", not parsed.get("issues"))),
                issues=[
                    DiagnoseIssue(issue=i["issue"], suggestion=i["suggestion"]) for i in parsed.get("issues", [])
                ],
            )
        except AiVisionError as exc:
            raise AiDiagnoseError(str(exc)) from exc
