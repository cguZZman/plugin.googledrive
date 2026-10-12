import unittest

import stubs  # noqa: F401
import kodistubs
from resources.lib.provider.googledrive import GoogleDrive

kodistubs.use_temp_profile()


def drive_file(file_id, name, mime='video/mp4', **extra):
    f = {'id': file_id, 'name': name, 'mimeType': mime, 'size': '7', 'modifiedTime': '2026-10-01T10:00:00Z',
         'parents': ['folder'], 'owners': [{'permissionId': 'owner'}]}
    f.update(extra)
    return f


class FakeGoogleDrive(GoogleDrive):
    def __init__(self, responses):
        super(GoogleDrive, self).__init__('googledrive')
        self.responses = list(responses)
        self.calls = []
        self._driveid = 'me'
        self._is_shared_drive = False

    def configure(self, account_manager, driveid):
        pass

    def get(self, url, parameters=None, **kwargs):
        self.calls.append((url, dict(parameters or {})))
        return self.responses.pop(0)


class GoogleDriveProviderTest(unittest.TestCase):
    def test_pages_follow_next_page_token(self):
        d = FakeGoogleDrive([
            {'kind': 'drive#fileList', 'files': [drive_file('a', 'a.mp4')], 'nextPageToken': 'p2'},
            {'kind': 'drive#fileList', 'files': [drive_file('b', 'b.mp4')]}])
        self.assertEqual([i['id'] for i in d.get_folder_items(item_id='folder')], ['a', 'b'])
        self.assertEqual(d.calls[0][1]['q'], "'folder' in parents and not trashed")
        self.assertEqual(d.calls[1][1]['pageToken'], 'p2')

    def test_item_mapping(self):
        d = FakeGoogleDrive([])
        video = d._extract_item(drive_file('a', 'Movie.mkv', videoMediaMetadata={'width': 1920, 'height': 1080, 'durationMillis': '5000'},
                                           hasThumbnail=True, thumbnailLink='https://thumb'), include_download_info=True)
        self.assertEqual((video['parent'], video['drive_id'], video['size']), ('folder', 'owner', 7))
        self.assertEqual(video['video'], {'width': 1920, 'height': 1080, 'duration': 5})
        self.assertEqual(video['download_info']['url'], 'https://www.googleapis.com/drive/v3/files/a?alt=media')
        self.assertIn('folder', d._extract_item(drive_file('f', 'Folder', 'application/vnd.google-apps.folder')))
        shortcut = d._extract_item(drive_file('s', 'link', 'application/vnd.google-apps.shortcut', shortcutDetails={'targetId': 't', 'targetMimeType': 'video/mp4'}))
        self.assertEqual((shortcut['id'], shortcut['mimetype']), ('t', 'video/mp4'))

    def test_search_escapes_the_query(self):
        d = FakeGoogleDrive([{'kind': 'drive#fileList', 'files': []}])
        d.search("it's a \\ test")
        self.assertEqual(d.calls[0][1]['q'], "fullText contains 'it\\'s a \\\\ test' and not trashed")

    def test_subtitles_come_from_the_video_folder(self):
        d = FakeGoogleDrive([{'files': [drive_file('s1', 'Movie.srt', 'text/plain'), drive_file('x', 'Movie.nfo', 'text/plain')]}])
        subtitles = d.get_subtitles('folder', "Movie's.mkv")
        self.assertEqual([s['name'] for s in subtitles], ['Movie.srt'])
        self.assertEqual(d.calls[0][1]['q'], "name contains 'Movie\\'s' and 'folder' in parents")

    def test_shared_drive_parameters(self):
        d = FakeGoogleDrive([])
        d._is_shared_drive = True
        parameters = d.prepare_parameters()
        self.assertEqual((parameters['corpora'], parameters['driveId']), ('drive', 'me'))
        self.assertEqual(GoogleDrive._shared_drive_parameters['driveId'], '', 'the shared dict is not changed')


if __name__ == '__main__':
    unittest.main()
