"""
Skill Creation Example - Using SkillNetClient
"""
import os
from skillnet_ai import SkillNetClient

# Sample trajectory
SAMPLE_TRAJECTORY = """
User: Please analyze this invoice.pdf and extract the total amount and date.
Agent: I will use the PDF tool. Opening invoice.pdf...
Agent: Text extracted. Found 'Total: $500' and 'Date: 2023-10-12'.
Agent: The total is $500 and the date is Oct 12, 2023.
"""

# Sample GitHub repository URL
SAMPLE_GITHUB_URL = "https://github.com/zjunlp/DeepKE"


def main():
    # Initialize client
    client = SkillNetClient(
        api_key=os.getenv("API_KEY"),
        base_url=os.getenv("BASE_URL", "https://api.openai.com/v1"),
        github_token=os.getenv("GITHUB_TOKEN"),
    )

    # Example 1: Create from trajectory
    print("🚀 Creating skill from trajectory...")
    paths = client.create(
        trajectory_content=SAMPLE_TRAJECTORY,
        output_dir="./created_skills"
    )
    for p in paths:
        print(f" - {p}")

    # Example 2: Create from GitHub repository
    print("\n🚀 Creating skill from GitHub...")
    paths = client.create(
        github_url=SAMPLE_GITHUB_URL,
        output_dir="./created_skills"
    )
    for p in paths:
        print(f" - {p}")


if __name__ == "__main__":
    main()