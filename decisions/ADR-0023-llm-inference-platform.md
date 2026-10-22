# ADR-0023 — LLM inference platform

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

Serving engine selection drives VRAM sizing, throughput targets, and the artifact footprint.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. vLLM only.
- 2. Triton only.
- 3. Multiple engines.

## Decision

vLLM as the primary production engine, llama.cpp for small or aggressively quantized models and CPU fallback, Triton only if non-LLM model types enter the estate, and NIM evaluated against licence and offline artifact size before any use.

## Rationale and trade-offs

- vLLM has the best throughput and continuous batching for LLMs.
- llama.cpp runs tiny models on small hardware with GGUF.
- Triton is multi-framework but heavier to run.
- NIM removes tuning effort but adds licence terms.
- vLLM covers the primary use case with the best throughput. The others are justified by specific constraints, not by preference.

## Security and operational implications

Each engine brings its own model formats, quantization, memory behaviour, and metrics. Supporting several means supporting several artifact sets offline. A model converted for one engine is not directly usable in another.

## Dependencies

Inference API port (for example 8000 for an OpenAI-compatible endpoint), DCGM exporter 9400, model store access 443, and the metrics port per engine.

## Failure scenarios

Engine failure affects inference availability only. Autoscaling on queue depth and GPU utilisation is required, and pre-loading models on the node-local NVMe cache avoids cold-start latency.

## Migration considerations

Engine migration requires model conversion and re-benchmarking. Model conversion is a lossy operation for some quantization schemes.
