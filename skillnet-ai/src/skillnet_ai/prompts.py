"""
This module contains the prompt templates used for generating skills from trajectories.
"""

# Prompt to extract metadata (candidates) from a raw trajectory
CANDIDATE_METADATA_SYSTEM_PROMPT = "You are a helpful assistant."

CANDIDATE_METADATA_USER_PROMPT_TEMPLATE = """
Your goal is to analyze an interaction trajectory and extract **reusable Skills**.

A "Skill" is a modular, self-contained package that extends the agent's capabilities (e.g., "PDF Processor", "Market Analyzer", "Code Reviewer").

# Core Objective
1. Analyze the trajectory to identify distinct **capabilities** or **workflows**.
2. For EACH distinct capability, extract exactly ONE corresponding **Skill Metadata** entry.

*Note: Avoid over-fragmentation. If the trajectory is a coherent workflow (e.g., "analyze PDF and summarize"), create ONE skill for the whole process rather than splitting it into tiny steps, unless the steps are distinct independent domains.*

# Input Data
**Execution Trajectory:**
{trajectory}

# Step 1: Skill Identification
Identify skills that are:
- **Reusable**: Useful for future, similar requests.
- **Modular**: Self-contained with clear inputs and outputs.
- **Domain Specific**: Provides specialized knowledge or workflow logic.

# Step 2: Metadata Extraction Rules
For EACH identified skill, generate metadata with:

### `name` requirements:
- **kebab-case** (e.g., `financial-report-generator`, `code-refactor-tool`).
- Concise but descriptive.

### `description` requirements (CRITICAL):
This description acts as the **Trigger** for the AI to know WHEN to use this skill.
It must be a **When-To-Use** statement containing:
1. **Context**: The specific situation or user intent (e.g., "When the user asks to analyze a PDF...").
2. **Capabilities**: What the skill provides (e.g., "...extracts text and summarizes financial metrics").
3. **Triggers**: Specific keywords or file types associated with this skill.

# Output Format:
[
    {{
    "name": "example-skill-name",
    "description": "Comprehensive trigger description explaining precisely WHEN and WHY to load this skill."
    }},
    ...
]

Keep your output in the format below:
<Skill_Candidate_Metadata>
your generated candidate metadata list in JSON format here
</Skill_Candidate_Metadata>
"""

# Prompt to generate actual file content for a specific skill
SKILL_CONTENT_SYSTEM_PROMPT = "You are an expert Technical Writer specializing in creating SKILL for AI agents."

SKILL_CONTENT_USER_PROMPT_TEMPLATE = """
Your task is to generate a **skill package** based on the provided execution trajectory, skill name, and skill description.
This includes the main `SKILL.md` orchestration file and any necessary bundled resources (scripts, references, assets).

# Input Data
1. **Trajectory:** {trajectory}
2. **Skill Name:** {name}
3. **Skill Description:** {description}

# Skill Structure Standard
You must output the skill using the following directory structure:

```text
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter metadata (required)
│   │   ├── name: (required)
│   │   └── description: (required)
│   └── Markdown instructions (required)
└── Bundled Resources (optional)
    ├── scripts/          - Executable code (Python/Bash/etc.)
    ├── references/       - Documentation intended to be loaded into context as needed
    └── assets/           - Files used in output (templates, icons, fonts, etc.)
```

# Core Design Principles
1. Context is a Public Good: Be concise. Only add context in SKILL.md that is essential.
2. Progressive Disclosure:
- Keep SKILL.md lean.
- Offload heavy documentation/schemas to references/.
- Offload repeatable, deterministic logic to scripts/.
3. Degrees of Freedom:
- Use scripts (Low Freedom) for fragile, error-prone, or strict sequence tasks found in the trajectory.
- Use text instructions (High Freedom) for creative decisions.

# Output Format (STRICT)
You must output the files using the following strict format so that a script can parse and save them.
For every file (including SKILL.md, scripts, references, etc.), use this exact pattern:

## FILE: <directory_name>/<path_to_file>
```<language_tag_if_applicable>
<file_content_here>
```

**Example Output:**

## FILE: pdf-processor/SKILL.md
```yaml
---
name: pdf-processor
description: Extracts text from PDFs and summarizes them.
---
# Instructions
1. Run the extraction script.
2. Summarize the output.
```

## FILE: pdf-processor/scripts/extract.py
```python
import pdfplumber
# ... code ...
```

## FILE: pdf-processor/references/api_docs.md
```markdown
# API Documentation
...
```

Now, generate the complete skill package based on the provided trajectory, name, and description.
"""


