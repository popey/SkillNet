import os
import json
import logging
import re
from typing import List, Dict, Any, Optional

from openai import OpenAI
from skillnet_ai.prompts import (
    RELATIONSHIP_ANALYSIS_SYSTEM_PROMPT,
    RELATIONSHIP_ANALYSIS_USER_PROMPT_TEMPLATE
)

logger = logging.getLogger(__name__)

class SkillRelationshipAnalyzer:
    """
    Analyzes a directory of skills to determine relationships between them.
    
    Relationships determined:
    - similar_to: A and B are functionally similar and interchangeable.
    - belong_to: A is a sub-task/part of B (B is the larger scope).
    - compose_with: A and B are independent but often used together.
    - depend_on: A requires B to execute (prerequisite).
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("API_KEY")
        self.base_url = base_url or os.getenv("BASE_URL") or "https://api.openai.com/v1"
        self.model = model
        
        if not self.api_key:
            raise ValueError("API Key is missing. Please provide it in init or set API_KEY environment variable.")
            
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def analyze_local_skills(self, skills_dir: str, save_to_file: bool = True) -> List[Dict[str, Any]]:
        """
        Main entry point: Scans a directory for skills and maps their relationships.

        Args:
            skills_dir: Path to the directory containing skill folders.
            save_to_file: Whether to save the result as 'relationships.json' in the dir.

        Returns:
            A list of relationship dictionaries:
            [
                {
                    "source": "skill_a",
                    "target": "skill_b",
                    "type": "depend_on",
                    "reason": "Skill A imports modules provided by Skill B"
                },
                ...
            ]
        """
        logger.info(f"Starting relationship analysis in: {skills_dir}")
        
        if not os.path.exists(skills_dir):
            raise FileNotFoundError(f"Directory not found: {skills_dir}")

        # 1. Load Skill Metadata
        skills_metadata = self._load_skills_metadata(skills_dir)
        if len(skills_metadata) < 2:
            logger.warning("Not enough skills found to analyze relationships (need at least 2).")
            return []

        logger.info(f"Found {len(skills_metadata)} skills. Analyzing potential connections...")

        # 2. Analyze with LLM
        relationships = self._generate_relationship_graph(skills_metadata)
        
        # 3. Save Results
        if save_to_file and relationships:
            output_path = os.path.join(skills_dir, "relationships.json")
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(relationships, f, indent=2, ensure_ascii=False)
                logger.info(f"Relationships saved to: {output_path}")
            except IOError as e:
                logger.error(f"Failed to save relationships file: {e}")

        return relationships

    def _load_skills_metadata(self, root_dir: str) -> List[Dict[str, str]]:
        """
        Walks the directory to extract 'name' and 'description' from SKILL.md or README.md.
        """
        skills = []
        
        # Assuming typical structure: root_dir/skill_name/SKILL.md
        for entry in os.scandir(root_dir):
            if entry.is_dir():
                skill_path = entry.path
                skill_name = entry.name
                description = "No description provided."
                
                # Try to read SKILL.md
                content_file = None
                if os.path.exists(os.path.join(skill_path, "SKILL.md")):
                    content_file = os.path.join(skill_path, "SKILL.md")
                
                if content_file:
                    try:
                        with open(content_file, 'r', encoding='utf-8') as f:
                            raw_content = f.read()
                            # Extract description from Frontmatter or first paragraph
                            description = self._extract_description(raw_content)
                    except Exception as e:
                        logger.warning(f"Could not read content for {skill_name}: {e}")

                skills.append({
                    "name": skill_name,
                    "description": description
                })
        
        return skills

    def _extract_description(self, content: str) -> str:
        """Helper to parse description from markdown frontmatter or body."""
        # 1. Try YAML Frontmatter
        frontmatter_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
        if frontmatter_match:
            fm_text = frontmatter_match.group(1)
            # Simple regex search for description: ... line
            desc_match = re.search(r'description:\s*(.+)$', fm_text, re.MULTILINE)
            if desc_match:
                return desc_match.group(1).strip().strip('"').strip("'")
        
        # 2. Fallback: Use the first non-header text block
        # Remove headers
        clean_text = re.sub(r'#+\s.*', '', content)
        # Remove code blocks
        clean_text = re.sub(r'```.*?```', '', clean_text, flags=re.DOTALL)
        lines = [line.strip() for line in clean_text.split('\n') if line.strip()]
        
        if lines:
            return lines[0]
            
        return "No description available."

    def _generate_relationship_graph(self, skills: List[Dict]) -> List[Dict]:
        """Calls LLM to infer edges between nodes."""
        
        skills_json = json.dumps(skills, indent=2)
        
        messages = [
            {"role": "system", "content": RELATIONSHIP_ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": RELATIONSHIP_ANALYSIS_USER_PROMPT_TEMPLATE.format(
                skills_list=skills_json
            )}
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            content = response.choices[0].message.content
            
            parsed = json.loads(content)
            edges = parsed.get("relationships", [])
            
            # Validate edges structure
            valid_edges = []
            valid_names = {s['name'] for s in skills}
            
            for edge in edges:
                if (edge.get('source') in valid_names and 
                    edge.get('target') in valid_names and 
                    edge.get('type') in ['similar_to', 'belong_to', 'compose_with', 'depend_on']):
                    valid_edges.append(edge)
                    
            logger.info(f"Identified {len(valid_edges)} valid relationships.")
            return valid_edges

        except Exception as e:
            logger.error(f"Failed to analyze relationships: {e}")
            return []