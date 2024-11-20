from git import Repo
from typing import Dict, List
from rich.console import Console
from rich.syntax import Syntax

console = Console()

class GitAnalyzer:
    def __init__(self, repo_path='.'):
        self.repo = Repo(repo_path)
    
    def get_staged_changes(self) -> List[Dict]:
        """Get detailed information about staged changes"""
        changes = []
        
        try:
            # For repositories with commits
            staged_diff = self.repo.index.diff("HEAD")
            # Process normal staged changes
            for diff in staged_diff:
                try:
                    # Get the raw diff text
                    diff_text = self.repo.git.diff('--cached', diff.a_path)
                    
                    # Determine change type
                    change_type = 'M'  # Default to modified
                    if diff.new_file:
                        change_type = 'A'
                    elif diff.deleted_file:
                        change_type = 'D'
                    elif diff.renamed:
                        change_type = 'R'
                    
                    change_info = {
                        'path': diff.a_path,
                        'change_type': change_type,
                        'additions': diff_text.count('\n+'),
                        'deletions': diff_text.count('\n-'),
                        'diff': diff_text,
                        'file_type': diff.a_path.split('.')[-1] if '.' in diff.a_path else 'unknown'
                    }
                    changes.append(change_info)
                except Exception as e:
                    console.print(f"[warning]Could not process file {diff.a_path}: {str(e)}[/]")
                    
        except Exception as e:
            # For newly initialized repositories
            console.print("[info]Processing new repository...[/]")
            
            # Get all staged files (works for both new and existing repos)
            staged_files = self.repo.git.diff('--cached', '--name-only').split('\n')
            staged_files = [f for f in staged_files if f]  # Remove empty strings
            
            for staged_file in staged_files:
                try:
                    # Get the diff for the staged file
                    diff_text = self.repo.git.diff('--cached', staged_file)
                    
                    # For new repositories, check if file exists in HEAD
                    try:
                        self.repo.head.commit.tree[staged_file]
                        change_type = 'M'  # File exists in HEAD, so it's modified
                    except (KeyError, ValueError):
                        change_type = 'A'  # File doesn't exist in HEAD, so it's new
                    
                    change_info = {
                        'path': staged_file,
                        'change_type': change_type,
                        'additions': diff_text.count('\n+'),
                        'deletions': diff_text.count('\n-'),
                        'diff': diff_text,
                        'file_type': staged_file.split('.')[-1] if '.' in staged_file else 'unknown'
                    }
                    changes.append(change_info)
                except Exception as e:
                    console.print(f"[warning]Could not process file {staged_file}: {str(e)}[/]")
        
        return changes
    
    def get_untracked_files(self) -> List[str]:
        """Get list of untracked files"""
        return self.repo.untracked_files
    
    def commit_changes(self, message: str) -> bool:
        """Commit staged changes with the given message"""
        try:
            # Create an initial commit if this is a new repository
            if not self.repo.head.is_valid():
                console.print("[info]Creating initial commit...[/]")
            
            self.repo.index.commit(message)
            return True
        except Exception as e:
            console.print(f"[error]Failed to commit changes: {str(e)}[/]")
            return False 