import unittest
import unittest.mock

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


FOLDER = 'application/vnd.google-apps.folder'


class TreeDrive(FakeGoogleDrive):
    """Answers '... in parents' queries from a folder tree: {folder id: [drive files]}."""

    def __init__(self, tree):
        super(TreeDrive, self).__init__([])
        self.tree = tree

    def get(self, url, parameters=None, **kwargs):
        import re
        self.calls.append((url, dict(parameters or {})))
        parents = re.findall(r"'([^']+)' in parents", parameters['q'])
        files = []
        for parent in parents:
            for f in self.tree.get(parent, []):
                files.append(dict(f, parents=[parent]))
        return {'kind': 'drive#fileList', 'files': files}


def tree_of(folders):
    tree = {}
    for parent, entries in folders.items():
        tree[parent] = [drive_file(i, n, FOLDER if n.endswith('/') else 'video/mp4') for i, n in entries]
    return tree


class SubtreeListingTest(unittest.TestCase):
    TREE = tree_of({
        'root': [('A', 'A/'), ('B', 'B/'), ('r', 'r.mp4')],
        'A': [('a', 'a.mp4'), ('C', 'C/')],
        'B': [('b', 'b.mp4')],
        'C': [('c', 'c.mp4')],
    })

    def test_lists_the_whole_tree_in_one_request_per_level(self):
        d = TreeDrive(self.TREE)
        tree = d.list_subtree('me', 'root')
        self.assertEqual({k: sorted(i['id'] for i in v) for k, v in tree.items()}, {'root': ['A', 'B', 'r'], 'A': ['C', 'a'], 'B': ['b'], 'C': ['c']})
        self.assertEqual([c[1]['q'] for c in d.calls], [
            "('root' in parents) and not trashed",
            "('A' in parents or 'B' in parents) and not trashed",
            "('C' in parents) and not trashed"])
        self.assertTrue(all('download_info' in i for i in tree['A'] if 'folder' not in i))

    def test_exports_get_every_folder_from_one_listing(self):
        d = TreeDrive(self.TREE)
        for folder in ('root', 'A', 'B', 'C'):
            d.get_export_folder_items('me', folder)
        self.assertEqual(len(d.calls), 3)

    def test_many_folders_are_split_into_batches(self):
        d = TreeDrive(tree_of({'root': [('f%d' % n, 'f%d/' % n) for n in range(250)]}))
        d.list_subtree('me', 'root')
        self.assertEqual([c[1]['q'].count(' in parents') for c in d.calls], [1, 100, 100, 50])

    def test_a_shortcut_to_an_ancestor_does_not_loop(self):
        tree = tree_of({'root': [('A', 'A/')], 'A': [('a', 'a.mp4')]})
        tree['A'].append(drive_file('s', 'back', 'application/vnd.google-apps.shortcut', shortcutDetails={'targetId': 'root', 'targetMimeType': FOLDER}))
        d = TreeDrive(tree)
        d.list_subtree('me', 'root')
        self.assertEqual(len(d.calls), 2)

    def test_browsing_still_lists_one_folder(self):
        d = TreeDrive(self.TREE)
        self.assertEqual(sorted(i['id'] for i in d.get_folder_items(item_id='root', include_download_info=True)), ['A', 'B', 'r'])
        self.assertEqual([c[1]['q'] for c in d.calls], ["'root' in parents and not trashed"])


class PathLookupTest(unittest.TestCase):
    def test_paths_are_resolved_name_by_name_without_trashed_files(self):
        d = FakeGoogleDrive([
            {'files': [drive_file('m', 'Movies', 'application/vnd.google-apps.folder', parents=['root'])]},
            {'files': [drive_file('f', "It's.mkv", parents=['m'])]}])
        d._items_cache = unittest.mock.MagicMock(get=lambda key: None)
        self.assertEqual(d.get_item_by_path("/Movies/It's.mkv")['id'], 'f')
        self.assertEqual([c[1]['q'] for c in d.calls], [
            "'root' in parents and name = 'Movies' and not trashed",
            "'m' in parents and name = 'It\\'s.mkv' and not trashed"])

    def test_shared_drive_paths_start_at_the_drive(self):
        d = FakeGoogleDrive([{'files': [drive_file('m', 'Movies', 'application/vnd.google-apps.folder')]}])
        d._items_cache = unittest.mock.MagicMock(get=lambda key: None)
        d._is_shared_drive, d._driveid = True, 'shared1'
        d.prepare_parameters = lambda: {}
        d.get_item_by_path('/Movies')
        self.assertEqual(d.calls[0][1]['q'], "'shared1' in parents and name = 'Movies' and not trashed")
