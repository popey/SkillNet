"""
Skill Evaluation Example - Using SkillNetClient
"""
import os
from skillnet_ai import SkillNetClient


def main():
    # Initialize client
    client = SkillNetClient(
        api_key=os.getenv("API_KEY"),
        base_url=os.getenv("BASE_URL", "https://api.openai.com/v1"),
    )

    # Evaluate a remote skill from GitHub
    print("📊 Evaluating remote skill...")
    result = client.evaluate(
        target="https://github.com/anthropics/skills/tree/main/skills/algorithmic-art"
    )
    print("Result:", result)

    # Evaluate a local skill directory
    print("\n📊 Evaluating local skill...")
    result = client.evaluate(target="./my_skills/example-skill")
    print("Result:", result)


if __name__ == "__main__":
    main()