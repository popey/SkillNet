import ast
import json
import logging
import os
import shlex
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple

from openai import OpenAI
from tqdm import tqdm

from skillnet_ai.downloader import SkillDownloader
from skillnet_ai.prompts import SKILL_EVALUATION_PROMPT

logger = logging.getLogger(__name__)


# ==========================================================================
# Configuration and data models
# ==========================================================================

@dataclass
class EvaluatorConfig:
    """Configuration for the skill evaluator."""
    api_key: str
    base_url: str
    model: str
    cache_dir: str
    max_workers: int = 5
    temperature: float = 0.3
    run_scripts: bool = False
    script_timeout_sec: int = 8
    max_script_runs: int = 5
    script_python: str = "python"
    include_script_results: bool = False
    max_script_output_chars: int = 400


@dataclass
class Skill:
    """Unified representation of a skill."""
    path: str  # Local path to the skill root directory
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    url: Optional[str] = None  # Original URL (when created from URL)
    
    @classmethod
    def from_url(
        cls,
        url: str,
        downloader: 'SkillDownloader',
        cache_dir: str,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        **kwargs
    ) -> Tuple[Optional['Skill'], Optional[str]]:
        """
        Create a Skill from a GitHub URL.
        下载失败时会重试，最终失败返回 (None, error_msg) 而非抛出异常。

        Returns:
            (Skill, None) 成功；(None, error_msg) 失败。
        """
        normalized_url = cls._normalize_url(url)
        if not normalized_url:
            return None, f"Invalid GitHub URL: {url}"
        # Download to local cache (with retries in evaluator)
        local_path = None
        for attempt in range(max_retries):
            local_path = downloader.download(normalized_url, target_dir=cache_dir)
            if local_path:
                break
            if attempt < max_retries - 1:
                logger.warning(
                    "Download failed (attempt %d/%d). Retrying in %.1fs...",
                    attempt + 1, max_retries, retry_delay,
                )
                time.sleep(retry_delay)
        if not local_path:
            return None, f"Failed to download after {max_retries} retries: {url}"
        # Derive skill name from URL if not provided
        name = kwargs.get('name') or normalized_url.rstrip('/').split('/')[-1]

        return cls(
            path=local_path,
            name=name,
            url=url,
            description=kwargs.get('description'),
            category=kwargs.get('category')
        ), None
    
    @classmethod
    def from_path(cls, path: str, **kwargs) -> 'Skill':
        """Create a Skill from a local directory path.

        Returns:
            (Skill, None) on success; (None, error_msg) on failure.
        """
        abs_path = os.path.abspath(path)
        if not os.path.isdir(abs_path):
            return None, f"Invalid skill path: {path}"

        name = kwargs.get('name') or os.path.basename(abs_path)

        return (
            cls(
                path=abs_path,
                name=name,
                description=kwargs.get('description'),
                category=kwargs.get('category')
            ),
            None,
        )
    
    @staticmethod
    def _normalize_url(url: str) -> Optional[str]:
        """Normalize GitHub URL to /tree/ format."""
        if not url:
            return None
        if "/blob/" in url:
            return url.replace("/blob/", "/tree/")
        if "/tree/" in url:
            return url
        return None


@dataclass
class ScriptExecutionResult:
    """Result of executing a single script."""
    path: str
    status: str  # success | compiled_only | failed | timeout | skipped
    command: str
    exit_code: Optional[int] = None
    error: Optional[str] = None
    duration_sec: Optional[float] = None
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "status": self.status,
            "command": self.command,
            "exit_code": self.exit_code,
            "error": self.error,
            "duration_sec": self.duration_sec,
            "note": self.note,
        }


