from wandb.errors import Error
class LaunchError(Error):
    """Raised when a known error occurs in wandb launch."""
    

class LaunchDockerError(LaunchError):
    """Raised when Docker daemon is not running."""
    

class ExecutionError(LaunchError):
    """Generic execution exception."""
