#!/usr/bin/env python3
"""
Pi Arm AI Optimizer — Benchmark Suite
Tests model performance on ARM64 Raspberry Pi 5 via Ollama API
"""

import asyncio
import time
import json
import sys
import argparse
import subprocess
import statistics
from dataclasses import dataclass, asdict
from typing import Optional

try:
    import aiohttp
except ImportError:
    print("Installing aiohttp...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp"])
    import aiohttp


@dataclass
class BenchmarkResult:
    model: str
    prompt: str
    tokens_generated: int
    time_to_first_token: float
    total_time: float
    tokens_per_second: float
    ram_usage_mb: float
    cpu_temp: float
    success: bool
    error: Optional[str] = None


class PiBenchmark:
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.results: list[BenchmarkResult] = []

    async def check_ollama(self) -> bool:
        """Check if Ollama is running."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.ollama_url}/api/tags", timeout=5) as r:
                    return r.status == 200
        except Exception:
            return False

    def get_system_stats(self) -> dict:
        """Get current system stats (RAM, temp)."""
        # RAM usage
        try:
            with open("/proc/meminfo") as f:
                meminfo = {}
                for line in f:
                    key, val = line.split(":")
                    meminfo[key.strip()] = int(val.strip().split()[0])
            total = meminfo.get("MemTotal", 0)
            available = meminfo.get("MemAvailable", 0)
            used_mb = (total - available) / 1024
        except Exception:
            used_mb = 0

        # CPU temperature
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                temp = int(f.read().strip()) / 1000.0
        except Exception:
            temp = 0

        return {"ram_used_mb": used_mb, "cpu_temp": temp}

    async def benchmark_prompt(
        self, model: str, prompt: str, session: aiohttp.ClientSession
    ) -> BenchmarkResult:
        """Benchmark a single prompt against a model."""
        stats_before = self.get_system_stats()

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": 0.2, "num_predict": 200},
        }

        start_time = time.time()
        first_token_time = None
        tokens = 0
        full_response = ""
        error = None

        try:
            async with session.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as response:
                if response.status != 200:
                    error = f"HTTP {response.status}"
                    return BenchmarkResult(
                        model=model, prompt=prompt[:50], tokens_generated=0,
                        time_to_first_token=0, total_time=0, tokens_per_second=0,
                        ram_usage_mb=stats_before["ram_used_mb"],
                        cpu_temp=stats_before["cpu_temp"],
                        success=False, error=error,
                    )

                async for line in response.content:
                    chunk = json.loads(line)
                    if chunk.get("response"):
                        if first_token_time is None:
                            first_token_time = time.time()
                        full_response += chunk["response"]
                        tokens += 1
                    if chunk.get("done"):
                        break
        except Exception as e:
            error = str(e)
            return BenchmarkResult(
                model=model, prompt=prompt[:50], tokens_generated=tokens,
                time_to_first_token=(first_token_time - start_time) if first_token_time else 0,
                total_time=time.time() - start_time, tokens_per_second=0,
                ram_usage_mb=stats_before["ram_used_mb"],
                cpu_temp=stats_before["cpu_temp"],
                success=False, error=error,
            )

        total_time = time.time() - start_time
        ttft = (first_token_time - start_time) if first_token_time else 0
        tps = tokens / total_time if total_time > 0 else 0

        stats_after = self.get_system_stats()

        return BenchmarkResult(
            model=model, prompt=prompt[:50], tokens_generated=tokens,
            time_to_first_token=ttft, total_time=total_time,
            tokens_per_second=tps,
            ram_usage_mb=stats_after["ram_used_mb"],
            cpu_temp=stats_after["cpu_temp"],
            success=True,
        )

    async def run_benchmark(
        self, model: str, iterations: int = 10
    ) -> list[BenchmarkResult]:
        """Run a full benchmark suite for a model."""
        prompts = [
            "Write a Python function to check if a domain is available using RDAP",
            "Summarize the key points of: The quick brown fox jumps over the lazy dog.",
            "List 5 ways to optimize LLM inference on ARM processors.",
            "Write a bash script to monitor CPU temperature on a Raspberry Pi.",
            "Explain the difference between TCP and UDP in simple terms.",
            "Write a regex to validate email addresses and explain it.",
            "Create a JSON schema for a product catalog with nested categories.",
            "Debug this code: def add(a, b): return a - b",
            "Write a systemd service file for a Python web application.",
            "Explain how quantization affects LLM performance on edge devices.",
        ]

        results = []
        print(f"\nBenchmarking {model} ({iterations} iterations)")
        print("-" * 60)

        async with aiohttp.ClientSession() as session:
            for i in range(iterations):
                prompt = prompts[i % len(prompts)]
                result = await self.benchmark_prompt(model, prompt, session)
                results.append(result)

                status = "✓" if result.success else "✗"
                print(
                    f"  [{i+1}/{iterations}] {status} "
                    f"{result.tokens_per_second:.1f} tok/s | "
                    f"TTFT: {result.time_to_first_token:.2f}s | "
                    f"RAM: {result.ram_usage_mb:.0f}MB | "
                    f"Temp: {result.cpu_temp:.1f}°C"
                )

        # Summary
        successful = [r for r in results if r.success]
        if successful:
            print("\nSummary:")
            print(f"  Avg tokens/sec: {statistics.mean(r.tokens_per_second for r in successful):.1f}")
            print(f"  Avg TTFT: {statistics.mean(r.time_to_first_token for r in successful):.3f}s")
            print(f"  Avg RAM: {statistics.mean(r.ram_usage_mb for r in successful):.0f}MB")
            print(f"  Avg Temp: {statistics.mean(r.cpu_temp for r in successful):.1f}°C")
            print(f"  Success rate: {len(successful)}/{len(results)}")

        return results

    def save_results(self, filename: str):
        """Save results to JSON."""
        data = [asdict(r) for r in self.results]
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\nResults saved to {filename}")


async def main():
    parser = argparse.ArgumentParser(description="Benchmark LLM models on Raspberry Pi 5")
    parser.add_argument("--model", default="llama3.2:3b", help="Ollama model name")
    parser.add_argument("--iterations", type=int, default=10, help="Number of benchmark iterations")
    parser.add_argument("--url", default="http://localhost:11434", help="Ollama API URL")
    parser.add_argument("--output", default="results/benchmark_results.json", help="Output file")
    args = parser.parse_args()

    bench = PiBenchmark(args.url)

    if not await bench.check_ollama():
        print("Error: Ollama is not running at", args.url)
        print("Start it with: ollama serve")
        sys.exit(1)

    print(f"Ollama is running at {args.url}")
    print(f"System: Raspberry Pi 5, ARM64")

    results = await bench.run_benchmark(args.model, args.iterations)
    bench.results = results

    import os
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    bench.save_results(args.output)


if __name__ == "__main__":
    asyncio.run(main())
