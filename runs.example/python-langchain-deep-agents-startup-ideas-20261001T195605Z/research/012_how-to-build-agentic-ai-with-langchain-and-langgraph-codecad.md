---
source_id: S-12
url: https://www.codecademy.com/article/agentic-ai-with-langchain-langgraph
title: How to Build Agentic AI with LangChain and LangGraph | Codecademy
author: Codecademy
published: null
fetched: '2026-10-01T19:57:51Z'
word_count: 2331
---
# How to Build Agentic AI with LangChain and LangGraph | Codecademy

[Articles](https://www.codecademy.com/articles)

# How to Build Agentic AI with LangChain and LangGraph

You ask ChatGPT to find the best laptops for [programming](https://www.codecademy.com/article/what-is-programming), and it does. Then you ask it to compare them, and it tries. Next, you ask it to pick one based on your budget and previous preferences—and it forgets. Why? Because most LLMs don’t reason across steps or remember goals. That’s where agentic AI comes in.

## What is agentic AI?

Imagine an AI that doesn’t just respond to prompts but actively makes decisions, gathers information, uses tools, stores memory, and works toward a goal without needing you to hold its hand at every step. That’s what agentic AI is all about.

**Agentic AI** refers to a new class of intelligent systems where [large language models (LLMs)](https://www.codecademy.com/resources/docs/general/llm) act autonomously using a combination of memory, tools, logic, and interaction. Rather than generating isolated responses, these agents behave more like problem solvers, capable of carrying out complex, multistep tasks. Some key characteristics of agentic AI are as follows: 

- **Autonomy:** The agent takes initiative, plans, and makes decisions.
- **Tool Use:** It can call[APIs](https://www.codecademy.com/resources/docs/general/api) , perform searches, trigger functions, or interact with files.
- **Memory:** The agent retains short-term or long-term context to maintain continuity across steps.
- **Reasoning:** It can break down a task, evaluate responses, and loop through logic chains.

Some real-world examples of agentic AI are as follows:

- Research assistants that explore, summarize, and cite sources.
- Coding copilots that can plan, write, and debug code.
- Auto-email agents that read emails, draft responses, and take follow-up actions.

These systems represent a shift from static prompt-response LLMs to interactive, goal-oriented agents. To build such agents, you need powerful frameworks like LangChain and LangGraph.

Let’s understand why LangChain is the go-to framework for building agentic AI.

## Why use LangChain for agentic AI?

Building an agent isn’t just about generating responses—it’s about giving your AI a structure to think, decide, and act. That’s where LangChain comes in.

LangChain is a robust framework that helps developers define the logic, tools, memory, and workflows an agent needs to function more intelligently and, in a goal driven manner. Instead of prompting an LLM in isolation, LangChain lets you design how an agent should behave step by step, like how it chooses tools, retains memory, or interacts with a user.

LangChain consists of the following core concepts:

- **Chains:** Sequences of steps that process input → transform it → produce output.
- **Agents:** Dynamic systems that decide what to do next based on the current context.
- **Tools:** External functions or APIs the agent can call—like a calculator, search API, or code interpreter.
- **Memory:** Mechanisms store and recall past interactions or facts across conversations.

LangChain supports different agent types, from **reactive agents** responding to one task at a time, to **conversational agents** tracking history and planning multistep actions. Here are some real-world use cases of LangChain: 

- Coding copilots that use online docs and run code
- Travel planners that interact with search and map APIs
- AI tutors that remember student progress and adapt lessons
- Data analyzers that ingest documents, summarize, and answer questions

LangChain provides modular building blocks for designing capable agents, but agents still need a brain that can coordinate decisions, loop over logic, and manage branching workflows. And that’s where LangGraph takes over.

## What is LangGraph

Think of LangGraph as the graph engine that powers intelligent AI workflows. While LangChain provides the building blocks for agents, LangGraph helps you connect those blocks into complex, stateful workflows with branching, looping, and multi-agent coordination.

Built on top of LangChain, LangGraph lets you define:

- **Nodes:** Individual steps or actions in your workflow, like asking a question or calling a tool
- **Edges:** Paths that connect nodes and determine the flow
- **States:** Data and context stored across steps to maintain memory and decision history
- **Conditional transitions:** Logic to decide which path to take next based on agent outputs or external conditions

This makes LangGraph ideal for orchestrating agents that need to perform iterative tasks, coordinate multiple agents, or manage workflows that aren’t just linear sequences.

It also supports persistent memory and state storage, so your AI agents can remember essential details throughout long-running processes.

Now that you know what LangChain and LangGraph are, let’s see how to combine them to build a powerful multistep research agent.

## Build a multistep research agent using LangChain and LangGraph

Let’s build a research assistant that searches, reasons, summarizes, and remembers. This agent will:

- Take a user query
- Search the web
- Summarize the results
- Store the result in memory
- Respond back with a final summary

We’ll use LangChain to create tools and define an LLM, and LangGraph to manage the step-by-step workflow through modular nodes.

### Step 1: Install the required packages

To get started, install the necessary Python packages:

pip install langchain langgraph langchain_ollama langchain-community

**Note:** If you get an error installing `langchain_ollama`, use the alternative command `pip install -U langchain_ollama` to install it. 


Here:

- `langchain` : The Framework to build applications powered by language models.
- `langgraph` : A framework extension for defining complex, stateful workflows using directed graphs with LangChain components.
- `langchain_ollama` : Enables local LLM integration via Ollama, allowing you to run models like Mistral or LLaMA2 directly on your machine without cloud APIs.
- `langchain-community` : A collection of community-maintained integrations (e.g.,`SerpAPIWrapper` , etc.) for tools, models, and APIs used with LangChain.

### Step 2: Generate API key

We’ll use the following API:

- **SerpAPI** : We need a search engine interface to simulate real-time research. SerpAPI wraps Google Search and returns results in a structured format.

**Create SerpAPI key** 

- Visit the official [SerpAPI](https://serpapi.com/) website
- Sign up and go to your dashboard
- Copy your API key

### Step 3: Setting up API key in the terminal

To set up the API key in Windows, use the following command:

setx SERPAPI_API_KEY=your-serpapi-key

To set up the API key in Linux/macOS, use the following command:

export SERPAPI_API_KEY=your-serpapi-key

**Note:** Replace `your-serpapi-key` with the actual API key that you generated in step 2. 


### Step 4: Install Ollama and pull `llama2`

To run your language model locally, we’ll use Ollama, a powerful and easy-to-use tool for serving open-source LLMs on your machine.

Head to the official [Ollama website](https://ollama.com) and follow the installation instructions based on your OS. 

Next, we need to pull `llama2`, which is a high-performance open-source language model developed by Meta, suitable for summarization, chat, and reasoning tasks. 

Use this command in your terminal to download it locally via Ollama:

ollama pull llama2

Once downloaded, Ollama will run the model in the background when called from your Python code.

### Step 5: Set up the API key in the environment

From this point onward, all the code will go into a single Python file (e.g., `research_agent.py`) to create and run your LangGraph-powered agent. 

Start writing the code by accessing your environment variables using `os.getenv()`: 

import osSERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")print("SERPAPI_API_KEY:", SERPAPI_API_KEY)if not SERPAPI_API_KEY:raise ValueError("Please set SERPAPI_API_KEY environment variables")

This code ensures your key is available to authenticate your API calls. If not found, it throws an error.

### Step 6: Initialize the LLM and tools

After setting up the API, we’ll initialize the local language model and set up the web search tool to power our agent’s capabilities.

from langchain_ollama import ChatOllamafrom langchain_community.utilities import SerpAPIWrapper# Initialize LLMllm = ChatOllama(model="llama2", temperature=0)# Web search tool using SerpAPIsearch = SerpAPIWrapper(serpapi_api_key=SERPAPI_API_KEY)

Here:

- `ChatOllama` : loads the LLaMA 2 model locally using Ollama, allowing you to run the language model without needing an internet connection or paid API.
- `SerpAPIWrapper` : Sets up a web search tool that uses your SerpAPI key to fetch real-time search results from the internet.

### Step 7: Define the state schema

Next, we define a state schema to manage and track the data as it flows through each step of the agent’s workflow.

from typing import TypedDictclass ResearchState(TypedDict, total=False):query: strsearch_results: strsummary: strstore_message: strresponse: str

This code defines a custom data structure using Python’s `TypedDict`. It acts like a [dictionary](https://www.codecademy.com/resources/docs/python/dictionaries) but with defined keys and their expected value types.

### Step 8: Define each tool (function)

Let’s now define the core tools that perform specific tasks in our research workflow, i.e, searching, summarizing, storing, and retrieving information.

1. **Web search** 

def web_search_tool(query: str) -> str:print(f"Searching the web for: {query}")results = search.run(query)return results

This function uses the SerpAPI tool to perform a live web search based on the user’s query. It returns the raw search results as a text string.

2. **Summarization** 

from langchain.chains import LLMChainfrom langchain.prompts import PromptTemplatedef summarize_tool(text: str) -> str:# Basic prompt to summarize textprompt = PromptTemplate(input_variables=["text"],template="Summarize the following text in a concise way:\n\n{text}")chain = prompt | llmresult = chain.invoke({"text": text})return result.content if hasattr(result, "content") else str(result)

Here:

- `PromptTemplate` creates a prompt that asks the LLM to summarize the given text concisely.
- The line `chain = prompt | llm` builds a simple pipeline where the prompt is passed directly to the local LLM (llm) for processing.
- The `invoke()` method runs the chain with input text, and the result is returned as a string, handling both object and plain text formats.

3. **Store result** 

memory_store = {}def store_tool(data: dict) -> str:query = data.get("query")summary = data.get("summary")if query and summary:memory_store[query] = summaryreturn f"Stored summary for query: '{query}'"return "No data to store"

This function saves the summary in a dictionary using the query as the key. If the storage is successful, it returns a confirmation message.

4. **Retrieve result** 

def respond_tool(query: str) -> str:summary = memory_store.get(query)return f"Final Answer:\n{summary}" if summary else "Sorry, no summary found for your query."

This function looks up the stored summary for a given query from memory. It returns the final answer or a fallback message if no summary is found.

### Step 9: Create LangGraph handlers

Define the logic for each step in the research workflow. These handler functions update the shared state and guide the flow between nodes in the LangGraph.

def ask_handler(state):user_query = input("What do you want to research? ")state["query"] = user_queryreturn statedef search_handler(state):query = state.get("query", "")state["search_results"] = web_search_tool(query)return statedef summarize_handler(state):state["summary"] = summarize_tool(state.get("search_results", ""))return statedef store_handler(state):state["store_message"] = store_tool({"query": state.get("query"),"summary": state.get("summary")})return statedef respond_handler(state):state["response"] = respond_tool(state.get("query"))return state

### Step 10: Build and compile the graph

Now we build the logic of the agent in LangGraph:

- Node 1: Ask – Receive the user’s query
- Node 2: Search – Call the web search tool
- Node 3: Summarize – Condense the results
- Node 4: Store – Save important findings (simulated memory)
- Node 5: Respond – Return the final output

from langgraph.graph.state import StateGraphgraph = StateGraph(state_schema=ResearchState)graph.add_node("ask", ask_handler)graph.add_node("search", search_handler)graph.add_node("summarize", summarize_handler)graph.add_node("store", store_handler)graph.add_node("respond", respond_handler)graph.set_entry_point("ask")graph.add_edge("ask", "search")graph.add_edge("search", "summarize")graph.add_edge("summarize", "store")graph.add_edge("store", "respond")research_agent = graph.compile()

This defines the flow of operations and compiles it into a runnable agent. Each `*_handler` function processes the state and passes it along the graph. You can define them using Python functions that accept a dictionary and return an updated state.

### Step 11: Run the agent

In the final step, let us run the agent using:

state = {}final_state = research_agent.invoke(state)print(final_state.get("response"))

Here:

- An empty dictionary is created to represent the initial state.
- The agent executes its workflow step-by-step using this state.
- The final summarized response is printed as the result.

Let us test this agent with a sample input as follows:

Now that you’ve built a working agent, let’s explore where LangChain + LangGraph truly shine in the real world.

## Applications of LangGraph + LangChain

LangChain + LangGraph provide a modular and graph-based design that makes them ideal for building reliable, stateful workflows that can reason, act, and adapt. Below are some impactful use cases where these tools are already making a difference:

- **Research Assistants:** Automate deep-dive research, summarize findings, and provide actionable insights.
- **Autonomous Portfolio Managers:** Monitor markets, analyze trends, and make data-driven investment decisions.
- **Enterprise AI Copilots:** Assist teams by retrieving internal knowledge, generating reports, and suggesting actions.
- **Customer Support Agents:** Resolve queries end-to-end using knowledge bases, reasoning, and task execution.

## Conclusion

In this guide, we explored how to build a multistep research agent using LangChain and LangGraph, from installing dependencies and setting the API key to creating a complete agent workflow with state handlers. We also discussed practical applications like AI copilots, research assistants, and autonomous workflow agents, showcasing how agentic AI can streamline complex tasks.

To learn more about combining language models with external knowledge sources, check out Codecademy’s [Creating AI Applications using Retrieval-Augmented Generation (RAG)](https://www.codecademy.com/learn/retrieval-augmented-generation-for-ai-applications) course. This course will help you understand how RAG techniques enhance AI capabilities for building powerful, data-driven applications.

## Frequently asked questions

### 1. What is the difference between LangChain and LangGraph?

LangChain focuses on chaining language model calls and integrating external tools, while LangGraph provides a graph-based way to manage complex multistep workflows and state transitions.

### 2. Can I use LangGraph without LangChain?

Yes, LangGraph can be used independently to create and manage agent workflows, though it often complements LangChain for language model integrations.

### 3. What are the alternatives to LangGraph?

Alternatives include other workflow orchestration tools like Airflow or Prefect, but LangGraph is specialized for AI agent state and task management.

### 4. Can I integrate LangGraph with vector stores?

Yes, LangGraph can be extended to integrate with vector stores for retrieval and semantic search functionalities.

### 5. Is LangGraph better than LangChain?

They serve different purposes: LangChain is great for chaining LLM calls, while LangGraph excels at managing complex agent workflows. They are often used together for best results.

'The Codecademy Team, composed of experienced educators and tech experts, is dedicated to making tech skills accessible to all. We empower learners worldwide with expert-reviewed content that develops and enhances the technical skills needed to advance and succeed in their careers.'

[Meet the full team](https://www.codecademy.com/pages/curriculum-developers)
