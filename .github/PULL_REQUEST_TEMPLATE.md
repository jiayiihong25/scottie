## What changed

## Why

## Which piece does this touch?
- [ ] `ingest/` (deterministic — should rarely change)
- [ ] `graph/` (pacing_agent / content_router / concept_agent / card_agent / packet_writer)
- [ ] OmniRoute / `config/models.yaml`
- [ ] Docs (`docs/orchestration-design.md`, `CLAUDE.md`)
- [ ] Other

## Testing
How did you verify this? (e.g. ran the pipeline locally, unit tests, manual packet/apkg inspection)

## Checklist
- [ ] No secrets committed (`.env`, API keys)
- [ ] No `data/` or `output/` files committed
- [ ] Agent nodes call `call_model()` rather than a model client directly
- [ ] Failures fail loudly (no silent empty/malformed output on an unattended run)
