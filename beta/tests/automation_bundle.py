"""Use the exact packaged automation code when testing a built artifact."""
import os
import types
from desktop import automation


def automation_module():
    bundle = os.environ.get("LOLHELPER_TEST_AUTOMATION_BUNDLE")
    if not bundle:
        return automation
    from PyInstaller.archive.readers import CArchiveReader
    reader = CArchiveReader(bundle)
    module = types.ModuleType("desktop.automation")
    module.__package__ = "desktop"
    module.__file__ = automation.__file__
    exec(reader.open_embedded_archive("PYZ.pyz").extract("automation"), module.__dict__)
    return module
