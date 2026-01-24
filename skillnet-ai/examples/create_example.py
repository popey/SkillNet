import os
import logging
from skillnet_ai import SkillCreator

# Setup logging
logging.basicConfig(level=logging.INFO)

# Dummy trajectory data for demonstration
SAMPLE_TRAJECTORY = """
User: Please analyze this invoice.pdf and extract the total amount and date.
Agent: I will use the PDF tool. Opening invoice.pdf...
Agent: Text extracted. Found 'Total: $500' and 'Date: 2023-10-12'.
Agent: The total is $500 and the date is Oct 12, 2023.
"""

def main():
    # Ensure you have API_KEY set in your environment
    api_key = os.getenv("API_KEY")
    if not api_key:
        print("Please set API_KEY environment variable to run this demo.")
        return
    base_url = os.getenv("BASE_URL") or "https://api.openai.com/v1" # Optional, custom base URL or default

    creator = SkillCreator(api_key=api_key, base_url=base_url, model="gpt-4o")
    
    print("🚀 Starting skill creation from trajectory...")
    
    try:
        # Create skills into the ./created_skills folder
        paths = creator.create_from_trajectory(
            trajectory=SAMPLE_TRAJECTORY, 
            output_dir="./created_skills"
        )
        
        print("\n✨ Creation Complete!")
        for p in paths:
            print(f" - Created Skill at: {p}")
            
    except Exception as e:
        print(f"❌ Error during creation: {e}")

if __name__ == "__main__":
    main()