# 🎯 Streamlit App Timing Instrumentation Summary

## What Was Added to app.py

### 1. **Import time module** (line 17)
```python
import time
```

### 2. **Timing measurement around process_query()** (lines 606-650)
```python
# Timing for performance measurement
t_total_start = time.perf_counter()
t_llm_elapsed = 0.0
t_audit_elapsed = 0.0

# [execute process_query]

# Extract timing from metrics
if hasattr(audit_result, 'metrics') and audit_result.metrics:
    audit_metrics = audit_result.metrics
    t_audit_elapsed = audit_metrics.get('audit_duration_sec', t_process_elapsed)
    # LLM time = total - audit time
    if t_audit_elapsed > 0:
        t_llm_elapsed = max(0, t_process_elapsed - t_audit_elapsed)

t_total_elapsed = time.perf_counter() - t_total_start
```

### 3. **Store timing in chat history** (lines 713-716)
```python
# Timing measurements
"timing_llm_sec": t_llm_elapsed,
"timing_audit_sec": t_audit_elapsed,
"timing_total_sec": t_total_elapsed,
```

### 4. **Display timing in telemetry panel** (lines 827-835)
```python
# Extract timing info if available
timing_llm = last_audit.get("timing_llm_sec", 0)
timing_audit = last_audit.get("timing_audit_sec", 0)
timing_total = last_audit.get("timing_total_sec", 0)

# Create timing display string with percentages
if timing_total > 0:
    llm_pct = (timing_llm / timing_total * 100)
    audit_pct = (timing_audit / timing_total * 100)
    timing_str = f"⏱️ LLM: {timing_llm:.2f}s ({llm_pct:.0f}%) | Auditoría: {timing_audit:.2f}s ({audit_pct:.0f}%) | Total: {timing_total:.2f}s"
```

## How to Use

### Step 1: Run the Streamlit app
```bash
cd Idicoc-demo-ui
streamlit run app.py
```

### Step 2: Submit a query
Type a message in the chat box and submit.

### Step 3: Check the timing display
Look at the right sidebar under **"🛡️ Última Auditoría IDICOC"**

You'll see something like:
```
⏱️ LLM: 15.23s (85%) | Auditoría: 2.45s (15%) | Total: 17.68s
```

## How to Interpret Results

### LLM is the bottleneck
```
⏱️ LLM: 15.50s (90%) | Auditoría: 1.70s (10%) | Total: 17.20s
                ↑↑↑
           90% of time here
```
**Action:** Optimize LLM model, reduce context size, or use faster model

### Notary is the bottleneck
```
⏱️ LLM: 2.00s (15%) | Auditoría: 11.50s (85%) | Total: 13.50s
                              ↑↑↑↑↑
                         85% of time here
```
**Action:** Optimize DSE evaluation (policy graph evaluation is the culprit)

### Balanced
```
⏱️ LLM: 8.50s (50%) | Auditoría: 8.50s (50%) | Total: 17.00s
```
**Action:** Optimize both LLM and Notary equally

## Architecture

```
┌─────────────────────────────────────────────┐
│   Streamlit App (app.py)                    │
│  ┌─────────────────────────────────────────┐│
│  │ Time t_total_start                      ││
│  │   ↓                                      ││
│  │   process_query()                       ││ ← Calls LLM + Audit
│  │   ├─ LLM Generation    (from metrics)   ││
│  │   └─ Audit Pipeline    (audit_duration) ││
│  │   ↓                                      ││
│  │ Time t_total_elapsed                    ││
│  │   ↓                                      ││
│  │ Display timing breakdown in UI          ││
│  └─────────────────────────────────────────┘│
│                                              │
│  Telemetry Panel:                           │
│  ⏱️ LLM: Xs (Y%) | Auditoría: Xs (Z%)      │
└─────────────────────────────────────────────┘
```

## Timing Data Flow

1. **Orchestrator calculates timing**
   - `orchestrator.execute_audit()` → logs `audit_duration_sec`
   - `orchestrator.generate()` → logs `timing_llm_sec` (implicit)

2. **Metrics passed to app.py**
   - `audit_result.metrics` contains `audit_duration_sec`
   - App calculates: `t_llm_elapsed = t_total - t_audit_elapsed`

3. **App displays in UI**
   - Shows as "⏱️ LLM: Xs (Y%) | Auditoría: Xs (Z%)"
   - Calculates percentages automatically
   - Displayed below dissonance components

## Testing Locally

To verify timing works without running the full Streamlit app:

```python
import time

# Simulate what the app does
t_total = 17.5  # seconds
t_audit = 2.45  # seconds
t_llm = t_total - t_audit  # 15.05 seconds

llm_pct = (t_llm / t_total * 100) if t_total > 0 else 0
audit_pct = (t_audit / t_total * 100) if t_total > 0 else 0

print(f"⏱️ LLM: {t_llm:.2f}s ({llm_pct:.0f}%) | Auditoría: {t_audit:.2f}s ({audit_pct:.0f}%) | Total: {t_total:.2f}s")
# Output: ⏱️ LLM: 15.05s (86%) | Auditoría: 2.45s (14%) | Total: 17.50s
```

## Files Modified

- **`Idicoc-demo-ui/app.py`**
  - 4 locations modified
  - ~40 lines added
  - No breaking changes
  - Fully backward compatible

- **`TIMING_GUIDE.md`**
  - Added documentation for Streamlit app timing display
  - Added "Option 4: View timing in Streamlit App UI" section

---

**Status:** ✅ Ready to use
**Validation:** app.py compiles without errors
**Display:** Real-time in Streamlit telemetry panel
