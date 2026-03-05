"""PolicyLoader: loads PolicyBundle from file or defaults. Supports non-prod hot reload."""

import json
import logging
import os

from .types import PolicyBundle

logger = logging.getLogger("gateway")


class PolicyLoader:
    """Loads PolicyBundle from file or defaults. Supports non-prod hot reload."""

    def __init__(self, policy_file: str | None = None, hot_reload: bool = False):
        self._policy_file = policy_file
        self._hot_reload = hot_reload
        self._policy: PolicyBundle | None = None
        self._file_mtime: float = 0.0

    def load(self) -> PolicyBundle:
        """Load policy from file, or return defaults if no file configured."""
        if not self._policy_file:
            self._policy = PolicyBundle.defaults()
            logger.info("Policy loaded from defaults (no POLICY_FILE configured)")
            return self._policy

        try:
            with open(self._policy_file, "r") as f:
                data = json.load(f)
            self._policy = PolicyBundle.from_dict(data)
            self._file_mtime = os.path.getmtime(self._policy_file)
            logger.info("Policy loaded from file", extra={"policy_file": self._policy_file})
        except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(
                f"Failed to load policy file, using defaults: {e}",
                extra={"policy_file": self._policy_file},
            )
            if self._policy is None:
                self._policy = PolicyBundle.defaults()

        return self._policy

    @property
    def policy(self) -> PolicyBundle:
        """Get current policy, reloading from file if hot_reload enabled and file changed."""
        if self._hot_reload and self._policy_file:
            try:
                current_mtime = os.path.getmtime(self._policy_file)
                if current_mtime != self._file_mtime:
                    logger.info("Policy file changed, reloading", extra={"policy_file": self._policy_file})
                    self.load()
            except OSError:
                pass
        if not self._policy:
            return self.load()
        return self._policy
