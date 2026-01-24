import os
import json
import logging
import shutil
from typing import Dict, Any
from skillnet_ai import SkillEvaluator, EvaluatorConfig

# Setup logging configuration
logging.basicConfig(level=logging.INFO)

def main():
    # 1. Configure Evaluator
    api_key = os.getenv("API_KEY")
    if not api_key:
        print("Please set API_KEY environment variable to run this demo.")
        return
    base_url = os.getenv("BASE_URL") or "https://api.openai.com/v1" # Optional, custom base URL or default

    config = EvaluatorConfig(
        api_key=api_key,
        base_url=base_url,
        model="gpt-4o",
        temperature=0.2,
    )
    
    try:
        evaluator = SkillEvaluator(config)
        print("Evaluator initialized successfully.")
    except Exception as e:
        print(f"Failed to init evaluator: {e}")
        return

    # =================================================================
    # A: Evaluate Local Skill Path
    # =================================================================
    local_skill_path = "/zjunlp/liangyuan/code/skills-resource/skillnet-ai/created_skills/pdf-invoice-data-extractor"  # replace with your local skill path
    
    try:
        print(f"Starting evaluation for local path: {local_skill_path}")
        
        result_local = evaluator.evaluate_from_path(
            local_skill_path
        )
        
        print("Local Skill Evaluation", result_local)
        
    except Exception as e:
        print(f"Local evaluation failed: {e}")

    # =================================================================
    # B: Evaluate Skill from URL
    # =================================================================
    target_url = "https://github.com/anthropics/skills/tree/main/skills/algorithmic-art"
    
    try:
        print(f"Starting evaluation for URL: {target_url}")
        
        result_url = evaluator.evaluate_from_url(
            target_url,
            description="Auto-downloaded skill for web searching"
        )
        
        print("URL Skill Evaluation", result_url)
        
    except Exception as e:
        print(f"URL evaluation failed (Create mock Downloader to fix): {e}")

if __name__ == "__main__":
    main()