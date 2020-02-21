from unittest.mock import (
    MagicMock,
    Mock,
)

from test.picardtestcase import PicardTestCase

from picard import config
from picard.acoustid.manager import AcoustIDManager
from picard.file import File


def mock_succeed_submission(*args, **kwargs):
    # Run the callback
    args[1]({}, None, None)


def mock_fail_submission(*args, **kwargs):
    # Run the callback with error arguments
    args[1]({}, MagicMock(), True)


class AcoustIDManagerTest(PicardTestCase):
    def setUp(self):
        super().setUp()
        config.setting = {
            "clear_existing_tags": False,
            "compare_ignore_tags": []
        }
        self.mock_api_helper = MagicMock()
        self.mock_api_helper.submit_acoustid_fingerprints = Mock(wraps=mock_succeed_submission)
        self.acoustidmanager = AcoustIDManager(self.mock_api_helper)
        self.tagger.window = MagicMock()
        self.tagger.window.enable_submit = MagicMock()

    def _add_unsubmitted_files(self, count):
        files = []
        for i in range(0, count):
            file = File('foo%d.flac' % i)
            files.append(file)
            file.acoustid_fingerprint = 'foo'
            file.acoustid_length = 120
            self.acoustidmanager.add(file, None)
            self.acoustidmanager.update(file, '00000000-0000-0000-0000-%012d' % i)
            self.assertFalse(self.acoustidmanager.is_submitted(file))
        return files

    def test_add_invalid(self):
        file = File('foo.flac')
        self.acoustidmanager.add(file, '00000000-0000-0000-0000-000000000001')
        self.tagger.window.enable_submit.assert_not_called()

    def test_add_and_update(self):
        file = File('foo.flac')
        file.acoustid_fingerprint = 'foo'
        file.acoustid_length = 120
        self.acoustidmanager.add(file, '00000000-0000-0000-0000-000000000001')
        self.tagger.window.enable_submit.assert_called_with(False)
        self.acoustidmanager.update(file, '00000000-0000-0000-0000-000000000002')
        self.tagger.window.enable_submit.assert_called_with(True)
        self.acoustidmanager.update(file, '00000000-0000-0000-0000-000000000001')
        self.tagger.window.enable_submit.assert_called_with(False)

    def test_add_and_remove(self):
        file = File('foo.flac')
        file.acoustid_fingerprint = 'foo'
        file.acoustid_length = 120
        self.acoustidmanager.add(file, '00000000-0000-0000-0000-000000000001')
        self.tagger.window.enable_submit.assert_called_with(False)
        self.acoustidmanager.update(file, '00000000-0000-0000-0000-000000000002')
        self.tagger.window.enable_submit.assert_called_with(True)
        self.acoustidmanager.remove(file)
        self.tagger.window.enable_submit.assert_called_with(False)

    def test_is_submitted(self):
        file = File('foo.flac')
        file.acoustid_fingerprint = 'foo'
        file.acoustid_length = 120
        self.assertTrue(self.acoustidmanager.is_submitted(file))
        self.acoustidmanager.add(file, '00000000-0000-0000-0000-000000000001')
        self.assertTrue(self.acoustidmanager.is_submitted(file))
        self.acoustidmanager.update(file, '00000000-0000-0000-0000-000000000002')
        self.assertFalse(self.acoustidmanager.is_submitted(file))
        self.acoustidmanager.update(file, '')
        self.assertTrue(self.acoustidmanager.is_submitted(file))

    def test_submit_single_batch(self):
        f = self._add_unsubmitted_files(1)[0]
        self.acoustidmanager.submit()
        self.assertEqual(self.mock_api_helper.submit_acoustid_fingerprints.call_count, 1)
        self.assertEqual(
            f.acoustid_fingerprint,
            self.mock_api_helper.submit_acoustid_fingerprints.call_args[0][0][0].fingerprint
        )

    def test_submit_multi_batch(self):
        files = self._add_unsubmitted_files(5 * AcoustIDManager.BATCH_SUBMIT_COUNT + 1)
        self.acoustidmanager.submit()
        self.assertEqual(self.mock_api_helper.submit_acoustid_fingerprints.call_count, 6)
        for f in files:
            self.assertTrue(self.acoustidmanager.is_submitted(f))

    def test_submit_multi_batch_failure(self):
        self.mock_api_helper.submit_acoustid_fingerprints = Mock(wraps=mock_fail_submission)
        files = self._add_unsubmitted_files(5 * AcoustIDManager.BATCH_SUBMIT_COUNT + 1)
        self.acoustidmanager.submit()
        self.assertEqual(self.mock_api_helper.submit_acoustid_fingerprints.call_count, 6)
        for f in files:
            self.assertFalse(self.acoustidmanager.is_submitted(f))
