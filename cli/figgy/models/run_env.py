
class RunEnv:

    def __init__(self, env, account_id: str = None):
        self.env = env
        self.account_id = account_id

    def __str__(self):
        return self.env

    def __eq__(self, obj):
        if isinstance(obj, RunEnv):
            return obj.env == self.env

        return False