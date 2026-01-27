import os
import logging
from skillnet_ai import SkillCreator

logging.basicConfig(level=logging.INFO)

# Sample trajectory for demonstration
SAMPLE_TRAJECTORY = """
User: Please analyze this invoice.pdf and extract the total amount and date.
Agent: I will use the PDF tool. Opening invoice.pdf...
Agent: Text extracted. Found 'Total: $500' and 'Date: 2023-10-12'.
Agent: The total is $500 and the date is Oct 12, 2023.
"""


def create_from_trajectory():
    """Create skill from execution trajectory."""
    api_key = os.getenv("API_KEY")
    if not api_key:
        print("Please set API_KEY environment variable.")
        return
    
    base_url = os.getenv("BASE_URL") or "https://api.openai.com/v1"
    creator = SkillCreator(api_key=api_key, base_url=base_url, model="gpt-4o")
    
    print("🚀 Creating skill from trajectory...")
    
    try:
        paths = creator.create_from_trajectory(
            trajectory=SAMPLE_TRAJECTORY, 
            output_dir="./created_skills"
        )
        print("\n✨ Creation Complete!")
        for p in paths:
            print(f" - Created: {p}")
    except Exception as e:
        print(f"❌ Error: {e}")


def create_from_github():
    """Create skill from GitHub repository."""
    api_key = os.getenv("API_KEY")
    if not api_key:
        print("Please set API_KEY environment variable.")
        return
    
    base_url = os.getenv("BASE_URL") or "https://api.openai.com/v1"
    github_token = os.getenv("GITHUB_TOKEN")
    
    creator = SkillCreator(api_key=api_key, base_url=base_url, model="gpt-4o")
    
    # Example: DeepKE - Knowledge Extraction Toolkit
    github_url = "https://github.com/zjunlp/DeepKE"
    
    print(f"🚀 Creating skill from GitHub: {github_url}")
    
    try:
        paths = creator.create_from_github(
            github_url=github_url,
            output_dir="./created_skills",
            api_token=github_token,
            max_files=20
        )
        print("\n✨ Creation Complete!")
        for p in paths:
            print(f" - Created: {p}")
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--github":
        create_from_github()
    else:
        create_from_trajectory()
        print("\n💡 Tip: Use --github flag to create from GitHub repository")


if __name__ == "__main__":
    main()