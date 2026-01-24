# SkillNet AI SDK

[![PyPI version](https://badge.fury.io/py/skillnet-ai.svg)](https://badge.fury.io/py/skillnet-ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

**SkillNet AI** is the official Python SDK for interacting with the SkillNet platform. It allows AI Agents to **Search**, **Install**, **Evaluate** and **Create** reusable skills dynamically.

SkillNet enables agents to evolve by learning from execution trajectories and sharing capabilities via a centralized registry.

---

## 🚀 Features

- **🔍 Search**: Find skills using keywords or natural language queries.
- **📦 One-Line Installation**: Download and install skill packages directly from GitHub repositories.
- **✨ Skill Creation**: Automatically convert trajectories (agent execution logs, conversation logs ...) into structured, reusable `skill` packages using LLMs.
- **📊 Evaluation**: Evaluate and score skills for quality assurance (Safety, Completeness, Excutability, Modifiability, Cost-Aware).

---

## 📥 Installation

```bash
pip install skillnet-ai
```

---

## 🛠 Usage (Python SDK)

### 1. Search for Skills

You can search for skills using keywords or natural language (AI Search).

```python
from skillnet_ai import SkillNetSearcher

searcher = SkillNetSearcher()

# 1. Standard Keyword Search
results = searcher.search(q="pdf")

# 2. Semantic Search
results = searcher.search(q="Help me analyze financial PDF reports", mode="vector")

top_skill = results[0]
print(f"Top Skill: {top_skill.skill_name} (Stars: {top_skill.stars})")
print(f"Description: {top_skill.skill_description}")
print(f"URL: {skill.skill_url}")

```

### 2. Install a Skill

Once you have a skill's URL (usually from the search results), you can download and install it into your agent's workspace.

```python
from skillnet_ai import SkillDownloader

skill_url = "https://github.com/anthropics/skills/tree/main/skills/skill-creator"

# Downloads and extracts the skill to target_dir
skilldownloader = SkillDownloader()
local_path = skilldownloader.download(skill_url, target_dir="./my_agent_skills")

if local_path:
    print(f"Skill successfully installed at: {local_path}")
```

### 3. Create a Skill from Trajectory

Turn raw conversation logs or execution traces into a polished Skill Package (`SKILL.md`, scripts, etc.).

> **Note:** This feature requires an LLM API Key.

```python
import os
from skillnet_ai import SkillCreator

# 1. Prepare your trajectory (e.g., a conversation log)
trajectory_log = """
User: I need to rename all .jpg files in this folder to .png.
Agent: I will write a python script to iterate through the folder...
Agent: Script executed. Renamed 5 files.
"""

# Set your API key and url
api_key="sk-...",       # Your API Key
base_url="xxxxxx",      # Optional. Useful if using a proxy or compatible API

# 2. Initialize Creator
creator = SkillCreator(api_key=api_key, base_url=base_url, model="gpt-4o")

# 3. Create Skills
output_dir = "./created_skills"
created_paths = creator.create_from_trajectory(trajectory_log, output_dir=output_dir)

print(f"Created {len(created_paths)} new skills in {output_dir}")
```

### 4. Skill Evaluation

Assess the Safety, Completeness, Excutability, Modifiability and Cost-Aware of a skill before using it. This tool generates a complete evaluation based on the skill's code and documentation.

> **Note:** This feature requires an LLM API Key.

```python
import os
from skillnet_ai import SkillEvaluator, EvaluatorConfig

# 1. Configure the Evaluator
config = EvaluatorConfig(
    api_key="sk-...",             # Your API Key
    base_url="xxxxxx",            # Optional. Useful if using a proxy or compatible API
    model="gpt-4o"                # Model to use for evaluation
)
evaluator = SkillEvaluator(config)

# 2. Evaluate a Skill (from URL or Local Path)
skill_url = "https://github.com/microsoft/autogen/tree/main/samples/tools/web_search"

# You can also use evaluator.evaluate_from_path("./my_skills/web_search")
result = evaluator.evaluate_from_url(skill_url)

print(f"Evaluation: {result}")
```

---

## 💻 CLI Usage

SkillNet AI provides a robust Command Line Interface (CLI) powered by `Typer` and `Rich`. It allows you to search, download, create, and evaluate skills directly from the terminal with visual feedback.

**Tip:** You can view the full list of options for any command using `--help` (e.g., `skillnet search --help`).

### 1. Search Skills (`search`)

Search the registry using keywords or AI-powered semantic search.

```bash
# Basic keyword search
skillnet search "pdf extraction"

# Semantic/Vector search (finds skills by meaning)
skillnet search "tools for reading financial documents" --mode vector --threshold 0.8

# Filter by category and sort results
skillnet search "visualization" --category "Data" --sort-by stars --limit 10
```

#### Key Options:

--mode: Search mode, either keyword (default) or vector.

--threshold: Similarity threshold for vector search (0.0 - 1.0).

--min-stars: Filter results by minimum star rating.

### 2. Download Skills (download)

Download and install a skill directly from a GitHub repository subdirectory.

```bash
# Download to the current directory
skillnet download [https://github.com/owner/repo/tree/main/skills/math_solver](https://github.com/owner/repo/tree/main/skills/math_solver)

# Download to a specific target directory
skillnet download [https://github.com/owner/repo/tree/main/skills/math_solver](https://github.com/owner/repo/tree/main/skills/math_solver) -d ./my_agent/skills

# Download from a private repository
skillnet download <private_url> --token <your_github_token>
```

### 3. Create Skills (create)

Analyze an execution trajectory (log file) and automatically generate a structured Skill Package using LLMs.

Requirement: Ensure API_KEY is set in your environment variables.

```bash
# Generate a skill from a trajectory file
skillnet create ./logs/trajectory.txt --output-dir ./generated_skills

# Specify a specific LLM model
skillnet create ./logs/chat_history.txt --model gpt-4o
```

### Evaluate Skills (evaluate)
Generate a comprehensive quality report (Safety, Completeness, Executability, Modifiability, Cost Awareness) for a skill.

Requirement: Ensure API_KEY is set in your environment variables.

```bash
# Evaluate a remote skill via GitHub URL
skillnet evaluate [https://github.com/owner/repo/tree/main/skills/web_search](https://github.com/owner/repo/tree/main/skills/web_search)

# Evaluate a local skill directory
skillnet evaluate ./my_skills/web_search

# Custom evaluation config
skillnet evaluate ./my_skills/tool --category "DevOps" --model gpt-4o
```

## ⚙️ Configuration

### Environment Variables

If you are using the **Skill Creation** or **Skill Evaluation** feature, you must configure your LLM provider.

| Variable | Description | Default |
| :--- | :--- | :--- |
| `API_KEY` | Required for creating or evaluating skills. | `None` |
| `BASE_URL` | Optional. Useful if using a proxy or compatible API. | `https://api.openai.com/v1` |

---

## 📂 Project Structure

When you create or install a skill, it follows the **Standard Skill Structure**:

```text
skill-name/
├── SKILL.md          # (required) Main orchestration file (YAML metadata + Instructions)
├── scripts/          # (optional) Executable Python/Bash scripts
├── references/       # (optional) Static documentation or API specs
└── assets/           # (optional) Templates, icons, etc.
```

---

## 🗺 Roadmap

- [x] Search & AI Search
- [x] Skill Installer
- [x] Trajectory-to-Skill Creator
- [x] Skill Evaluation & Scoring

---

## 🤝 Contributing

Contributions are welcome! Please submit a Pull Request or open an Issue on GitHub.

## 📄 License

This project is licensed under the [MIT License](LICENSE).