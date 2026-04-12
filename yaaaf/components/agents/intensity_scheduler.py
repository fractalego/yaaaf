import logging
import re
from typing import List, Optional, Tuple

from yaaaf.components.agents.artefacts import ArtefactStorage
from yaaaf.components.agents.intensity_level import IntensityLevel, INTENSITY_LEVELS
from yaaaf.components.data_types import Messages, Note

# When the active palette has only one agent, bypass the planner entirely with this
# hardcoded plan. Keeps the LLM from hallucinating agents that aren't in the palette.
_SINGLE_AGENT_PLAN_TEMPLATE = """\
assets:
  answer:
    agent: {agent}
    description: "Answer the user's question"
    type: text
"""

_logger = logging.getLogger(__name__)


class IntensityScheduler:
    """Runs the orchestrator at increasing intensity levels until the answer is sufficient.

    Exposes the same query() interface as OrchestratorAgent and is a drop-in replacement
    from the server's perspective.

    The scheduler:
    1. Builds the active level sequence at construction time by intersecting each level's
       ideal palette with the configured agent set and deduplicating consecutive identical
       palettes.
    2. For each active level, configures the planner via set_active_palette(), runs the
       orchestrator, then asks ValidationAgent.check_sufficiency() to decide whether to
       stop or escalate.
    3. Carries forward (prior_result, reason, level_name) as context so the next level's
       plan can reference what was already tried.
    """

    def __init__(
        self,
        orchestrator,
        validation_agent,
        configured_agents: List[str],
        levels: Optional[List[IntensityLevel]] = None,
    ):
        self._orchestrator = orchestrator
        self._validation_agent = validation_agent
        self._active_levels = self._build_active_levels(
            configured_agents, levels or INTENSITY_LEVELS
        )
        _logger.info(
            "IntensityScheduler active levels: %s",
            [level.name for level, _ in self._active_levels],
        )

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _build_active_levels(
        self,
        configured_agents: List[str],
        levels: List[IntensityLevel],
    ) -> List[Tuple[IntensityLevel, List[str]]]:
        """Return filtered, deduplicated (level, active_palette) pairs."""
        configured_set = set(configured_agents)
        active: List[Tuple[IntensityLevel, List[str]]] = []
        prev_palette: Optional[List[str]] = None

        for level in levels:
            palette = [a for a in level.ideal_palette if a in configured_set]
            if not palette:
                _logger.debug("Level %s skipped: no configured agents", level.name)
                continue
            if palette == prev_palette:
                _logger.debug("Level %s skipped: duplicate palette", level.name)
                continue
            active.append((level, palette))
            prev_palette = palette

        return active

    # ------------------------------------------------------------------
    # Public interface (mirrors OrchestratorAgent.query)
    # ------------------------------------------------------------------

    async def query(
        self,
        messages: Messages,
        notes=None,
        stream_id=None,
        env_path=None,
        working_dir=None,
    ) -> str:
        prior_context: Optional[Tuple[str, str, str]] = None  # (result, reason, level_name)
        best_result: Optional[str] = None
        consecutive_exceptions = 0
        max_consecutive_exceptions = 2  # stop escalating if tools keep failing

        for level, palette in self._active_levels:
            _logger.info("Intensity level: %s  palette: %s", level.name, palette)

            if notes is not None:
                notes.append(
                    Note(
                        message=f"Intensity: {level.name} — {level.description}",
                        artefact_id=None,
                        agent_name="intensityscheduler",
                    )
                )

            # For single-agent palettes, bypass the planner with a hardcoded plan.
            # This prevents the LLM from ignoring palette constraints (e.g. using
            # brave_search at Easy level when only 'answerer' is allowed).
            if len(palette) == 1:
                self._orchestrator._preset_plan = _SINGLE_AGENT_PLAN_TEMPLATE.format(
                    agent=palette[0]
                )
            else:
                self._orchestrator._preset_plan = None

            # Configure the planner for this level (used when preset plan is not set)
            self._orchestrator.planner.set_active_palette(
                agent_names=palette,
                directive=level.directive,
                prior_context=prior_context,
            )

            try:
                result = await self._orchestrator.query(
                    messages,
                    notes=notes,
                    stream_id=stream_id,
                    env_path=env_path,
                    working_dir=working_dir,
                )
                best_result = result

                original_goal = (
                    self._orchestrator._original_goal
                    or messages.utterances[-1].content
                )

                # Decode artifact reference so the judge sees actual text, not a tag
                decoded = self._decode_result(result)

                is_sufficient, reason = await self._validation_agent.check_sufficiency(
                    result=decoded,
                    original_goal=original_goal,
                    level_name=level.name,
                )

                consecutive_exceptions = 0  # successful execution resets the counter

                if is_sufficient:
                    _logger.info("Answer sufficient at level %s", level.name)
                    return result

                _logger.info(
                    "Answer insufficient at level %s: %s — escalating", level.name, reason
                )
                prior_context = (result, reason, level.name)

                if notes is not None:
                    notes.append(
                        Note(
                            message=f"Escalating from {level.name}: {reason}",
                            artefact_id=None,
                            agent_name="intensityscheduler",
                        )
                    )

            except Exception as e:
                _logger.warning("Level %s raised exception: %s", level.name, e)
                consecutive_exceptions += 1
                prior_context = ("", str(e), level.name)

                if consecutive_exceptions >= max_consecutive_exceptions:
                    _logger.warning(
                        "%d consecutive level failures — stopping escalation "
                        "(likely a tool infrastructure problem)",
                        consecutive_exceptions,
                    )
                    if notes is not None:
                        notes.append(
                            Note(
                                message=(
                                    f"Stopping after {consecutive_exceptions} consecutive "
                                    f"failures — tool infrastructure may be unavailable"
                                ),
                                artefact_id=None,
                                agent_name="intensityscheduler",
                            )
                        )
                    break

        _logger.warning("All intensity levels exhausted — returning best result so far")
        return best_result or "I was unable to produce a sufficient answer."

    @staticmethod
    def _decode_result(result: str) -> str:
        """Resolve an artifact reference to its actual text content.

        The orchestrator returns the raw result string from the workflow executor,
        which looks like 'Operation completed. Result: <artefact type="text">id</artefact>'.
        The sufficiency judge needs the actual content, not the reference.
        """
        match = re.search(r"<artefact[^>]*>([^<]+)</artefact>", result)
        if not match:
            return result
        artifact_id = match.group(1).strip()
        try:
            artifact = ArtefactStorage().retrieve_from_id(artifact_id)
            if artifact and artifact.code:
                return artifact.code
        except Exception:
            pass
        return result

    @staticmethod
    def get_info() -> str:
        return "Runs agents at increasing intensity levels until the answer is sufficient"
