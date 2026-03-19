import typer
import os
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from skillnet_ai.creator import SkillCreator
from skillnet_ai.downloader import SkillDownloader, GitHubAPIError
from skillnet_ai.evaluator import SkillEvaluator, EvaluatorConfig
from skillnet_ai.searcher import SkillNetSearcher
from skillnet_ai.analyzer import SkillRelationshipAnalyzer

app = typer.Typer(help="SkillNet AI CLI Tool")
console = Console()

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL") or "https://api.openai.com/v1"

@app.command()
def search(
    q: str = typer.Argument(..., help="The search query (keywords or natural language description)."),
    mode: str = typer.Option("keyword", help="Search mode: 'keyword' (exact/fuzzy) or 'vector' (semantic AI)."),
    category: str = typer.Option(None, help="Filter results by category (e.g., 'Development')."),
    limit: int = typer.Option(20, help="Maximum number of results to return."),
    # Keyword specific options
    page: int = typer.Option(1, help="Page number (only for keyword mode)."),
    min_stars: int = typer.Option(0, help="Minimum star rating (only for keyword mode)."),
    sort_by: str = typer.Option("stars", help="Sort criteria: 'stars' or 'recent' (only for keyword mode)."),
    # Vector specific options
    threshold: float = typer.Option(0.8, help="Similarity threshold 0.0-1.0 (only for vector mode)."),
):
    """
    Search for skills on SkillNet using Keyword match or Vector (AI) semantic search.
    """
    try:
        # Initialize Searcher (Ensure URL points to your actual API)
        searcher = SkillNetSearcher()

        # Visual feedback during API call
        with console.status(f"[bold green]Searching SkillNet ({mode} mode)..."):
            results = searcher.search(
                q=q,
                mode=mode,  # type: ignore
                category=category,
                limit=limit,
                page=page,
                min_stars=min_stars,
                sort_by=sort_by,
                threshold=threshold
            )

        # Handle Empty Results
        if not results:
            console.print(f"[yellow]No results found for query: '{q}'[/yellow]")
            return

        # Build Output Table
        table = Table(title=f"Search Results: {q} ({len(results)} items)", show_lines=True)
        
        # Define Columns
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Category", style="magenta")
        table.add_column("Stars", justify="right", style="green")
        table.add_column("Description", style="white")
        table.add_column("Evaluation", justify="left", style="yellow")
        table.add_column("URL", style="dim blue", overflow="fold") # Added URL column

        for item in results:
            name = item.skill_name
            cat = item.category if item.category else "N/A"
            stars = str(item.stars)
            desc = item.skill_description if item.skill_description else ""
            url = item.skill_url if item.skill_url else "N/A"

            if url != "N/A":
                url = f"[link={url}]{url}[/link]"

            # Truncate long descriptions for display
            short_desc = (desc[:100] + '...') if len(desc) > 100 else desc

            eval_lines = []
            if item.evaluation and isinstance(item.evaluation, dict):
                metrics = {
                    "safety": "Safety",
                    "executability": "Executability",
                    "completeness": "Completeness",
                    "maintainability": "Maintainability",
                    "cost_awareness": "Cost-Awareness"
                }         
                for key, display_name in metrics.items():
                    level = item.evaluation.get(key, {}).get("level", "N/A")
                    eval_lines.append(f"{display_name}: {level}") 
            eval_full_str = "\n".join(eval_lines) if eval_lines else "N/A"
            
            # Prepare row data
            row_data = [
                name,
                cat,
                stars,
                short_desc,
                eval_full_str,
                url
            ]

            table.add_row(*row_data)

        console.print(table)
        
        # Suggest next step
        console.print("\n[dim]Tip: Use 'skillnet download <skill_url>' to get a skill.[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error during search:[/bold red] {str(e)}")
        # Optional: Print full traceback for debugging
        # console.print_exception() 
        raise typer.Exit(code=1)

