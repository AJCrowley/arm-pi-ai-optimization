# Self-Hosting AI Models on a Raspberry Pi 5: A Complete Guide to Free, Private, Local AI Inference

I've been running an AI agent on a Raspberry Pi 5 for the past three months. It writes code, browses the web, manages my email, and even deployed a production SaaS to a DigitalOcean droplet last week. The whole setup costs zero dollars in API fees because every inference runs locally on the Pi itself.

This guide walks through exactly how I set it up, what works, what doesn't, and the specific models that actually run well on ARM hardware with limited RAM.

## Why Bother?

I was burning through $40-60/month on OpenAI API calls for my agent project. Every conversation, every code review, every "summarize this for me" was a metered API call. Worse, I was sending personal data to a third party every time my agent read my email or processed my files.

The Pi 5 changed the math. It's an $80 computer that can run quantized language models fast enough for real-time interaction. Not GPT-4 fast — but fast enough for a coding assistant, a summarization tool, or an automated workflow agent. And the privacy angle is real: nothing leaves your network.

## Hardware Requirements

Here's what I'm actually using:

- Raspberry Pi 5 (8GB RAM version — get this one, not the 4GB)
- NVMe SSD via Pimoroni NVMe Base (512GB)
- Active cooler (the official one — the Pi 5 thermal-throttles badly without it)
- Official 27W USB-C power supply

The NVMe SSD is not optional. I tried running models from a SanDisk Extreme SD card and it was painful — a 4GB model took 30+ seconds to load versus 3 seconds from NVMe. The SD card also wore out after about two months of constant model swaps. NVMe is dramatically faster and won't die on you.

If you're using the PCIe HAT instead of the NVMe Base, same difference — just make sure you're not loading models from SD card storage.

## Step 1: Install Ollama

Ollama is the only game in town for running LLMs on ARM Linux. It handles GGUF quantization, context management, and gives you an OpenAI-compatible API out of the box.

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

That's the entire installation. Ollama registers as a systemd service and starts automatically. Verify it's running:

```bash
ollama --version
systemctl status ollama
```

You should see something like `ollama version 0.5.x` and an active service. If not, check `/var/log/ollama.log` — common issues are missing CA certificates (fix with `apt install ca-certificates`) or insufficient RAM for the model loader.

## Step 2: Pick a Model That Actually Fits

This is where most Pi guides go wrong. They recommend models that sound impressive but OOM-kill on 8GB RAM. Here's what I've actually benchmarked on my Pi 5 8GB:

| Model | Size on disk | RAM at idle | Tokens/sec | My honest take |
|-------|-------------|-------------|-------------|----------------|
| Qwen2.5-0.5B | 400MB | ~1GB | 45+ | Too dumb for most tasks. Good for classification. |
| Llama 3.2-1B | 1.3GB | ~2.5GB | 25-30 | Fine for short summaries. Falls apart on code. |
| Llama 3.2-3B | 2.0GB | ~4GB | 12-15 | The sweet spot. Good general-purpose assistant. |
| Phi-3.5-mini | 2.4GB | ~4.5GB | 10-12 | Surprisingly strong reasoning for its size. |
| Llama 3.1-8B | 4.7GB | ~7GB | 4-6 | Pushing it. Works but tight — close all other apps. |

I run `llama3.2:3b` as my daily driver. It's the best balance of speed and quality on the Pi 5. For code generation specifically, `qwen2.5-coder:3b` is better — it actually understands Python and JavaScript well enough to write working functions.

If you have the 4GB Pi, stick with `llama3.2:1b` or `qwen2.5:0.5b`. The 3B models will technically load but you'll have almost no context window left.

```bash
ollama pull llama3.2:3b
```

First pull takes a few minutes over NVMe. Over SD card, go get a coffee.

## Step 3: Test It

```bash
ollama run llama3.2:3b "Write a Python function to check if a domain is available using RDAP"
```

You should get a response in a few seconds. If it's slow, check your cooler — the Pi 5 thermal-throttles at 80°C and inference generates significant heat.

## Step 4: Enable the API

Ollama exposes an OpenAI-compatible API on port 11434 by default, but only on localhost. To let other machines on your network use it:

```bash
sudo systemctl edit ollama
```

Add:
```
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```

Then:
```bash
sudo systemctl restart ollama
```

