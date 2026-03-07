import os
from openai import OpenAI
import re
from retry import retry
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import json
import sys
import argparse

from scienceworld import ScienceWorldEnv

from src.scienceworld.prompts.system_prompt import scienceworld_system_prompt
from src.skill import SkillModule

client = OpenAI(
    api_key=os.environ["API_KEY"],
    base_url=os.environ["BASE_URL"]
)

@retry(tries=5, delay=5, backoff=2, jitter=(1, 3))
def llm(prompt, model="YOUR_MODEL_NAME"):
    print(f'Calling LLM with model: {model}')
    # Normalize messages format
    if isinstance(prompt, list):
        messages = prompt
    elif isinstance(prompt, str):
        messages = [{"role": "user", "content": prompt}]
    else:
        raise ValueError(f'prompt must be a list or a string, but got {type(prompt)}')
    response = client.chat.completions.create(
        model=model,
        messages=messages
    )
    # Extract content
    content = response.choices[0].message.content
    if content is not None:
        return content
    return "Output Error"



# ==========================================
# Constants & Configuration
# ==========================================

class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

# ==========================================
# Helper Functions
# ==========================================

def parse_action(response: str) -> str:
    """
    Extracts the action from the LLM response using regex.
    """
    pattern = re.compile(r"Action:\s*(.+)", re.IGNORECASE)
    match = pattern.search(response)
    if match:
        return match.group(1).strip().strip('"\'*`')
    return ""

def run_standard_procedure(env, llm, model, messages, max_steps):
    """
    Executes the standard interaction loop when no skills are used.
    """
    task_done = False
    task_reward = 0
    current_steps = 0

    while not task_done and current_steps < max_steps:
        current_steps += 1
        
        # 1. Get Agent Response
        try:
            response = llm(messages, model)
            print(f'{Colors.GREEN}Agent response: \n{response}{Colors.RESET}')
        except Exception as e:
            print(f'{Colors.RED}Error in LLM call: {e}{Colors.RESET}')
            break

        messages.append({"role": "assistant", "content": response})

        # 2. Parse and Execute Action
        action = parse_action(response)
        observation, step_reward, task_done, info = env.step(action)

        task_reward = info['score'] if info['score'] is not None and info['score'] > task_reward else task_reward

        print(f'{Colors.YELLOW}Observation: \n{observation}{Colors.RESET}')

        # 3. Update History
        messages.append({"role": "user", "content": f"Observation: {observation}"})

        if task_done:
            print(f'{Colors.GREEN}Whole Task completed! Reward: {task_reward}{Colors.RESET}')

    return messages, task_done, task_reward, current_steps

# ==========================================
# Core Execution Logic
# ==========================================

def scienceworld_run_single(env, task_name, var_idx, args, Skill_Module=None):
    """
    Execute a single task variation.
    """
    # 1. Reset Environment & Get Initial Observation
    # ScienceWorld reset returns (observation, info)
    obs, info = env.reset()
    
    # Construct Task Description
    query = env.get_task_description()
    
    print(f'{Colors.RED}Processing: {task_name} (Var: {var_idx}){Colors.RESET}')
    print(f"Query: {query}")

    # 2. Initialize Prompt / Messages
    messages = [{"role": "system", "content": scienceworld_system_prompt}]
    messages.append({"role": "user", "content": query})

    # 3. Execution Strategy (Skill vs Standard)
    task_done = False
    task_reward = 0
    steps = 0
    relevant_skill_names = []
    overall_procedure = ""
    overall_procedure_code = ""


    use_skill = False
    if Skill_Module is not None:
        relevant_skill_names = Skill_Module.retrieve_relevant_skills(query)
        if relevant_skill_names:
            use_skill = True
            print(f'{Colors.BLUE}Retrieved relevant skills: {relevant_skill_names}{Colors.RESET}')
    
    if use_skill:
        overall_procedure = Skill_Module.generate_overall_procedure(query, relevant_skill_names)
        print(f'\n{Colors.BLUE}Generated Overall Procedure:\n{overall_procedure}{Colors.RESET}')

        MAX_RETRIES = 3
        retries = 0
        while retries < MAX_RETRIES:
            try:
                overall_procedure_code = Skill_Module.generate_overall_procedure_code(query, overall_procedure)
                print(f'\n{Colors.BLUE}Generated Procedure Code:\n{overall_procedure_code}{Colors.RESET}')

                namespace = {}
                exec(overall_procedure_code, namespace)
                func = namespace.get("overall_procedure_code")
                
                if func:
                    messages, task_done, task_reward, steps = func(
                        env, llm, args.model, parse_action, messages, args.max_steps
                    )
                else:
                    raise ValueError("Function 'overall_procedure_code' not found in generated code.")
                
                if task_done:
                    print(f'{Colors.GREEN} Task completed! Reward: {task_reward}{Colors.RESET}')
                    break 
            except Exception as e:
                print(f'Error loading/executing procedure script: {e}')
                retries += 1
    else:
        messages, task_done, task_reward, steps = run_standard_procedure(
            env, llm, args.model, messages, args.max_steps
        )

    return {
        "query": query,
        "name": task_name,
        "variation_idx": var_idx,
        "task_done": task_done,
        "reward": task_reward,
        "steps": steps,
        "messages": messages,
        "relevant_skill_names": relevant_skill_names
    }