class ScriptRunner:
    """Execute python scripts under scripts/ with safe defaults."""

    def __init__(self, python_bin: str, timeout_sec: int, max_runs: int,
                 max_output_chars: int):
        self.python_bin = python_bin
        self.timeout_sec = timeout_sec
        self.max_runs = max_runs
        self.max_output_chars = max_output_chars

    def run_for_skill(self, skill_dir: str) -> List[ScriptExecutionResult]:
        scripts = self._discover_py_scripts(skill_dir)
        results: List[ScriptExecutionResult] = []

        for script_path in scripts[: self.max_runs]:
            results.append(self._run_script(skill_dir, script_path))

        if len(scripts) > self.max_runs:
            logger.info(
                "Found %s scripts, truncated to %s for execution",
                len(scripts),
                self.max_runs
            )

        return results

    def _discover_py_scripts(self, skill_dir: str) -> List[str]:
        paths: List[str] = []
        for root, _, files in os.walk(skill_dir):
            if "scripts" not in root.split(os.sep):
                continue
            for filename in files:
                if filename.lower().endswith(".py"):
                    paths.append(os.path.join(root, filename))
        return sorted(paths)

    def _run_script(self, skill_dir: str, script_path: str) -> ScriptExecutionResult:
        rel_path = os.path.relpath(script_path, skill_dir)
        usage_cmd = self._build_usage_command(script_path, rel_path)
        if usage_cmd:
            missing_inputs = self._detect_missing_inputs(usage_cmd, skill_dir)
            if missing_inputs:
                compile_result = self._run_command(
                    [self.python_bin, "-m", "py_compile", rel_path],
                    skill_dir
                )
                if compile_result["timed_out"]:
                    return ScriptExecutionResult(
                        path=rel_path,
                        status="timeout",
                        command=compile_result["command"],
                        exit_code=None,
                        error=compile_result.get("error"),
                        duration_sec=compile_result["duration_sec"],
                        note=f"missing inputs: {', '.join(missing_inputs)}"
                    )
                if compile_result["exit_code"] == 0:
                    return ScriptExecutionResult(
                        path=rel_path,
                        status="compiled_only",
                        command=compile_result["command"],
                        exit_code=compile_result["exit_code"],
                        error=self._pick_error(compile_result),
                        duration_sec=compile_result["duration_sec"],
                        note=f"missing inputs: {', '.join(missing_inputs)}"
                    )
                return ScriptExecutionResult(
                    path=rel_path,
                    status="failed",
                    command=compile_result["command"],
                    exit_code=compile_result["exit_code"],
                    error=self._pick_error(compile_result),
                    duration_sec=compile_result["duration_sec"],
                    note=f"missing inputs: {', '.join(missing_inputs)}"
                )
            run_result = self._run_command(usage_cmd, skill_dir)
            if run_result["timed_out"]:
                return ScriptExecutionResult(
                    path=rel_path,
                    status="timeout",
                    command=run_result["command"],
                    exit_code=None,
                    error=run_result.get("error"),
                    duration_sec=run_result["duration_sec"],
                    note="usage-derived command"
                )
            if run_result["exit_code"] == 0:
                return ScriptExecutionResult(
                    path=rel_path,
                    status="success",
                    command=run_result["command"],
                    exit_code=run_result["exit_code"],
                    duration_sec=run_result["duration_sec"],
                    note="usage-derived command"
                )
            return ScriptExecutionResult(
                path=rel_path,
                status="failed",
                command=run_result["command"],
                exit_code=run_result["exit_code"],
                error=self._pick_error(run_result),
                duration_sec=run_result["duration_sec"],
                note="usage-derived command"
            )

        compile_result = self._run_command(
            [self.python_bin, "-m", "py_compile", rel_path],
            skill_dir
        )
        if compile_result["timed_out"]:
            return ScriptExecutionResult(
                path=rel_path,
                status="timeout",
                command=compile_result["command"],
                exit_code=None,
                error=compile_result.get("error"),
                duration_sec=compile_result["duration_sec"]
            )
        if compile_result["exit_code"] == 0:
            return ScriptExecutionResult(
                path=rel_path,
                status="compiled_only",
                command=compile_result["command"],
                exit_code=compile_result["exit_code"],
                error=self._pick_error(compile_result),
                duration_sec=compile_result["duration_sec"],
                note="no usage examples found; py_compile succeeded"
            )

        return ScriptExecutionResult(
            path=rel_path,
            status="failed",
            command=compile_result["command"],
            exit_code=compile_result["exit_code"],
            error=self._pick_error(compile_result),
            duration_sec=compile_result["duration_sec"],
            note="no usage examples found"
        )

    def _build_usage_command(self, script_path: str,
                             rel_path: str) -> Optional[List[str]]:
        script_name = os.path.basename(script_path)
        usage_lines = self._extract_usage_lines(script_path, script_name)
        if not usage_lines:
            return None

        candidates: List[List[str]] = []
        for line in usage_lines:
            cmd = self._parse_usage_line(line, rel_path, script_name)
            if cmd:
                candidates.append(cmd)

        if not candidates:
            return None

        # Prefer runnable commands:
        # - Commands containing placeholder tokens like "<file>", "[options]", "{path}" are
        #   often documentation examples and not directly runnable.
        # - If placeholders exist, prefer a help-style command to at least verify the script
        #   starts up, otherwise fall back to compilation-only.
        runnable = [cmd for cmd in candidates if not self._has_placeholder_tokens(cmd)]
        for cmd in runnable:
            if not self._is_help_command(cmd):
                return cmd

        for cmd in candidates:
            if self._is_help_command(cmd):
                return cmd

        return None
    
    def _extract_usage_lines(self, script_path: str,
                             script_name: str) -> List[str]:
        try:
            with open(script_path, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()
        except Exception as e:
            logger.warning("Failed to read %s: %s", script_path, e)
            return []

        try:
            tree = ast.parse(source)
            doc = ast.get_docstring(tree) or ""
        except Exception:
            doc = ""

        if not doc:
            return []

        lines = doc.splitlines()
        usage_lines: List[str] = []
        for idx, line in enumerate(lines):
            if line.strip().lower().startswith("usage:"):
                for follow in lines[idx + 1:]:
                    if not follow.strip():
                        break
                    usage_lines.append(follow.strip())

        if usage_lines:
            return usage_lines

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(("./", "python", "python3")):
                usage_lines.append(stripped)
                continue
            if stripped.startswith(script_name):
                usage_lines.append(stripped)

        return usage_lines

    def _parse_usage_line(self, line: str, rel_path: str,
                          script_name: str) -> Optional[List[str]]:
        try:
            tokens = shlex.split(line)
        except ValueError:
            return None

        if not tokens:
            return None

        python_prefix = tokens[0].startswith("python")
        if python_prefix:
            tokens = [self.python_bin] + tokens[1:]

        script_idx = None
        for idx, token in enumerate(tokens):
            token_base = os.path.basename(token)
            if token_base == script_name:
                script_idx = idx
                break

        if script_idx is None:
            return None

        tokens[script_idx] = rel_path

        if not python_prefix:
            tokens = [self.python_bin] + tokens[script_idx:]

        return tokens

    def _is_help_command(self, cmd: List[str]) -> bool:
        for token in cmd:
            lowered = token.lower()
            if lowered in {"--help", "-h", "help"}:
                return True
        return False

    def _has_placeholder_tokens(self, cmd: List[str]) -> bool:
        for token in cmd:
            if not token or token.startswith("-"):
                continue
            if token == self.python_bin:
                continue
            if self._is_placeholder_token(token):
                return True
        return False

    @staticmethod
    def _is_placeholder_token(token: str) -> bool:
        # Common usage placeholders: <...>, [...], {...}
        if any(ch in token for ch in ("<", ">", "[", "]", "{", "}")):
            return True
        lowered = token.strip().lower()
        return lowered in {"options", "[options]", "<options>", "{options}"}

    def _detect_missing_inputs(self, cmd: List[str], cwd: str) -> List[str]:
        missing: List[str] = []
        for token in cmd:
            if not token or token.startswith("-"):
                continue
            if token == self.python_bin:
                continue
            if self._is_placeholder_token(token):
                continue
            if not self._looks_like_path(token):
                continue
            path = token
            if not os.path.isabs(path):
                path = os.path.join(cwd, path)
            if not os.path.exists(path):
                missing.append(token)
        return missing

    def _looks_like_path(self, token: str) -> bool:
        if "/" in token or token.startswith("."):
            return True
        _, ext = os.path.splitext(token)
        return ext.lower() in {
            ".xml",
            ".json",
            ".yaml",
            ".yml",
            ".csv",
            ".tsv",
            ".txt",
            ".md",
            ".ini",
            ".toml",
            ".coverage",
            ".db",
            ".sqlite",
            ".sql",
            ".parquet",
        }

    def _run_command(self, cmd: List[str], cwd: str) -> Dict[str, Any]:
        command_str = shlex.join(cmd)
        start = time.time()
        try:
            completed = subprocess.run(
                cmd,
                cwd=cwd,
                text=True,
                capture_output=True,
                timeout=self.timeout_sec
            )
            duration = time.time() - start
            return {
                "command": command_str,
                "exit_code": completed.returncode,
                "stdout": self._truncate(completed.stdout),
                "stderr": self._truncate(completed.stderr),
                "duration_sec": round(duration, 3),
                "timed_out": False
            }
        except subprocess.TimeoutExpired:
            duration = time.time() - start
            return {
                "command": command_str,
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "duration_sec": round(duration, 3),
                "timed_out": True,
                "error": f"Timeout after {self.timeout_sec}s"
            }
        except FileNotFoundError as e:
            duration = time.time() - start
            return {
                "command": command_str,
                "exit_code": None,
                "stdout": "",
                "stderr": str(e),
                "duration_sec": round(duration, 3),
                "timed_out": False,
                "error": str(e)
            }

    def _truncate(self, text: str) -> str:
        if not text:
            return ""
        if len(text) <= self.max_output_chars:
            return text
        return text[: self.max_output_chars] + "...[truncated]"

    def _pick_error(self, *results: Dict[str, Any]) -> Optional[str]:
        for result in results:
            if not result:
                continue
            stderr = result.get("stderr") or ""
            stdout = result.get("stdout") or ""
            if stderr.strip():
                return stderr.strip()
            if stdout.strip():
                return stdout.strip()
            if result.get("error"):
                return str(result.get("error"))
        return None


# ==========================================================================
# Skill content loader
# ==========================================================================

class SkillLoader:
    """Load SKILL.md, scripts, and reference files for a skill."""
    
    @staticmethod
    def load_skill_md(skill_dir: str, max_chars: int = 12000) -> Optional[str]:
        """Load SKILL.md content with optional truncation."""
        path = SkillLoader._find_file(skill_dir, "skill.md")
        if not path:
            logger.warning(f"SKILL.md not found in {skill_dir}")
            return None
        
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n...[truncated]..."
        
        return content
    
    @staticmethod
    def load_scripts(skill_dir: str, max_files: int = 5, 
                    max_chars: int = 1200) -> List[Dict[str, str]]:
        """Load a sample of files under the scripts directory."""
        scripts = []
        
        for root, _, files in os.walk(skill_dir):
            if "scripts" not in root.split(os.sep):
                continue
            
            for filename in files:
                if len(scripts) >= max_files:
                    return scripts
                
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, skill_dir)
                
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(max_chars)
                    scripts.append({"path": rel_path, "content": content})
                except Exception as e:
                    logger.warning(f"Skip {filepath}: {e}")
        
        return scripts
    
    @staticmethod
    def load_references(
        skill_dir: str,
        max_files: int = 10,
        max_chars: int = 4000,
    ) -> List[Dict[str, str]]:
        """
        Load non-script reference files for a skill.

        This is intended for files other than SKILL.md and scripts/,
        e.g. README.md, references/, assets/, etc.
        """
        references: List[Dict[str, str]] = []

        # text-like extensions we are willing to inline
        allowed_exts = {
            ".md",
            ".txt",
            ".json",
            ".yaml",
            ".yml",
            ".ini",
            ".toml",
            ".cfg",
            ".csv",
            ".tsv",
        }

        for root, _, files in os.walk(skill_dir):
            # skip anything under scripts/
            if "scripts" in root.split(os.sep):
                continue

            for filename in files:
                if len(references) >= max_files:
                    return references

                # skip SKILL.md itself (already handled separately)
                if filename.lower() == "skill.md":
                    continue

                ext = os.path.splitext(filename)[1].lower()
                if ext and ext not in allowed_exts:
                    continue

                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, skill_dir)

                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(max_chars)
                    references.append({"path": rel_path, "content": content})
                except Exception as e:
                    logger.warning(f"Skip reference {filepath}: {e}")

        return references
    
    @staticmethod
    def _find_file(directory: str, filename: str) -> Optional[str]:
        """Recursively find a file in directory (case-insensitive)."""
        for root, _, files in os.walk(directory):
            for f in files:
                if f.lower() == filename.lower():
                    return os.path.join(root, f)
        return None


