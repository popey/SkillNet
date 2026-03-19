import os
import time
import logging
import requests
from typing import Optional, List, Dict, Tuple

logger = logging.getLogger(__name__)

class GitHubAPIError(Exception):
    """
    Custom exception for GitHub API errors, encapsulating the status code 
    and the specific error message returned by GitHub.
    """
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"GitHub API Error [{status_code}]: {message}")


class SkillDownloader:
    """
    A class to handle downloading specific subdirectories from GitHub repositories
    and installing them as local skills.

    Supports configurable timeout, retry with exponential backoff, and automatic
    fallback to a mirror when the primary GitHub source is slow or unavailable.
    """

    def __init__(
        self,
        api_token: Optional[str] = None,
        mirror_url: Optional[str] = None,
        timeout: int = 15,
        max_retries: int = 3,
    ):
        """
        Initializes the SkillDownloader.

        Args:
            api_token: GitHub Personal Access Token to increase rate limits
                       and access private repositories.
            mirror_url: Mirror URL for fallback when GitHub is slow/unavailable.
                        Priority: explicit parameter > GITHUB_MIRROR env var.
                        Not set by default; users in China can configure via
                        GITHUB_MIRROR env var or --mirror CLI flag.
                        Example mirrors: https://ghfast.top/, https://ghproxy.com/
            timeout: Request timeout in seconds (default 15).
            max_retries: Maximum retry attempts per request (default 3).
        """
        self.api_token = api_token
        self.timeout = timeout
        self.max_retries = max_retries

        # Mirror resolution: explicit param > env var > None (no mirror)
        if mirror_url is not None:
            self.mirror_url = mirror_url
        else:
            self.mirror_url = os.getenv("GITHUB_MIRROR", "")

        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json"
        })
        
        if self.api_token:
            self.session.headers.update({"Authorization": f"token {self.api_token}"})

        if self.mirror_url:
            logger.info(f"Mirror fallback enabled: {self.mirror_url}")

    def download(self, folder_url: str, target_dir: str = ".") -> Optional[str]:
        """
        Downloads a specific GitHub subdirectory or file to the target directory.

        Args:
            folder_url (str): The full URL to the GitHub folder or file 
                              (e.g., tree or blob URL).
            target_dir (str): The local directory where the skill will be installed.

        Returns:
            Optional[str]: The absolute path to the installed skill directory, 
                           or None if the download fails.
        """
        try:
            # 1. Parse the GitHub URL
            parsed_info = self._parse_github_url(folder_url)
            if not parsed_info:
                return None
            
            owner, repo, ref, dir_path, folder_name = parsed_info
            logger.info(f"Parsing repository details: {owner}/{repo} @ {ref} -> {dir_path}")

            # 2. Fetch the file tree for the specific directory
            # This may now raise a GitHubAPIError if rate limited or not found
            files_to_download = self._get_file_tree(owner, repo, ref, dir_path)
            if not files_to_download:
                logger.warning(f"No matching files found or API error for path: {dir_path}")
                return None

            logger.info(f"Identified {len(files_to_download)} file(s). Starting download...")

            # 3. Download the identified files
            success_count = 0
            failed_files = []
            
            for file_info in files_to_download:
                is_success = self._download_single_file(
                    owner, repo, ref, dir_path, file_info, folder_name, target_dir
                )
                if is_success:
                    success_count += 1
                else:
                    failed_files.append(file_info.get("path", "Unknown path"))

            # 4. Handle results and determine final installation path
            if success_count == 0:
                logger.error("❌ Failed to download any files. Please verify network connectivity and GitHub API limits.")
                return None
            
            final_path = os.path.abspath(os.path.join(target_dir, folder_name))

            if failed_files:
                logger.warning(f"⚠️ Successfully downloaded {success_count} file(s) to {final_path}, but {len(failed_files)} failed.")
                logger.warning("The following files could not be downloaded:")
                for f in failed_files:
                    logger.warning(f"  - {f}")
            else:
                logger.info(f"✅ Skill installed successfully at: {final_path}")
                
            return final_path

        except GitHubAPIError:
            # Allow the GitHub API error to bubble up to the client/CLI
            raise
        except Exception as e:
            logger.error(f"Critical error during skill installation: {e}")
            return None

    def _request_with_retry(
        self,
        url: str,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        base_delay: float = 1.0,
    ) -> Optional[requests.Response]:
        """HTTP GET with configurable timeout and exponential-backoff retry."""
        timeout = timeout if timeout is not None else self.timeout
        max_retries = max_retries if max_retries is not None else self.max_retries

        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.get(url, timeout=timeout)

                # Handle GitHub rate-limit (403 with remaining == 0)
                if response.status_code == 403:
                    remaining = response.headers.get("X-RateLimit-Remaining", "?")
                    if remaining == "0":
                        reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                        wait_seconds = max(0, reset_time - int(time.time()))
                        logger.warning(f"GitHub rate limit exceeded. Resets in {wait_seconds}s")
                        if wait_seconds < 60:
                            time.sleep(wait_seconds + 1)
                            continue

                return response

            except requests.exceptions.Timeout:
                if attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(f"Timeout (attempt {attempt}/{max_retries}), retry in {delay:.1f}s: {url}")
                    time.sleep(delay)
                else:
                    logger.error(f"Request timed out after {max_retries} attempts: {url}")
                    return None

            except requests.exceptions.ConnectionError:
                if attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(f"Connection error (attempt {attempt}/{max_retries}), retry in {delay:.1f}s: {url}")
                    time.sleep(delay)
                else:
                    logger.error(f"Connection failed after {max_retries} attempts: {url}")
                    return None

            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}")
                return None

        return None

    def _build_mirror_url(self, original_url: str) -> Optional[str]:
        """
        Build a mirror URL by prepending the configured mirror prefix.
        Returns None if no mirror is configured or the URL is not a raw GitHub URL.
        """
        if not self.mirror_url:
            return None
        if "raw.githubusercontent.com" not in original_url:
            return None

        mirror = self.mirror_url.rstrip("/")
        return f"{mirror}/{original_url}"

    def _parse_github_url(self, url: str) -> Optional[Tuple[str, str, str, str, str]]:
        """
        Parses a standard GitHub tree or blob URL into its constituent components.

        Args:
            url (str): The GitHub URL to parse.

        Returns:
            Optional[Tuple]: A tuple containing (owner, repo, ref, dir_path, folder_name),
                             or None if the URL is invalid.
        """
        parts = url.rstrip('/').split('/')
        if len(parts) < 7:
            logger.error(f"Invalid GitHub URL format provided: {url}")
            return None
        
        # Assume parts[2] is 'github.com'
        owner = parts[3]
        repo = parts[4]
        ref = parts[6]  # branch name or commit hash
        dir_path = "/".join(parts[7:])
        folder_name = parts[-1]
        
        return owner, repo, ref, dir_path, folder_name

    def _get_file_tree(self, owner: str, repo: str, ref: str, dir_path: str) -> List[Dict[str, str]]:
        """
        Fetches the file list using the GitHub Contents API. 
        Recursively resolves subdirectories while bypassing repository-wide limits.

        Args:
            owner (str): Repository owner.
            repo (str): Repository name.
            ref (str): Branch or commit reference.
            dir_path (str): The target directory or file path within the repository.

        Returns:
            List[Dict[str, str]]: A list of dictionaries containing file 'path' and 'download_url'.
        """
        files_to_download = []
        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{dir_path}?ref={ref}"
        
        try:
            response = self._request_with_retry(api_url)

            if response is None:
                logger.error(f"GitHub API request failed after retries: {api_url}")
                raise GitHubAPIError(0, "Request failed after retries (timeout or connection error)")
            
            if response.status_code != 200:
                error_msg = response.text
                try:
                    # Attempt to parse the exact message from GitHub's JSON response
                    error_msg = response.json().get("message", error_msg)
                except ValueError:
                    pass # Retain raw text if parsing fails
                
                raise GitHubAPIError(response.status_code, error_msg)

            contents = response.json()
            
            # Handle single file scenario (e.g., blob URL)
            if isinstance(contents, dict) and contents.get("type") == "file":
                return [{
                    "path": contents.get("path", ""),
                    "download_url": contents.get("download_url", "")
                }]

            # Handle directory scenario (e.g., tree URL)
            if isinstance(contents, list):
                for item in contents:
                    if item.get("type") == "file":
                        files_to_download.append({
                            "path": item.get("path", ""),
                            "download_url": item.get("download_url", "")
                        })
                    elif item.get("type") == "dir":
                        # Recursively fetch contents of subdirectories
                        sub_path = item.get("path", "")
                        sub_files = self._get_file_tree(owner, repo, ref, sub_path)
                        files_to_download.extend(sub_files)

            return files_to_download

        except GitHubAPIError:
            # Allow the custom exception to bubble up through recursive calls
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve file tree for {dir_path}: {e}")
            return []

    def _download_single_file(
        self, 
        owner: str, 
        repo: str, 
        ref: str, 
        dir_path: str, 
        file_info: Dict[str, str], 
        folder_name: str, 
        target_dir: str
    ) -> bool:
        """
        Downloads a single file from GitHub and saves it to the local target directory.

        Args:
            owner (str): Repository owner.
            repo (str): Repository name.
            ref (str): Branch or commit reference.
            dir_path (str): The base directory path requested by the user.
            file_info (Dict[str, str]): File metadata containing 'path' and 'download_url'.
            folder_name (str): The root folder name for local installation.
            target_dir (str): The local target directory.

        Returns:
            bool: True if the file was downloaded and saved successfully, False otherwise.
        """
        raw_url = file_info.get("download_url")
        file_path = file_info.get("path", "")

        # Fallback for raw content URL if download_url is unexpectedly missing
        if not raw_url:
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{file_path}"
        
        # Calculate the relative path for the local file system
        if file_path == dir_path:
            # Exact file match (blob download)
            relative_path = os.path.basename(file_path)
        else:
            # Directory match: strip the base requested directory from the path
            relative_path = file_path.replace(f"{dir_path}/", "", 1)
        
        relative_path = relative_path.lstrip('/')
        local_file_path = os.path.join(target_dir, folder_name, relative_path)
        
        # Ensure parent directories exist
        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

        # If mirror is configured, use it directly; otherwise use GitHub
        mirror_url = self._build_mirror_url(raw_url)
        download_url = mirror_url if mirror_url else raw_url

        response = self._request_with_retry(download_url)
        if response is not None and response.status_code == 200:
            with open(local_file_path, "wb") as f:
                f.write(response.content)
            return True

        status = response.status_code if response else "no response"
        logger.warning(f"Failed to download {file_path} (status: {status})")
        return False