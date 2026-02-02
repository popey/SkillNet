"""
Skill Relationship Analysis Example - Using SkillNetClient
"""
import os
import shutil
from typing import List, Dict
from skillnet_ai import SkillNetClient

# Define directory for demonstration
DEMO_SKILLS_DIR = "./demo_skills_library"

def setup_demo_environment():
    """
    Helper to create a few dummy skills locally so the analyzer has something to scan.
    In a real scenario, you would point this to your actual skills directory.
    """
    if os.path.exists(DEMO_SKILLS_DIR):
        shutil.rmtree(DEMO_SKILLS_DIR)
    os.makedirs(DEMO_SKILLS_DIR)

    # Define some dummy skills with descriptions that imply relationships
    dummy_skills = [
        {
            "name": "python_runtime",
            "desc": "Sets up the base Python 3.10 environment with standard libraries. This is the foundational layer."
        },
        {
            "name": "code_interpreter",
            "desc": "Executes arbitrary Python code snippets safely. It strictly REQUIRES the 'python_runtime' to be installed and active to function."
        },
        {
            "name": "code_review_agent",
            "desc": "A high-level AI agent that manages the entire Pull Request review workflow, including syntax checking, logic analysis, and comment generation."
        },
        {
            "name": "linter_tool",
            "desc": "A specific tool that checks code style (PEP8). It is a built-in sub-component/module of the larger 'code_review_agent'."
        },
        {
            "name": "git_diff_reader",
            "desc": "Extracts changes between two git commits."
        },
        {
            "name": "patch_generator",
            "desc": "Generates a fix patch file. It is typically used immediately AFTER 'git_diff_reader' has identified the bugs."
        },
        {
            "name": "postgres_client",
            "desc": "A database client for connecting to PostgreSQL databases to execute SQL queries."
        },
        {
            "name": "mysql_client",
            "desc": "A database client for connecting to MySQL databases. It performs the same function as 'postgres_client' and can be used as a substitute."
        }
    ]

    # Create skill folders and SKILL.md files
    for skill in dummy_skills:
        skill_path = os.path.join(DEMO_SKILLS_DIR, skill["name"])
        os.makedirs(skill_path, exist_ok=True)
        with open(os.path.join(skill_path, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(f"---\nname: {skill['name']}\ndescription: {skill['desc']}\n---\n")
            f.write(f"# {skill['name']}\n\n{skill['desc']}")
    
    print(f"📦 Created {len(dummy_skills)} dummy skills in '{DEMO_SKILLS_DIR}' for analysis.")


def main():
    # 1. Setup demo data (Optional: remove if you have your own skills folder)
    setup_demo_environment()

    # 2. Initialize client
    client = SkillNetClient(
        api_key=os.getenv("API_KEY"),
        base_url=os.getenv("BASE_URL", "https://api.openai.com/v1")
    )

    # 3. Run Analysis
    print("\n🚀 Analyzing relationships between skills...")
    try:
        relationships = client.analyze(
            skills_dir=DEMO_SKILLS_DIR,
            save_to_file=True,
            model="gpt-4o"
        )

        # 4. Display Results
        if not relationships:
            print("No relationships detected.")
            return

        print(f"\n✅ Analysis Complete! Found {len(relationships)} connections:\n")
        
        # Simple header
        print(f"{'Source':<20} | {'Relationship':<15} | {'Target':<20} | {'Reasoning'}")
        print("-" * 100)

        for relationship in relationships:
            source = relationship.get('source', 'N/A')
            rtype = relationship.get('type', 'N/A')
            target = relationship.get('target', 'N/A')
            reason = relationship.get('reason', '')[:40] + "..." # Truncate for display

            print(f"{source:<20} | {rtype:<15} | {target:<20} | {reason}")

        print(f"\n💾 relationships saved to: {os.path.join(DEMO_SKILLS_DIR, 'relationships.json')}")

    except Exception as e:
        print(f"❌ Analysis failed: {e}")

if __name__ == "__main__":
    main()