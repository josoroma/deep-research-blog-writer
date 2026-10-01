"""Load reviewed agent prompts from packaged resources, not the working directory."""

from importlib.resources import files

from schemas.config import AGENT_NAMES, AgentName


def load_prompt(agent: AgentName) -> str:
    if agent not in AGENT_NAMES:
        raise ValueError(f"Unknown agent: {agent}")
    content = files("prompts").joinpath(f"{agent}.md").read_text(encoding="utf-8")
    if not content.strip():
        raise ValueError(f"Prompt is empty: {agent}")
    return content
