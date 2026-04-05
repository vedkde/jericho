# Jericho – Debugging Environment

A lightweight OpenEnv-compatible RL environment where AI agents fix buggy Python code by interacting with a REST API.

## Overview

Agents iteratively edit functions and run tests, receiving rewards based on improvements in correctness. Designed to simulate real-world debugging workflows across multiple difficulty levels.

## Project Structure

```
api/        # FastAPI routes (env, tasks, grader, baseline)
env/        # Core environment (state, executor, reward)
tasks/      # Task definitions and registry
run.py      # Starts the API server
inference.py # Baseline inference script
Dockerfile  # Container setup
```

## Setup

```bash
pip install -r requirements.txt
python run.py
```

Server starts at `http://localhost:8000`

## Docker

```bash
docker build -t jericho .
docker run -p 8000:8000 jericho
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/env/reset` | Start a new session |
| POST | `/env/step` | Take an action |
| GET | `/env/state/{session_id}` | Get current state |
| GET | `/tasks` | List all tasks |
| GET | `/tasks/{task_id}` | Get task details |
| POST | `/grader/` | Grade final code |

## Actions

```json
{ "type": "run_tests" }
```
```json
{
  "type": "edit_function",
  "function_name": "my_func",
  "new_code": "def my_func(...): ..."
}
```

## Reward System

| Event | Reward |
|-------|--------|
| Each step | -0.05 |
| Test newly passing | +1.0 per test |
| Regression | -0.5 per test broken |
| All tests pass | +2.0 bonus |
| Broken code | -0.3 |

## Tasks

| Task | Tests | Description |
|------|-------|-------------|
| Easy | 4 | Wrong operator and missing logic in discount calculator |
| Medium | 5 | Wrong mean, variance and std_dev in stats calculator |
| Hard | 10 | Cascading bugs across a multi-function payroll pipeline |

## Inference

```bash
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=meta-llama/Llama-3.3-70B-Instruct
export HF_TOKEN=your_token
python inference.py
```

## Baseline Scores

| Task | Score | Steps |
|------|-------|-------|
| Easy | 1.00 | 5 |
| Medium | 1.00 | 7 |
| Hard | 0.90 | 20 |