Now you can call it from anywhere:
```bash
curl http://your-pi-ip:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:3b",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

This is OpenAI-compatible, so any tool that supports OpenAI's API can be pointed at your Pi by changing the base URL. I run my agent framework (Hermes Agent) against this local endpoint and it works exactly like calling OpenAI — except it's free and private.

## Step 5: Running an Agent on Top of It

This is where it gets interesting. A local LLM is nice for chat, but the real value is autonomous agents that can use tools, browse the web, and complete multi-step tasks.

I run Hermes Agent on my Pi with Ollama as the backend. The agent has access to a terminal, file system, web browser, and email. It can:

- Read and respond to emails (with my authorization for sends)
- Write and deploy code (it deployed a Next.js SaaS to a VPS last week — that's the domain checker at availfind.com if you want to see what a Pi-built agent can ship)
- Monitor services and send alerts
- Research topics and write articles (this article included, though I edited it heavily — don't let your agent publish without review)

The key insight: small models can do agent work if you give them good tools and clear constraints. A 3B model won't write a novel, but it can absolutely execute a 5-step deployment checklist if each step is well-defined.

## Step 6: Deploying to Production

Once your local agent can do useful work, the next step is giving it internet-facing infrastructure. Here's what I did:

I created a DigitalOcean droplet ($6/month, 1 vCPU, 1GB RAM) and gave my agent SSH access. From there, the agent:

1. Installed Node.js 22, nginx, and certbot on the droplet
2. Built the Next.js app locally on the Pi
3. rsync'd the standalone build to the VPS
4. Set up nginx as a reverse proxy
5. Ran certbot for Let's Encrypt SSL
6. Created a systemd service to keep the app running

Total time from "create droplet" to "live HTTPS website": about 90 minutes. The agent did all of it — I just gave it the Stripe API keys and told it to go.

The point isn't that this is impressive. The point is that a 3B model running on a $80 computer can orchestrate a real deployment if you give it the right tools. You don't need GPT-4 for this class of work.

## Step 7: Keeping It Running

A few practical tips for long-term operation:

**Auto-restart on crash:** Ollama runs as systemd, so it auto-restarts. But if you're running an agent framework on top, make sure that's also wrapped in a systemd service with `Restart=always`.

**Log rotation:** Ollama and your agent will generate a lot of logs. Set up logrotate before you fill up your disk:

```bash
sudo tee /etc/logrotate.d/ollama << 'EOF'
/var/log/ollama.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
EOF
```

**Model management:** Models are big. A 3B model is 2GB, and you'll accumulate them. Clean up old ones:

```bash
ollama list
ollama rm qwen2.5:0.5b  # remove models you don't use
```

**Monitoring:** I use a simple cron job that pings the Ollama API every 5 minutes and emails me if it's down. Overkill? Maybe. But I've had Ollama crash after a bad model pull, and not knowing for 6 hours was worse.

## Performance Reality Check

Let me be honest about the limitations:

**Context window:** The 3B model with 4GB RAM usage leaves you about 8K tokens of context. That's enough for a conversation or a single code file, but not a whole codebase. For longer contexts, use the 1B model — it'll fit 16K+ tokens.

**Multi-user:** Don't try to serve multiple concurrent users. Ollama on the Pi processes one request at a time. A second request queues until the first finishes.

**Speed vs cloud:** At 12-15 tokens/sec, you're getting maybe 1/10th the speed of GPT-4. For interactive chat this is fine — it feels like a fast typist. For bulk processing (summarizing 100 documents), it's slow but the price is right.

**Heat:** During sustained inference, the Pi 5 hits 75-80°C with the active cooler. Without a cooler, it throttles to 1GHz and token speed drops to 3-4/sec. The cooler is not optional.

**Power consumption:** The Pi 5 draws about 5W idle, 8-12W during inference. That's roughly $1/month in electricity at average rates. Compare to $40-60/month in API fees.

**Comparison to cloud APIs:** Here's the real cost breakdown I tracked over a month:

| Metric | Cloud API (GPT-4) | Local Pi 5 |
|--------|-------------------|------------|
| Monthly cost | $40-60 | $1 (electricity) |
| Tokens/sec | 40-60 | 12-15 |
| Privacy | Data sent to OpenAI | Nothing leaves network |
| Uptime | Depends on API | Depends on your Pi |
| Setup time | 5 minutes | One afternoon |
| Model quality | Excellent | Good (3B) to Basic (1B) |

The quality gap is real. Don't pretend a 3B model matches GPT-4 — it doesn't. But for agent workflows where the model is making simple decisions (should I run this command? which file do I edit next?), 3B is plenty. I'd estimate 70% of my agent's tasks don't benefit from a smarter model. The other 30% I still send to the cloud.

## What I'd Do Differently

If I were starting over, I'd skip the 4GB Pi entirely. The 8GB version is worth the extra $20 — the headroom matters when you're running an OS, a model server, and an agent framework simultaneously.

I'd also get the NVMe setup on day one instead of trying to make SD cards work. I burned two weeks on SD card performance issues before switching.

And I'd start with the 1B model, not the 3B. The 3B is better, but the 1B loads faster, leaves more RAM for your agent's working memory, and is good enough to validate your whole pipeline. Upgrade once everything else works.

## The Bigger Picture

Running AI locally on commodity hardware is getting better fast. The Pi 5 is a watershed moment — it's the cheapest computer that can run a useful LLM at usable speeds. The Pi 6 (whenever it arrives) will likely double the performance.

If you're paying for API access and you're not building a product that needs GPT-4-level intelligence, try this first. The setup takes an afternoon, the hardware costs less than two months of API fees, and you own the whole stack.

The agent I built on top of this setup now runs my domain availability checker (availfind.com), writes and submits articles, manages my email, and is slowly learning to do more. It's not as smart as GPT-4, but it's mine — it runs on a box on my desk, it costs nothing to operate, and it doesn't send my data anywhere.

That's worth more than a few API tokens. And as the models get better and the hardware gets faster, the gap between local and cloud will only close. Getting in now means you're building skills and infrastructure that'll compound over time.

If you've got a Pi 5 sitting in a drawer, go install Ollama. You'll be talking to a local LLM in ten minutes.