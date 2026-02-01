# skillnet-ai

[![PyPI version](https://badge.fury.io/py/skillnet-ai.svg)](https://badge.fury.io/py/skillnet-ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

**skillnet-ai** is the official Python Toolkit for interacting with the SkillNet platform. It allows AI Agents to **Create**, **Evaluate** and **Organize** AI skills at scale. It functions seamlessly as both a powerful Python Library and a feature-rich Command Line Interface (CLI).

---

## 🚀 Features

- **🔍 Search**: Find skills using keywords match or semantic search.
- **📦 One-Line Installation**: Download skill packages directly from GitHub repositories.
- **✨ Skill Creation**: Automatically convert various sources into structured, reusable `skill` packages using LLMs:
  - Execution trajectories / conversation logs
  - GitHub repositories
  - Office documents (PDF, PPT, Word)
  - Direct text prompts
- **📊 Evaluation**: Evaluate and score skills for quality assurance (Safety, Completeness, Excutability, Modifiability, Cost-Aware).
- **🕸️ Relationship Analysis**: Automatically map the connections between skills in your local library, identifying structural relationships between skills (similar_to, belong_to, compose_with, depend_on).

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
Perform keywords match or semantic searches to find skills.

```python
# 1. Standard Keywords Match
results = client.search(q="pdf tool")

# 2. Semantic Search
results = client.search(q="Help me analyze financial PDF reports", mode="vector")

if results:
    top_skill = results[0]
    print(f"Found: {top_skill.skill_name} (Stars: {top_skill.stars})")
    print(f"URL: {top_skill.skill_url}")
```
#### Parameter Reference
| Parameter   | Type   | Default     | Description |
|------------|--------|-------------|-------------|
| q          | str    | Required    | Search query (keywords or natural language). |
| mode       | str    | "keyword"   | Search mode: "keyword" or "vector". |
| category   | str    | None        | Filter skills by category. |
| limit      | int    | 20          | Maximum number of results per request. |
| page       | int    | 1           | [Keyword Mode Only] Page number for pagination. |
| min_stars  | int    | 0           | [Keyword Mode Only] Filter by minimum star count. |
| sort_by    | str    | "stars"     | [Keyword Mode Only] Sort by "stars" or "recent". |
| threshold  | float  | 0.8         | [Vector Mode Only] Minimum similarity threshold (0.0 - 1.0). |


### 3. Install Skills
Download and install a skill directly from a URL (e.g., from above search results) into your local workspace.

```python
skill_url = "https://github.com/anthropics/skills/tree/main/skills/skill-creator"

try:
    # Downloads to ./my_agent_skills
    local_path = client.download(url=skill_url, target_dir="./my_agent_skills")
    print(f"Skill successfully installed at: {local_path}")
except Exception as e:
    print(f"Download failed: {e}")
```

### 4. Create Skills
#### 4.1 Create from Local Trajectory
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

#### 4.2 Create from GitHub Repository
Convert an existing GitHub repository into a skill package.

```python
# Create skill from a GitHub repository
created_paths = client.create(
    github_url="https://github.com/zjunlp/DeepKE",
    output_dir="./created_skills",
    model="gpt-4o"
)
```

#### 4.3 Create from Office Documents
Convert PDF, PowerPoint, or Word documents into skill packages.

```python
# Create skill from a PDF document
created_paths = client.create(
    office_file="./docs/user_guide.pdf",
    output_dir="./created_skills"
)
```

#### 4.4 Create from Prompt
Generate a skill directly from a text description.

```python
# Create skill from a prompt description
created_paths = client.create(
    prompt="Create a skill for web scraping that extracts article titles and content",
    output_dir="./created_skills"
)
```

### 5. Skill Evaluation
Assess the Safety, Completeness, Executability, Modifiability and Cost-Aware of a skill. Supports both remote GitHub URLs and local directories.

```python
# target_skill = "./my_skills/web_search"
target_skill = "https://github.com/microsoft/autogen/tree/main/samples/tools/web_search"

# Evaluates the skill using the client's API key
result = client.evaluate(target=target_skill)

# Display results
print(f"Evaluation Result: {result}")
```

### 6. Skill Relationship Analysis
Analyze a local directory containing multiple skills to infer a relationship graph. It identifies relationships like dependencies (depend_on), collaboration (compose_with), hierarchy (belong_to), and alternatives (similar_to).

```python
# Directory containing multiple skill folders
skills_directory = "./my_agent_skills"

# Analyze relationships between skills
# This will also save a 'relationships.json' in the directory by default
relationships = client.analyze(skills_dir=skills_directory)

# Display the relationships
for rel in relationships:
    print(f"{rel['source']} --[{rel['type']}]--> {rel['target']}")
    # Output: PDF_Parser --[compose_with]--> Text_Summarizer
```

---

## 💻 CLI Usage

skillnet-ai provides a robust Command Line Interface (CLI) powered by `Typer` and `Rich`. It allows you to create, evaluate, and organize skills directly from the terminal with visual feedback.

**Tip:** You can view the full list of options for any command using `--help` (e.g., `skillnet search --help`).

### 1. Search Skills (`search`)

Search the registry using keywords match or semantic search.

```bash
# Basic keywords match
skillnet search "pdf extraction"

# Semantic/Vector search (finds skills by meaning)
skillnet search "tools for reading financial documents" --mode vector --threshold 0.85

# Filter by category and sort results
skillnet search "visualization" --category "Data" --sort-by stars --limit 10
```

#### Key Options:

| Option        | Type  | Default  | Description |
|--------------|-------|----------|-------------|
| q (Argument) | str   | Required | Your search query (keywords or natural language description). |
| --mode       | str   | keyword  | Search mode: keyword (fuzzy match) or vector (AI semantic). |
| --category   | str   | None     | Filter results by category (e.g., `Development`, `Business`). |
| --limit      | int   | 20       | Maximum number of results to return. |
| **[Keyword Mode Only]** |       |          |             |
| --page       | int   | 1        | Page number for pagination. |
| --min-stars | int   | 0        | Minimum star rating required. |
| --sort-by   | str   | stars    | Sort criteria: stars or recent. |
| **[Vector Mode Only]**  |       |          |             |
| --threshold  | float | 0.8      | Similarity threshold (0.0–1.0). Higher is stricter. |


### 2. Install Skills (`download`)

Download and install a skill directly from a GitHub repository subdirectory.

```bash
# Download to the current directory
skillnet download https://github.com/owner/repo/tree/main/skills/math_solver

# Download to a specific target directory
skillnet download https://github.com/owner/repo/tree/main/skills/math_solver -d ./my_agent/skills

# Download from a private repository
skillnet download <private_url> --token <your_github_token>
```

### 3. Create Skills (`create`)

Generate structured Skill Packages from various sources using LLMs.

Requirement: Ensure API_KEY is set in your environment variables.

```bash
# From a trajectory file
skillnet create ./logs/trajectory.txt -d ./generated_skills

# From a GitHub repository
skillnet create --github https://github.com/owner/repo

# From an office document (PDF, PPT, Word)
skillnet create --office ./docs/guide.pdf

# From a direct prompt
skillnet create --prompt "Create a skill for extracting tables from images"

# Specify a custom model
skillnet create --office report.pdf --model gpt-4o
```

### 4. Evaluate Skills (`evaluate`)
Generate a comprehensive quality report (Safety, Completeness, Executability, Modifiability, Cost Awareness) for a skill.

Requirement: Ensure API_KEY is set in your environment variables.

```bash
# Evaluate a remote skill via GitHub URL
skillnet evaluate https://github.com/owner/repo/tree/main/skills/web_search

# Evaluate a local skill directory
skillnet evaluate ./my_skills/web_search

# Custom evaluation config
skillnet evaluate ./my_skills/tool --category "DevOps" --model gpt-4o
```

### 5. Analyze Relationships (`analyze`)
Scan a directory of skills to analyze their connections using AI.

Requirement: Ensure API_KEY is set in your environment variables.

```bash
# Analyze a directory containing multiple skill folders
skillnet analyze ./my_agent_skills

# Analyze without saving the result file (just print to console)
skillnet analyze ./my_agent_skills --no-save

# Specify a model for the analysis
skillnet analyze ./my_agent_skills --model gpt-4o
```

## ⚙️ Configuration

### Environment Variables

If you are using the **Creation**, **Evaluation**, or **Analyze** feature, you must configure your LLM provider.

| Variable | Description | Default |
| :--- | :--- | :--- |
| `API_KEY` | Required for creating or evaluating skills. | `None` |
| `BASE_URL` | Optional. Useful if using a proxy or compatible API. | `https://api.openai.com/v1` |

---

## 📂 Skill Structure

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

- [x] Keywords Match & Semantic Search
- [x] Skill Installer
- [x] Skill Creator (Local File & GitHub Repository)
- [x] Skill Evaluation & Scoring

---

## 🤝 Contributing

Contributions are welcome! Please submit a Pull Request or open an Issue on GitHub.

## 📄 License

This project is licensed under the [MIT License](LICENSE).
