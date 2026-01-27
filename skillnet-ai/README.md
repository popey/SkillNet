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
- **✨ Skill Creation**: Automatically convert trajectories or GitHub repositories into structured, reusable `skill` packages using LLMs.
- **📊 Evaluation**: Evaluate and score skills for quality assurance (Safety, Completeness, Excutability, Modifiability, Cost-Aware).

---

## 📥 Installation

```bash
pip install skillnet-ai
```

---

## 🛠 Usage (Python SDK)

The `SkillNetClient` provides a unified interface for searching, downloading, creating, and evaluating skills.

### 1. Initialize the Client

Initialize the client with your credentials. You can also set `API_KEY` and `GITHUB_TOKEN` in your environment variables.

```python
from skillnet_ai import SkillNetClient

# Initialize with optional credentials
client = SkillNetClient(
    api_key="sk-...",       # Required for AI Search, Creation, and Evaluation
    base_url="...",         # Optional custom LLM base URL
    github_token="ghp-..."  # Optional, for private repos or higher rate limits
)
```

### 2. Search for Skills
Perform keyword-based or semantic AI searches to find skills.

```python
# 1. Standard Keyword Search
results = client.search(q="pdf tool")

# 2. Semantic AI Search (requires api_key)
results = client.search(q="Help me analyze financial PDF reports", mode="vector")

if results:
    top_skill = results[0]
    print(f"Found: {top_skill.skill_name} (Stars: {top_skill.stars})")
    print(f"URL: {top_skill.skill_url}")
```

### 3. Install a Skill
Download and install a skill directly from a URL (e.g., from search results) into your local workspace.

```python
skill_url = "https://github.com/anthropics/skills/tree/main/skills/skill-creator"

try:
    # Downloads to ./my_agent_skills
    local_path = client.download(url=skill_url, target_dir="./my_agent_skills")
    print(f"Skill successfully installed at: {local_path}")
except Exception as e:
    print(f"Download failed: {e}")
```

### 4. Create a Skill from Trajectory
Turn conversation logs or execution traces into a polished Skill Package (SKILL.md, scripts, etc.).

```python
# 1. Prepare your trajectory (e.g., a conversation log string)
trajectory_log = """
User: I need to rename all .jpg files in this folder to .png.
Agent: I will write a python script to iterate through the folder...
Agent: Script executed. Renamed 5 files.
"""

# 2. Generate Skills
# Returns a list of paths to the generated skill folders
created_paths = client.create(
    trajectory_content=trajectory_log, 
    output_dir="./created_skills",
    model="gpt-4o"
)

print(f"Created {len(created_paths)} new skills.")
for path in created_paths:
    print(f"- {path}")
```

### 4.1 Create a Skill from GitHub Repository
Convert an existing GitHub repository into a skill package.

```python
# Create skill from a GitHub repository
created_paths = client.create(
    github_url="https://github.com/zjunlp/DeepKE",
    output_dir="./created_skills",
    model="gpt-4o"
)
```

### 5. Skill Evaluation
Assess the Safety, Completeness, Executability, and Modifiability of a skill. Supports both remote GitHub URLs and local directories.

```python
# target_skill = "./my_skills/web_search"
target_skill = "https://github.com/microsoft/autogen/tree/main/samples/tools/web_search"

# Evaluates the skill using the client's API key
result = client.evaluate(target=target_skill)

# Display results
print(f"Evaluation Result: {result}")
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

### 2. Install Skills (download)

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

Analyze an execution trajectory (log file) or GitHub repository and automatically generate a structured Skill Package using LLMs.

Requirement: Ensure API_KEY is set in your environment variables.

```bash
# Generate a skill from a trajectory file
skillnet create ./logs/trajectory.txt --output-dir ./generated_skills

# Specify a specific LLM model
skillnet create ./logs/chat_history.txt --model gpt-4o

# Generate a skill from a GitHub repository
skillnet create --github https://github.com/owner/repo --output-dir ./generated_skills
```

### 4. Evaluate Skills (evaluate)
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
| `GITHUB_TOKEN` | Optional. For private repos or higher API rate limits. | `None` |

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
- [x] GitHub-to-Skill Creator
- [x] Skill Evaluation & Scoring

---

## 🤝 Contributing

Contributions are welcome! Please submit a Pull Request or open an Issue on GitHub.

## 📄 License

This project is licensed under the [MIT License](LICENSE).