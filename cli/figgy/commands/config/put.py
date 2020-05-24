import re

from config import *
from botocore.exceptions import ClientError
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter

from commands.config.get import Get
from commands.config_context import ConfigContext
from commands.types.config import ConfigCommand
from data.dao.ssm import SsmDao
from svcs.observability.usage_tracker import UsageTracker
from utils.utils import Utils


class Put(ConfigCommand):

    def __init__(self, ssm_init: SsmDao, colors_enabled: bool, config_context: ConfigContext,
                 config_completer: WordCompleter, get: Get):
        super().__init__(put, colors_enabled, config_context)
        self._ssm = ssm_init
        self._utils = Utils(colors_enabled)
        self._config_completer = config_completer
        self._get = get
        self._source_key = Utils.attr_if_exists(copy_from, config_context.args)

        self._select_name = [
            ('class:', 'Please input a PS Name: ')
        ]

        self._FILE_PREFIX = "file://"

    def _load_file(self, file_path: str) -> str:
        try:
            with open(file_path, 'r') as file:
                return file.read()
        except FileNotFoundError:
            print(
                f"Provided file path: {file_path} is invalid. No file found.")
            exit(1)

    def put_param(self, key="default", loop=False, display_hints=True) -> None:
        """
        Allows a user to define a PS name and add a new parameter at that named location. User will be prompted for a
        value, desc, and whether or not the parameter is a secret. If (Y) is selected for the secret, will encrypt the
        value with the appropriately mapped KMS key with the user's role.

        :param key: If specified, the user will be prompted for the specified key. Otherwise the user will be prompted
                    to specify the PS key to set.
        :param loop: Whether or not to continually loop and continue prompting the user for more keys.
        :param display_hints: Whether or not to display "Hints" to the user. You may want to turn this off if you are
                              looping and constantly calling put_param with a specified key.
        """

        value, desc, selection, notify, put_another = "default", None, "y", False, True

        if display_hints:
            print(f"{self.c.fg_bl}Hint:{self.c.rs} To upload a file's contents, pass in `file:///path/to/your/file` "
                  f"in the value prompt")

        while not self._utils.is_valid_input(value, f'{value} parameter value', notify) \
                or not self._utils.is_valid_input(key, f'{key} parameter name', notify) \
                or not self._utils.is_valid_selection(selection, notify) \
                or put_another:

            if key == "default" or not key:
                key = prompt(self._select_name,
                             completer=self._config_completer)

            self._utils.validate_ps_name(key)

            if self._source_key:
                plain_key = '/'.join(key.strip('/').split('/')[2:])
                source_key = f'{self._source_key}/{plain_key}'
                orig_value, orig_description = self._get.get_val_and_desc(source_key)
            else:
                orig_description = ''
                orig_value = ''

            value = prompt(f"Please input a value for {key}: ", default=orig_value if orig_value else '')

            if value.lower().startswith(self._FILE_PREFIX):
                value = self._load_file(value.replace(self._FILE_PREFIX, ""))

            existing_desc = self._ssm.get_description(key)
            desc = prompt(f"Please input an optional description: ",
                          default=existing_desc if existing_desc else orig_description if orig_description else '')

            if re.match(f'^{shared_ns}/.*$', key) is None:
                selection = prompt(is_secret, completer=WordCompleter(['Y', 'N'])).strip().lower()
                selection = selection if selection != '' else 'n'
            else:
                selection = "n"

            notify = True
            parameter_type = SSM_STRING if selection.lower() == "n" else SSM_SECURE_STRING
            key_id = None if parameter_type == SSM_STRING else \
                self._ssm.get_parameter(self._utils.get_kms_key(self.role))

            try:
                if not self._utils.is_valid_input(key, f"Parameter name", False) \
                        or not self._utils.is_valid_selection(selection, False)\
                        or not self._utils.is_valid_input(value, key, False):
                    continue

                self._ssm.set_parameter(
                    key, value, desc, parameter_type, key_id=key_id)
                if key not in self._config_completer.words:
                    self._config_completer.words.append(key)
            except ClientError as e:
                if "AccessDeniedException" == e.response['Error']['Code']:
                    print(f"\n\nYou do not have permissions to put a new config value at the path:"
                          f" {self.c.fg_bl}{key}{self.c.rs}")
                    print(f"Developers may add keys under the following namespaces: "
                          f"{self.c.fg_bl}{DEV_PS_WRITE_NS}{self.c.rs}")
                    print(f"{self.c.fg_rd}Error message: {e.response['Error']['Message']}{self.c.rs}")
                else:
                    print(f"{self.c.fg_rd}Exception caught attempting to add config: {e}{self.c.rs}")

            print()
            if loop:
                to_continue = input(f"\nAdd another? (y/N): ")
                put_another = True if to_continue.lower() == 'y' else False
                key = "default"
            else:
                put_another = False

    @UsageTracker.track_command_usage
    def execute(self):
        self.put_param(loop=True)