import logging
from skillnet_ai import SkillNetSearcher, SkillDownloader

# Setup logging configuration
logging.basicConfig(level=logging.INFO)

def main():
    # Initialize the searcher
    searcher = SkillNetSearcher()
    
    query = "python"
    print(f"🔍 Searching for: {query}")
    
    # Perform AI Search (Vector mode)
    # Note: We now use the unified 'search' method with mode="vector"
    results = searcher.search(
        q=query, 
        limit=10,
        category="Development",
    )
    
    if not results:
        print("❌ No skills found.")
        return

    print(f"✅ Found {len(results)} skills.")
    
    # Display the top result
    top_skill = results[0]
    print(f"Top Skill: {top_skill.skill_name} (Stars: {top_skill.stars})")
    print(f"Description: {top_skill.skill_description}")
    
    # Install the skill if a valid URL exists
    if top_skill.skill_url:
        print("⬇️  Installing skill...")
        skilldownloader = SkillDownloader()
        
        # Download the skill to a local directory
        local_path = skilldownloader.download(
            top_skill.skill_url, 
            target_dir="./my_skills"
        )
        
        if local_path:
            print(f"🎉 Skill ready at: {local_path}")
        else:
            print("⚠️ Download failed or returned no path.")
    else:
        print("ℹ️  No download URL available for this skill.")

if __name__ == "__main__":
    main()