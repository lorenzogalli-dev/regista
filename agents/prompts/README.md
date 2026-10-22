# Agent prompts

One system prompt per agent, loaded by `agents/pipeline.py` (`PROMPTS / f"{name}.md"`). Each
agent answers with structured output: a Pydantic schema from `agents/schemas.py`. Model
deployments: `fast` = `gtf-fast` (gpt-5.4-mini), `reasoning` = `gtf-reasoning` (gpt-5-mini, low
reasoning effort).

| Prompt | Agent | Model | Output schema | Job |
|---|---|---|---|---|
| `detector.md` | Detector | fast | `DetectorVerdict` | Keep or drop a candidate moment that code flagged (two signals above their noise level) |
| `analyst.md` | Analyst | reasoning | `Explanation` | Explain what changed and why, citing only numbers from the metrics tools (MCP); `{max_tool_calls}` is filled from settings |
| `verifier.md` | Verifier | fast | `TextCheck` | Check the claim text against evidence that code has already recomputed; reject factual errors (one retry with the reason) |
| `narrator.md` | Narrator | fast | `Caption` | One broadcast caption from the verified claim, no new numbers |
| `persona.md` | Persona | fast | `PersonaSet` | The verified insight for nine viewers (analyst / casual / player focus × EN / IT / ES) |
| `director.md` | Director | fast | `DirectorCue` | Whether the card goes on air now, later or not at all, and for how long |

Texts the Narrator and Persona write are checked by code against the verified claim (numbers,
names; `agents/textcheck.py`) and fall back to templates when they fail.
