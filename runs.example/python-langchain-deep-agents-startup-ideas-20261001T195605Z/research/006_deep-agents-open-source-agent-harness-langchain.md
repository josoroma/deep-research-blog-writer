---
source_id: S-06
url: https://www.langchain.com/deep-agents
title: 'Deep Agents: Open Source Agent Harness | LangChain'
author: null
published: null
fetched: '2026-10-01T19:57:49Z'
word_count: 308
---
# Deep Agents: Open Source Agent Harness | LangChain

# Build agents for complex, multi-step tasks

Deep Agents is an open source agent harness built for long-running tasks. It handles planning, context management, and multi-agent orchestration for complex work like research and coding.

## Why use Deep Agents?

### Designed for autonomous agents

Agents are taking on increasingly complex work over long time horizons, like research, coding, and multi-step workflows. Deep Agents provides the primitives for these patterns:

- **Break down complex objectives:***Planning tools let agents decompose tasks, track progress, and adapt as they learn*
- **Delegate work in parallel:***Spawn subagents for independent subtasks, each with isolated context*
- **Persist knowledge across sessions:***Virtual filesystem stores system prompts, skills, and long-term memory*

[Learn about the agent harness](https://docs.langchain.com/oss/python/deepagents/harness)

### Native context management

Context management is critical for long-running agents, and hard to get right. Deep Agents includes middleware that helps agents compress conversation history, offload large tool results, isolate context with subagents, and use prompt caching to reduce latency and cost.

[Context management with deep agents](https://blog.langchain.com/context-management-for-deepagents/)

### Model neutral with maximum configurability

Deep Agents is a batteries-included, general purpose agent harness. Use any model provider, manage state, and add human-in-the-loop when you need it. Tracing and deployment work natively with LangSmith.

[Deploy deep agents with LangSmith](https://www.langchain.com/langsmith-platform)

### Build with dcode

**dcode is an open-source terminal coding agent built on the Deep Agents SDK. With dcode you can bring your own model, customize the agent harness, and control how code execution is approved, traced, and run.**

[Learn more about dcode](https://www.langchain.com/dcode)

#### Deep Agents

Learn how to build long-running agents for complex workflows with Deep Agents. You’ll explore what an agent harness is, how it accelerates development, and how to use LangSmith to improve your agents.

[Take the course](https://academy.langchain.com/courses/foundation-introduction-to-deepagents)

### FAQs for Deep Agents

### See what your agent is really doing

LangSmith, our agent engineering platform, helps developers debug every agent decision, eval changes, and deploy in one click.
