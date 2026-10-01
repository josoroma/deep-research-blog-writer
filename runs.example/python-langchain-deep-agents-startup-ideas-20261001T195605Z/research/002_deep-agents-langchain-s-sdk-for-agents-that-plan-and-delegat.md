---
source_id: S-02
url: https://talkpython.fm/episodes/show/543/deep-agents-langchains-sdk-for-agents-that-plan-and-delegate
title: 'Deep Agents: LangChain''s SDK for Agents That Plan and Delegate'
author: Michael Kennedy
published: null
fetched: '2026-10-01T19:57:48Z'
word_count: 15302
---
# Deep Agents: LangChain's SDK for Agents That Plan and Delegate

Sydney Runkle is back on Talk Python representing LangChain and their new open source library, Deep Agents: A framework for building your own deep agents with plain Python functions, middleware hooks, and MCP support. This is how the magic works under the hood.

### Guest Introduction

**Sydney Runkle** is a software engineer at LangChain, the company behind the popular open source Python framework for building LLM-powered applications. Before joining LangChain, Sydney worked at Pydantic, contributing to one of Python's most widely used data validation libraries. She has appeared on Talk Python To Me multiple times, previously discussing topics like LangGraph and Pydantic, as well as her early career journey in the episode "A Young Coder's Blueprint for Success." Sydney brings a unique perspective bridging open source data validation and the cutting edge of AI agent development.