# ==========================================================================
# Prompt builder
# ==========================================================================

class PromptBuilder:
    """Build prompts for skill evaluation."""
    
    @staticmethod
    def build(skill: Skill, skill_md: Optional[str],
              scripts: List[Dict[str, str]],
              references: Optional[List[Dict[str, str]]] = None,
              script_exec_results: Optional[List[ScriptExecutionResult]] = None) -> str:
        """Build the evaluation prompt for a given skill."""
        skill_md_block = skill_md or "[SKILL.md not found]"

        if references:
            formatted_refs: List[str] = []
            for r in references:
                if not isinstance(r, dict):
                    continue
                path = r.get("path") or "[unknown path]"
                content = r.get("content") or ""
                formatted_refs.append(f"# {path}\n{content}\n")
            references_block = "\n".join(formatted_refs) if formatted_refs else "[No references or additional assets found]"
        else:
            references_block = "[No references or additional assets found]"
        
        if scripts:
            formatted_scripts: List[str] = []
            for s in scripts:
                if not isinstance(s, dict):
                    continue
                path = s.get("path") or "[unknown path]"
                content = s.get("content") or ""
                formatted_scripts.append(f"# {path}\n{content}\n")
            scripts_block = "\n".join(formatted_scripts) if formatted_scripts else "[No scripts found]"
        else:
            scripts_block = "[No scripts found]"

        if script_exec_results is None:
            script_exec_block = "[Scripts not executed]"
        elif not script_exec_results:
            script_exec_block = "[No runnable python scripts found]"
        else:
            script_exec_block = "\n".join(
                PromptBuilder._format_exec_result(r)
                for r in script_exec_results
            )
        
        return SKILL_EVALUATION_PROMPT.format(
            skill_name=skill.name,
            skill_description=skill.description or "N/A",
            category=skill.category or "N/A",
            repo_name="N/A",
            author="N/A",
            skill_md_block=skill_md_block,
            references_block=references_block,
            scripts_block=scripts_block,
            script_exec_block=script_exec_block
        )

    @staticmethod
    def _format_exec_result(result: ScriptExecutionResult) -> str:
        base = f"- {result.path}: {result.status}"
        if result.exit_code is not None:
            base += f" (exit={result.exit_code})"
        base += f" | cmd: {result.command}"
        if result.note:
            base += f" | note: {result.note}"
        if result.error:
            clean_error = " ".join(result.error.splitlines())
            base += f" | error: {clean_error}"
        return base