@app.command()
def download(
    url: str = typer.Argument(..., help="The GitHub URL of the specific skill folder (e.g., https://github.com/owner/repo/tree/main/skills/math_solver)."),
    target_dir: str = typer.Option(".", "--target-dir", "-d", help="Local directory to install the skill into."),
    token: str = typer.Option(None, "--token", "-t", envvar="GITHUB_TOKEN", help="GitHub Personal Access Token (for private repos or higher rate limits)."),
    mirror: str = typer.Option(None, "--mirror", "-m", help="Mirror URL for fallback when GitHub is slow/unavailable (e.g. https://ghfast.top/). Also reads GITHUB_MIRROR env var."),
):
    """
    Download and install a specific skill directly from a GitHub repository subdirectory.
    """
    # 1. Initialize Downloader
    # Checks CLI option first, then environment variable GITHUB_TOKEN
    downloader = SkillDownloader(api_token=token, mirror_url=mirror)

    try:
        # 2. Visual Feedback
        console.print(f"[dim]Target directory: {os.path.abspath(target_dir)}[/dim]")
        
        with console.status(f"[bold green]Downloading skill from GitHub...[/bold green]", spinner="dots"):
            installed_path = downloader.download(folder_url=url, target_dir=target_dir)

        # 3. Handle Results
        if installed_path:
            # Success
            folder_name = os.path.basename(installed_path)
            
            table = Table(title="Installation Successful", show_header=False, box=None)
            table.add_row("[bold cyan]Skill:[/bold cyan]", folder_name)
            table.add_row("[bold cyan]Location:[/bold cyan]", installed_path)
            
            console.print(table)
            console.print(f"\n[green]✅ {folder_name} is ready to use.[/green]")
        else:
            # Generic Failure (e.g., no files found, URL invalid)
            console.print("[bold red]❌ Download Failed: Could not process the files.[/bold red]")
            raise typer.Exit(code=1)

    except GitHubAPIError as e:
        # 4. Handle Specific GitHub API Errors with actionable UI feedback
        console.print(f"[bold red]❌ GitHub API Error [{e.status_code}]:[/bold red] {e.message}")
        
        # Provide smart hints based on the status code
        if e.status_code == 403:
            console.print("\n[yellow]💡 Tip: You may have hit the GitHub API rate limit. Please provide a GitHub Personal Access Token (using the --token flag).[/yellow]")
        elif e.status_code == 404:
            console.print("\n[yellow]💡 Tip: The path does not exist, or this is a private repository (requires a --token to access).[/yellow]")
            
        raise typer.Exit(code=1)

    except Exception as e:
        # 5. Handle unexpected exceptions
        console.print(f"[bold red]An unexpected error occurred:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

@app.command()
def create(
    # Input sources (mutually exclusive)
    trajectory_file: Path = typer.Argument(None, exists=True, readable=True, help="Path to trajectory/log file."),
    github: str = typer.Option(None, "--github", "-g", help="GitHub repository URL (e.g., https://github.com/owner/repo)."),
    office: Path = typer.Option(None, "--office", "-o", exists=True, readable=True, help="Path to office document (PDF, PPT, Word)."),
    prompt: str = typer.Option(None, "--prompt", "-p", help="Direct description to generate skill from."),
    # Output options
    output_dir: Path = typer.Option(Path("./generated_skills"), "--output-dir", "-d", help="Directory to save generated skills."),
    # Model options
    model: str = typer.Option("gpt-4o", "--model", "-m", help="LLM model to use (e.g., gpt-4o, gpt-3.5-turbo)."),
    max_files: int = typer.Option(50, "--max-files", help="Max code files to analyze (--github only)."),
):
    """
    Create executable Skill packages using AI.
    
    Supports four modes:
    - From trajectory: skillnet create trajectory.txt
    - From GitHub: skillnet create --github https://github.com/owner/repo
    - From Office doc: skillnet create --office document.pdf
    - From prompt: skillnet create --prompt "Create a skill for..."
    """
    # 1. Validate Environment
    if not API_KEY:
        console.print("[bold red]Error:[/bold red] API_KEY environment variable is not set.")
        console.print("Please export API_KEY or set it in your environment.")
        raise typer.Exit(code=1)

    # 2. Determine mode based on provided options
    mode_count = sum([
        bool(github),
        bool(trajectory_file),
        bool(office),
        bool(prompt)
    ])
    
    if mode_count == 0:
        console.print("[bold red]Error:[/bold red] Must specify one input source.")
        console.print("\nUsage examples:")
        console.print("  skillnet create trajectory.txt")
        console.print("  skillnet create --github https://github.com/owner/repo")
        console.print("  skillnet create --office document.pdf")
        console.print('  skillnet create --prompt "Create a skill for web scraping"')
        raise typer.Exit(code=1)
    
    if mode_count > 1:
        console.print("[bold red]Error:[/bold red] Only one input source can be specified at a time.")
        raise typer.Exit(code=1)

    # 3. Route to appropriate handler
    if github:
        _create_from_github(github, output_dir, model, max_files)
    elif trajectory_file:
        _create_from_trajectory(trajectory_file, output_dir, model)
    elif office:
        _create_from_office(office, output_dir, model)
    elif prompt:
        _create_from_prompt(prompt, output_dir, model)


def _create_from_trajectory(trajectory_file: Path, output_dir: Path, model: str):
    """Internal function to create skill from trajectory file."""
    try:
        # Read Trajectory Content
        console.print(f"[dim]Reading trajectory from: {trajectory_file}[/dim]")
        with open(trajectory_file, "r", encoding="utf-8") as f:
            trajectory_content = f.read()

        if not trajectory_content.strip():
            console.print("[bold red]Error:[/bold red] Trajectory file is empty.")
            raise typer.Exit(code=1)

        # Initialize Creator
        creator = SkillCreator(
            api_key=API_KEY, 
            base_url=BASE_URL, 
            model=model
        )

        # Run Generation with Spinner
        with console.status("[bold green]AI is analyzing trajectory and generating skills...[/bold green]", spinner="dots"):
            created_paths = creator.create_from_trajectory(
                trajectory=trajectory_content,
                output_dir=str(output_dir)
            )

        # Report Results
        if created_paths:
            console.print(f"\n[bold green]Success! Generated {len(created_paths)} skill(s):[/bold green]")
            
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Skill Name", style="cyan")
            table.add_column("Location", style="white")

            for path in created_paths:
                skill_name = os.path.basename(path)
                table.add_row(skill_name, str(path))
            
            console.print(table)
            console.print(f"\n[dim]Files saved to: {os.path.abspath(output_dir)}[/dim]")
        else:
            console.print("\n[yellow]Analysis complete, but no clear skills were identified in this trajectory.[/yellow]")

    except Exception as e:
        console.print(f"\n[bold red]Creation Failed:[/bold red] {str(e)}")
        raise typer.Exit(code=1)


def _create_from_github(github_url: str, output_dir: Path, model: str, max_files: int):
    """Internal function to create skill from GitHub repository."""
    try:
        console.print(f"[dim]Creating skill from GitHub: {github_url}[/dim]")

        # Initialize Creator
        creator = SkillCreator(
            api_key=API_KEY,
            base_url=BASE_URL,
            model=model
        )

        # Run Generation with Spinner
        with console.status("[bold green]Fetching repository and generating skill...[/bold green]", spinner="dots"):
            created_paths = creator.create_from_github(
                github_url=github_url,
                output_dir=str(output_dir),
                api_token=os.getenv("GITHUB_TOKEN"),
                max_files=max_files
            )

        # Report Results
        if created_paths:
            console.print(f"\n[bold green]Success! Generated {len(created_paths)} skill(s) from GitHub:[/bold green]")
            
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Skill Name", style="cyan")
            table.add_column("Location", style="white")

            for path in created_paths:
                skill_name = os.path.basename(path)
                table.add_row(skill_name, str(path))
            
            console.print(table)
            console.print(f"\n[dim]Files saved to: {os.path.abspath(output_dir)}[/dim]")
            console.print("\n[dim]Tip: Use 'skillnet evaluate <skill_path>' to evaluate the generated skill.[/dim]")
        else:
            console.print("\n[yellow]Failed to generate skill from the GitHub repository.[/yellow]")

    except Exception as e:
        console.print(f"\n[bold red]GitHub Skill Creation Failed:[/bold red] {str(e)}")
        raise typer.Exit(code=1)


def _create_from_office(office_file: Path, output_dir: Path, model: str):
    """Internal function to create skill from office document."""
    try:
        console.print(f"[dim]Creating skill from office document: {office_file}[/dim]")

        # Initialize Creator
        creator = SkillCreator(
            api_key=API_KEY,
            base_url=BASE_URL,
            model=model
        )

        # Run Generation with Spinner
        with console.status("[bold green]Extracting content and generating skill...[/bold green]", spinner="dots"):
            created_paths = creator.create_from_office(
                file_path=str(office_file),
                output_dir=str(output_dir)
            )

        # Report Results
        if created_paths:
            console.print(f"\n[bold green]Success! Generated {len(created_paths)} skill(s) from document:[/bold green]")
            
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Skill Name", style="cyan")
            table.add_column("Location", style="white")

            for path in created_paths:
                skill_name = os.path.basename(path)
                table.add_row(skill_name, str(path))
            
            console.print(table)
            console.print(f"\n[dim]Files saved to: {os.path.abspath(output_dir)}[/dim]")
            console.print("\n[dim]Tip: Use 'skillnet evaluate <skill_path>' to evaluate the generated skill.[/dim]")
        else:
            console.print("\n[yellow]Failed to generate skill from the document.[/yellow]")

    except ImportError as e:
        console.print(f"\n[bold red]Missing Dependency:[/bold red] {str(e)}")
        console.print("\n[dim]Install office document support with:[/dim]")
        console.print("  pip install PyPDF2 pycryptodome python-docx python-pptx")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"\n[bold red]Office Skill Creation Failed:[/bold red] {str(e)}")
        raise typer.Exit(code=1)


