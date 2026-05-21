# Audit logging vs CTM

## CTM (fixed, deterministic)

The CTM never stores logs and never decides where output goes. It only produces a cryptographic **receipt**:

- `merkle_root`, `ds`, `prompt_hash`, `response_hash`
- `timestamp`, `model_id`, `ctm_seal`

No environment dependency. **Do not configure the CTM.**

## Audit logs (configurable)

Runtime audit lines come from the Python logging layer:

```python
logger.info("IIAE_AUDIT_RECORD", extra={"iiae_data": record})
logger.info("INTEGRITY_VERIFIED", extra={"iiae_data": log_data})
```

Destination is set via **`IIAEConfig.log_destination`** or env **`IIAE_LOG_DESTINATION`**.

| Value | Handler |
|-------|---------|
| `stdout` | Default `StreamHandler` |
| `file:/var/log/iiae/audit.log` | `FileHandler` |
| `none` | Disabled (`NullHandler`) |
| `azure` | Azure Monitor (optional dep) |
| `splunk` | Splunk (optional dep) |
| `elastic` | Elasticsearch (optional dep) |
| `datadog` | Datadog (optional dep) |
| `siem` | Syslog → SIEM |

## Example

```python
from iiae import IIAEConfig, validate, build_audit_record, log_audit_record

cfg = IIAEConfig(log_destination="file:./logs/iiae-audit.jsonl")
result = validate(prompt, response, context, config=cfg)

# Receipt from CTM (forensic artifact)
receipt = result["receipt"]

# Optional structured audit log (redirected by config)
if cfg.audit_mode:
    from iiae import IIAESupervisor
    # or build from validate + manifest flow
    log_audit_record({"verified": result["verified"], "ctm_seal": result["ctm_seal"]}, config=cfg)
```

## Architecture

```
CTM          → receipt (cryptographic, immutable)
Logging      → JSON audit lines (enterprise-controlled destination)
IIAEConfig   → log_destination only affects logging
Supervisor   → emits INTEGRITY_* events to same logger tree
MAO          → optional filter metadata inside log payload
```
