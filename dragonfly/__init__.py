"""Dragonfly Core library."""
import importlib
import pkgutil
import sys

from honeybee.logutil import get_logger


logger = get_logger(__name__, filename='dragonfly.log')

#  find and import dragonfly extensions
#  this is a critical step to add additional functionalities to dragonfly core library.
extensions = {}
for finder, name, ispkg in pkgutil.iter_modules():
    if not name.startswith('dragonfly_'):
        continue
    try:
        extensions[name] = importlib.import_module(name)
    except Exception:
        if (sys.version_info >= (3, 0)):
            logger.exception('Failed to import {0}!'.format(name))
    else:
        logger.info('Successfully imported Dragonfly plugin: {}'.format(name))
