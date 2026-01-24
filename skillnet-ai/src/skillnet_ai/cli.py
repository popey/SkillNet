import typer
import os
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from skillnet_ai.creator import SkillCreator
from skillnet_ai.downloader import SkillDownloader
from skillnet_ai.evaluator import SkillEvaluator, EvaluatorConfig
from skillnet_ai.searcher import SkillNetSearcher

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
        searcher = SkillNetSearcher(skillnet_url="http://127.0.0.1:8502")

        # Visual feedback during API call
        with console.status(f"[bold green]Searching SkillNet ({mode} mode)..."):
            # Assuming searcher.search returns List[SkillModel]
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
        table = Table(title=f"Search Results: {q} ({len(results)} items)")
        
        # Define Columns
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Category", style="magenta")
        table.add_column("Stars", justify="right", style="green")
        table.add_column("Description", style="white")
        table.add_column("URL", style="dim blue", overflow="fold") # Added URL column

        # Note: 'score' was removed because SkillModel definition does not have a 'score' field.
        # If your API returns a score for vector search, you must add it to SkillModel first.

        for item in results:
            # 1. Access fields using Pydantic dot notation
            # 2. Use correct field names from SkillModel (e.g. skill_description)
            name = item.skill_name
            cat = item.category if item.category else "N/A"
            stars = str(item.stars)
            desc = item.skill_description if item.skill_description else ""
            url = item.skill_url if item.skill_url else "N/A"

            # Truncate long descriptions for display
            short_desc = (desc[:100] + '...') if len(desc) > 100 else desc
            
            # Prepare row data
            row_data = [
                name,
                cat,
                stars,
                short_desc,
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
):
    """
    Download and install a specific skill directly from a GitHub repository subdirectory.
    """
    # 1. Initialize Downloader
    # Checks CLI option first, then environment variable GITHUB_TOKEN
    downloader = SkillDownloader(api_token=token)

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
            console.print(f"\n[green]✓ {folder_name} is ready to use.[/green]")
        else:
            # Failure (Logic handled inside class, but we catch the None return)
            console.print("[bold red]Download Failed.[/bold red]")
            console.print("Possible reasons:")
            console.print("1. The URL format is incorrect (must point to a specific folder, not just the repo root).")
            console.print("2. The repository is private and no token was provided.")
            console.print("3. GitHub API rate limits exceeded (try providing a token).")
            raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

@app.command()
def create(
    trajectory_file: Path = typer.Argument(..., exists=True, readable=True, help="Path to the text file containing the execution trajectory/logs."),
    output_dir: Path = typer.Option(Path("./generated_skills"), help="Directory where the new skills will be saved."),
    model: str = typer.Option("gpt-4o", help="The LLM model to use (e.g., gpt-4o, gpt-3.5-turbo)."),
):
    """
    Analyze a trajectory log and generate executable Skill packages using AI.
    """
    # 1. Validate Environment
    if not API_KEY:
        console.print("[bold red]Error:[/bold red] API_KEY environment variable is not set.")
        console.print("Please export API_KEY or set it in your environment.")
        raise typer.Exit(code=1)

    try:
        # 2. Read Trajectory Content
        console.print(f"[dim]Reading trajectory from: {trajectory_file}[/dim]")
        with open(trajectory_file, "r", encoding="utf-8") as f:
            trajectory_content = f.read()

        if not trajectory_content.strip():
            console.print("[bold red]Error:[/bold red] Trajectory file is empty.")
            raise typer.Exit(code=1)

        # 3. Initialize Creator
        creator = SkillCreator(
            api_key=API_KEY, 
            base_url=BASE_URL, 
            model=model
        )

        # 4. Run Generation with Spinner
        # The creation process involves multiple LLM calls, so it may take time.
        with console.status("[bold green]AI is analyzing trajectory and generating skills...[/bold green]", spinner="dots"):
            created_paths = creator.create_from_trajectory(
                trajectory=trajectory_content,
                output_dir=str(output_dir)
            )

        # 5. Report Results
        if created_paths:
            console.print(f"\n[bold green]Success! Generated {len(created_paths)} skill(s):[/bold green]")
            
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Skill Name", style="cyan")
            table.add_column("Location", style="white")

            for path in created_paths:
                # Assuming path ends with the skill name
                skill_name = os.path.basename(path)
                table.add_row(skill_name, str(path))
            
            console.print(table)
            console.print(f"\n[dim]Files saved to: {os.path.abspath(output_dir)}[/dim]")
        else:
            console.print("\n[yellow]Analysis complete, but no clear skills were identified in this trajectory.[/yellow]")

    except Exception as e:
        console.print(f"\n[bold red]Creation Failed:[/bold red] {str(e)}")
        # Optional: Print traceback if in debug mode
        # console.print_exception()
        raise typer.Exit(code=1)

@app.command()
def evaluate(
    target: str = typer.Argument(..., help="Path to a local skill directory OR a GitHub URL."),
    
    # Optional metadata overrides (useful if not auto-detected)
    name: str = typer.Option(None, help="Name of the skill (overrides auto-detection)."),
    category: str = typer.Option(None, help="Category of the skill (e.g., 'Data Analysis')."),
    description: str = typer.Option(None, help="Short description of what the skill does."),
    
    # Config options
    model: str = typer.Option("gpt-4o", help="The LLM model used for evaluation."),
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
    dimensions = ["safety", "completeness", "executability", "modifiability", "cost_awareness"]
    
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

if __name__ == "__main__":
    app()
