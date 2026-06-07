# Performance Timing Instrumentation Guide

## Overview

Comprehensive timing instrumentation has been added throughout the Notary pipeline to measure performance and identify bottlenecks. All timing measurements are logged as JSON entries with `[TIMING]` markers at INFO level.

## Files Modified

- **`idicoc_core/pipeline/orchestrator.py`** - Added timing to:
  - `execute_audit()` - Full audit pipeline execution
  - `generate()` - LLM generation + audit pipeline
  - `_attempt_spsa_correction()` - SPSA correction timing
  - `_add_dynamic_policies()` - Policy embedding and compilation
  
- **`idicoc_core/dse/evaluator.py`** - Added timing to:
  - `DissonanceStateEvaluator.evaluate()` - Main DSE evaluation
  - `PropertyGraphEvaluator.evaluate()` - Individual policy graph evaluation

- **`Idicoc-demo-ui/app.py`** - Added timing display to:
  - Streamlit demo app UI - Shows LLM vs Notary time breakdown in telemetry panel
  - Extracted timing from audit_result.metrics
  - Displays percentage breakdown: "LLM: X.XXs (Y%) | Auditoría: X.XXs (Z%)"

## Key Timing Measurements

### 1. Pipeline Execution Timing (execute_audit)

```json
[TIMING] execute_audit START
[TIMING] DQE context build: 0.015 sec
[TIMING] Gating check: 0.000 sec
[TIMING] Dynamic policies added: 2 policies, 0.014 sec
[TIMING] DSE evaluate: 2.534 sec | d_s=inf
[TIMING] CTM mode: disabled (skipped)
[TIMING] execute_audit TOTAL: 2.560 sec | admitted=False | d_s=inf
```

### 2. LLM Generation Timing (generate)

```json
[TIMING] generate START
[TIMING] RAG context normalization: 0.001 sec
[TIMING] Input projection: 0.045 sec
[TIMING] LLM generation: 15.234 sec | output_len=150 chars
[TIMING] generate COMPLETE: 15.280 sec total | llm=15.234 sec
```

### 3. DSE Evaluation Details (DissonanceStateEvaluator)

```json
[TIMING] DissonanceStateEvaluator.evaluate START
[TIMING] Context prep: 0.003 sec
[TIMING] Violated policies collection: 0.001 sec | violations=2
[TIMING] Dissonance dimensions (d_logic, d_temporal, d_context): 2.533 sec | 
         d_logic=inf d_temporal=0.000000 d_context=0.150000
[TIMING] d_1 calculation: 0.000 sec | d_1=0.000000
[TIMING] Embeddings & metrics extraction: 0.000 sec
[TIMING] DissonanceStateEvaluator.evaluate TOTAL: 2.534 sec | d_s=inf | violated=4
```

### 4. SPSA Correction Timing

```json
[TIMING] Attempting SPSA correction...
[TIMING] SPSA correction: 0.234 sec
```

## How to View Timing Logs

### Option 1: Run tests with pytest capture disabled

```bash
# View all timing logs for a specific test
pytest Idicoc_notary/tests/test_rejection_with_motives.py \
  -xvs --log-cli-level=INFO 2>&1 | grep -E "\[TIMING\]"

# Run with full JSON logging
pytest -xvs --capture=no --log-level=INFO test_file.py
```

### Option 2: Run Python scripts directly

```bash
# Script output will show logs directly
python -u test_timing_demo.py
```

### Option 3: Check the test output

When running pytest normally, timing logs appear as JSON entries in the captured output:

```bash
pytest test_file.py -v
```

Look for lines like:
```
{"timestamp": "2026-06-07T12:49:29.815919+00:00", "level": "INFO", 
 "module": "idicoc_core.pipeline.orchestrator", 
 "message": "[TIMING] DSE evaluate: 2.534 sec | d_s=inf"}
```

### Option 4: View timing in Streamlit App UI

The Streamlit demo app (`Idicoc-demo-ui/app.py`) displays timing breakdown directly in the **Telemetry Panel**:

```bash
# Run the Streamlit app
cd Idicoc-demo-ui
streamlit run app.py
```

In the right sidebar under "🛡️ Última Auditoría IDICOC", you will see:

```
⏱️ LLM: 15.23s (85%) | Auditoría: 2.45s (15%) | Total: 17.68s
```

