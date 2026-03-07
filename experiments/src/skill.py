import json
import os
import re
from pathlib import Path
from tqdm import tqdm
import yaml

from src.utils import get_llm_response
from src.prompt_generator import (
    retrieve_relevant_skills_prompt,
    generate_overall_procedure_prompt,
    generate_overall_procedure_code_prompt
)


class SkillModule:
    def __init__(self, **kwargs):
        self.skills_dir = Path(kwargs.get("skills_dir", "skills"))
        self.overall_procedure_examples_path = kwargs.get("overall_procedure_examples_path", "")
        self.procedure_code_template_path = kwargs.get("procedure_code_template_path", None)
        self.model = kwargs.get("model", "gpt-4o")

        self.metadata = self._load_metadata()

        # Load procedure code template and overall procedure examples
        if self.procedure_code_template_path is not None and os.path.exists(self.procedure_code_template_path):
            with open(self.procedure_code_template_path, "r") as f:
                self.procedure_code_template = f.read()
        else:
            self.procedure_code_template = ''

        if self.overall_procedure_examples_path is not None and os.path.exists(self.overall_procedure_examples_path):
            with open(self.overall_procedure_examples_path, "r") as f:
                self.overall_procedure_examples = f.read()
        else:
            self.overall_procedure_examples = ''


    def _load_metadata(self):
        """Load existing metadata from file, return empty dict if file does not exist."""
        metadata = {}
        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_md_path = skill_dir / "SKILL.md"
                if skill_md_path.exists():
                    try:
                        content = skill_md_path.read_text(encoding="utf-8")
                        if content.strip().startswith('---'):
                            parts = content.split('---', 2)
                            if len(parts) >= 3:
                                header_str = parts[1]
                                header_data = yaml.safe_load(header_str)
                                if isinstance(header_data, dict) and header_data.get('name') and header_data.get('description'):
                                    metadata[header_data['name']] = {
                                        'description': header_data['description'],
                                        'skill_dir': str(skill_dir)
                                    }
                                else:
                                    print(f"[WARNING] Invalid metadata format in {skill_dir.name}, skipping.")
                            else:
                                print(f"[WARNING] No valid metadata found in {skill_dir.name}, skipping.")
                        else:
                            print(f"[WARNING] No metadata header found in {skill_dir.name}, skipping.")
                    except Exception as e:
                        print(f"[ERROR] Failed to read or parse SKILL.md for {skill_dir.name}: {e}")
                else:
                    print(f"[WARNING] SKILL.md not found for {skill_dir.name}, skipping.")
        print(f"[INFO] Loaded metadata for {len(metadata)} skills.")
        return metadata
    
    def retrieve_relevant_skills(self, task):
        """
        Retrieve relevant skills from metadata based on task description.
        """
        response = get_llm_response(
            retrieve_relevant_skills_prompt(self.metadata, task),
            is_string=True,
            model=self.model
        )
        relevant_skill_names = response.split("<Relevant_Skill_Names>")[1].split("</Relevant_Skill_Names>")[0].strip("`json\n").strip("`\n").strip("```\n")
        relevant_skill_names = json.loads(relevant_skill_names)

        return relevant_skill_names
    
    def generate_overall_procedure(self, task, skill_names):
        """
        Generate overall procedure by combining individual skill contents.
        """
        # skill_contents = []
        # try:
        #     for skill_name in skill_names:
        #         skill_path = Path(self.metadata[skill_name]['path'])
        #         with open(skill_path, 'r') as file:
        #             skill_content = file.read()
        #         skill_contents.append((skill_name, skill_content))
        # except Exception as e:
        #     print(f"[ERROR] Failed to read skill scripts: {e}")
        skill_contents = []
        try:
            for skill_name in skill_names:
                skill_dir = Path(self.metadata[skill_name]['skill_dir'])
                if not skill_dir.is_dir():
                    continue

                # 1. Initialize combined text with skill name as header
                combined_text = f"=== Skill: {skill_name} ===\n"
                
                # 2. First read the main SKILL.md for core instructions, if it exists
                main_file = skill_dir / "SKILL.md"
                if main_file.exists():
                    combined_text += f"\n[File: SKILL.md]\n"
                    combined_text += main_file.read_text(encoding='utf-8') + "\n"
                
                # 3. Then read all other files in the skill directory (excluding SKILL.md) and append their content
                for file_path in skill_dir.rglob('*'):
                    if file_path.is_file() and file_path.name != "SKILL.md":
                        try:
                            relative_path = file_path.relative_to(skill_dir)
                            content = file_path.read_text(encoding='utf-8')
                            
                            combined_text += f"\n[File: {relative_path}]\n"
                            combined_text += content + "\n"
                        except (UnicodeDecodeError, Exception):
                            continue
                
                skill_contents.append((skill_name, combined_text))
                
        except Exception as e:
            print(f"[ERROR] Failed to compile skill data: {e}")

        response = get_llm_response(
            generate_overall_procedure_prompt(task, self.overall_procedure_examples, skill_contents),
            is_string=True,
            model=self.model
        )
        overall_procedure = response.split("<Overall_Procedure>")[1].split("</Overall_Procedure>")[0].strip()
        return overall_procedure
    
    def generate_overall_procedure_code(self, task, overall_procedure):
        """
        Generate overall procedure code.
        """
        response = get_llm_response(
            generate_overall_procedure_code_prompt(task, overall_procedure, self.procedure_code_template),
            is_string=True,
            model=self.model
        )
        pattern = r"<Overall_Procedure_Code>(.*?)</Overall_Procedure_Code>"
        matchs = re.findall(pattern, response, re.DOTALL)
        if matchs:
            raw_content = matchs[-1]
            if "<Overall_Procedure_Code>" in raw_content: # handle nested tags
                overall_procedure_code = raw_content.split("<Overall_Procedure_Code>")[-1]
            overall_procedure_code = raw_content.strip().strip("```python").strip("```")
        else:
            overall_procedure_code = ""

        return overall_procedure_code