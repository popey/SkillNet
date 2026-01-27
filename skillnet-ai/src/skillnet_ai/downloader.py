import requests
import os
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class SkillDownloader:
    """
    A class to handle downloading specific subdirectories from GitHub repositories
    and installing them as local skills.
    """

    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize the downloader.
        
        Args:
            api_token: Optional GitHub Personal Access Token to avoid rate limits 
                       and access private repositories.
        """
        self.api_token = api_token
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json"
        })
        if self.api_token:
            self.session.headers.update({"Authorization": f"token {self.api_token}"})

    def download(self, folder_url: str, target_dir: str = ".") -> Optional[str]:
        """
        Download a specific GitHub subdirectory to the target directory.
        
        Args:
            folder_url: The full URL to the GitHub folder.
            target_dir: The local directory to install the skill into.
            
        Returns:
            The absolute path to the installed skill directory, or None if failed.
        """
        try:
            # 1. Parse the URL
            parsed_info = self._parse_github_url(folder_url)
            if not parsed_info:
                return None
            
            owner, repo, ref, dir_path, folder_name = parsed_info
            logger.info(f"Parsing: {owner}/{repo} @ {ref} -> {dir_path}")

            # 2. Get file tree
            files_to_download = self._get_file_tree(owner, repo, ref, dir_path)
            if not files_to_download:
                logger.warning("No matching files found or API error.")
                return None

            logger.info(f"Found {len(files_to_download)} files, starting download...")

            # 3. Download files
            success_count = 0
            failed_files = []
            for file_info in files_to_download:
                if self._download_single_file(owner, repo, ref, dir_path, file_info, folder_name, target_dir):
                    success_count += 1
                else:
                    failed_files.append(file_info['path'])

            if success_count == 0:
                logger.error("❌ Failed to download any files. Please check your network settings and ensure connection to GitHub is working properly.")
                return None
            
            final_path = os.path.abspath(os.path.join(target_dir, folder_name))

            if failed_files:
                logger.warning(f"⚠️ Successfully downloaded {success_count} files at {final_path}, but {len(failed_files)} failed.")
                logger.warning("The following files could not be downloaded:")
                for f in failed_files:
                    logger.warning(f"  - {f}")
                logger.warning("Please check your network settings and ensure connection to GitHub is working properly.")
            else:
                logger.info(f"✅ Skill installed successfully at: {final_path}")
            return final_path

        except Exception as e:
            logger.error(f"Critical error during installation: {e}")
            return None

    def _parse_github_url(self, url: str) -> Optional[tuple]:
        """
        Parses the GitHub URL into components.
        Expected format: https://github.com/owner/repo/tree/ref/path/to/dir
        """
        parts = url.rstrip('/').split('/')
        if len(parts) < 7:
            logger.error(f"Invalid GitHub URL format: {url}")
            return None
        
        # parts[2] is usually 'github.com'
        owner, repo = parts[3], parts[4]
        ref = parts[6]  # branch or commit hash
        dir_path = "/".join(parts[7:])
        folder_name = parts[-1]
        
        return owner, repo, ref, dir_path, folder_name

    def _get_file_tree(self, owner: str, repo: str, ref: str, dir_path: str) -> List[Dict]:
        """
        Fetches the recursive file tree from GitHub API and filters for the target directory.
        """
        api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{ref}?recursive=1"
        
        response = self.session.get(api_url)
        if response.status_code != 200:
            logger.error(f"GitHub API error: {response.status_code} - {response.text}")
            return []

        tree = response.json().get('tree', [])
        
        # Filter files that are inside the target dir_path and are blobs (files, not folders)
        return [
            item for item in tree 
            if item['path'].startswith(dir_path) and item['type'] == 'blob'
        ]

    def _download_single_file(self, owner: str, repo: str, ref: str, dir_path: str, file_info: Dict, folder_name: str, target_dir: str) -> bool:
        """
        Downloads a single file from raw.githubusercontent.com.
        """
        # Construct raw URL
        # Note: Handling private repos might require using the API content endpoint instead of raw.githubusercontent
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{file_info['path']}"
        
        # Calculate local path
        relative_path = file_info['path'].replace(f"{dir_path}/", "")
        # Remove leading slash if present to avoid path join issues
        relative_path = relative_path.lstrip('/')
        
        local_file_path = os.path.join(target_dir, folder_name, relative_path)
        
        # Create parent directories
        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
        
        try:
            # If it's a private repo, raw.githubusercontent might need token in header
            # The session already has the token if provided.
            file_resp = self.session.get(raw_url)
            
            if file_resp.status_code == 200:
                with open(local_file_path, "wb") as f:
                    f.write(file_resp.content)
                return True
            else:
                logger.warning(f"Failed to download {raw_url}: {file_resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"Exception downloading {raw_url}: {e}")
            return False