"""
Skill Search & Download Example - Using SkillNetClient
"""
from skillnet_ai import SkillNetClient


def main():
    # Initialize client (api_key optional for search/download)
    client = SkillNetClient()

    # Search for skills
    print("🔍 Searching for skills: pdf")
    results = client.search(q="pdf", limit=5)

    if not results:
        print("❌ No skills found.")
        return

    print(f"✅ Found {len(results)} skills.\n")
    for skill in results:
        print(f"  - {skill.skill_name} (⭐ {skill.stars})")

    # Download top skill
    top_skill = results[0]
    if top_skill.skill_url:
        print(f"\n⬇️ Downloading: {top_skill.skill_name}")
        local_path = client.download(url=top_skill.skill_url, target_dir="./my_skills")
        print(f"🎉 Installed at: {local_path}")


if __name__ == "__main__":
    main()