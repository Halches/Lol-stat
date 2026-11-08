"""Переход между основными версиями без предложения откатить приложение."""
import unittest
from unittest.mock import Mock, patch

import lolhelper


class ReleaseVersionTests(unittest.TestCase):
    def check_update(self, current, latest, offered):
        app = Mock()
        with patch.object(lolhelper, 'VERSION', current), \
                patch.object(lolhelper, 'FROZEN', True), \
                patch.object(lolhelper, 'log'), \
                patch.object(lolhelper, 'latest_release', return_value=(latest, 'https://example.com/LoLHelper.exe')):
            result = lolhelper.update_app(app)
        self.assertEqual(app.root.after.call_count, int(offered), result)
        if offered:
            delay, callback = app.root.after.call_args.args
            self.assertEqual(delay, 0)
            callback()
            self.assertEqual(app.offer_update.call_args.args[0], latest)
        return result

    def test_major_upgrade(self):
        self.check_update('v1.0.38', 'v2.0.0', True)

    def test_no_major_downgrade(self):
        self.check_update('v2.0.0', 'v1.0.38', False)

    def test_equal_version_with_or_without_prefix(self):
        self.check_update('v2.0.0', '2.0.0', False)

    def test_numeric_patch_comparison(self):
        self.check_update('v2.0.9', 'v2.0.10', True)
        self.check_update('v2.0.10', 'v2.0.9', False)

    def test_minor_upgrade_and_downgrade(self):
        self.check_update('v2.0.10', 'v2.1.0', True)
        self.check_update('v2.1.0', 'v2.0.10', False)

    def test_source_checkout_still_reports_release(self):
        self.check_update('dev', 'v2.0.0', True)

    def test_service_and_invalid_tags_are_not_updates(self):
        for tag in ('voices', 'v2', 'v2.0.0-beta', 'v2.00.0', 'v2.0.0\n'):
            with self.subTest(tag=tag):
                self.check_update('v2.0.0', tag, False)

    def test_missing_executable_does_not_offer_update(self):
        app = Mock()
        with patch.object(lolhelper, 'VERSION', 'v1.0.38'), \
                patch.object(lolhelper, 'log'), \
                patch.object(lolhelper, 'latest_release', return_value=('v2.0.0', None)):
            message = lolhelper.update_app(app)
        app.root.after.assert_not_called()
        self.assertIn('недоступен', message)


if __name__ == '__main__':
    unittest.main()
