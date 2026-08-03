# What 3 Months of Running an AI Agent on a Raspberry Pi Taught Me About Task Design

I've been running an AI agent on a Raspberry Pi 5 since May. Not a chatbot, not a demo, an actual agent that manages email, writes code, deploys software, and submits articles. The model running locally is a 3B parameter quantized LLM. This post is about what I learned the hard way about designing tasks for small models.

The setup details are covered in another post. Here I want to talk about the part nobody writes about: what happens after you get the model running and try to make it do real work. The gap between "it responds to prompts" and "it completes multi-step tasks reliably" is where most projects die.

## The Core Problem

A 3B model is not GPT-4. I know, shocking. But the implications go deeper than "it's less smart." The failure modes are specific and predictable, and once you understand them, you can design around most of them.

Here's what actually goes wrong when a small model tries to do agent work:

**It loses the thread.** Around step 4 or 5 of a multi-step task, the model forgets what it was doing. Not in a vague way. It literally outputs a response that contradicts something it said two steps earlier, or repeats a step it already completed. Context window isn't the issue here, attention is. The 3B model has worse attention over long contexts than larger models, even when the context fits.

**It hallucinates tool calls.** The model invents parameters that don't exist, or calls a tool with the wrong argument type. It might try to pass a URL where a file path is expected, or invent a flag for a command that doesn't support it.

**It gets stuck in loops.** Something fails, the model tries to fix it, the fix fails slightly differently, it tries again with a variation that's basically the same. This can go on indefinitely if you don't have a circuit breaker.

**It overcomplicates simple things.** Ask it to create a file and it writes a 40-line script with error handling and logging instead of just writing the file. Small models seem to compensate for their limitations by being overly verbose, which ironically makes them worse.

## What Actually Works

After three months of trial and error, here's the task design philosophy that works for small-model agents:

### Break Everything Into Atomic Steps

This is the single most important thing. Don't say "deploy the app to the VPS." Say:

1. SSH to the server at this IP
2. Run `apt install nginx`
3. Create this config file with this exact content
4. Run `systemctl restart nginx`
5. Verify with `curl localhost`

Each step should produce a clear result that you can check. The model doesn't need to hold the whole deployment in its head, it just needs to execute one command, see the output, and move on.

I structure my agent's work as a checklist. Each item is one action with one expected outcome. If the outcome doesn't match, the agent stops and reports. This alone took my success rate from maybe 40% to 85%.

### Give It Real Tools, Not Just Prompts

The biggest mistake I see in agent projects is trying to do everything through prompt engineering. The model's job should be deciding *what* to do, not *how* to do it. Give it tools that handle the how.

My agent has a terminal tool, a file editor, a web browser, and an email client. When it needs to install something, it doesn't generate the apt command from scratch. It calls the terminal tool with `apt install nginx` and gets the real output back. The tool handles error codes, timeouts, retries. The model just reads the result and decides what to do next.

This matters more with small models because they're worse at generating correct syntax. If the tool handles the syntax, the model only needs to make the high-level decision correctly.

### Use Checksums, Not Vibes

When my agent says it completed a task, I don't trust the narrative. I check the artifact. Did the file actually change? Did the process actually start? Is the endpoint actually responding?

I built a verification step into every workflow. After the agent claims completion, a separate check runs that inspects the actual system state. If the agent says "nginx is running" but `systemctl is-active nginx` returns "inactive," the task is marked failed.

This sounds obvious but you'd be amazed how many agent projects skip it. The model says "Done!" and the system reports success without checking. Then you find out three hours later that nothing actually happened.

### Limit Context Aggressively

The 3B model gets confused when you feed it too much context. I trim tool outputs before they go back into the conversation. If a command produces 500 lines of output, I send the model the last 20 lines plus a summary. If a file has 2000 lines, I send only the relevant section.

This is the opposite of what you'd do with GPT-4, where more context is generally better. With small models, less context means better decisions. The signal-to-noise ratio in the context window matters more than completeness.

### Have a Circuit Breaker

If the agent tries the same action three times and fails, it stops. No retries, no "let me try a different approach." It stops and reports the failure to me. This prevents the loop problem and also prevents the agent from doing something destructive when it's confused.

I learned this the hard way. Early on, my agent got stuck trying to fix a nginx config error and cycled through increasingly creative (and increasingly wrong) configurations for 45 minutes before I noticed. Now the circuit breaker cuts it off at three attempts.

## The Honest Cost Numbers

I track every task the agent attempts. Here's what three months of data looks like:

- Tasks attempted: 342
- Tasks completed successfully: 289 (84%)
- Tasks that required human intervention: 38 (11%)
- Tasks that failed completely: 15 (4%)

The 84% success rate is after all the design improvements above. Before I started breaking tasks into atomic steps and adding verification, it was closer to 50%.

For context, the agent handles: email triage and responses (drafted, I review before sending), code writing and deployment, file management, web research, and article drafting. The code and deployment tasks have the highest success rate (90%+) because they're the most structured. Article drafting has the lowest (around 70%) because writing quality is harder to verify programmatically.

## What I Still Send to the Cloud

About 30% of my agent's work goes to a cloud model instead of the local Pi. Specifically:

- Complex code review (anything over 200 lines)
- Article writing (the 3B model's prose is too repetitive)
- Anything requiring reasoning across multiple large files
- Tasks where I need the model to be creative rather than procedural

The local model handles the procedural work. The cloud model handles the creative work. This split keeps costs down to maybe $8-10/month in cloud API fees instead of the $40-60 I was paying before. The Pi handles the other 70% for free.

## The Surprising Part

The thing that surprised me most is how much useful work a 3B model can do if you structure the tasks correctly. I expected it to be a toy. It's not. It's a competent executor with a narrow scope. It won't design your architecture or write your marketing copy, but it will reliably install software, configure servers, manage files, and execute checklists.

The engineering effort is in designing the tasks, not in the model. A well-structured 3-step task with clear verification will complete reliably on a 3B model. A vague "figure out how to deploy this" task will fail on a 3B model and waste your time on a 70B model too. The task design discipline you build for small models makes your large-model agents better too.

## Practical Recommendations

If you're building an agent on small models:

1. Write your task as a numbered checklist before you give it to the model. If you can't write it as a checklist, the task is too vague for a small model.

2. Every step should have exactly one action and one verifiable outcome. "Install nginx and configure it" is two steps, not one.

3. Truncate tool outputs. Send the model 20 lines, not 200. The model makes better decisions with less noise.

4. Build verification into the workflow. Don't trust the model's self-report. Check the system state.

5. Set a retry limit. Three attempts, then stop. Loops are the number one way small-model agents waste time.

6. Keep a log of what works and what doesn't. After a month you'll see patterns. Certain task types will have 95% success rates, others will be 50%. Double down on the ones that work, send the rest to a bigger model.

The Pi 5 running a 3B model is not going to replace your cloud API. But it can handle a surprising amount of the boring, procedural work that makes up most of an agent's day. The key is treating task design as the actual engineering work, not an afterthought.

That's the lesson. The model is fine. Your task structure is probably the problem.