def _create_from_prompt(user_prompt: str, output_dir: Path, model: str):
    """Internal function to create skill from user's prompt description."""
    try:
        console.print(f"[dim]Creating skill from user prompt...[/dim]")

        # Initialize Creator
        creator = SkillCreator(
            api_key=API_KEY,
            base_url=BASE_URL,
            model=model
        )

        # Run Generation with Spinner
        with console.status("[bold green]AI is generating your custom skill...[/bold green]", spinner="dots"):
            created_paths = creator.create_from_prompt(
                user_input=user_prompt,
                output_dir=str(output_dir)
            )

        # Report Results
        if created_paths:
            console.print(f"\n[bold green]Success! Generated {len(created_paths)} skill(s) from your description:[/bold green]")
            
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Skill Name", style="cyan")
            table.add_column("Location", style="white")

            for path in created_paths:
                skill_name = os.path.basename(path)
                table.add_row(skill_name, str(path))
            
            console.print(table)
            console.print(f"\n[dim]Files saved to: {os.path.abspath(output_dir)}[/dim]")
            console.print("\n[dim]Tip: Use 'skillnet evaluate <skill_path>' to evaluate the generated skill.[/dim]")
        else:
            console.print("\n[yellow]Failed to generate skill from your description.[/yellow]")

    except Exception as e:
        console.print(f"\n[bold red]Prompt-based Skill Creation Failed:[/bold red] {str(e)}")
        raise typer.Exit(code=1)


