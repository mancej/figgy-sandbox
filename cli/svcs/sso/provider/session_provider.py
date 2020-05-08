import logging
from abc import ABC, abstractmethod

import boto3
from botocore.exceptions import ClientError

from input import Input
from models.assumable_role import AssumableRole
from models.defaults.defaults import CLIDefaults
from utils.secrets_manager import SecretsManager
from utils.utils import Utils

log = logging.getLogger(__name__)


class SessionProvider(ABC):

    def __init__(self, defaults: CLIDefaults):
        self._defaults = defaults

    @Utils.retry
    @Utils.trace
    def _is_valid_session(self, session: boto3.Session):
        """Tests whether a cached session is valid or not."""
        try:
            sts = session.client('sts')
            sts.get_caller_identity()
            return True
        except ClientError:
            return False

    @abstractmethod
    def get_session(self, assuamble_role: AssumableRole, prompt: bool, exit_on_fail=True) -> boto3.Session:
        pass

    #Todo later decide whether to move this to SSOSessionProvider
    @abstractmethod
    def get_assumable_roles(self):
        pass

    @abstractmethod
    def cleanup_session_cache(self):
        pass

    def _get_user(self, prompt: bool) -> str:
        """
        Get the user either from cache, or prompt the user.

        Returns: str -> username
        """

        defaults = self._defaults
        if defaults is not None and not prompt:
            return defaults.user
        else:
            return Input.get_user()

    def _get_password(self, user_name, prompt: bool, save: bool = False) -> str:
        """
        Get the password either from keyring, or prompt the user.

        Returns: str -> password
        """

        password = SecretsManager.get_password(user_name)
        reset_password = not password

        if reset_password or prompt:
            password = Input.get_password()
            if reset_password or save:
                SecretsManager.set_password(user_name, password)

        return password