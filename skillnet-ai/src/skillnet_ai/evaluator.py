import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

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
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"
    cache_dir: str = ".skill_cache"
    max_workers: int = 5
    temperature: float = 0.3


@dataclass
class Skill:
    """Unified representation of a skill."""
    path: str  # Local path to the skill root directory
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    url: Optional[str] = None  # Original URL (when created from URL)
    
    @classmethod
    def from_url(cls, url: str, downloader: 'SkillDownloader', 
                 cache_dir: str, **kwargs) -> 'Skill':
        """Create a Skill from a GitHub URL."""
        normalized_url = cls._normalize_url(url)
        if not normalized_url:
            raise ValueError(f"Invalid GitHub URL: {url}")
        # Download to local cache
        local_path = downloader.download(normalized_url, target_dir=cache_dir)
        if not local_path:
            raise RuntimeError(f"Failed to download: {url}")
        # Derive skill name from URL if not provided
        name = kwargs.get('name') or normalized_url.rstrip('/').split('/')[-1]
        
        return cls(
            path=local_path,
            name=name,
            url=url,
            description=kwargs.get('description'),
            category=kwargs.get('category')
        )
    
    @classmethod
    def from_path(cls, path: str, **kwargs) -> 'Skill':
        """Create a Skill from a local directory path."""
        abs_path = os.path.abspath(path)
        if not os.path.isdir(abs_path):
            raise ValueError(f"Invalid skill path: {path}")
        
        name = kwargs.get('name') or os.path.basename(abs_path)
        
        return cls(
            path=abs_path,
            name=name,
            description=kwargs.get('description'),
            category=kwargs.get('category')
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


# ==========================================================================
# Skill content loader
# ==========================================================================

class SkillLoader:
    """Load SKILL.md and script files for a skill."""
    
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
              scripts: List[Dict[str, str]]) -> str:
        """Build the evaluation prompt for a given skill."""
        skill_md_block = skill_md or "[SKILL.md not found]"
        
        if scripts:
            scripts_block = "\n".join([
                f"# {s['path']}\n{s['content']}\n" for s in scripts
            ])
        else:
            scripts_block = "[No scripts found]"
        
        return SKILL_EVALUATION_PROMPT.format(
            skill_name=skill.name,
            skill_description=skill.description or "N/A",
            category=skill.category or "N/A",
            repo_name="N/A",
            author="N/A",
            skill_md_block=skill_md_block,
            scripts_block=scripts_block
        )


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
                    "Use ONLY the provided metadata, SKILL.md, and scripts snippets."
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
        skill = Skill.from_url("https://github.com/.../skill", evaluator.downloader, config.cache_dir)
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
            
            # Build prompt
            prompt = self.prompt_builder.build(skill, skill_md, scripts)
            
            # Call LLM
            return self.llm_client.evaluate(prompt)
            
        except Exception as e:
            logger.error(f"Evaluation failed for {skill.name}: {e}")
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
        skill = Skill.from_url(url, self.downloader, self.config.cache_dir, **kwargs)
        return self.evaluate(skill)
    
    def evaluate_from_path(self, path: str, **kwargs) -> Dict[str, Any]:
        """Convenience helper: create and evaluate a skill from a local path."""
        skill = Skill.from_path(path, **kwargs)
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