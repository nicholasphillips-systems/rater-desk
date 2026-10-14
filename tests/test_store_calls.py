import unittest
import os
import re
import sys
import glob

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from store import Store


class TestStoreCallsExist(unittest.TestCase):
    """Every self.store.<name>(...) the UI calls must exist on Store.

    A missing one only fails when Qt fires that slot, and an exception in a Qt
    slot aborts the whole app (main.py once called get_open_sessions, which
    never existed, and the app died a minute after every launch).
    """

    def test_ui_only_calls_real_store_methods(self):
        sources = [os.path.join(PROJECT_ROOT, "main.py")]
        sources += glob.glob(os.path.join(PROJECT_ROOT, "ui", "*.py"))
        call = re.compile(r"\bstore\.([A-Za-z_]\w*)\s*\(")
        missing = set()
        for path in sources:
            with open(path, encoding="utf-8") as fh:
                for name in call.findall(fh.read()):
                    if not hasattr(Store, name):
                        missing.add(f"{os.path.relpath(path, PROJECT_ROOT)}: store.{name}()")
        self.assertEqual(sorted(missing), [])


if __name__ == "__main__":
    unittest.main()
