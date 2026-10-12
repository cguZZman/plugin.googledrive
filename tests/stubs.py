# Test setup: Kodi stand-ins and the common module (script.module.clouddrive.common) on the path. Locally the common
# module is the sibling folder; elsewhere set CLOUDDRIVE_COMMON to its path.
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMMON = os.environ.get('CLOUDDRIVE_COMMON', os.path.join(HERE, '..', '..', 'script.module.clouddrive.common'))
sys.path.insert(0, os.path.join(COMMON, 'tests'))
import kodistubs  # noqa: E402,F401  (stubs Kodi's modules and adds the common module to the path)

# The plugin's own "resources" package must win over the common module's.
sys.path.insert(0, os.path.dirname(HERE))
