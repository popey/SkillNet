# Evaluation Experiments

This section provides instructions for setting up the evaluation environments.

## 📂 Expected Directory Structure

To ensure the scripts can locate the environments, please organize your files as follows:

```text
SkillNet/
├── experiments/
│   ├── alfworld/          # git clone here
│   ├── ScienceWorld/      # git clone here
│   ├── WebShop/           # git clone here
│   ├── src/
│   ├── requirements.txt
│   ├── alfworld_run.py
│   ├── scienceworld_run.py
│   └── webshop_run.py
```

## 🚀 Quick Start

We suggest configuring separate conda environments for these three datasets to avoid dependency conflicts.

### ALFWorld
1. **Clone & Setup:**
  ```bash
  cd experiments
  git clone https://github.com/alfworld/alfworld.git
  cd alfworld
  # Follow the official installation steps from the repo (https://github.com/alfworld/alfworld)
  ```
2. **Environment Variable:**
- Set `ALFWORLD_DATA` to the dataset root or edit `src/alfworld/base_config.yaml` to point to your local paths:

  ```bash
  export ALFWORLD_DATA=/path/to/alfworld_data
  ```

### ScienceWorld
1. **Clone & Setup:**
  ```bash
  cd experiments
  git clone https://github.com/allenai/ScienceWorld.git
  cd ScienceWorld
  # Refer to the ScienceWorld repository for environment setup (https://github.com/allenai/ScienceWorld)
  ```

### WebShop
1. **Clone & Setup:**
  ```bash
  cd experiments
  git clone https://github.com/princeton-nlp/WebShop.git
  cd WebShop
  # Refer to the WebShop repository for environment setup (https://github.com/princeton-nlp/WebShop)
  ```

---

For each environment, install common dependencies:
```bash
cd experiments
pip install -r requirements.txt
```

### Running
#### Step 1: Initialize Environment Variables
Before running the scripts, configure your API credentials:
```bash
export API_KEY=YOUR_API_KEY
export BASE_URL=YOUR_API_BASE_URL
```

#### Step 2: Execution
Run the corresponding evaluation script from the `experiments/` directory.
```python
cd experiments

# ALFWorld
python alfworld_run.py --model o4-mini --split dev --max_workers 10 --exp_name alf_test --use_skill

# ScienceWorld
python scienceworld_run.py --model o4-mini --split test --max_workers 5 --exp_name sci_test --use_skill

# WebShop
python webshop_run.py --model o4-mini --max_workers 3 --exp_name web_test --use_skill
```

#### 🛠️ Argument Descriptions
- `--model`: The name of the LLM to evaluate.

- `--split`: Data split to use (`dev` or `test`).

- `--max_workers`: Number of parallel workers for evaluation.

- `exp_name`: results save name.

- `--use_skill`: Enable the skill-augmented module.