import os
import json
import re
import logging
from typing import List, Optional
from openai import OpenAI
from skillnet_ai.prompts import (
    CANDIDATE_METADATA_SYSTEM_PROMPT,
    CANDIDATE_METADATA_USER_PROMPT_TEMPLATE,
    SKILL_CONTENT_SYSTEM_PROMPT,
    SKILL_CONTENT_USER_PROMPT_TEMPLATE
)

logger = logging.getLogger(__name__)

class SkillCreator:
    """
    Creates Skill packages from execution trajectories using OpenAI-compatible LLMs.
    """
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("API_KEY")
        self.base_url = base_url or os.getenv("BASE_URL") or "https://api.openai.com/v1"
        self.model = model
        
        if not self.api_key:
            raise ValueError("API Key is missing. Please provide it in init or set API_KEY environment variable.")
            
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _get_llm_response(self, messages: List[dict]) -> str:
        """Helper to call LLM and get string content."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM Call Failed: {e}")
            raise

    def create_from_trajectory(self, trajectory: str, output_dir: str = ".") -> List[str]:
        """
        Main entry point: Analyze trajectory and create skill files.
        
        Args:
            trajectory: The string content of the user's action log/trajectory.
            output_dir: The directory where skills should be saved.
            
        Returns:
            List of paths to the created skill directories.
        """
        logger.info("Step 1: Analyzing trajectory to identify skills...")
        
        # 1. Create Metadata
        meta_messages = [
            {"role": "system", "content": CANDIDATE_METADATA_SYSTEM_PROMPT},
            {"role": "user", "content": CANDIDATE_METADATA_USER_PROMPT_TEMPLATE.format(trajectory=trajectory)}
        ]
        
        raw_meta_response = self._get_llm_response(meta_messages)
        candidates = self._parse_candidate_metadata(raw_meta_response)
        
        if not candidates:
            logger.warning("No skills identified in the trajectory.")
            return []

        created_paths = []
        
        # 2. Create Content for each candidate
        for cand in candidates:
            name = cand.get("name")
            description = cand.get("description")
            logger.info(f"Creating content for skill: {name}...")
            
            content_messages = [
                {"role": "system", "content": SKILL_CONTENT_SYSTEM_PROMPT},
                {"role": "user", "content": SKILL_CONTENT_USER_PROMPT_TEMPLATE.format(
                    trajectory=trajectory, name=name, description=description
                )}
            ]
            
            raw_content_response = self._get_llm_response(content_messages)
            
            # 3. Parse and Save Files
            self._save_skill_files(raw_content_response, output_dir)
            created_paths.append(os.path.join(output_dir, name))
            
        return created_paths

    def _parse_candidate_metadata(self, llm_output: str) -> List[dict]:
        """Extract JSON from the LLM output tags."""
        try:
            # Look for content between <Skill_Candidate_Metadata> tags
            if "<Skill_Candidate_Metadata>" in llm_output:
                json_str = llm_output.split("<Skill_Candidate_Metadata>")[1].split("</Skill_Candidate_Metadata>")[0]
            else:
                # Fallback: try to find the first JSON list block
                json_str = llm_output
            
            # clean markdown code blocks if present
            json_str = json_str.replace("```json", "").replace("```", "").strip()
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Failed to parse metadata JSON: {e}")
            return []

    def _save_skill_files(self, llm_output: str, output_base_dir: str):
        """Parse the FILE blocks and write them to disk."""
        # Regex to find: ## FILE: path \n ```lang \n content \n ```
        pattern = re.compile(r'##\s*FILE:\s*(.+?)\s*\n```(?:\w*)\n(.*?)```', re.DOTALL)
        matches = pattern.findall(llm_output)
        
        if not matches:
            logger.warning("No file blocks found in LLM output.")
            return

        for file_path, content in matches:
            file_path = file_path.strip()
            full_path = os.path.join(output_base_dir, file_path)
            
            # Create directory if missing
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            try:
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.info(f"Saved: {full_path}")
            except IOError as e:
                logger.error(f"Failed to write {full_path}: {e}")