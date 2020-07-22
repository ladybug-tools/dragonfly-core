"""Dragonfly configurations.

Import this into every module where access configurations are needed.

Usage:

.. code-block:: python

    from dragonfly.config import folders
    print(folders.dragonfly_schema_version_str)
"""

import os


class Folders(object):
    """Dragonfly folders.

    Properties:
        * dragonfly_schema_version
        * dragonfly_schema_version_str
        * python_package_path
    """

    def __init__(self):
        # search for the version of dragonfly-schema
        self._dragonfly_schema_version = self._find_dragonfly_schema_version()

    @property
    def dragonfly_schema_version(self):
        """Get a tuple for the installed version of dragonfly-schema (eg. (1, 5, 27)).

        This will be None if the version could not be sensed (it was not installed
        via pip) or if no dragonfly-schema installation was found next to the
        dragonfly-core installation.
        """
        return self._dragonfly_schema_version

    @property
    def dragonfly_schema_version_str(self):
        """Get a string for the installed version of dragonfly-schema (eg. "1.5.27").

        This will be None if the version could not be sensed.
        """
        if self._dragonfly_schema_version is not None:
            return '.'.join([str(item) for item in self._dragonfly_schema_version])
        return None

    @property
    def python_package_path(self):
        """Get the path to where this Python package is installed."""
        return os.path.split(os.path.dirname(__file__))[0]

    def _find_dragonfly_schema_version(self):
        """Get a tuple of 3 integers for the version of dragonfly_schema if installed."""
        schema_info_folder = None
        for item in os.listdir(self.python_package_path):
            if item.startswith('dragonfly_schema-') and item.endswith('.dist-info'):
                if os.path.isdir(os.path.join(self.python_package_path, item)):
                    schema_info_folder = item
        if schema_info_folder is not None:
            schema_info_folder = schema_info_folder.replace('.dist-info', '')
            ver = ''.join(s for s in schema_info_folder if (s.isdigit() or s == '.'))
            if ver:  # version was found in the file path name
                return tuple(int(d) for d in ver.split('.'))
        return None


"""Object possesing all key folders within the configuration."""
folders = Folders()