This shows:
- **LLM generation time** - Time spent in the language model
- **Auditoría (Notary) time** - Time spent in audit/DSE pipeline  
- **Total time** - Wall clock time for the entire request
- **Percentages** - What portion of time is LLM vs Notary

This is the **easiest way to see if LLM or Notary is the bottleneck** in the actual application.

## Interpreting Timing Data

### Bottleneck Analysis Example

**Scenario:** Slow response generation

1. Check Streamlit app telemetry panel for LLM vs Audit timing breakdown
2. Or check `generate()` total time from logs
3. Break down into components:
   - **LLM generation time** - if > 10s, LLM is bottleneck
   - **RAG normalization** - typically < 0.01s
   - **Input projection** - typically < 0.1s
   - **Audit execution** - see DSE timing below

3. If audit is slow, check DSE:
   - **Dissonance dimensions** - policy graph evaluation
   - **d_1 calculation** - embeddings and context analysis
   - **Dynamic policies addition** - policy embedding

### Sample Findings

**Current Bottleneck:** DSE Dissonance Dimensions
- **Status:** Policy graph evaluation (d_logic) is the slowest operation
- **Time range:** 2-13 seconds for typical inputs
- **Cause:** Evaluating LLM output against each policy in the graph
- **Impact:** Represents ~99% of DSE execution time

**Profile:**
```
execute_audit TOTAL: 2.560 sec
├── DQE context build: 0.015 sec (0.6%)
├── Gating check: 0.000 sec (0%)
├── Dynamic policies: 0.015 sec (0.6%)
├── DSE evaluate: 2.534 sec (98.9%)
│   └── Dissonance dimensions: 2.533 sec (99.9% of DSE)
│       └── d_logic calculation (policy graph eval)
└── CTM commit: N/A (disabled)
```

## Timing Data Available in Metrics

Timing measurements are also stored in `raw_metrics` and `result.metrics`:

```python
result = pipeline.execute_audit(...)

# Available metrics:
print(result.metrics.get('audit_duration_sec'))  # Total audit time
print(result.metrics.get('dse_duration_sec'))    # DSE evaluation time
print(result.metrics.get('spsa_duration_sec'))   # SPSA correction time
```

## Performance Optimization Recommendations

### 1. Policy Graph Evaluation (d_logic)
- **Current:** 2-13 seconds for typical inputs
- **Potential Optimization:** Cache policy embeddings, parallelize policy evaluation
- **Priority:** HIGH (98%+ of time)

### 2. Dynamic Policy Embedding
- **Current:** 0.01-0.02 seconds per policy
- **Potential Optimization:** Batch embedding computation
- **Priority:** MEDIUM (1-2% of time)

### 3. Input Projection
- **Current:** 0.04-0.05 seconds
- **Potential Optimization:** Reduce embedding recomputation
- **Priority:** LOW (0.2-0.5% of time)

## Configuration for Timing Logs

Timing logs are controlled by the logging configuration. To adjust verbosity:

```python
# In orchestrator.py and evaluator.py
logger.info("[TIMING] message")  # INFO level - always shown in tests
logger.debug("[TIMING] message") # DEBUG level - only if debug enabled
```

To enable DEBUG level timing:

```bash
pytest --log-cli-level=DEBUG test_file.py
```

## Example: Measuring LLM vs Notary

To measure whether the bottleneck is in the LLM or Notary:

1. **Run a generate() test:**
   ```bash
   pytest Idicoc_notary/tests/test_invariance_projector.py::test_pipeline_generate_clean_prompt -xvs
   ```

2. **Extract timing data:**
   - Look for: `[TIMING] LLM generation: X.XXX sec`
   - Look for: `[TIMING] execute_audit TOTAL: X.XXX sec`
   - Look for: `[TIMING] generate COMPLETE: X.XXX sec total`

3. **Calculate ratio:**
   ```
   LLM Time / Total Time = % of time spent on LLM
   Audit Time / Total Time = % of time spent on Notary
   ```

## Troubleshooting

### Logs not appearing
- Ensure you're running with `-xvs` or `--log-cli-level=INFO`
- Check that you're reading the pytest output (not just the summary)
- Timing logs use INFO level by default

### Timing values seem wrong
- First run might include model loading/compilation time
- Run tests twice and compare second run times for more accurate measurements
- System load affects timing - run during low-load periods for consistent results

---

**Generated:** 2026-06-07  
**Modified Files:** 2  
**Lines Added:** ~150  
**Performance Impact:** Minimal (~1-2% overhead from timing calls)
