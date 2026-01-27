import os
from typing import List, Optional, Dict, Any, Union
from pathlib import Path

from skillnet_ai.creator import SkillCreator
from skillnet_ai.downloader import SkillDownloader
from skillnet_ai.evaluator import SkillEvaluator, EvaluatorConfig
from skillnet_ai.searcher import SkillNetSearcher

class SkillNetError(Exception):
    """Custom exception class for SkillNet Client errors."""
    pass

class SkillNetClient:
    """
    A Python SDK client for interacting with SkillNet AI services.
    
    This client aggregates Search, Download, Creation, and Evaluation functionalities.
    """

    def __init__(
        self, 
        api_key: Optional[str] = None, 
        base_url: Optional[str] = None,
        github_token: Optional[str] = None
    ):
        """
        Initialize the SkillNet Client.

        Args:
            api_key: OpenAI/SkillNet API Key. Defaults to env var API_KEY.
            base_url: Base URL for the LLM API. Defaults to env var BASE_URL or OpenAI default.
            github_token: GitHub token for downloading private skills or avoiding rate limits.
                          Defaults to env var GITHUB_TOKEN.
        """
        self.api_key = api_key or os.getenv("API_KEY")
        self.base_url = base_url or os.getenv("BASE_URL")
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")


    def search(
        self,
        q: str,
        mode: str = "keyword",
        category: Optional[str] = None,
        limit: int = 20,
        page: int = 1,
        min_stars: int = 0,
        sort_by: str = "stars",
        threshold: float = 0.8
    ) -> List[Any]:
        """
        Search for skills on SkillNet.

        Args:
            q: The search query.
            mode: 'keyword' or 'vector'.
            category: Filter by category.
            limit: Max results.
            page: Page number (keyword mode only).
            min_stars: Filter by stars (keyword mode only).
            sort_by: 'stars' or 'recent' (keyword mode only).
            threshold: Similarity threshold (vector mode only).

        Returns:
            List[SkillModel]: A list of skill objects found.
        """
        try:
            searcher = SkillNetSearcher()
            results = searcher.search(
                q=q,
                mode=mode, 
                category=category,
                limit=limit,
                page=page,
                min_stars=min_stars,
                sort_by=sort_by,
                threshold=threshold
            )
            return results
        except Exception as e:
            raise SkillNetError(f"Search failed: {str(e)}") from e

    def download(
        self,
        url: str,
        target_dir: str = ".",
        token: Optional[str] = None
    ) -> str:
        """
        Download a skill from a GitHub URL.

        Args:
            url: The GitHub URL of the specific skill folder.
            target_dir: Local directory to install into.
            token: Optional override for GitHub token.

        Returns:
            str: The absolute path to the installed skill folder.

        Raises:
            SkillNetError: If download fails.
        """
        # Use instance token if specific token not provided
        use_token = token if token else self.github_token
        downloader = SkillDownloader(api_token=use_token)

        try:
            installed_path = downloader.download(folder_url=url, target_dir=target_dir)
            if not installed_path:
                raise SkillNetError("Download returned None. Check URL validity or permissions.")
            return os.path.abspath(installed_path)
        except Exception as e:
            raise SkillNetError(f"Download failed: {str(e)}") from e

    def create(
        self,
        trajectory_content: str,
        output_dir: Union[str, Path] = "./generated_skills",
        model: str = "gpt-4o"
    ) -> List[str]:
        """
        Generate executable skills from a trajectory log.

        Args:
            trajectory_content: The text content of the execution log/trajectory.
            output_dir: Directory where new skills will be saved.
            model: The LLM model to use.

        Returns:
            List[str]: A list of paths to the generated skill folders.
        """
        if not self.api_key:
            raise SkillNetError("API_KEY is required for skill creation.")

        if not trajectory_content.strip():
            raise SkillNetError("Trajectory content is empty.")

        try:
            creator = SkillCreator(
                api_key=self.api_key, 
                base_url=self.base_url, 
                model=model
            )
            
            created_paths = creator.create_from_trajectory(
                trajectory=trajectory_content,
                output_dir=str(output_dir)
            )
            
            return created_paths if created_paths else []
        except Exception as e:
            raise SkillNetError(f"Creation failed: {str(e)}") from e

    def create_from_github(
        self,
        github_url: str,
        output_dir: Union[str, Path] = "./generated_skills",
        model: str = "gpt-4o",
        max_files: int = 20
    ) -> List[str]:
        """
        Generate a skill package from a GitHub repository.

        Args:
            github_url: Full URL to GitHub repository (e.g., https://github.com/owner/repo).
            output_dir: Directory where new skills will be saved.
            model: The LLM model to use.
            max_files: Maximum number of Python files to analyze for code signatures.

        Returns:
            List[str]: A list of paths to the generated skill folders.
        """
        if not self.api_key:
            raise SkillNetError("API_KEY is required for skill creation from GitHub.")

        if not github_url or not github_url.strip():
            raise SkillNetError("GitHub URL is empty.")

        try:
            creator = SkillCreator(
                api_key=self.api_key,
                base_url=self.base_url,
                model=model
            )
            
            created_paths = creator.create_from_github(
                github_url=github_url,
                output_dir=str(output_dir),
                api_token=self.github_token,
                max_files=max_files
            )
            
            return created_paths if created_paths else []
        except Exception as e:
            raise SkillNetError(f"GitHub skill creation failed: {str(e)}") from e

    def evaluate(
        self,
        target: str,
        name: Optional[str] = None,
        category: Optional[str] = None,
        description: Optional[str] = None,
        model: str = "gpt-4o",
        max_workers: int = 5
    ) -> Dict[str, Any]:
        """
        Evaluate a skill (local path or URL).

        Args:
            target: Local folder path OR GitHub URL.
            name: Override skill name.
            category: Override skill category.
            description: Override skill description.
            model: LLM model for evaluation.
            max_workers: Concurrency limit.

        Returns:
            Dict[str, Any]: The evaluation report dictionary.
        """
        if not self.api_key:
            raise SkillNetError("API_KEY is required for evaluation.")

        config = EvaluatorConfig(
            api_key=self.api_key,
            base_url=self.base_url,
            model=model,
            max_workers=max_workers
        )
        evaluator = SkillEvaluator(config)

        try:
            is_url = target.startswith("http://") or target.startswith("https://")
            
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
            
            if "error" in result:
                raise SkillNetError(f"Evaluation logic returned error: {result['error']}")
                
            return result

        except Exception as e:
            raise SkillNetError(f"Evaluation process failed: {str(e)}") from e