# ==========================================
# Worker Function
# ==========================================

def eval_single_variation(idx, indices, args, output_path):
    """
    Worker function: Instantiates its own ScienceWorldEnv.
    task_info: tuple (task_name, variation_index)
    """
    task_name, var_idx = indices[idx]
    env = None
    try:
        # 1. Independent Environment Initialization
        env = ScienceWorldEnv(taskName=None, serverPath=None, envStepLimit=args.max_steps)
        
        # 2. Load Specific Task & Variation
        env.load(task_name, var_idx, simplificationStr="easy")

        # 3. Initialize SkillModule (if enabled)
        Skill_Module = None
        if args.use_skill:
            skill_config = {
                "skills_dir": "src/skills/scienceworld",
                "overall_procedure_examples_path": "src/scienceworld/scienceworld_overall_procedure_examples.txt",
                "procedure_code_template_path": "src/scienceworld/scienceworld_procedure_code_template.py",
                "model": args.model
            }
            Skill_Module = SkillModule(**skill_config)

        # 4. Run Task
        result = scienceworld_run_single(env, task_name, var_idx, args, Skill_Module)

        # 5. Save Results (Atomic write per file)
        save_file = f'{output_path}/idx_{idx}.json'
        with open(save_file, 'w') as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
            
        return result

    except Exception as e:
        print(f"Error in task {task_name} var {var_idx}: {e}")
        return None
    finally:
        # 6. CRITICAL: Close the environment to kill the Java process
        if env:
            env.close()

# ==========================================
# Main Entry Point
# ==========================================

def main(args):
    model_name = args.model
    
    # Setup output directory
    output_path = f'results/scienceworld/{model_name}/{args.split}_{args.exp_name}_skill_{args.use_skill}'
    if not os.path.exists(output_path):
        os.makedirs(output_path, exist_ok=True)

    if args.split == 'dev':
        with open('src/scienceworld/data/valid_indices.json', 'r') as f:
            indices = json.load(f)
    elif args.split == 'test':
        with open('src/scienceworld/data/test_indices.json', 'r') as f:
            indices = json.load(f)

    num_games = len(indices)
    print(f"Total games to evaluate: {num_games}")

    # ---------------------------------------------------------
    # Checkpointing (Filter finished)
    # ---------------------------------------------------------
    tasks_to_run = []
    finished_games = 0
    all_rewards = 0
    all_steps = 0
    existing_files = set()

    if os.path.exists(output_path):
        for file in os.listdir(output_path):
            if file.endswith('.json') and file.startswith('idx_'):
                try:
                    idx = int(file.split('_')[1].split('.')[0])
                    existing_files.add(idx)
                    
                    with open(f'{output_path}/{file}', 'r') as f:
                        res = json.load(f)
                        all_rewards += res['reward']
                        all_steps += res['steps']
                    finished_games += 1
                except:
                    continue

    # Filter tasks to run
    for idx in range(num_games):
        if idx not in existing_files:
            tasks_to_run.append(idx)

    print(f"Already finished: {finished_games}, Remaining: {len(tasks_to_run)}")

    # ---------------------------------------------------------
    # Parallel Execution
    # ---------------------------------------------------------
    max_workers = args.max_workers
    print(f"Starting parallel evaluation with {max_workers} workers...")

    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {
            executor.submit(
                eval_single_variation, 
                idx,
                indices,
                args, 
                output_path
            ): idx for idx in tasks_to_run
        }

        pbar = tqdm(total=len(tasks_to_run), desc="Evaluating ScienceWorld")
        
        for future in concurrent.futures.as_completed(future_to_task):
            idx = future_to_task[future]
            try:
                result = future.result()
                if result:
                    finished_games += 1
                    all_rewards += result['reward']
                    all_steps += result['steps']
                    
                    # Update progress bar description
                    current_avg_reward = all_rewards / finished_games if finished_games > 0 else 0
                    current_avg_steps = all_steps / finished_games if finished_games > 0 else 0
                    pbar.set_postfix({
                        'Avg Reward': f'{current_avg_reward:.2f}', 
                        'Avg Steps': f'{current_avg_steps:.2f}'
                    })
            except Exception as exc:
                print(f'\nTask {idx} generated an exception: {exc}')
            
            pbar.update(1)
        
        pbar.close()

    # Final Summary
    print(f"Evaluation finished. Total Games: {finished_games}")
    if finished_games > 0:
        print(f"Final Avg Reward: {all_rewards / finished_games}")
        print(f"Final Avg Steps: {all_steps / finished_games}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=str, default='gpt-4o')
    parser.add_argument('--split', type=str, default='dev', choices=['dev', 'test'])
    parser.add_argument('--max_workers', type=int, default=5, help="Number of parallel workers")
    parser.add_argument('--max_steps', type=int, default=30)
    parser.add_argument('--exp_name', type=str, default='')
    parser.add_argument('--use_skill', action='store_true')
    args = parser.parse_args()
        
    main(args)