# ==========================================================================
# LLM client
# ==========================================================================

class LLMClient:
    """Thin wrapper around the OpenAI client for evaluation calls."""
    
    def __init__(self, config: EvaluatorConfig):
        self.client = OpenAI(api_key=config.api_key, base_url=config.base_url)
        self.model = config.model
        self.temperature = config.temperature
    
    def evaluate(self, prompt: str) -> Dict[str, Any]:
        """Call the LLM with the given prompt and parse JSON response."""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert evaluator of AI Agent Skills. "
                    "Follow the JSON schema and constraints exactly. "
                    "Use ONLY the provided metadata, SKILL.md, reference files, and scripts snippets."
                )
            },
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=self.temperature
            )
            raw_response = response.choices[0].message.content
            return json.loads(raw_response)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise


# ==========================================================================
# Core evaluator
# ==========================================================================

class SkillEvaluator:
    """
    Main entry point for evaluating AI skills.

    Typical usage:
        config = EvaluatorConfig(api_key="your-key")
        evaluator = SkillEvaluator(config)

        # Single skill from URL
        skill, err = Skill.from_url("https://github.com/.../skill", evaluator.downloader, config.cache_dir)
        if err:
            result = evaluator._create_error_result(err)
        else:
            result = evaluator.evaluate(skill)

        # Single skill from local path
        skill = Skill.from_path("/path/to/skill")
        result = evaluator.evaluate(skill)

        # Batch evaluation
        skills = [skill1, skill2, skill3]
        results = evaluator.evaluate_batch(skills)
    """
    
    def __init__(self, config: EvaluatorConfig):
        """Initialize the evaluator with configuration."""
        if not config.api_key:
            raise ValueError("API key is required")
        
        self.config = config
        self.downloader = SkillDownloader()
        self.loader = SkillLoader()
        self.prompt_builder = PromptBuilder()
        self.llm_client = LLMClient(config)
        self.script_runner = ScriptRunner(
            python_bin=config.script_python,
            timeout_sec=config.script_timeout_sec,
            max_runs=config.max_script_runs,
            max_output_chars=config.max_script_output_chars
        )
    
    def evaluate(self, skill: Skill) -> Dict[str, Any]:
        """
        Evaluate a single skill.

        Args:
            skill: A Skill instance to evaluate.

        Returns:
            A dict containing the evaluation result.
        """
        try:
            # Load content
            skill_md = self.loader.load_skill_md(skill.path)
            scripts = self.loader.load_scripts(skill.path)
            references = self.loader.load_references(skill.path)

            # Optional script execution
            script_exec_results: Optional[List[ScriptExecutionResult]] = None
            if self.config.run_scripts:
                script_exec_results = self.script_runner.run_for_skill(skill.path)

            # Build prompt
            prompt = self.prompt_builder.build(
                skill,
                skill_md,
                scripts,
                references=references,
                script_exec_results=script_exec_results
            )
            
            # Call LLM
            result = self.llm_client.evaluate(prompt)
            if self.config.include_script_results and script_exec_results is not None:
                result["script_execution"] = [
                    r.to_dict() for r in script_exec_results
                ]
            return result
            
        except Exception as e:
            skill_name = getattr(skill, "name", "[unknown skill]")
            logger.exception("Evaluation failed for %s: %s", skill_name, e)
            return self._create_error_result(str(e))
    
    def evaluate_batch(self, skills: List[Skill]) -> List[Dict[str, Any]]:
        """
        Evaluate multiple skills in parallel.

        Args:
            skills: List of Skill objects.

        Returns:
            List of evaluation results in the same order as input.
        """
        results = [None] * len(skills)
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            future_to_idx = {
                executor.submit(self.evaluate, skill): idx 
                for idx, skill in enumerate(skills)
            }
            
            with tqdm(total=len(skills), desc="Evaluating skills") as pbar:
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    results[idx] = future.result()
                    pbar.update(1)
        
        return results
    
    def evaluate_from_url(self, url: str, **kwargs) -> Dict[str, Any]:
        """Convenience helper: create and evaluate a skill from a URL."""
        skill, err = Skill.from_url(
            url, self.downloader, self.config.cache_dir, **kwargs
        )
        if err:
            return self._create_error_result(err)
        return self.evaluate(skill)
    
    def evaluate_from_path(self, path: str, **kwargs) -> Dict[str, Any]:
        """Convenience helper: create and evaluate a skill from a local path."""
        skill, err = Skill.from_path(path, **kwargs)
        if err:
            return self._create_error_result(err)
        return self.evaluate(skill)
    
    @staticmethod
    def _create_error_result(error_msg: str) -> Dict[str, Any]:
        """Create a default error-shaped evaluation result."""
        error_item = {"level": "Poor", "reason": f"Evaluation failed: {error_msg}"}
        return {
            "error": error_msg,
            "safety": error_item,
            "completeness": error_item,
            "executability": error_item,
            "modifiability": error_item,
            "cost_awareness": error_item
        }


