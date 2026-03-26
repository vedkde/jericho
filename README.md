# Jericho – Debugging Environment

A lightweight, OpenEnv-style reinforcement learning environment where AI agents learn to fix buggy Python code by interacting with an API.

## Overview

This project provides a structured environment for training and evaluating code-fixing agents. Agents iteratively edit code and run tests, receiving rewards based on improvements in correctness.

The system is designed to simulate real-world debugging workflows and supports multiple difficulty levels.

## Features

- REST API built with FastAPI
- Step-based environment (reset, edit, run tests)
- Reward function for reinforcement learning
- Multiple tasks: easy, medium, hard
- Pytest-based evaluation
- Compatible with LLM agents (Gemini, Groq, etc.)

## Project Structure

```
api/            # FastAPI routes (env, tasks, grader, baseline)
env/            # Core environment (state, executor, reward)
tasks/          # Task definitions and registry
agents/         # Agent scripts (Gemini, Groq, baseline)
run.py          # Starts the API server
```

## Installation

```bash
pip install -r requirements.txt
```

## Running the Server

```bash
python run.py
```

Server will start at:
http://localhost:8000

## API Endpoints

- POST /env/reset — Initialize a new session with a task
- POST /env/step — Take an action (edit or run tests)
- GET  /env/state/{session_id} — Get current state
- GET  /tasks — List available tasks
- GET  /tasks/{task_id} — Get task details
- POST /grader/ — Evaluate final code

## Actions

### Run Tests
```json
{ "type": "run_tests" }
```

### Edit Code
```json
{
  "type": "edit_function",
  "function_name": "function_name",
  "new_code": "def function_name(...): ..."
}
```

## Reward System

- Positive reward for passing more tests
- Penalty for regressions or broken code
- Small step penalty to encourage efficiency
- Bonus for solving all tests

## Tasks

- Easy: Basic logic bugs
- Medium: Mathematical/statistical errors
- Hard: Multi-function pipeline with interacting bugs

## Usage

1. Start the server
2. Run an agent script (e.g., Gemini or Groq)
3. Agent interacts with environment:
   - Runs tests
   - Edits code
   - Improves solution iteratively
4. Final solution is graded