@app.command()
def evaluate(
    target: str = typer.Argument(..., help="Path to a local skill directory OR a GitHub URL."),
    
    # Optional metadata overrides (useful if not auto-detected)
    name: str = typer.Option(None, help="Name of the skill (overrides auto-detection)."),
    category: str = typer.Option(None, help="Category of the skill (e.g., 'Data Analysis')."),
    description: str = typer.Option(None, help="Short description of what the skill does."),
    
    # Config options
    model: str = typer.Option("gpt-4o", "--model", "-m", help="LLM model to use."),
    max_workers: int = typer.Option(5, help="Concurrency for batch operations (not used for single eval)."),
):
    """
    Evaluate the quality, safety, and completeness of a skill using AI.
    
    Target can be a local folder path or a GitHub URL (e.g., https://github.com/user/repo/tree/main/skill).
    """
    # 1. Validate Environment
    if not API_KEY:
        console.print("[bold red]Error:[/bold red] API_KEY environment variable is not set.")
        raise typer.Exit(code=1)

    # 2. Configure Evaluator
    config = EvaluatorConfig(
        api_key=API_KEY,
        base_url=BASE_URL,
        model=model,
        max_workers=max_workers
    )
    evaluator = SkillEvaluator(config)

    try:
        # 3. Determine Mode (URL vs Local Path) and Run Evaluation
        is_url = target.startswith("http://") or target.startswith("https://")
        
        with console.status(f"[bold green]Evaluating skill ({'Remote' if is_url else 'Local'})...[/bold green]", spinner="dots"):
            if is_url:
                result = evaluator.evaluate_from_url(
                    url=target, 
                    name=name, 
                    category=category, 
                    description=description
                )
            else:
                result = evaluator.evaluate_from_path(
                    path=target, 
                    name=name, 
                    category=category, 
                    description=description
                )

        # 4. Display Results
        if "error" in result:
            console.print(f"[bold red]Evaluation Failed:[/bold red] {result['error']}")
            raise typer.Exit(code=1)

        _display_evaluation_report(target, result)

    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

