# Pi Arm AI Optimizer: Running Production AI Agents on ARM64 with Ollama

> Submitted to the **Arm Create: AI Optimization Challenge** — Physical AI track

## Overview

This project demonstrates real-world AI optimization on ARM-powered platforms by running a **production AI agent** entirely on a **Raspberry Pi 5 (ARM64, 8GB RAM)**. The agent manages email, writes and deploys code, monitors services, and submits content — all using locally-quantized LLMs via Ollama.

The optimization work focuses on making small (3B and below) language models viable for agentic workloads on ARM64 hardware with severe memory constraints.

## What Makes This Interesting

Most AI optimization work targets cloud-scale ARM servers. This project targets the **most constrained ARM platform** that can still run useful AI: a $80 Raspberry Pi. If you can make a 3B model do production agent work on a Pi 5, those same optimizations apply to every ARM device in the ecosystem.

## Key Optimizations

### 1. Model Selection & Quantization
- Benchmarked 5 models (0.5B to 8B) on Pi 5 ARM64
- Identified optimal model: `llama3.2:3b` (Q4_K_M quantization)
- Measured tokens/sec, RAM usage, and task success rates

### 2. Context Window Management
- Aggressive output truncation (20-line max per tool output)
- Rolling context window (last 10 messages only)
- Separate summarization pass for long outputs

### 3. Task Decomposition for Small Models
- Atomic step design (one action, one verifiable outcome per step)
- Circuit breaker pattern (3 retry limit)
- Verification layer (checksums, not vibes)

### 4. Memory-Efficient Inference
- Model swapping strategy for multi-model workflows
- systemd service configuration for stable inference
- Thermal management (active cooler requirement, throttle prevention)

## Benchmarks

| Model | Size | RAM (idle) | Tokens/sec | Task Success Rate |
|-------|------|-----------|------------|-------------------|
| Qwen2.5-0.5B | 400MB | ~1GB | 45+ | 60% |
| Llama 3.2-1B | 1.3GB | ~2.5GB | 25-30 | 75% |
| Llama 3.2-3B | 2.0GB | ~4GB | 12-15 | 84% |
| Phi-3.5-mini | 2.4GB | ~4.5GB | 10-12 | 82% |
| Llama 3.1-8B | 4.7GB | ~7GB | 4-6 | 85% |

## Setup Instructions

### Prerequisites
- Raspberry Pi 5 (8GB RAM version recommended)
- NVMe SSD (via Pimoroni NVMe Base or PCIe HAT)
- Active cooler (official Pi 5 cooler)
- Ubuntu 24.04 or Raspberry Pi OS 64-bit

### Installation

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull the optimized model
ollama pull llama3.2:3b

# Configure for network access (optional)
sudo systemctl edit ollama
# Add: Environment="OLLAMA_HOST=0.0.0.0:11434"
sudo systemctl restart ollama

# Test
ollama run llama3.2:3b "Write a Python function to check if a domain is available"
```

### Running the Benchmark Suite

```bash
python3 benchmark.py --model llama3.2:3b --iterations 100
```

## Files

- `benchmark.py` — Automated benchmarking suite for model comparison
- `agent_config.yaml` — Agent configuration for small-model optimization
- `task_templates/` — Pre-structured task templates for small-model agents
- `results/` — Raw benchmark data and analysis
- `docs/` — Detailed optimization documentation

## Cost Comparison

| Metric | Cloud API (GPT-4) | Local Pi 5 |
|--------|-------------------|------------|
| Monthly cost | $40-60 | $1 (electricity) |
| Tokens/sec | 40-60 | 12-15 |
| Privacy | Data sent to cloud | Nothing leaves network |
| Setup time | 5 minutes | One afternoon |

## License

MIT