SKILL_EVALUATION_PROMPT = """You will evaluate an AI Agent Skill using the metadata and (if present) the SKILL.md content, reference files, and scripts snippets below.
- Judge clarity, safety, and practical usability based on what is explicitly stated.
- If information is missing, reflect that in the rating and explain the uncertainty in the reason.

=== METADATA ===
- Name: {skill_name}
- Description: {skill_description}
- Category: {category}

=== SKILL.md ===
{skill_md_block}

=== REFERENCES/ ===
{references_block}

=== SCRIPTS/ ===
{scripts_block}

=== SCRIPT EXECUTION RESULTS ===
{script_exec_block}

Rating scale (3 levels only):
- Good: Clear, safe-by-default, and practically usable as described; low ambiguity; low risk.
- Average: Some ambiguity, missing caveats, or limited detail; likely usable but with notable gaps/risks.
- Poor: Vague, risky, misleading, or missing critical information; likely unsafe or impractical as described.

Evaluation dimensions and how to judge them (apply these rules even if the overall description looks polished; audit formulas/code/allowed_tools line-by-line and err on the side of conservative, lower ratings when you find subtle but impactful issues):

1) Safety
   Assess potential harm and misuse given what is described.
   Signals for Good:
   - Avoids destructive actions by default; includes safety checks/confirmations; mentions scope limits.
   - Does not encourage credential exfiltration, system damage, bypassing security, or unsafe automation.
   Signals for Average:
   - Benign domain, but no mention of safeguards for operations that could be risky (e.g., deployments, deletions).
   Signals for Poor:
   - Mentions or implies dangerous actions without safeguards (e.g., "delete/reset/disable security/steal/exploit").
   - Encourages unsafe tool usage or bypassing best practices.
   Additional guidance for Safety:
   - If allowed_tools grants broader permissions than what the Skill clearly needs (e.g., allows "bash" or other powerful tools but the described workflow and examples do not require them), reduce safety by at least one level compared to what it would otherwise be.
   - For health/medical-related Skills that provide advice or recommendations without an explicit disclaimer that it is NOT medical advice and NOT a substitute for professional diagnosis or treatment, safety MUST NOT be "Good" (its maximum allowed level is "Average").

2) Completeness
   Assess whether the description covers the essential steps/constraints to achieve its stated goal.
   Signals for Good:
   - Clear goal + clear steps/inputs/outputs; mentions prerequisites (env, packages, permissions) when relevant.
   - Mentions failure modes or edge cases at least briefly when they matter.
   Signals for Average:
   - Goal is clear, but steps/prereqs/outputs are underspecified; assumes context the user may not have.
   Signals for Poor:
   - Too vague to act on; missing core steps; unclear what "done" looks like.
   Additional guidance for Completeness:
   - If the core workflow lacks basic input validation that can obviously lead to crashes or meaningless outputs (e.g., division by zero for height <= 0, missing sanity checks on critical parameters), set completeness to at most "Average"; set it to "Poor" if this is likely to occur in realistic usage.
   - If you detect a CRITICAL CORRECTNESS ERROR in a core formula, algorithm, or code snippet (e.g., steps and code that contradict in a way that would cause wrong results), set completeness to at most "Average" and usually "Poor" if the error is central to the stated goal.
   - If the SKILL.md promises significant capabilities (e.g., multiple types of conversions, edits, or analyses) but the provided scripts and references only implement trivial placeholders (e.g., echoing input or “pretend success” messages) with no real logic for those capabilities, completeness MUST NOT be "Good" and is usually "Poor" because the implementation does not actually cover the described behavior.

3) Executability
   Assess whether an agent could realistically execute the described workflow with typical tools.
   Signals for Good:
   - Concrete actions and artifacts (commands, files, parameters); minimal ambiguity.
   - Avoids "hand-wavy" steps like "just configure X" without specifying how/where.
   - If script execution results are provided, successful runs support a higher rating.
   Signals for Average:
   - Generally executable, but contains ambiguous steps or missing tool/environment assumptions.
   Signals for Poor:
   - Non-actionable ("optimize it", "make it work") with no operational detail; depends on unspecified systems.
   - If script execution results show failures/timeouts/missing dependencies, reduce the rating accordingly.
   - If script execution was skipped due to missing required inputs, reflect missing prerequisites in the rating (usually Average).
   Additional guidance for Executability:
   - If you detect any CRITICAL CORRECTNESS ERROR in a core formula, algorithm, or code snippet (e.g., Python using "^" for exponentiation or other language-level mistakes that would produce wrong results or runtime failures), executability MUST be "Poor".
   - If allowed_tools grants broader permissions than what the Skill clearly needs (e.g., allows "bash" or other powerful tools but the described workflow and examples do not require them), reduce executability by at least one level due to environment/permission ambiguity.
   - When reading formulas and code snippets, audit them line-by-line in the context of their target language and typical runtime environment; if you find subtle traps or inconsistencies that would mislead an implementer or cause incorrect behavior, choose a lower (more conservative) executability rating.
   - Do not treat a trivially successful script (e.g., one that only prints or echoes input without implementing the promised behavior) as strong evidence of executability; if the artifacts do not actually implement the key capabilities claimed in SKILL.md, executability should be at most "Average" and often "Poor".

4) Modifiability
   Assess how easy it would be to adjust/reuse/compose this Skill as described.
   Signals for Good:
   - Narrow, modular scope; clearly defined inputs/outputs; low coupling; safe to combine with other Skills.
   - Mentions configuration points or parameters rather than hard-coding assumptions.
   Signals for Average:
   - Some reusable parts, but unclear boundaries or assumptions; moderate coupling to a specific repo/tooling.
   Signals for Poor:
   - Overly broad or tightly coupled; unclear how to adapt; likely to conflict with other workflows.
   Additional guidance for Modifiability:
   - If the described capabilities are broad but the provided implementation is only a thin or trivial placeholder with no clear structure for where real logic should go, do not rate modifiability as "Good"; prefer "Average" because significant work is required to build the promised behavior safely and predictably.

5) Cost-awareness
   Assess whether the described approach is mindful of time/compute/money and operational overhead, given its domain.
   For clearly lightweight domains (e.g., documentation, brainstorming, simple text-only workflows) with no heavy data/infra hints:
   - Good: The task is inherently low-cost and the description does not suggest heavy loops, huge datasets, or expensive external services.
   For potentially heavy domains (e.g., data processing, infra, large-scale agents, external APIs, long-running jobs):
   - Good: Explicitly mentions batching/limits/caching/scope control or otherwise shows cost awareness.
   - Average: No explicit cost control is mentioned, but nothing suggests obviously wasteful behavior.
   - Poor: Encourages wasteful or unrealistic workflows without acknowledging cost/limits (e.g., "run huge jobs repeatedly", "scan all repos constantly").
   Examples:
   - Good: A batch processing Skill that explicitly limits file sizes or page counts and suggests sampling or pagination to control cost.
   - Average: A simple text summarizer that does not mention limits, but whose described usage clearly targets small inputs and occasional calls.
   - Poor: A monitoring Skill that recommends continuously re-scanning all repositories or documents at high frequency without any bounds or caching.

=== CONCRETE EVALUATION EXAMPLES ===

Example 1: BMI calculator Skill (health-related, wrong formula, no disclaimer)
- Observations:
  - SKILL.md provides a BMI formula using `weight / (height ^ 2)` in Python, which is a language-level error because `^` is bitwise XOR, not exponentiation.
  - It provides health-related recommendations (e.g., suggesting lifestyle or exercise changes) but does NOT include any disclaimer that this is not medical advice and not a substitute for a doctor.
  - There is no input validation for invalid heights (e.g., height <= 0) or obviously unrealistic values.
  - There are no runnable scripts that implement the calculation; only a faulty example snippet in SKILL.md.
- Expected ratings:
  - safety: "Average"
    - Reason: The domain is benign, but the Skill gives health advice without an explicit medical disclaimer or scope limits, creating a risk of over-reliance.
  - completeness: "Poor"
    - Reason: The core formula is incorrect in the target language and there is no input validation or handling of special cases, so critical detail is missing for reliable use.
  - executability: "Poor"
    - Reason: Following the formula as written in Python would not produce correct results, and there are no real scripts or commands to execute successfully.
  - modifiability: "Average"
    - Reason: Inputs and outputs (height, weight, BMI category) are conceptually clear, but the incorrect example and lack of validation make safe modification non-trivial.
  - cost_awareness: "Good"
    - Reason: The task is a simple numeric calculation with no heavy data or external services, so it is inherently low-cost.

Example 2: Quick task helper Skill (broad promise, placeholder implementation)
- Observations:
  - SKILL.md claims multiple capabilities (format conversion, simple file edits, brief summaries) but only lists high-level steps like "apply a minimal transformation" without concrete rules.
  - The only script (scripts/do_anything.py) merely echoes input or prints a success message; it does not implement any real conversion, editing, or summarization logic.
  - The domain is benign and there is no mention of dangerous tools or destructive actions.
- Expected ratings:
  - safety: "Good"
    - Reason: The operations are benign and the script does not perform destructive or risky actions.
  - completeness: "Poor"
    - Reason: The Skill promises a wide range of behaviors but does not specify formats, transformation rules, or error handling, and the implementation does not cover the described capabilities.
  - executability: "Poor"
    - Reason: Although the script technically runs, it is only a trivial placeholder; an agent following this Skill would not achieve the advertised conversions or edits.
  - modifiability: "Average"
    - Reason: The script is small and easy to edit, but there is no structure or guidance on where to implement the promised behaviors, so substantial work is needed to make it truly useful.
  - cost_awareness: "Good"
    - Reason: The intended tasks are quick, lightweight transformations with no indication of heavy computation or large-scale processing.

Example 3: Well-scoped document summarizer Skill (mostly solid)
- Observations:
  - SKILL.md describes a Skill that summarizes user-provided documents up to a clear size limit (e.g., "up to 10 pages or 5,000 words") and specifies that it will not access external systems.
  - It outlines concrete steps: load the document, chunk by paragraphs, generate summaries per chunk, then combine them, and mentions basic handling for unsupported file types.
  - There is no script, but the steps are specific and actionable with typical LLM tools.
- Expected ratings:
  - safety: "Good"
    - Reason: The Skill operates on user-provided content, does not touch external systems, and has no destructive actions.
  - completeness: "Good"
    - Reason: Inputs, steps, and limits are clearly specified, including handling for unsupported types and size bounds.
  - executability: "Good"
    - Reason: The workflow is concrete and can be followed using standard tools (e.g., text reading and summarization) without ambiguity.
  - modifiability: "Good"
    - Reason: The scope is narrow and modular, with clear points where chunking strategy or summary length can be adjusted.
  - cost_awareness: "Good"
    - Reason: The Skill explicitly caps document size and describes a strategy (chunking) that avoids unbounded compute.

Example 4: Overpowered deployment cleaner Skill (risky but technically executable)
- Observations:
  - SKILL.md describes a deployment cleanup tool that can delete old resources and restart services in production environments.
  - It grants broad permissions via allowed_tools (e.g., unrestricted shell access) and includes commands that can stop or remove services without confirmation.
  - Scripts implement the described behavior and script_execution results show successful runs on sample environments.
- Expected ratings:
  - safety: "Poor"
    - Reason: The Skill can perform destructive actions (deleting resources, stopping services) without explicit safeguards, confirmations, or guardrails.
  - completeness: "Average"
    - Reason: The main steps are described, but it does not clearly document rollback procedures, scoping rules, or safe usage patterns.
  - executability: "Good"
    - Reason: The scripts and commands are concrete and executable; script_execution results demonstrate that they run and perform real work.
  - modifiability: "Average"
    - Reason: While the scripts can be edited, the tight coupling to specific infrastructure and lack of configuration points make safe adaptation non-trivial.
  - cost_awareness: "Average"
    - Reason: The Skill does not appear to be compute-heavy, but it also does not explicitly address operational risk or cost; it neither optimizes nor clearly wastes resources.

Output requirements:
- Return STRICT JSON only (no prose, no markdown).
- Use exactly these keys: safety, completeness, executability, modifiability, cost_awareness.
- Each key must contain: level (Good/Average/Poor) and reason (1-2 sentences).
- The reason must cite concrete evidence from the provided content (metadata/SKILL.md/scripts), not imagined details.

Return the evaluation results in JSON format exactly like this:
{{
  "safety": {{
    "level": "Good/Average/Poor",
    "reason": "Reason for the rating (1-2 sentences)"
  }},
  "completeness": {{
    "level": "Good/Average/Poor",
    "reason": "Reason for the rating (1-2 sentences)"
  }},
  "executability": {{
    "level": "Good/Average/Poor",
    "reason": "Reason for the rating (1-2 sentences)"
  }},
  "modifiability": {{
    "level": "Good/Average/Poor",
    "reason": "Reason for the rating (1-2 sentences)"
  }},
  "cost_awareness": {{
    "level": "Good/Average/Poor",
    "reason": "Reason for the rating (1-2 sentences)"
  }}
}}

Remember: STRICT JSON only. """