- [github.com/langchain-ai/deepagents](https://github.com/langchain-ai/deepagents) -- Deep Agents GitHub repo
- [langchain.com](https://langchain.com) -- LangChain company
- [docs.pydantic.dev](https://docs.pydantic.dev/) -- Pydantic documentation

### What to Know If You're New to Python

If you are newer to the Python ecosystem, here are a few things that will help you get the most out of this episode:

- **Doc strings and type hints** are core Python features used throughout this episode. Doc strings document what a function does, and type hints specify the expected data types for function arguments. Deep Agents uses both to automatically tell the LLM how to call your custom tools.
- **Pydantic** is a data validation library that converts Python type hints into JSON schemas. It plays a key role in how Deep Agents communicates tool definitions to language models.
- **Middleware** is a common software pattern where you hook into lifecycle events (before/after a step) to run custom logic. If you have used web frameworks like Flask, Django, or FastAPI, the concept is very similar here.
- Understanding the difference between an **API** (a programmatic interface you call) and an**LLM** (a language model that generates text) will help you follow the discussion of how agents combine the two.

### Key Points and Takeaways

#### 1. The Agent Harness Is Where the Magic Lives

The central idea of this episode is that the power of tools like Claude Code, Codex, and Deep Agents does not come from the raw language model alone. It comes from the "agent harness," the scaffolding of system prompts, planning tools, file system access, sub-agents, and middleware that surrounds the model. Sydney describes a harness as "add-ons around that core model and tool calling loop that help to make an agent more effective with more complex tasks." Michael drives this home by noting that the Claude Code system prompt alone is 16,000 words -- a third of a novel -- and that swapping or tweaking just the prompt can dramatically change an agent's behavior. The harness is the invisible layer that separates a shallow chatbot exchange from the iterative, self-correcting workflows that make deep agents genuinely useful.

- [blog.langchain.com/the-anatomy-of-an-agent-harness](https://blog.langchain.com/the-anatomy-of-an-agent-harness/) -- LangChain blog post on agent harness anatomy
- [blog.langchain.com/improving-deep-agents-with-harness-engineering](https://blog.langchain.com/improving-deep-agents-with-harness-engineering/) -- Blog post on systematically improving harnesses with traces

#### 2. Deep Agents vs. Shallow Agents

Sydney draws a clear line between "shallow" and "deep" agents. A shallow agent is the kind of agent from a year or two ago: you give it a prompt and a handful of tools, it makes a couple of tool calls, and returns a result, like booking a flight. A deep agent, by contrast, has access to far more context, can organize complex multi-step tasks, run for extended periods, and recover from mistakes along the way. The trend in the industry is pushing toward agents that can tackle increasingly complex problems over longer time horizons. This distinction matters because many people's frustrations with "AI" stem from experiences with shallow interactions, not the full capabilities of a deep agent system.

#### 3. The Four Pillars of a Deep Agent Harness

LangChain's Deep Agents framework is built around four core components that make an agent effective for complex, long-running tasks:

- **Planning tool** : Gives the agent a to-do list to stay organized, break down problems, and track progress through multi-step tasks. Even just adding a planning tool can improve an agent's trajectory on harder problems.
- **File system access** : Lets the agent selectively read, write, and search files rather than cramming everything into the context window at once. This mirrors how a person would reference a textbook chapter rather than memorizing the whole book.
- **Sub-agents** : Enable parallelization and context isolation. Multiple sub-agents can pursue different research paths simultaneously, and each sub-agent only receives the context it needs for its specific subtask.
- **System prompt with memory** : A carefully crafted system prompt instructs the agent on how to use its tools, and memory loaded into the prompt can persist across conversations to personalize the experience.

#### 4. Deep Agents: The Open Source Library

LangChain's `deepagents` package lets you build your own deep agents in just a few lines of Python. You call `create_deep_agent`, specify your model, pass in custom tools, and get back a compiled LangGraph graph ready to invoke or deploy. Under the hood, it automatically adds the planning tool, file system access, summarization middleware, and sub-agent capabilities. The library is MIT-licensed, actively maintained with over 15,000 GitHub stars, and designed so you can start simple and customize as needed.

- [github.com/langchain-ai/deepagents](https://github.com/langchain-ai/deepagents) -- Deep Agents GitHub repository (MIT license, ~15k stars)
- Install: `pip install deepagents` or`uv add deepagents`

#### 5. Tools Are Just Python Functions

One of the most Pythonic aspects of Deep Agents is how custom tools are defined. You write a regular Python function with type hints and a doc string, and the framework automatically parses the function signature, argument types, and documentation to generate the JSON schema that gets passed to the LLM. The model then knows what arguments to provide and when to call the tool. This approach uses Pydantic under the hood for schema generation, creating a natural bridge between writing clean Python code and communicating with language models. Sydney called it "a wonderful marriage between developer docs and LLMs."

- [docs.pydantic.dev](https://docs.pydantic.dev/) -- Pydantic data validation library

#### 6. Any Model, No Vendor Lock-In

Deep Agents is model-agnostic. You can use OpenAI, Anthropic, Google, or even a local open-weights model running on your own hardware through an OpenAI-compatible API endpoint. Michael mentioned running the 20-billion-parameter OpenAI open-weights model locally on his Mac Mini Pro and confirmed he could plug that into Deep Agents. Additionally, sub-agents can use different models than the main agent, so you might plan with a more powerful (and expensive) model and delegate execution to a cheaper, faster one. This flexibility is built on LangChain's standardized model interface.

- [docs.langchain.com/oss/python/langchain/overview](https://docs.langchain.com/oss/python/langchain/overview) -- LangChain Python documentation

#### 7. MCP Support Expands the Tool Ecosystem

Deep Agents supports the Model Context Protocol (MCP), meaning your agent can consume tools provided by external MCP servers. This opens up a world of pre-built integrations created by the community or other teams. Michael highlighted his own Talk Python MCP server as an example: you plug it into Claude or another MCP-compatible client, and the AI can query the latest episodes in real time rather than relying on stale training data. Sydney emphasized that MCP helps with cross-team collaboration and gives agents access to timely, accurate, and even private data sources.

- [modelcontextprotocol.io](https://modelcontextprotocol.io/) -- Official MCP specification and documentation

#### 8. Middleware: Hooking Into the Agent Lifecycle

Middleware in Deep Agents lets you inject custom logic at specific points in the agent's model-and-tool-calling loop. Before the model runs, you might check if context needs summarization. After the model decides to call a tool but before it executes, you might require human approval for sensitive operations like sending an email or executing a stock trade. LangChain ships several pre-built middlewares including human-in-the-loop approval, auto-summarization, personal information detection, and tool retry logic. You can also build your own middleware for domain-specific needs.

#### 9. Context Summarization Keeps Long Conversations Alive

For long-running tasks, context window limits become a real constraint. Deep Agents handles this with automatic summarization middleware that compresses earlier parts of the conversation as the context fills up. Claude Code users see this as the "compacting" step. Deep Agents guarantees you will never hit a context overflow error because it proactively summarizes as the conversation progresses. Combined with prompt caching (which reduces cost by caching repeated system prompts across invocations), this makes sustained, multi-step agent sessions practical and affordable.

#### 10. Built on LangChain and LangGraph

Deep Agents is not a standalone framework but is layered on top of two other LangChain open source projects. LangChain serves as the "agent framework" providing standardized model integrations and building blocks. LangGraph serves as the "agent runtime" powering the execution graph, streaming, durability, human-in-the-loop support, and deployment capabilities. The `create_deep_agent` function returns a compiled LangGraph graph. Understanding this layering helps developers know where to look for specific features and how to extend the system.

- [docs.langchain.com/oss/python/langgraph/overview](https://docs.langchain.com/oss/python/langgraph/overview) -- LangGraph documentation

#### 11. Security Through Tool Boundaries, Not Model Self-Policing

Deep Agents follows a "trust the LLM" security model: the agent can do anything its tools allow, and security boundaries are enforced at the tool and sandbox level rather than expecting the model to self-police. This is a pragmatic design choice because LLM jailbreaks have shown that relying on the model to refuse dangerous actions is unreliable. LangGraph provides first-class human-in-the-loop support so developers can require approval before sensitive tool calls execute. Permissions can also be whitelisted, so once you approve a safe operation like `ls`, the agent stops asking.

#### 12. Deep Research and Text-to-SQL Examples

The Deep Agents repo includes several practical examples. The deep research example demonstrates a long-running agent that uses Tavily for web search and can be run as a Jupyter Notebook or through the LangGraph dev UI, with full trace visibility into each step. The text-to-SQL example shows an agent that takes natural-language questions, converts them into SQL queries based on a database schema, and returns results, a powerful pattern for data analysis without needing SQL expertise. There is also a "Ralph mode" example for agents that aggressively retry on failure.

- [tavily.com](https://tavily.com/) -- Tavily real-time search API for AI agents

#### 13. Non-Coding Uses of Deep Agents

A recurring theme is that deep agents are not limited to coding. Michael referenced an X/Twitter post by Alex Albert asking what non-coding things people use Claude Code for, which received 319 replies covering note-taking with Obsidian, writing books, calendar management, medical diagnosis support, and building "second brain" systems. Sydney shared that she uses Deep Agents for triaging open source PRs and issues, and experimented with an agent that learns from her past social media posts. The key insight is that the deep agent pattern -- planning, file system, sub-agents, memory -- generalizes to any domain where complex, multi-step work is needed.

#### 14. The CLI: A Claude Code Alternative

LangChain built a CLI on top of the Deep Agents harness that serves as their internal alternative to Claude Code. It supports streaming output (word-by-word), model switching, built-in memory, and the full set of harness features. The team uses it internally for their own development work. It defaults to requiring human approval on tool calls, with the ability to whitelist trusted operations to reduce noise over time.

### Interesting Quotes and Stories

"Effective agents are just like effective people. They think carefully and plan, and then they keep their notes and thoughts organized and make things accessible when they need them." -- Sydney Runkle


"13 Markdown files just took a billion dollars off the stock market... that just shows how powerful prompts are." -- Michael Kennedy, referencing how Claude's release of specialized agent prompts as simple Markdown files rattled Wall Street


"If you're not the model, you're the harness." -- From LangChain's blog on agent architecture, referenced in the discussion


"It's too much work, but it's not too much work for you, AI, because you don't get tired, so you do it." -- Michael Kennedy, on why AI-generated doc strings are actually a benefit for tool definitions


"I have a project called Claude as Chat, where I just want to talk about a bunch of documents and have it be more thorough and maybe create other documents and then reference those back." -- Michael Kennedy, describing how he uses a fake code project in his editor purely to leverage Claude Code's deep agent capabilities for non-coding work


"Coding is just a productivity accelerator. You can use code to perform data analysis or to do so many other things that need to be automated. So I think we're going to start to see more general purpose agents who just write code to help them with things." -- Sydney Runkle, on the future of agents


### Key Definitions and Terms

- **Agent harness** : The infrastructure surrounding a language model -- system prompts, tools, planning capabilities, memory, and middleware -- that transforms a basic LLM into an effective autonomous agent.
- **Shallow agent** : An agent that makes a small number of tool calls in response to a prompt to accomplish a simple, well-defined task (e.g., booking a flight).
- **Deep agent** : An agent with extensive context access, planning capabilities, sub-agents, and memory that can tackle complex, long-running tasks with self-correction.
- **Sub-agent** : A child agent spawned by a main agent to handle a specific subtask, enabling parallelization and context isolation.
- **Context isolation** : The practice of giving a sub-agent only the context it needs for its specific task, rather than the full conversation history, improving both performance and efficiency.
- **Middleware** : Hooks into the agent's lifecycle (before/after model calls, before/after tool calls) that let developers inject custom logic like summarization, human approval, or retry handling.
- **MCP (Model Context Protocol)** : An open standard for connecting AI applications to external tools and data sources through a unified interface, supported by Claude, Cursor, VS Code, and others.
- **Prompt caching** : A technique that caches repeated portions of prompts (like the system prompt) across invocations to reduce cost and latency.
- **Context compaction/summarization** : The process of condensing earlier parts of a conversation to stay within the model's context window during long-running tasks.
- **Harness engineering** : The practice of systematically improving an agent's harness by analyzing traces of agent behavior, identifying failure patterns, and iterating on prompts, tools, and middleware.

### Learning Resources

Here are courses from Talk Python Training to go deeper on topics covered in this episode:

- [LLM Building Blocks for Python](https://training.talkpython.fm/courses/llm-building-blocks-for-python?utm_source=talkpythondeepdive) : Learn to integrate large language models into Python applications, including structured outputs, chat workflows, and async pipelines -- foundational skills for building the kinds of tools Deep Agents orchestrates.
- [Rock Solid Python with Python Typing](https://training.talkpython.fm/courses/python-type-hint-course-with-hands-on-examples?utm_source=talkpythondeepdive) : Deep Agents relies heavily on type hints and Pydantic for tool schema generation. This course covers Python typing in depth along with frameworks like Pydantic and FastAPI that build on types.
- [Python for Absolute Beginners](https://training.talkpython.fm/courses/python-for-absolute-beginners?utm_source=talkpythondeepdive) : If you are brand new to Python and want to build up to working with AI agent frameworks, this course teaches the fundamentals from the ground up with engaging, project-based learning.
- [Async Techniques and Examples in Python](https://training.talkpython.fm/courses/python-concurrency-deep-dive?utm_source=talkpythondeepdive) : Deep Agents and LangGraph use async Python extensively for parallel sub-agent execution and streaming. This course covers async/await, asyncio, and parallel programming patterns in Python.

### Overall Takeaway

The most important lesson from this episode is that the intelligence people experience from tools like Claude Code is not just the language model -- it is the carefully engineered harness around it. Planning tools, file system access, sub-agents, memory, middleware, and detailed system prompts are what transform a raw LLM into something that can plan, iterate, recover from mistakes, and deliver genuinely useful results. LangChain's Deep Agents open source library democratizes this pattern, letting any Python developer build their own deep agents for any domain -- not just coding -- in just a few lines of code. Whether you are automating research, triaging issues, analyzing data, or building a personal assistant, the combination of a good model and a great harness is the recipe. The tools are open, the barrier to entry is low, and the potential applications are limited only by your imagination.

## Links from the show

**Guest**

**Sydney Runkle**:

[github.com](https://github.com/sydney-runkle?featured_on=talkpython)

**Claude Code uses**:

[x.com](https://x.com/alexalbert__/status/1948765443776544885?ref=blog.langchain.com&featured_on=talkpython)

**Deep Research**:

[openai.com](https://openai.com/index/introducing-deep-research/?ref=blog.langchain.com&featured_on=talkpython)

**Manus**:

[manus.im](https://manus.im/?ref=blog.langchain.com&featured_on=talkpython)

**Blog post announcement**:

[blog.langchain.com](https://blog.langchain.com/deep-agents/?featured_on=talkpython)

**Claudes system prompt**:

[github.com](https://github.com/kn1026/cc/blob/main/claudecode.md?ref=blog.langchain.com&featured_on=talkpython)

**sub agents**:

[docs.anthropic.com](https://docs.anthropic.com/en/docs/claude-code/sub-agents?ref=blog.langchain.com&featured_on=talkpython)

**the quick start**:

[docs.langchain.com](https://docs.langchain.com/oss/python/deepagents/quickstart?featured_on=talkpython)

**CLIs**:

[github.com](https://github.com/langchain-ai/deepagents?tab=readme-ov-file#deep-agents-cli)

**Talk Python's CLI**:

[talkpython.fm](https://talkpython.fm/blog/posts/talk-python-now-has-a-cli/)

**custom tools**:

[docs.langchain.com](https://docs.langchain.com/oss/python/deepagents/overview#create-a-deep-agent)

**DeepAgents Examples**:

[github.com](https://github.com/langchain-ai/deepagents/tree/main/examples?featured_on=talkpython)

**Custom Middleware**:

[docs.langchain.com](https://docs.langchain.com/langsmith/custom-middleware#how-to-add-custom-middleware)

**Built in middleware**:

[docs.langchain.com](https://docs.langchain.com/oss/python/deepagents/customization#middleware)

**Improving Deep Agents with harness engineering**:

[blog.langchain.com](https://blog.langchain.com/improving-deep-agents-with-harness-engineering/?featured_on=talkpython)

**Prebuilt middleware**:

[docs.langchain.com](https://docs.langchain.com/oss/python/langchain/middleware/built-in?featured_on=talkpython)

**Watch this episode on YouTube**:

[youtube.com](https://www.youtube.com/watch?v=NRwA-fBNZZ4)

**Episode #543 deep-dive**:

[talkpython.fm/543](https://talkpython.fm/episodes/show/543/deep-agents-langchains-sdk-for-agents-that-plan-and-delegate#takeaways-anchor)

**Episode transcripts**:

[talkpython.fm](https://talkpython.fm/episodes/transcript/543/deep-agents-langchains-sdk-for-agents-that-plan-and-delegate)

**Theme Song: Developer Rap**

**🥁 Served in a Flask 🎸**:

[talkpython.fm/flasksong](https://talkpython.fm/flasksong)

**---== Don't be a stranger ==---**

**YouTube**:

**Bluesky**:

[@talkpython.fm](https://bsky.app/profile/talkpython.fm)

**Mastodon**:

**X.com**:

**Michael on Bluesky**:

[@mkennedy.codes](https://bsky.app/profile/mkennedy.codes?featured_on=talkpython)

**Michael on Mastodon**:

**Michael on X.com**:

## Episode Transcript

## Collapse transcript

[00:00](https://talkpython.fm#play-at) When you type a question in the ChatGPT, the model only has what you typed to work with.
        

[00:05](https://talkpython.fm#play-at) But tools like Claude Code can plan, iterate, test, and recover from mistakes.
        

[00:09](https://talkpython.fm#play-at) They work more like we do. The difference is the agent harness. Planning tools, file system access, sub-agents, and carefully crafted system prompts that turn raw LLMs into something genuinely
        

[00:21](https://talkpython.fm#play-at) capable. Sydney Runkle is back on Talk Python from LangChain to talk about their new open-source library DeepAgents, a framework for building your own DeepAgents with plain Python functions,
        

[00:32](https://talkpython.fm#play-at) middleware hooks, and MCP support. This is a framework that allows you to build tools similar to Claude Code. This is Talk Python To Me, episode 543, recorded February 19th, 2026.
        

[00:57](https://talkpython.fm#play-at) We started in Pyramid, cruising old-school lanes, had that stable base, yes sir.
        

[01:02](https://talkpython.fm#play-at) Welcome to Talk Python To Me, the number one Python podcast for developers and data scientists.
        

[01:07](https://talkpython.fm#play-at) This is your host, Michael Kennedy. I'm a PSF fellow who's been coding for over 25 years.
        

[01:13](https://talkpython.fm#play-at) Let's connect on social media. You'll find me and Talk Python on Mastodon, Bluesky, and X. The social links are all in your show notes. You can find over 10 years of past episodes at talkpython.fm. And if you want to be part of the show, you can join our recording live streams.
        

[01:27](https://talkpython.fm#play-at) That's right, we live stream the raw, uncut version of each episode on YouTube.
        

[01:32](https://talkpython.fm#play-at) Just visit talkpython.fm/youtube to see the schedule of upcoming events. Be sure to subscribe there and press the bell so you'll get notified anytime we're recording. This episode is brought
        

[01:42](https://talkpython.fm#play-at) to you by Sentry. You know Sentry for the error monitoring, but they now have logs too. And with Sentry, your logs become way more usable, interleaving into your error reports to enhance debugging and
        

[01:53](https://talkpython.fm#play-at) understanding. Get started today at talkpython.fm/sentry. And it's brought to you by Temporal, durable workflows for Python. Write your workflows as normal Python code and Temporal ensures they run
        

[02:06](https://talkpython.fm#play-at) reliably, even across crashes and restarts. Get started at talkpython.fm/Temporal.
        

[02:12](https://talkpython.fm#play-at) Sydney, welcome back to Talk Python on me. Awesome to have you here.
        

[02:16](https://talkpython.fm#play-at) Thanks. Yeah, super excited to be back.
        

[02:18](https://talkpython.fm#play-at) I am super excited to have you here. We're going to be talking about almost the topic du jour, the AI, but not in the way that people might think. Not using AI to build code, although what we're
        

[02:31](https://talkpython.fm#play-at) talking about could be used for that, and so on. But actually, how do you build your own AI tools?
        

[02:37](https://talkpython.fm#play-at) How do you build your own Claude Code equivalent if you wanted to have a lot more control over that?
        

[02:43](https://talkpython.fm#play-at) So I'm really excited about it. I think it's pretty eye-opening and great tools. Last time we were on, I think we talked about LangGraph. Was that right?
        

[02:52](https://talkpython.fm#play-at) Yeah, yeah, I think so.
        

[02:54](https://talkpython.fm#play-at) And now, carrying on with more Lang things from LangChain, we're going to talk about Deep Agents.
        

[02:59](https://talkpython.fm#play-at) So, super cool topic. I think people who feel like this is mysterious, or you sign up for some frontier model and it does all the magic. Well, we're going to dig into how that magic works and
        

[03:13](https://talkpython.fm#play-at) how you might build your own as well with some really cool tools here. Now, it has been a little while since you've been on. I think you've been on three times, which is amazing. But here's number four. There's a ton of new people listening to the show or coming into the Python space in general.
        

[03:27](https://talkpython.fm#play-at) I mean, it's amazing to me that 50% of the people doing Python are new to it professionally the last two years. I guess it makes sense. Anyway, quick introduction about who you are for everyone who doesn't know already.
        

[03:40](https://talkpython.fm#play-at) Yeah, sure thing. Well, very excited to get to share all of our new Deep Agents stuff with folks.
        

[03:47](https://talkpython.fm#play-at) My name is Sydney. I currently work at LangChain, which might sound familiar. It started as an open source package helping folks use AI. Basically, as soon as LLMs started to blow up, LangChain emerged
        

[04:01](https://talkpython.fm#play-at) as a toolkit for building with LLMs in Python. And then it since has evolved into a company. So we offer
        

[04:09](https://talkpython.fm#play-at) observability and evals products for agents. We basically are building a platform for folks to build agents. But we still are kind of built on our open source core, which is that LangChain project,
        

[04:23](https://talkpython.fm#play-at) and now Deep Agents. And then I've also spoken with you about LangGraph. So we'll kind of talk about how all of those open source projects are related today. And then I guess I'll also note I've chatted
        

[04:34](https://talkpython.fm#play-at) with you before about other open source projects like Pydantic and Pydantic AI is where I worked previously. So very excited to kind of be in the open source AI space.
        

[04:43](https://talkpython.fm#play-at) It's been quite the roller coaster I think you've probably been on the last couple years.
        

[04:48](https://talkpython.fm#play-at) We talked about the Young Coders Blueprint for success, right? As you were graduating college, and now you spent a good stint with Pydantic.dev, which is awesome. And that's a really,
        

[04:58](https://talkpython.fm#play-at) that's a big center of the open source Python world. And so is LangChain. So very exciting, I'm sure.
        

[05:05](https://talkpython.fm#play-at) Yeah, yeah. I think if I could redo the Young Coders Blueprint success now, it would probably look pretty different than it did when we chatted.
        

[05:12](https://talkpython.fm#play-at) I was wondering about that as well. Maybe we'll get to that later. Maybe we will.
        

[05:16](https://talkpython.fm#play-at) So let's start by setting the stage with, let's start here. So I want to talk about this idea of deep agents, obviously the name of the product or the library that we're going to be talking about,
        

[05:31](https://talkpython.fm#play-at) but more high level for the moment, as opposed to shallow agents. So give us a contrast, I guess, if you will, between what is a shallow agent as you all refer to it? And then why the term deep agents?
        

[05:45](https://talkpython.fm#play-at) Yeah, great question. So I think a shallow agent is sort of what the agents of a year or two ago looked like. So agents are basically a model calling tools in a loop in response to some prompt.
        

[05:58](https://talkpython.fm#play-at) And so a shallow agent maybe does like a couple of tool calls to help an end user achieve a goal.
        

[06:05](https://talkpython.fm#play-at) So maybe you need help with a flight booking and your agent has powers to, you know, call flight and hotel booking tools. So that's like a relatively simple task. It's pretty easy to like judge whether
        

[06:17](https://talkpython.fm#play-at) or not that was successful. But deep agents have access to much more context and are able to perform
        

[06:26](https://talkpython.fm#play-at) much more complex tasks with kind of longer horizons. And so we're generally seeing a trend towards, you know, folks always pushing the boundaries of like how complex of tasks can agents solve?
        

[06:39](https://talkpython.fm#play-at) And then also like, you know, how long can they run for in a sustainable way?
        

[06:43](https://talkpython.fm#play-at) Yeah, I think deep agents, I think they're where it's at. You know, one of the, I feel like there's this sort of split in what people feel like is possible with AI. And a lot of it comes down to this,
        

[06:55](https://talkpython.fm#play-at) I believe. I go to ChatGPT or Gemini or somewhere, you know, like ChatGPT.com and I type into the text box, create me a function to do this, or I want you to solve this problem. And all it has to work
        

[07:10](https://talkpython.fm#play-at) with is the text that you've typed into the text box, right? And it's, it's got very little to go on. I mean, depending on how much you give it as a prompt, I guess, but generally it has very little to go on and you get pretty good answers. I mean, to be honest, ChatGPT and things are like utter magic,
        

[07:25](https://talkpython.fm#play-at) but relative to deep agents, they, they don't necessarily come up with the best answers.
        

[07:30](https://talkpython.fm#play-at) And really, I think the essence of it is that they can't check and revalidate, right? As opposed to something like Claude Code or Codex, where it has an idea, it reads about the code and it's okay,
        

[07:43](https://talkpython.fm#play-at) well, let me try to write that. Now let me apply some tools to see how that worked, right? Let me run ruff against it and see if that passed. Oh, the ruff, does it work? It says there's wrong code.
        

[07:54](https://talkpython.fm#play-at) Well, let me go back and do it again. Let me run the unit tests. Oh, look, they did pass. Okay. I think I'm on the right track, right? This back and forth and this kind of tool use and iteration,
        

[08:03](https://talkpython.fm#play-at) that is more indicative of a deep agent, would you say? Yeah, definitely. I think like a deep agent has kind of much more agency than a shallow agent, if we're calling it that. And yeah, the more like
        

[08:17](https://talkpython.fm#play-at) capabilities and power you give your agent, the more useful it has the potential to be. And so what we're doing in building deep agents is kind of trying to build the most effective harness,
        

[08:27](https://talkpython.fm#play-at) trying to equip this, you know, agent builder with the best set of tools and instructions so that, yeah, it can do really challenging things. And you're, you're kind of talking through some of
        

[08:41](https://talkpython.fm#play-at) the like coding agent applications that I think a lot of us are seeing kind of revolutionize our day-to-day workflows. Absolutely. And I'm using coding agents because I feel like that probably most significant and most strongly connects with the audience, but it doesn't have to be coding,
        

[08:55](https://talkpython.fm#play-at) right? It could be, be anything. But before we get into what that might be, I just want to circle back and say, I really think that there's, I don't know if you have a better way you individually,
        

[09:05](https://talkpython.fm#play-at) you as a LangChain representative, a better way to represent this. Because when people talk about, oh, AI makes this mistake or AI hallucinates or this or that or whatever, right? People use the
        

[09:17](https://talkpython.fm#play-at) same words, but they're not necessarily talking about the same thing. And then they debate whether their version of the thing that they don't really make clear is better or worse than some other thing that's not actually the same thing, right? It's kind of people are talking a bit past each other.
        

[09:31](https://talkpython.fm#play-at) Do you see a good way of this conversation being more specific, evolving, or is that where we are for a while? Yeah, that's a great question. Basically, just is what you mean the fact that
        

[09:43](https://talkpython.fm#play-at) people are very concerned about AI not being grounded in truth or hallucinating and that sort of thing?
        

[09:48](https://talkpython.fm#play-at) Yeah, yeah. So for example, let's say somebody says, oh, this stuff is terrible. It made up all this stuff and it gave me really shout and it was actually wrong about a fact. And what they meant is they use
        

[09:57](https://talkpython.fm#play-at) the free non-logged-in version of ChatGPT with the lowest model, like instant answer, versus another person who used, let's say, deep research, the top pro model, and a 500-word
        

[10:12](https://talkpython.fm#play-at) prompt with a couple of files to back. People say, well, I used it and it's wrong and it's bad and I did it and look how amazing it is. And they think they're talking about the same thing. And those are
        

[10:21](https://talkpython.fm#play-at) even putting agents aside. Those are really different things, right? We're debating whether we're sort of comparing those as if they're the same experience and then judging them.
        

[10:32](https://talkpython.fm#play-at) Yeah, I think that's a great question. So, you know, I think there's always the baseline thing that like, you know, you should be skeptical and ask questions of your results that you get from AI
        

[10:43](https://talkpython.fm#play-at) tooling. That being said, the rate at which AI tooling is improving is pretty hard to believe. And so I think, you know, even thinking about things like citations and, yeah, deep research abilities,
        

[10:55](https://talkpython.fm#play-at) agents and AI tools are getting pretty good at grounding things in truth and like in current truth, not just like data that they were trained on, right? And so I generally have high confidence
        

[11:08](https://talkpython.fm#play-at) in the AI tools that I use with that like asterisk of like, okay, but like I do ask follow-up questions and like get them to check their work sometimes.
        

[11:17](https://talkpython.fm#play-at) Yeah, yeah, yeah. I think there's a big, there's a wide varied skill gap here and tool chain gap and so it's, it's super interesting. So as a way to sort of set the stage for deep agents, yeah. Would you
        

[11:29](https://talkpython.fm#play-at) say Claude Code is a pretty good representative of this idea? Maybe describe why if you think so?
        

[11:34](https://talkpython.fm#play-at) Yeah, I think so. When I think about a deep agent, I think about something that has access to an abundance of context. And so for Claude Code, that's like your file system.
        

[11:46](https://talkpython.fm#play-at) I think about something that's autonomous and kind of can organize complex tasks. And so that's like, you know, spitting up sub-agents and keeping a to-do list handy to be able to organize all the
        

[11:59](https://talkpython.fm#play-at) things going on. And then I also think about, you know, an agent being really kind of optimized for the user that it's working with. And so that really ties into like memory and updating memory. And I think
        

[12:11](https://talkpython.fm#play-at) Claude Code does all of those things. So I think it's a very like, you know, coding specific deep agent.
        

[12:17](https://talkpython.fm#play-at) Right. Very cool. So the blog post that announced deep agents at LangChain referenced this X post, which is, I think it's pretty interesting. It's certainly something that resonates with me. And
        

[12:28](https://talkpython.fm#play-at) it says, this person, Alex Albert says, I'm making a list of all the non-coding things people are doing with Claude Code. What are you using Claude Code for? I got, you know, in parentheses, like silent,
        

[12:39](https://talkpython.fm#play-at) that's not coding. So I think that really highlights how powerful this stuff is of people who are not even coders are like, you know what, I'm willing to open up the terminal. I figured out where that is
        

[12:50](https://talkpython.fm#play-at) and I made it not white on my Mac. And now I'm able to do way, way more by basically giving it access to the file system and other things. And then, you know, Claude themselves came out with Cowork,
        

[13:03](https://talkpython.fm#play-at) which is basically Claude Code for non-coders, you know, something like that, right? If you install the desktop app, it will, you can give it access to a files, a part of your file system and it'll, it can use much of the things that Claude Code would do, right?
        

[13:17](https://talkpython.fm#play-at) Yep. Yeah. Definitely like a big motivator here for us. I think like, you know, we saw how revolutionary Claude Code was just within like almost weeks of release. And so I think the idea is like,
        

[13:29](https://talkpython.fm#play-at) well, certainly this revolution is coming to other areas. And so how can we kind of generalize that?
        

[13:35](https://talkpython.fm#play-at) This portion of Talk Python To Me is brought to you by Sentry. You know Sentry for their great error monitoring, but let's talk about logs. Logs are messy. Trying to grep through them and line
        

[13:47](https://talkpython.fm#play-at) them up with traces and dashboards just to understand one issue isn't easy. Did you know that Sentry has logs too? And your logs just became way more usable. Sentry's logs are trace connected and
        

[13:58](https://talkpython.fm#play-at) structured. So you can follow the request flow and filter by what matters. And because Sentry surfaces the context, right where you're debugging, the trace relevant logs, the error, and even the session
        

[14:09](https://talkpython.fm#play-at) replay all land in one timeline. No timestamp matching, no tool hopping. From front end to mobile to backend, whatever you're debugging, Sentry gives you the context you need so you can fix the
        

[14:19](https://talkpython.fm#play-at) problem and move on. More than 4.5 million developers use Sentry, including teams at Anthropic and Disney Plus. Get started with Sentry logs and error monitoring today at talkpython.fm/sentry.
        

[14:31](https://talkpython.fm#play-at) Be sure to use our code talkpython26. The link is in your podcast player show notes.
        

[14:36](https://talkpython.fm#play-at) Thank you to Sentry for supporting the show.
        

[14:39](https://talkpython.fm#play-at) Yeah, so I'm going to just kind of, I'll just scroll through here a little bit and see what people put down, but I think, yeah, 319 replies. So I guess people are doing stuff with it.
        

[14:50](https://talkpython.fm#play-at) So somebody says notes plus research plus knowledge base plus obsidian. And I think that's pretty interesting. I've heard about somebody building, I don't know if people have read the
        

[15:01](https://talkpython.fm#play-at) book, a second brain, but the idea that you drop stuff into like an inbox and then eventually you categorize it. And it means you don't have to remember so much. And somebody building,
        

[15:11](https://talkpython.fm#play-at) basically using Claude Code automation to build that kind of stuff. Somebody says writing a book.
        

[15:17](https://talkpython.fm#play-at) I hope that means it's helping them write the book, not actually Claude is writing the book, but I don't know. I don't know how you feel. I feel a little creeped out if it's just like, here's a whole bunch of text created purely by AI. You know, I gave it a vague idea and now read it.
        

[15:32](https://talkpython.fm#play-at) Yeah, I definitely feel a little bit more kind of ethically conflicted about like work that I would like to consume that's like original versus like, I don't really have ethical qualms with code not being
        

[15:43](https://talkpython.fm#play-at) like original thoughts from someone, but definitely like writing or art. I think the lines start to get fuzzy. Yeah, I really dislike it. And I'm, it's so bad on YouTube. Now you go to YouTube and you see
        

[15:54](https://talkpython.fm#play-at) videos and you're like, Oh, this is just pictures with some AI generated thing and then text to speech thing. And, you know, I don't know, it feels, feels not good. So hopefully this is not, this book is
        

[16:07](https://talkpython.fm#play-at) like, it's helping me write the book, not writing the book. And then, yeah, what else we got?
        

[16:11](https://talkpython.fm#play-at) helped me learn hledger, including, working with banks and all sorts of stuff. person says, yeah, another person says a second brain browser use calendar and scheduling medical
        

[16:23](https://talkpython.fm#play-at) diagnosis for my oncologist wife. Okay. That almost sounds like coding, but there's a lot of ideas here. And I've certainly personally actually have in my editor, I have a project called
        

[16:34](https://talkpython.fm#play-at) Claude as Chat, where I just want to talk about a bunch of documents and have it, you know, be more thorough and maybe create other documents and then reference those back and so on. So instead
        

[16:44](https://talkpython.fm#play-at) of opening up a kind of chat thing, I'll open up my, my code editor and, you know, fire up Claude Code or something and go after it. So yeah. Are you doing anything like this?
        

[16:53](https://talkpython.fm#play-at) That's a good question. I have been using deep agents kind of our, more general purpose equivalent to help me with some like life admin things, or even just like work admin things.
        

[17:05](https://talkpython.fm#play-at) So working in open source, we get, a lot of, you know, incoming PRs and issues, et cetera.
        

[17:12](https://talkpython.fm#play-at) so we're working on using deep agents to kind of help us like triage and categorize there. what else? I have been experimenting with a deep agent that helps learn from my past
        

[17:26](https://talkpython.fm#play-at) social media posts and their performance. and then help me write new ones, based on like docs that I provide, et cetera. Admittedly, again, I think that like crosses the fuzzy line
        

[17:38](https://talkpython.fm#play-at) with writing. And I've kind of found that like, I actually prefer to just like write quick tweets and LinkedIn posts, you know, originally, and then, maybe have like Claude help me edit if
        

[17:48](https://talkpython.fm#play-at) I'm like really struggling with a line. but I do think that's an interesting use case because it like definitely has gotten better at kind of learning my style, but at some, yeah. Yeah.
        

[17:58](https://talkpython.fm#play-at) Very interesting. So it's, it's not just Claude code. You'll also point out that, you know, as I mentioned as well, OpenAI is deep research, which is incredible as well as Manus. I just
        

[18:09](https://talkpython.fm#play-at) recently learned about Manus, but I feel like this is a little bit similar. It's a little more agentic, but it still feels like just a ChatGPT chat experience. So interesting. I don't know. I've
        

[18:19](https://talkpython.fm#play-at) used Manus any, I don't know anything about it. I haven't used it a ton, but we've definitely taken some inspiration from their, their features. I'm sure. Cool. all I know now is that Manus
        

[18:30](https://talkpython.fm#play-at) is part of meta apparently. Yeah. I guess. Congratulations Manus people. Yeah. Yeah.
        

[18:35](https://talkpython.fm#play-at) That's cool. Yeah. There have been a lot of crazy acquisitions recently. Yeah, absolutely. All right.
        

[18:40](https://talkpython.fm#play-at) So that brings us to maybe what is the essence, the characteristics of deep agents, right? There's these different examples, but what, how is that different than just an LLM or you ask it a question,
        

[18:52](https://talkpython.fm#play-at) right? What you guys laid out with a nice little picture, kind of what that means to you.
        

[18:57](https://talkpython.fm#play-at) Yeah. Yeah. So when we think about deep agents, we think about it as an agent harness. And so, it's a tool for building agents that comes with these, built in things that kind of build up
        

[19:10](https://talkpython.fm#play-at) the harness so that the agents are highly effective at those complex long running tasks. and so I'll talk a little bit more about kind of what's built in here. before we do, I think we got to do some,
        

[19:21](https://talkpython.fm#play-at) we got to do some nomenclature, some definitions here. Yeah. Yeah. So you, you said that an agent harness. So what is an agent harness? Yeah. That's invisible to many people, but it's,
        

[19:33](https://talkpython.fm#play-at) it's part of the magic, right? Yeah. so this is an agent harness is kind of add-ons around that core like model and tool calling loop, that help to make an agent more effective with more complex
        

[19:47](https://talkpython.fm#play-at) tasks. so you kind of have your like basic agent. That's just like you give a model, prompt and some tools and it like runs in a loop and then produces a final result. whereas a
        

[19:59](https://talkpython.fm#play-at) harness adds in extra support to make the agent more effective.
        

[20:03](https://talkpython.fm#play-at) I see. So a little bit like when people would say you are a marketing wizard who was created seven successful, whatever, and then you ask it something like that's the, that's a real baby version of,
        

[20:17](https://talkpython.fm#play-at) of maybe what a harness, maybe a little flavor of what a harness is, right? It's, here's all of the things that you're doing. Here's your skills. Here's what I want you to focus on. Here's maybe
        

[20:26](https://talkpython.fm#play-at) your tool chain that you can use, right? To, you can call these things to do more, to learn more, something like that. Yeah. Yeah. So the harness helps to provide the model with like extra
        

[20:39](https://talkpython.fm#play-at) context and capabilities so that it can perform better. I think it's a little bit easier to understand kind of what a harness is if we talk about some of the components of an agent
        

[20:51](https://talkpython.fm#play-at) harness. Got it. Yeah. Okay. So what are the characteristics maybe? Yeah. Yeah. So for the first, the first thing we think about with our agent harness is giving the agent access to a planning
        

[21:01](https://talkpython.fm#play-at) tool. So for Claude Code users, you're, you know, very intimately familiar with the to-do list that Claude generates and then kind of checks off as it makes its way through various tasks. And this just
        

[21:13](https://talkpython.fm#play-at) helps your agent to like stay organized and kind of ensure that it gets through all of the various steps in, in a complex problem. And even just giving the agent this planning tool can help it
        

[21:24](https://talkpython.fm#play-at) like have a better trajectory for those harder problems. It's really wild the plan, how much the planning helps, but it really does. You know, Claude Code and cursor and others even have planning mode.
        

[21:36](https://talkpython.fm#play-at) And I think probably this harness shifts a little bit when you switch it into planning mode, it probably gets a different set of instructions that you don't even see you're in planning mode and here's how you're
        

[21:47](https://talkpython.fm#play-at) going to act. And you're going to now interview the user to really try to understand what it is they want and so on. Right. Like they don't, they don't tell you that it's just a drop down planning mode, but it probably means something like that. Right. Yeah. Yeah, exactly. And I think we've even seen
        

[22:02](https://talkpython.fm#play-at) the power of planning kind of reflected at the model level where like models, you know, there was a big boom in kind of like reasoning or thinking models about a year ago. And just the idea that if a model
        

[22:16](https://talkpython.fm#play-at) thinks through or like reasons about tasks more before producing a final result, then it's likely to do better. So yeah, the planning tools kind of part one. Another thing that's big for our harness is
        

[22:31](https://talkpython.fm#play-at) access to a file system. So, you know, models have limited context windows, which is just like the amount of tokens, text and other things that you can send to the model. And so being able to use a
        

[22:45](https://talkpython.fm#play-at) file system and kind of selectively search or read or write files is a really effective tool for kind of context management that's more organized than just like sending everything all at once to
        

[22:57](https://talkpython.fm#play-at) the model. Yeah. And I think that might be a little bit why my Claude as Chat fake programming project actually is useful. Right. Because I can, because it has a file system. Right. And like, here's a couple files you start with. And then when you need to, you create more files and then you reference that.
        

[23:11](https://talkpython.fm#play-at) You're right. It's, it's some of those files. I don't know. I think, you know, 20, 30,000 words, which is a lot of, it's most of the context, just try to keep that in memory, right. If it had to do it
        

[23:22](https://talkpython.fm#play-at) that way. And so letting the AI unload its mind, it's like asking you to read a textbook and remember everything instead of ever going back to it. Right. Yeah. One shot, read a textbook. Now go.
        

[23:33](https://talkpython.fm#play-at) Yeah, exactly. I think like we're kind of starting to see this pattern emerge where it's like, well, effective agents are just like effective people, right? They like think carefully and plan
        

[23:43](https://talkpython.fm#play-at) and then they keep their notes and thoughts organized and, you know, make things accessible when they need them, but don't like, you know, it makes much more sense to like read a textbook
        

[23:53](https://talkpython.fm#play-at) chapter than just like read the textbook. Yeah. Yeah, absolutely. It's like using a highlighter almost. Okay. So planning tool, file system, and then sub agents. This one is less obvious to me.
        

[24:06](https://talkpython.fm#play-at) Tell me about the sub agents. Yeah. So in my mind, sub agents are largely for helping a,
        

[24:14](https://talkpython.fm#play-at) your deep agent accomplish tasks more efficiently. So if you, you know, ask your deep agent to go do a bunch of research on some given thing, it probably wants to like pursue a couple different
        

[24:28](https://talkpython.fm#play-at) paths for that research, right? Like you want it to be really thorough. And it's more effective if you spin up sub agents to do that in parallel than if you just had your main agent do like all of the
        

[24:40](https://talkpython.fm#play-at) research in sequence. And then we also, I'll give a coding example too. Like if you wanted your agent to edit a bunch of files in like a similar way, it'd probably be better for it to go edit like 10
        

[24:53](https://talkpython.fm#play-at) files at the same time than to do the first file. Then when it finishes, go to the second. And so the name of the game here really is like parallelization. And then the final like buzzword
        

[25:04](https://talkpython.fm#play-at) that I'll drop here is context isolation. which is that like, if you have kind of a like small subtask, an agent is likely to perform better. If you like just give it the context it needs rather
        

[25:15](https://talkpython.fm#play-at) than like all of this other history and things like that. and so that's really what motivates sub agents. Awesome. Yeah. I think the parallelism is pretty straightforward. People probably think, oh, sub agent, maybe you can fan out. Like we're going to go read this article and we're going to
        

[25:29](https://talkpython.fm#play-at) read the document you gave us. Then we'll write if you did those two in parallel, that's great. But I think it's the context management is also super important, right? The little sub agent that might read the Wikipedia article doesn't consume all the, it doesn't have to know all the other
        

[25:43](https://talkpython.fm#play-at) stuff. All it has to do is say, given this article, get this piece of information out of it. And then it kind of resets almost back to just a sentence or two. Right. So it's a good way to do that context
        

[25:53](https://talkpython.fm#play-at) isolation, like you say. Yep. Yep. Definitely. and then the fourth one we have listed here is, system prompt. Perhaps what I'll like, elaborate on here is the fact that we do give it
        

[26:07](https://talkpython.fm#play-at) like a system prompt that instructs it on how to use the file system and the planning tool and, you know, the fact that it can invoke sub agents. but we also load, memory into the system
        

[26:20](https://talkpython.fm#play-at) prompt. and so that's something that can like persist across conversations and things like that.
        

[26:25](https://talkpython.fm#play-at) and so the idea here just being like prompts power agents and we want to, you know, really optimize the kind of under the hood prompt that's powering this harness. Yeah. two thoughts on
        

[26:36](https://talkpython.fm#play-at) that really quick. I think that's great. There was, I'm sure you've seen this, but there was an article that said something to the effect of 13 Markdown files just took a billion dollars off the stock market
        

[26:47](https://talkpython.fm#play-at) or no, it was some huge amount, maybe 200 billion. I don't know. It was some huge number. And effectively that was when like Claude released the legal agent as a Markdown file or, you know,
        

[26:59](https://talkpython.fm#play-at) a couple other specialized knowledge worker things. And people just realized, wow, it can actually solve all these problems that we used to employ people for, which is really kind of, it's a whole
        

[27:10](https://talkpython.fm#play-at) another kind of tough debate, but that just shows how powerful prompts are, right? If like, oh, we just gave it a different addition to its prompt. And now it it's wall street is freaked out
        

[27:21](https://talkpython.fm#play-at) because it's right. That's crazy. Do you see that? Do you see that article? Yeah. Yeah. Yeah. It's, it's definitely, wild. I mean, I think we've known for a long time that like prompt engineering
        

[27:31](https://talkpython.fm#play-at) and, you know, really carefully tailoring your prompt to your use case is super powerful. but I think people are like really starting to realize how much that might affect like various
        

[27:43](https://talkpython.fm#play-at) industries. Yeah. A hundred percent. So I'll, I'll link to, actually the Claude code system prompt and how many words this is. It's, it's a lot, it's a lot of words. let
        

[27:55](https://talkpython.fm#play-at) me see if I can answer that question, but I'll link to the Claude code system prompt and people can check it out. It's, it's kinda, yeah, it's 16,000 words, which is third of a novel.
        

[28:05](https://talkpython.fm#play-at) And I think that's noteworthy because if, if you ask a question of your AI, some of them show the context that's being used up, right? That counts towards it, right? That's kind of,
        

[28:16](https://talkpython.fm#play-at) that precedes your, your, your one sentence question. You know, if you're like fix failing test, you know, 16,000 words that precedes fix failing test. Yeah. It's crazy, right?
        

[28:27](https://talkpython.fm#play-at) Yeah, definitely. One of the, key things that we also add in deep agents under the hood is like prompt caching. so you might think like, oh man, like my cost is really going to rack up if,
        

[28:38](https://talkpython.fm#play-at) this is being sent every time under the hood, but, we can kind of cache those like shared prompts across invocations. so that, that's very helpful for very verbose symptom system prompts.
        

[28:50](https://talkpython.fm#play-at) Good. You'll want to send that every time. I mean, this is the Claude code one, but you, you'll probably have a non-trivial one as well, right? Yeah. but this definitely speaks to the fact that like, obviously prompts are important, you know, we're like very dependent
        

[29:01](https://talkpython.fm#play-at) on Claude code for, productivity and like the detailed system prompt is a big part of why it's so effective. Yeah, absolutely. And why people are like, well, I feel like it's changed. It's now less friendly or whatever, you know, maybe that means just this, the model might not have even
        

[29:16](https://talkpython.fm#play-at) changed. It could just be the system prompt has changed and now it's doing something slightly different. Yeah. This portion of talk Python to me is sponsored by Temporal. Ever since I had Mason
        

[29:26](https://talkpython.fm#play-at) Edgar on the podcast for episode 515, I've been fascinated with durable workflows in Python. That's why I'm thrilled that Temporal has decided to become a podcast sponsor since that episode. If you've built
        

[29:38](https://talkpython.fm#play-at) background jobs or multi-step workflows, you know how messy things get with retries, timeouts, partial failures, and keeping state consistent. I'm sure many of you have written brutal code to keep the workflow moving and to track when you run into problems, but it's trickier
        

[29:52](https://talkpython.fm#play-at) than that. What if you have a long running workflow and you need to redeploy the app or restart the server while it's running? This is where Temporal's open source framework is a game changer. You write
        

[30:03](https://talkpython.fm#play-at) workflows as normal Python code and Temporal ensures that they execute reliably, even across crashes, restarts, or long running processes while handling retries, states, and orchestrations for you so you
        

[30:14](https://talkpython.fm#play-at) don't have to build and maintain that logic yourself. You may be familiar with writing asynchronous code using the async and await keywords in Python. Temporal's brilliant programming model leverages the exact
        

[30:26](https://talkpython.fm#play-at) same programming model that you are familiar with, but uses it for durability, not just concurrency.
        

[30:31](https://talkpython.fm#play-at) Imagine writing awaitworkflow.sleep, time delta, 30 days. Yes, seriously, sleep for 30 days. Restart the server, deploy new versions of the app. That's it. Temporal takes care of the rest. Temporal is used
        

[30:44](https://talkpython.fm#play-at) by teams at Netflix, Snap, and NVIDIA for critical production systems. Get started with the open source Python SDK today. Learn more at talkpython.fm/Temporal. The link is in your podcast player's show
        

[30:56](https://talkpython.fm#play-at) notes. Thank you to Temporal for supporting the show. All right, let's talk about
        

[31:01](https://talkpython.fm#play-at) Deep Agents, LangChain style, not just in general the concept of it. And you have a GitHub repo over here just
        

[31:11](https://talkpython.fm#play-at) called Deep Agents. And I thought it might be interesting just to kind of talk through what we got over here.
        

[31:17](https://talkpython.fm#play-at) So some of it we've already talked about, right? Like the planning, the file system, the sub-agents.
        

[31:22](https://talkpython.fm#play-at) But there's also more things like tools, middleware, the whole programming model. Where do we want to start? I guess before we start, let me, how old is this project? Not super old, right?
        

[31:34](https://talkpython.fm#play-at) Not super old.
        

[31:35](https://talkpython.fm#play-at) Let me see. I'll go here. I'll hit the history on the readme. That's usually the best way.
        

[31:39](https://talkpython.fm#play-at) Yeah.
        

[31:39](https://talkpython.fm#play-at) So August. Okay, so it's been around since August. That doesn't tell you when it's been public, right? That's the thing. Yeah. When was it early? I think it was made public very soon after. I think
        

[31:52](https://talkpython.fm#play-at) it might have started public, honestly. We're a very like first company, which is great. But yeah, so it started just this summer. Okay. Yeah. So it's already got, you know, 10,000 stars. It's
        

[32:02](https://talkpython.fm#play-at) pretty popular here. All right. So let's see. I guess maybe let's talk about the programming model, because I think that'll help make it concrete for people. Like what is the value of this? You know,
        

[32:13](https://talkpython.fm#play-at) maybe just talk us through like this quick start. Yeah. So as we mentioned kind of at the beginning, deep agents are, and the agents you can build with the deep agents package are very general. So
        

[32:27](https://talkpython.fm#play-at) Claude Code is an example of a like coding agent. But you might want to build deep agents with all sorts of specializations. And so our new open source library helps you do that. And so you can see
        

[32:40](https://talkpython.fm#play-at) here, we have basically a three line code snippet. You import create deep agent from the deep agents package, you call create deep agent, and you can add your own model tools, prompt additions,
        

[32:55](https://talkpython.fm#play-at) kind of other configuration. And then you like have a an agent that's ready to use and even deploy.
        

[33:02](https://talkpython.fm#play-at) So very basically easy way to get started with building effective agents.
        

[33:08](https://talkpython.fm#play-at) Awesome. So you might just say agent.invoke and use that research LangGraph and write a summary.
        

[33:14](https://talkpython.fm#play-at) Yeah. Yeah.
        

[33:14](https://talkpython.fm#play-at) So then what? How does it know what model to use? How does it, you know, how does it go about that?
        

[33:21](https://talkpython.fm#play-at) Can it use tools and to-dos, you know, planning like we've discussed?
        

[33:25](https://talkpython.fm#play-at) Yeah. So when you use the create deep agent function under the hood, we add tools for planning
        

[33:34](https://talkpython.fm#play-at) and also for file system access and things like that. We'll have a user or a developer specify like
        

[33:42](https://talkpython.fm#play-at) what file systems they'd like to use. And then you can bring your own tools in addition to the ones that we provide under the hood. So maybe going back to my like travel agent example, you could,
        

[33:55](https://talkpython.fm#play-at) you know, bring like, or actually I'll use like a personal assistant example. If you want to have, you know, a calendar API tool and a Gmail API tool, you could bring those along as well.
        

[34:07](https://talkpython.fm#play-at) So kind of more use case specific.
        

[34:09](https://talkpython.fm#play-at) I see. Maybe I'm working with Obsidian or some other Markdown thing for organization. And you could point it and say, you're allowed to access any of my Markdown files for this project or just in general, right? Something that could be a tool and you could teach it to do that. Yeah. So I noticed
        

[34:23](https://talkpython.fm#play-at) below that you can do things like specify a little more detail. For example, you can say it can use a certain model in this case. See how long that'll last. You could use GPT-4o. I hear,
        

[34:35](https://talkpython.fm#play-at) aren't they taking that away again? They took it away. People are freaked out on them. They put it back, but I think it's also not long for this world, but whatever you pick some model. And then as you pointed out, this tools as my custom tool, it's not super obvious from this code snippet,
        

[34:49](https://talkpython.fm#play-at) but my custom tool is just a Python function, right? Yes. Yep. That's correct. It's pretty easy to define tools. It can be just, yeah, a very simple Python function, can use some API of your
        

[35:02](https://talkpython.fm#play-at) choice, like maybe the calendar API, for example. I see. So you could, you could write pretty much any type of function. It just has to take in text and spit out text or something to that effect.
        

[35:14](https://talkpython.fm#play-at) Yeah. We actually support like multimodal content for tools as well. So it could produce images. It
        

[35:21](https://talkpython.fm#play-at) could produce files of other types and can take, you know, a varying, it can take any types of arguments. So the model is populating those arguments. But. Right. Okay. How does it,
        

[35:35](https://talkpython.fm#play-at) I mean, this might be getting too deep in the weeds for a quick start, but how does it know what to pass to your Python function and how does it know what to do with the return value? Yeah, that's a great
        

[35:45](https://talkpython.fm#play-at) question. So it all comes back to the prompt. And this is kind of a like wonderful marriage between developer docs and LLMs. So when you define a function, let's say like, I'll use a simple example,
        

[35:59](https://talkpython.fm#play-at) a weather tool, a get weather tool. You can imagine the arguments might be something like, I'll say like city and state or something like that. And then you might expect kind of structured
        

[36:12](https://talkpython.fm#play-at) weather data back, like, you know, current temperature, current conditions, et cetera.
        

[36:18](https://talkpython.fm#play-at) And when you define that function and your Python code, you can write a doc string and it says, this tool is used for getting the weather in a given city and state. And then you can document
        

[36:29](https://talkpython.fm#play-at) your arcs. And so city, you would say the city to get the weather for, and then state, you know, this is all pretty self-explanatory. And then that information is parsed under the hood and actually
        

[36:39](https://talkpython.fm#play-at) passed to the model as part of its prompt. And so what that looks like is, you know, we would parse the fact that we would parse the signature of the tool and the documentation and tell the model
        

[36:53](https://talkpython.fm#play-at) effectively like, hey, you have a get weather tool. If you, you know, you should call it when you want to get the weather for a given city and state. We pull that out of the doc string.
        

[37:03](https://talkpython.fm#play-at) And then we also say, when you call it, make sure to pass these arcs in.
        

[37:07](https://talkpython.fm#play-at) Right, right, right. So a lot of times I see this happening and people are like, well, let's try to specify a JSON schema. And your job is to generate data that looks like this and then maybe even validate and say, no, you did it wrong. Try it again. But this is really interesting
        

[37:22](https://talkpython.fm#play-at) using the native Python syntax and help, you know, doc strings, right? That's wild.
        

[37:28](https://talkpython.fm#play-at) Yeah, it's really nice. I think it lets developers kind of focus on just writing the code that makes sense for their use case. And then, yeah, under the hood, like we convert these schemas to LLM usable
        

[37:40](https://talkpython.fm#play-at) things. And this is a nice like intersection of my previous work and current work, which is like a lot of the, you know, function parsing uses tools like Pydantic to define schemas for models. So that's a cool overlap.
        

[37:52](https://talkpython.fm#play-at) Yeah, I know that that's an interesting aspect of what Pydantic is used for a lot. So as you were describing this, I was wondering, hmm, are you using Pydantic for this? Perhaps. Okay, amazing. I think
        

[38:02](https://talkpython.fm#play-at) this also blends well with Claude Code type written, I guess, just Claude, not, you know, Claude Opus on it, whatever. The models, they're very keen to write doc strings, right? They just, even if you don't ask it
        

[38:15](https://talkpython.fm#play-at) to a lot of times, it's doc string, doc string, doc string. So I guess that would be really helpful, right? Yeah, yeah, definitely. I think it's nice that like some of the things that we as developers weren't necessarily the best about in terms of like code cleanliness or quality, we can now kind
        

[38:30](https://talkpython.fm#play-at) of get some help enforcing as well. It was too much work, but it's not too much work for you, AI, because you don't get tired, so you do it. Yeah, exactly.
        

[38:38](https://talkpython.fm#play-at) Yeah. What about type int? Does that play into anything that you consider? If I say it's an int versus a string, does it communicate, oh, you'd have to pass an integer here? Yeah, yeah, we do. So we
        

[38:50](https://talkpython.fm#play-at) generate the JSON schema, both from the documentation for the parameters, as well as the types associated with them. So that helps the model kind of align to... Yeah, that's very cool. I see also that it says
        

[39:04](https://talkpython.fm#play-at) an MCP is supported. Yes. What does that mean?
        

[39:08](https://talkpython.fm#play-at) Yeah. So MCP stands for model context protocol. And as of now, MCP, the protocol has specs for a lot of things. But the thing that it's most popular for is kind of having a specification for what tools
        

[39:23](https://talkpython.fm#play-at) should look like. And so MCP clients can use tools provided on MCP servers. And this means basically
        

[39:31](https://talkpython.fm#play-at) that you can use tools provided elsewhere. So not just in your own code that have a tinder.
        

[39:38](https://talkpython.fm#play-at) So that means that you can plug in an MCP server as basically as a custom tool to this. Not that it itself does MCP server stuff, but it can consume MCP servers. Is that correct?
        

[39:51](https://talkpython.fm#play-at) Yes. So you can fetch tools from MCP servers to use in your agents, which is really helpful if you want to use tools defined by others or maybe defined by others, you know, on a team adjacent to yours, things like that.
        

[40:05](https://talkpython.fm#play-at) Yeah. Well, I think the world sleeps a little bit on MCP servers. I think we could do a lot of neat stuff if more AI support them. You know, Claude Code, Cursor, Claude, just no adjectives. Those
        

[40:17](https://talkpython.fm#play-at) all support MCP servers. But for example, ChatGPT doesn't, right? And that's probably the biggest one people use. But if you could say, I know it's got connect my calendar or three other things of all the
        

[40:28](https://talkpython.fm#play-at) possible data sources in the world. But you know, you could have a lot more things if there was a little bit more support for this stuff. But it's cool that you all support it.
        

[40:35](https://talkpython.fm#play-at) Yeah, definitely. I think it just helps a lot with like cross team collaboration. And then also just like general community collaboration, right? Like if there's some great idea for a tool, someone's probably implemented it somewhere. It's nice to have that standardized interface.
        

[40:49](https://talkpython.fm#play-at) Yeah. Yeah. The other thing I think is just the timeliness and the accuracy of the data. Because when you call it MCP server, you're basically just calling an API and it can give you back the data.
        

[40:59](https://talkpython.fm#play-at) Whereas, you know, ask if there was a weather MCP server, for example, instead of saying, what's the weather? It's like, well, my training data goes back to January, 2025. So then the weather, you're like, that is unhelpful to me. I want to know what the weather is now, right? It could ask
        

[41:13](https://talkpython.fm#play-at) exactly what it is. So I created MCP server for Talk Python for people who don't know. And you can plug it in Claude and other things. You can say, what's the latest episode or what are the
        

[41:23](https://talkpython.fm#play-at) last five episodes? And if I published an episode 10 seconds ago, it'll show up if you ask the AI, right? I think that's one of the big benefits. That plus access to data that's like private,
        

[41:34](https://talkpython.fm#play-at) you know? Yeah. Yeah. It's very helpful. And I think another thing to like highlight on this page is we support like using any model, which is really nice. So you don't have kind of this like
        

[41:48](https://talkpython.fm#play-at) vendor lock in, like the same flexibility that you get from, you know, being able to use tools from any provider. It's nice to be able to switch models based on your use case.
        

[41:59](https://talkpython.fm#play-at) Yeah. That's super cool. So for example, if you use Claude Code, you get to pick anything long as it's a Anthropic model, you can pick that one, right? Right. Right. Whereas this, you could pick anything.
        

[42:08](https://talkpython.fm#play-at) Could I pick, so I'm running on my Mac mini pro. It's a little bit better at those things.
        

[42:14](https://talkpython.fm#play-at) I'm running the OpenAI, open weights model locally, like the 20 billion parameter one. And I can, I got it set up so I can do basically treat it as an OpenAI API endpoint. Could I plug that in here
        

[42:28](https://talkpython.fm#play-at) and then talk to my Mac mini instead of talking to a cloud frontier model? Yeah. Yeah, you could.
        

[42:34](https://talkpython.fm#play-at) And so this is, you know, kind of been motivated by our like open source philosophy and like foundation, but you can use any, any model. We have tons of integrations in LangChain for all sorts of
        

[42:47](https://talkpython.fm#play-at) providers, including open source model adapters. And then it's also cool. Your, your sub agents can use different models than your main agent. So you might want sub agents to use like a cheaper and
        

[43:00](https://talkpython.fm#play-at) faster model inherently, right? Cause they should be handling kind of smaller tasks.
        

[43:04](https://talkpython.fm#play-at) Interesting. Yeah. Yeah. I think that is a pattern that people use. They sort of plan with the higher model, maybe plan with Opus, but then you execute with Sonnet or something like that. If you're in the cloud world that I think that can be really powerful because once you get
        

[43:18](https://talkpython.fm#play-at) everything set straight and you got the to do's broken down and the sub agents, you're right. It's a much smaller job to address the pieces. Also you got a CLI. See? Yeah. Very exciting. So the deep
        

[43:30](https://talkpython.fm#play-at) agent CLI is kind of our coding agent. You can think of it as analogous to Claude Code.
        

[43:36](https://talkpython.fm#play-at) we use it internally at LangChain, opposed to, as opposed to Claude Code. and enjoy some of those features. Like, we support streaming, which is really nice. So you can actually see like,
        

[43:49](https://talkpython.fm#play-at) you know, word by word outputs, which is kind of nice from like an end user perspective.
        

[43:54](https://talkpython.fm#play-at) and then the model switching and, built in memory and things like that. so basically CLI built on top of the deep agents, open source harness. Nice. let me go back real quick to this
        

[44:06](https://talkpython.fm#play-at) different model. So here it says OpenAI colon GPT-4o does it basically just know how to talk to OpenAI and then it, you've got to set an environment variable or something to specify your
        

[44:18](https://talkpython.fm#play-at) API key or how does it get connected behind the scenes? Yeah. that's exactly right. So you can set your, API key and environment variables. You could also pass it in explicitly here if you wanted
        

[44:30](https://talkpython.fm#play-at) to do that. I think it's really, not like the best practice, but, we deep agents is built
        

[44:37](https://talkpython.fm#play-at) on top of LangChain, which is kind of our, tool for like standardizing using different, models.
        

[44:45](https://talkpython.fm#play-at) and so we, you know, have standard content blocks that represent, different types of messages and that's like standardized across providers and models. and so we use LangChain under the hood
        

[44:56](https://talkpython.fm#play-at) to talk with all these different providers and then provide you the end user with kind of a unified experience. Nice. Yeah. So people who know LangChain or LangGraph, a lot of this is layered on,
        

[45:06](https://talkpython.fm#play-at) this is kind of on top of all that, right? Yeah, exactly. So it's actually built on both LangChain and LangGraph. so we think of LangGraph as like our agent runtime. This is like, you know,
        

[45:19](https://talkpython.fm#play-at) to get really like technical with it, the graph under the hood, that's powering those like model and tool call iterations and streaming and LangGraph also powers. Like if you actually want
        

[45:31](https://talkpython.fm#play-at) to deploy your agent, it's kind of the framework that, enables that with like durability and, and all of those like, you know, production grade features. then LangChain itself is, what we
        

[45:44](https://talkpython.fm#play-at) call an agent framework that's different from an agent harness. Like it doesn't have all these things built in under the hood. but it just has those like agent building blocks. and then deep agents
        

[45:55](https://talkpython.fm#play-at) is the agent harness where we plug in all of that other logic. Got it. Okay. Very cool. Yeah. It says the create deep agent returns a compiled LangGraph graph. So there you go, right? Yep. Yep. Um,
        

[46:07](https://talkpython.fm#play-at) one other thing I forgot to mention, just we'll bring it up here is, one of the most important parts of our harness is summarization. so if you have a really long conversation with like Claude Code,
        

[46:18](https://talkpython.fm#play-at) you might see it say like compacting and then it'll kind of spin for a minute or two. that's because you've actually hit or you're close to hitting the context limit, the context window
        

[46:29](https://talkpython.fm#play-at) limit for that model you're using. and so we see with these like long running long horizon tasks that effective summarization and compaction is super important. And so we basically guarantee
        

[46:40](https://talkpython.fm#play-at) with deep agents that you're never going to like hit your context overflow error because under the hood, we'll kind of keep track of things and, and summarize as we go. I love it. Okay. Yeah.
        

[46:49](https://talkpython.fm#play-at) That kind of brings us maybe to the, these life cycle events and middleware, I think a little bit. So this is an interesting idea because you have all these different capabilities that are,
        

[47:00](https://talkpython.fm#play-at) I guess I saw them middleware. I know where there's some, there's a list somewhere, I'm sure, but you can plug into what happens before code is sent to the model or what happens for each step
        

[47:14](https://talkpython.fm#play-at) and things like that. Right. Maybe maybe more about this. Yeah, sure. I'll send, I sent you the link for, I think we have a lot of, a lot of, middleware content on our docs. there we go.
        

[47:27](https://talkpython.fm#play-at) Yeah, perfect. So middleware is kind of this innovation that we shipped with LangChain 1.0 in October. and it's kind of the like intermediate step between it's what powers,
        

[47:41](https://talkpython.fm#play-at) or enables the harness. And so, we have that core model and tool calling loop, but you can imagine you might want to kind of hook into behavior around both of the model and tool
        

[47:53](https://talkpython.fm#play-at) kind of nodes. and I'll, I'll give some examples of what that might look like in context.
        

[47:58](https://talkpython.fm#play-at) So before your model runs, you might want to check if you need to summarize and do that before the model call, after the model runs and before you call a tool, you might want to check if, that
        

[48:12](https://talkpython.fm#play-at) tool requires a human in the loop to like approve, before that kind of sensitive tool call runs.
        

[48:18](https://talkpython.fm#play-at) The classic example there is like, if the model calls the send email tool, you might want to, like approve that email before it's, you know, sent to your boss, for example.
        

[48:27](https://talkpython.fm#play-at) Yeah. Do stock trade.
        

[48:28](https://talkpython.fm#play-at) Yeah. Yeah, exactly. and then, there's, some less flashy, but you know, still important things like, just robustness and like fallbacks, model fallbacks or tool
        

[48:42](https://talkpython.fm#play-at) retries or things like that, that you can support via middleware.
        

[48:46](https://talkpython.fm#play-at) Okay. Yeah. And you can build your own and as well, for sure. And there's also some that are prebuilt, right? Like you, you said some human in the loop summarization, personal information
        

[48:57](https://talkpython.fm#play-at) detection. That's pretty interesting. The to-do list or the retry.
        

[49:04](https://talkpython.fm#play-at) Yeah. Yeah. So we kind of tried to like standardize, and, and just observe common patterns that we saw for folks building agents and, expose some common middlewares, but you can kind of build your
        

[49:16](https://talkpython.fm#play-at) own as well. and then deep agents uses middleware to power all of the things we're doing, for our agents.
        

[49:24](https://talkpython.fm#play-at) Yeah. And I saw one of the presentations y'all did that, you know, Claude Code and so on, they have these, these types of custom tools and middleware as well. So people probably are familiar
        

[49:35](https://talkpython.fm#play-at) with experiencing them, just not quite realizing exactly how, right?
        

[49:39](https://talkpython.fm#play-at) Yeah. Yeah. I think that's true. And like middleware is generally just kind of a common software pattern, right? Like you want to hook into life cycle events and perform logic that's, you know, appropriate for your application.
        

[49:51](https://talkpython.fm#play-at) Yeah. A hundred percent. All right. Let's, we're getting short on time. Let's talk examples before we run out of time. And I think this will lead us into a couple more interesting elements that we maybe haven't necessarily talked about. So I'll link to this examples
        

[50:04](https://talkpython.fm#play-at) subfolder here on, on the GitHub repo. So we've got a deep research one, which I think is really cool.
        

[50:10](https://talkpython.fm#play-at) The content builder for writing the text to SQL agent, Ralph mode. I've, I've yet to experience Ralph mode. I haven't done anything with that, but that's just the, I don't care. Just keep trying.
        

[50:21](https://talkpython.fm#play-at) If you fail, just keep trying. All right. Sort of mode. Ralph from Simpsons South Park. I don't know one of them. Yeah. Anyway, maybe we could talk about the deep research one first, because it's got a cool
        

[50:32](https://talkpython.fm#play-at) UI component. So like you can run this in both as a Jupyter notebook and play with it or a LangGraph dev UI. And then you also have some other UIs as well, right? I can't remember.
        

[50:45](https://talkpython.fm#play-at) I feel like there's a third, third UI that you all support for this, this kind of stuff. So maybe let's talk through this one and then tell me, tell me about it. Yeah, definitely. So the idea with
        

[50:55](https://talkpython.fm#play-at) deep research is that you are going to be doing a pretty long running task. Like you want your model to be really thorough. And then one of the most important tools for deep research is web search,
        

[51:08](https://talkpython.fm#play-at) because you want to get like current and relevant information. So we use Tavily for web search.
        

[51:14](https://talkpython.fm#play-at) And then I can talk a little bit about our like UI as well. So we, I guess I'll, yeah, I can chat a little bit about our UI, but generally it's, it's hard to build agents, right? Like we talk about prompt
        

[51:28](https://talkpython.fm#play-at) optimizations and things. And LangChain, the company provides a lot of tools to make it easier to build agents. And so one of them is this kind of agent viewer where you can see each of the like steps
        

[51:40](https://talkpython.fm#play-at) in your agent. In this case, we see like the summarization middleware step and then the model and tool steps. And then, yeah, so, so that kind of makes it easier to like step through and understand the behavior of your model.
        

[51:54](https://talkpython.fm#play-at) Right. Ultimately, as we talked about, it's a bit of a LangGraph thing anyway. So it shows you how that all comes together, right?
        

[52:03](https://talkpython.fm#play-at) Yes. Yep. And you can see on the right, we're looking at kind of the trace of things. And so we see like the to do middleware being called and other tool calls, et cetera. So we try to really
        

[52:16](https://talkpython.fm#play-at) make those like agent behavior primitives first class. So you can really narrow into like, what is the model doing once I invoke it?
        

[52:26](https://talkpython.fm#play-at) Yeah. So that's LangGraph dev for this project. You can also do the notebook and there's a really nice, actually nice visualizations in there for, you know, what is the prompt that is the result and
        

[52:38](https://talkpython.fm#play-at) so on. Right. I think it comes out pretty, maybe I can open up the notebook and it's got the results cached. You know, sometimes that's, that's both a benefit and a drawback in notebooks, but right now
        

[52:47](https://talkpython.fm#play-at) would be a benefit of some of the, yeah, for example, has like a really nice display of what the prompt was with formatting and so on. Right. And then there's a third one, if I remember correctly,
        

[52:57](https://talkpython.fm#play-at) that's kind of like a web UI for like ChatGPT or Claude, just no adjectives.
        

[53:03](https://talkpython.fm#play-at) Yeah. So we had kind of a deep research UI that we built out as a POC around like, we just want to make this easy for folks to view. I will note, we have recently rolled out a product
        

[53:16](https://talkpython.fm#play-at) called Agent Builder, which is like a no code agent builder powered by deep agents. And it is, you know, somewhat inspired from this UI. It basically is like a chat interface for an agent
        

[53:28](https://talkpython.fm#play-at) that gives you insights into the tool calls that are happening and things like that. That's kind of our like modern version of how you would probably go about seeing this in a UI. Sure. Okay. What else?
        

[53:39](https://talkpython.fm#play-at) I guess a couple of other examples here. What's this text to SQL story? Yeah. So the idea here is that
        

[53:49](https://talkpython.fm#play-at) if an agent has some information about data structure for your, you know, for your database, et cetera, it is much easier as a like person to learn about that data. If you can kind of ask
        

[54:03](https://talkpython.fm#play-at) just like regular questions and the agent can convert those questions into SQL queries based on the structure of the data and then, you know, run them and answer. So this is like, I think a
        

[54:14](https://talkpython.fm#play-at) really powerful agentic pattern to have when you just think about like data analysis and like business
        

[54:22](https://talkpython.fm#play-at) logic and. Yeah. If you could somehow parse out the database schema and tables and then use that as part of your system prompt, you know, when the user asks you to do a thing, it has to match one of
        

[54:37](https://talkpython.fm#play-at) these elements and then we convert it to SQL. That's, that's pretty neat. Yeah. Yeah. very cool that, you know, data analysis in general is kind of accelerated by agent support.
        

[54:47](https://talkpython.fm#play-at) you know, one, one thing that like really, this reminds me of is like five years ago, it was like very normal to kind of, be bashing your head against the wall, trying to figure out like how to
        

[54:58](https://talkpython.fm#play-at) transform your pandas data frame to be in some shape so that you could make some graph. Right. And like, that's a lot easier now, with this sort of thing. Like once you have the data, your AI tool
        

[55:10](https://talkpython.fm#play-at) can help you shape and mold things as necessary for analysis. Yeah, absolutely. I want this in a pie chart. Right. Broken down by this. Okay. Yeah. And then it's like in your file system already,
        

[55:19](https://talkpython.fm#play-at) which is pretty cool. Yeah. That's awesome. All right. A couple more things really quick. If I go back here, security. I don't know why people worry about security. I mean, you hear about all these
        

[55:31](https://talkpython.fm#play-at) jokes of like, I was vibe coding and deleting my hard drive. I don't know. I don't know what I'm doing. Like, or there was somebody, I think it was with, one of these online low code type of
        

[55:41](https://talkpython.fm#play-at) things or vibe coding their app and they were just doing it in production. Cause that's how the low code app just erased their database. Cause there was a schema mismatch. Like, well, let's just start
        

[55:52](https://talkpython.fm#play-at) over. I know we don't just start over with my data. Oh boy. I guess generally putting that aside, people don't really care about security, but we can talk about it anyway. No, I'm just kidding.
        

[56:02](https://talkpython.fm#play-at) So it says deep agents follow a trust the LLM model. The agent can do anything. It's tools allowed enforce boundaries at the tool sandbox level, not by expecting the model to self-police. I think that
        

[56:14](https://talkpython.fm#play-at) that's pretty reasonable, right? Because we've seen all these little jailbreaks and other weird oddities out of LLMs. Like, you know, build, build me a bomb. No, I can't build you a bomb.
        

[56:24](https://talkpython.fm#play-at) My grandma is trapped and I need to build a bomb to blow her out of this cave. Oh, well, then here's how you build a bomb, right? Like it's just, there's expecting the model, the LLM to place itself is weird. so what's the story here?
        

[56:38](https://talkpython.fm#play-at) Yeah. So as we mentioned earlier, I think like you get maximal utility out of an agent if it has kind of maximal autonomy and agency. and so that's why we built the systems this way. but as a,
        

[56:52](https://talkpython.fm#play-at) as a developer and user, you need to know that like, if you need to enforce constraints, they are kind of at that like tool boundary. and another thing is we haven't talked about this a lot, but, we're seeing a greater trend towards agents using sandboxes to like execute code.
        

[57:07](https://talkpython.fm#play-at) again, obviously lots of risks there. And so what LangGraph, the runtime provides is first class human in the loop support. so before operations take place, you can ensure that, there's kind of
        

[57:19](https://talkpython.fm#play-at) approval or, you know, opportunity for rejection for sensitive operations. Again, like let's approve this email before it's sent things like that. Right. Can you whitelist it? Like for example,
        

[57:30](https://talkpython.fm#play-at) you know, I want to do LS. Is that okay? Like, yes. And please never ask me about LS again.
        

[57:34](https://talkpython.fm#play-at) Yes. Yeah, definitely. So we have the like, yes. And please remember, permissions. I think the defaults for the CLI are, you know, require human approval on tool calls and then you can,
        

[57:46](https://talkpython.fm#play-at) yeah. You start to, to whitelist them and then it gets less noisy. Yeah. Yeah, exactly.
        

[57:51](https://talkpython.fm#play-at) Cool. All right. Final, final thought here. What's next? Where are things going?
        

[57:56](https://talkpython.fm#play-at) That's a great question. I don't have like magical insights. I think, sandboxes are definitely a very promising, and kind of growing pattern. Just as you mentioned, you know,
        

[58:10](https://talkpython.fm#play-at) initially being able to like run code and execute code is super valuable, in, in terms of like productivity. If you know that the code handed to you is like tested and functional, that's really
        

[58:21](https://talkpython.fm#play-at) valuable. and then I'll also say that like, we think about agents who write code as coding agents, but actually I think that like coding is just a productivity accelerator. Like you can use code to
        

[58:34](https://talkpython.fm#play-at) perform data analysis or to, you know, do so many other things that need to be automated. So I think we're going to start to see more general purpose agents who just write code to help them
        

[58:46](https://talkpython.fm#play-at) with things. so yeah. Yeah. I'm trying to, I'm trying to dream up what I'm, I might build with this. There was this joke, joke that I did on the Python bites podcast. And it just, it comes to mind.
        

[58:57](https://talkpython.fm#play-at) And now there's this, this character putting their hands up. It's a silent side project. The new side project is talking. And I feel like that's how my life is. There's, it was just so exciting.
        

[59:08](https://talkpython.fm#play-at) You can build so many things with AI, have AI build the thing or any with this, like imbue it with really powerful agentic capabilities. And there's just, I think the real challenge is finding time and
        

[59:18](https://talkpython.fm#play-at) focusing and finishing in anything at all. Cause it's just so exciting to try ideas out, you know?
        

[59:23](https://talkpython.fm#play-at) Yeah. Yeah, definitely. It is nice that it's easier to, you know, get further with ideas in a very short period of time due to these tools. Yeah. Yeah. I think it's great. Cause you can, you can test out an idea and go, ah, that's not that great. Actually, this is a really good idea
        

[59:38](https://talkpython.fm#play-at) that I'm going to keep going, you know? So that's really cool. Anything new or anything planned with deep agents that's coming that we don't know about, or it's not obvious I haven't talked about yet.
        

[59:47](https://talkpython.fm#play-at) I think we'll probably release a more detailed roadmap soon. I mean, we're, we're really sprinting towards, I think a 1.0 eventually. we just kind of want to solidify
        

[01:00:00](https://talkpython.fm#play-at) those like core primitives. Like I mentioned, we have, file systems that you can use like remote file systems as well. Like, you know, an S3 backend or a database backed backend. And so,
        

[01:00:14](https://talkpython.fm#play-at) yeah, just, excited to kind of keep sprinting on what the latest and greatest trends are in agent harnesses. one resource that I would, point to, let me see if I can find the
        

[01:00:25](https://talkpython.fm#play-at) link is, more and more we're seeing with, with agent development that you're not really able to do it well. If you can't like look under the hood and see what your agent's doing. and so
        

[01:00:38](https://talkpython.fm#play-at) we just released this blog post on, harness engineering. So basically like how we go about improving our harness systematically. and it was very dependent on looking at our traces of,
        

[01:00:51](https://talkpython.fm#play-at) you know, agent behavior and like even using LLMs to analyze those traces. and yeah, like the tail is in the trace. So I guess, lesson here just being, it's really cool to use traces to self-improve,
        

[01:01:06](https://talkpython.fm#play-at) our own, you know, harness and things like that.
        

[01:01:09](https://talkpython.fm#play-at) Yeah. That's wild to actually see the steps and, and I guess you could probably even look at like failures and retries and how does the context vary?
        

[01:01:19](https://talkpython.fm#play-at) Yeah. Yeah, exactly.
        

[01:01:20](https://talkpython.fm#play-at) Interesting. Okay. Well, very cool. Thank you, Sydney. Maybe final call to action. People want to get started with deep agents. What do they do?
        

[01:01:28](https://talkpython.fm#play-at) You do pip, uv pip install deepagents. yeah, but super easy to get started in just a couple lines of code. and we're an open source team. So always happy to, answer questions or accepting contributions, et cetera.
        

[01:01:43](https://talkpython.fm#play-at) Awesome. Do you have a discord channel or something like that?
        

[01:01:45](https://talkpython.fm#play-at) I don't like a community group.
        

[01:01:48](https://talkpython.fm#play-at) We do have a forum, that we, yeah, I would, I would direct people to the forum generally.
        

[01:01:54](https://talkpython.fm#play-at) Sweet. All right. Very interesting. What a wild time. What a weird and interesting time we live in, but very cool.
        

[01:02:00](https://talkpython.fm#play-at) Yeah. Great to, great to chat with you about all things deep agents. Thanks for having me on.
        

[01:02:04](https://talkpython.fm#play-at) Yeah. You bet. Keep up the good work. Talk to you next time.
        

[01:02:07](https://talkpython.fm#play-at) This has been another episode of Talk Python To Me. Thank you to our sponsors. Be sure to check out what they're offering. It really helps support the show. This episode is brought to you by Sentry.
        

[01:02:16](https://talkpython.fm#play-at) You know Sentry for the error monitoring, but they now have logs too. And with Sentry, your logs become way more usable, interleaving into your error reports to enhance debugging and
        

[01:02:26](https://talkpython.fm#play-at) understanding. Get started today at talkpython.fm/sentry. And it's brought to you by Temporal. Durable workflows for Python. Write your workflows as normal Python code and Temporal
        

[01:02:38](https://talkpython.fm#play-at) ensures they run reliably, even across crashes and restarts. Get started at talkpython.fm/Temporal.
        

[01:02:45](https://talkpython.fm#play-at) If you or your team needs to learn Python, we have over 270 hours of beginner and advanced courses on topics ranging from complete beginners to async code, Flask, Django, HTMX, and even LLMs. Best of all,
        

[01:02:59](https://talkpython.fm#play-at) there's no subscription in sight. Browse the catalog at talkpython.fm. And if you're not already subscribed to the show on your favorite podcast player, what are you waiting for? Just search for Python in your podcast player. We should be right at the top. If you enjoy that geeky rap song,
        

[01:03:13](https://talkpython.fm#play-at) you can download the full track. The link is actually in your podcast blog or share notes.
        

[01:03:17](https://talkpython.fm#play-at) This is your host, Michael Kennedy. Thank you so much for listening. I really appreciate it.
        

[01:03:22](https://talkpython.fm#play-at) I'll see you next time.
        

[01:03:22](https://talkpython.fm#play-at) Talk Python for some time.
        

[01:03:34](https://talkpython.fm#play-at) Talk Python for some time.
        

[01:03:35](https://talkpython.fm#play-at) Yeah we ready to roll Upgrading the code No fear of getting old We tapped into that modern vibe Overcame each storm
        

[01:03:47](https://talkpython.fm#play-at) Talk Python To Me, async is the norm
