from typing import List, Set

import boto3
import logging
import time
import json
from config.constants import *
from lib.data.dynamo.config_cache_dao import ConfigCacheDao, ConfigItem
from lib.data.ssm.ssm import SsmDao
from lib.svcs.slack import SlackService
from lib.utils.utils import Utils

dynamo_resource = boto3.resource("dynamodb")
ssm_client = boto3.client('ssm')
ssm_dao = SsmDao(ssm_client)
cache_dao: ConfigCacheDao = ConfigCacheDao(dynamo_resource)
log = Utils.get_logger(__name__, logging.INFO)
MAX_DELETED_AGE = 60 * 60 * 24 * 14 * 1000  # 2 weeks in MS

webhook_url = ssm_dao.get_parameter_value(FIGGY_WEBHOOK_URL_PATH)
namespaces = json.loads(ssm_dao.get_parameter_value(FIGGY_NAMESPACES_PATH))
slack: SlackService = SlackService(webhook_url=webhook_url)


def remove_old_deleted_items():
    """
    Cleanup items marked as DELETED that are > MAX_AGE old
    """
    deleted_items: List[ConfigItem] = cache_dao.get_deleted_configs()
    for item in deleted_items:
        if int(time.time() * 1000) - item.last_updated > MAX_DELETED_AGE:
            log.info(f"Item: {item.name} is older than {MAX_DELETED_AGE / 1000}"
                     f" seconds and is marked deleted. Removing from cache...")
            cache_dao.delete(item)


def handle(event, context):
    try:
        param_names = ssm_dao.get_all_param_names(namespaces)
        cached_configs: Set[ConfigItem] = cache_dao.get_all_configs()
        cached_names = set([config.name for config in cached_configs])
        missing_params: Set[str] = param_names.difference(cached_names)
        names_to_delete: Set[str] = cached_names.difference(param_names)
        to_delete = [item.name for item in cached_configs if item.name in names_to_delete]

        for param in missing_params:
            log.info(f"Storing in cache: {param}")
            items: Set[ConfigItem] = cache_dao.get_items(param)
            cache_dao.put_in_cache(param)
            [cache_dao.delete(item) for item in items]  # If any dupes exist, get rid of em

        for param in to_delete:
            log.info(f"Deleting from cache: {param}")
            items: Set[ConfigItem] = cache_dao.get_items(param)
            sorted_items = sorted(items)
            [cache_dao.delete(item) for item in sorted_items[:-1]]  # Delete all but the most recent item.
            cache_dao.mark_deleted(sorted_items[-1])

        remove_old_deleted_items()

    except Exception as e:
        log.error(e)
        slack.send_error(title="Figgy experienced an irrecoverable error!",
                         message=f"The following error occurred in an the figgy-ssm-stream-replicator lambda. "
                                 f"If this appears to be a bug with figgy, please tell us by submitting a GitHub issue!"
                                 f" \n\n{Utils.printable_exception(e)}")
        raise e


if __name__ == "__main__":
    handle(None, None)