def _display_evaluation_report(target_name: str, data: dict):
    """Helper to render the JSON evaluation result into a nice Rich UI."""
    console.print(f"\n[bold underline]Evaluation Report: {os.path.basename(target_name)}[/bold underline]\n")

    # Dimensions to display
    dimensions = ["safety", "completeness", "executability", "maintainability", "cost_awareness"]
    
    # Create a grid of panels
    panels = []
    for dim in dimensions:
        info = data.get(dim, {})
        level = info.get("level", "Unknown")
        reason = info.get("reason", "No details provided.")
        
        # Color coding based on level
        color = "white"
        if "Excellent" in level: color = "green"
        elif "Good" in level: color = "blue"
        elif "Fair" in level: color = "yellow"
        elif "Poor" in level: color = "red"

        panel_content = f"[bold]{level}[/bold]\n\n[dim]{reason}[/dim]"
        panels.append(Panel(panel_content, title=f"[{color}]{dim.title()}[/{color}]", expand=True))

    console.print(Columns(panels, equal=True, expand=True))
    
    # Display Score if present
    overall_score = data.get("overall_score")
    if overall_score:
        score_color = "green" if overall_score >= 8 else "yellow" if overall_score >= 5 else "red"
        console.print(f"\n[bold]Overall Score:[/bold] [{score_color}]{overall_score}/10[/{score_color}]")

    # Summary
    summary = data.get("summary")
    if summary:
        console.print(Panel(summary, title="Executive Summary", border_style="cyan"))

@app.command()
def analyze(
    skills_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Directory containing multiple skill folders to analyze."),
    save: bool = typer.Option(True, "--save/--no-save", help="Save the result to relationships.json in the directory."),
    model: str = typer.Option("gpt-4o", "--model", "-m", help="LLM model to use."),
):
    """
    Analyze and map relationships (similar_to, belong_to, compose_with, depend_on) between local skills.
    
    This command scans all subdirectories in the target folder, reads their descriptions, 
    and uses AI to build a knowledge graph of how the skills relate to each other.
    """
    # 1. Validate Environment
    if not API_KEY:
        console.print("[bold red]Error:[/bold red] API_KEY environment variable is not set.")
        raise typer.Exit(code=1)

    try:
        # 2. Initialize Analyzer
        analyzer = SkillRelationshipAnalyzer(
            api_key=API_KEY,
            base_url=BASE_URL,
            model=model
        )

        # 3. Visual Feedback & Execution
        console.print(f"[dim]Scanning directory: {os.path.abspath(skills_dir)}[/dim]")
        
        results = []
        with console.status("[bold green]Reading skills and analyzing relationships...[/bold green]", spinner="earth"):
            results = analyzer.analyze_local_skills(
                skills_dir=str(skills_dir),
                save_to_file=save
            )

        # 4. Handle Empty Results
        if not results:
            console.print("\n[yellow]No strong relationships detected among the skills found.[/yellow]")
            console.print("[dim]Make sure the directory contains subfolders with valid SKILL.md or README.md files.[/dim]")
            return

        # 5. Render Results Table
        console.print(f"\n[bold green]Analysis Complete! Found {len(results)} relationships:[/bold green]\n")

        table = Table(show_header=True, header_style="bold magenta", title="Skill Relationship Graph")
        table.add_column("Source Skill", style="cyan", no_wrap=True)
        table.add_column("Relationship", style="bold white", justify="center")
        table.add_column("Target Skill", style="cyan", no_wrap=True)
        table.add_column("Reasoning", style="dim")

        for edge in results:
            # Color code the relationship types for better readability
            rel_type = edge.get('type', 'unknown')
            rel_style = "white"
            arrow = "->"
            
            if rel_type == "depend_on":
                rel_style = "red"  # Critical dependency
                arrow = "DEPEND ON"
            elif rel_type == "belong_to":
                rel_style = "blue" # Hierarchy
                arrow = "BELONG TO"
            elif rel_type == "compose_with": # pairs_with
                rel_style = "green" # Collaboration
                arrow = "COMPOSE WITH"
            elif rel_type == "similar_to":
                rel_style = "yellow" # Alternative
                arrow = "SIMILAR TO"

            table.add_row(
                edge.get('source', 'Unknown'),
                f"[{rel_style}]{arrow}[/{rel_style}]", 
                edge.get('target', 'Unknown'),
                edge.get('reason', '')
            )

        console.print(table)

        if save:
            console.print(f"\n[dim]Relationship data saved to: {os.path.join(skills_dir, 'relationships.json')}[/dim]")

    except Exception as e:
        console.print(f"\n[bold red]Analysis Failed:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