# ==========================================================================
# CLI entry point
# ==========================================================================

if __name__ == '__main__':
    """Command line entry point for batch evaluation from JSONL."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Evaluate AI Agent Skills')
    parser.add_argument('--input', required=True, help='Input JSONL file')
    parser.add_argument('--output', required=True, help='Output JSONL file')
    parser.add_argument('--api-key', help='OpenAI API key')
    parser.add_argument('--base-url', help='OpenAI API base URL')
    parser.add_argument('--model', default='gpt-4o', help='Model name')
    parser.add_argument('--max-workers', type=int, default=5, help='Max workers')
    parser.add_argument('--cache-dir', default='skill_downloads', help='Cache directory')
    parser.add_argument('--run-scripts', action='store_true',
                        help='Execute python scripts under scripts/')
    parser.add_argument('--script-timeout', type=int, default=8,
                        help='Timeout seconds per script run')
    parser.add_argument('--max-script-runs', type=int, default=5,
                        help='Max python scripts to execute per skill')
    parser.add_argument('--script-python', default='python',
                        help='Python executable for running scripts')
    parser.add_argument('--include-script-results', action='store_true',
                        help='Attach script execution results to evaluation output')
    parser.add_argument('--max-script-output-chars', type=int, default=400,
                        help='Max chars of script stdout/stderr to keep')
    
    args = parser.parse_args()
    
    with open(args.input, 'r', encoding='utf-8') as f:
        records = [json.loads(line) for line in f if line.strip()]
    
    config = EvaluatorConfig(
        api_key=args.api_key or os.getenv('API_KEY'),
        base_url=args.base_url or os.getenv('BASE_URL'),
        model=args.model,
        max_workers=args.max_workers,
        cache_dir=args.cache_dir,
        run_scripts=args.run_scripts,
        script_timeout_sec=args.script_timeout,
        max_script_runs=args.max_script_runs,
        script_python=args.script_python,
        include_script_results=args.include_script_results,
        max_script_output_chars=args.max_script_output_chars
    )
    evaluator = SkillEvaluator(config)
    
    skills = []
    download_errors = {}  # idx -> error_msg
    for idx, rec in enumerate(records):
        if 'skill_url' in rec:
            skill, err = Skill.from_url(
                rec['skill_url'],
                evaluator.downloader,
                config.cache_dir,
                name=rec.get('skill_name'),
                description=rec.get('skill_description'),
                category=rec.get('category')
            )
            if err:
                download_errors[idx] = err
                skills.append(None)
            else:
                skills.append(skill)
        elif 'skill_path' in rec:
            skill, err = Skill.from_path(
                rec['skill_path'],
                name=rec.get('skill_name'),
                description=rec.get('skill_description'),
                category=rec.get('category')
            )
            if err:
                download_errors[idx] = err
                skills.append(None)
            else:
                skills.append(skill)
        else:
            raise ValueError("Record must have 'skill_url' or 'skill_path'")

    # Use error results for failed downloads, and evaluate the rest in parallel
    skills_to_eval = [(idx, s) for idx, s in enumerate(skills) if s is not None]
    idx_to_result: Dict[int, Dict[str, Any]] = {}
    if skills_to_eval:
        indices, valid_skills = zip(*skills_to_eval)
        batch_results = evaluator.evaluate_batch(list(valid_skills))
        idx_to_result = dict(zip(indices, batch_results))
    results = [
        evaluator._create_error_result(download_errors[idx])
        if idx in download_errors
        else idx_to_result[idx]
        for idx in range(len(records))
    ]
    
    for rec, result in zip(records, results):
        rec['evaluation'] = result
    
    with open(args.output, 'w', encoding='utf-8') as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    
    json_path = args.output.replace('.jsonl', '.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({str(i): rec for i, rec in enumerate(records)}, 
                 f, ensure_ascii=False, indent=2)
    
    print(f"✓ Evaluated {len(results)} skills")
    print(f"✓ Results saved to {args.output} and {json_path}")