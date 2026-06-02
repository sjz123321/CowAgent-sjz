import os
import pathlib
import time

from config import conf


class TmpDir(object):
    """A temporary directory that is deleted when the object is destroyed."""

    tmpFilePath = pathlib.Path("./tmp/")

    def __init__(self):
        pathExists = os.path.exists(self.tmpFilePath)
        if not pathExists:
            os.makedirs(self.tmpFilePath)

    def path(self):
        return str(self.tmpFilePath) + "/"

    @staticmethod
    def cleanup(days: int = 7, path: str = None) -> int:
        """Remove files and empty subdirectories older than `days` days.

        Args:
            days: age threshold (default 7)
            path: directory to clean (defaults to ./tmp/)

        Returns:
            number of items removed
        """
        if path is None:
            path = str(TmpDir.tmpFilePath)
        cutoff = time.time() - days * 86400
        removed = 0
        if not os.path.isdir(path):
            return 0

        # Remove old files bottom-up so we can also clean empty dirs
        for root, dirs, files in os.walk(path, topdown=False):
            for name in files:
                fp = os.path.join(root, name)
                try:
                    if os.path.getmtime(fp) < cutoff:
                        os.remove(fp)
                        removed += 1
                except Exception:
                    pass
            for name in dirs:
                dp = os.path.join(root, name)
                try:
                    if not os.listdir(dp):
                        os.rmdir(dp)
                        removed += 1
                except Exception:
                    pass
        return removed
