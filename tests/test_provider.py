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
        # "name contains" also finds other videos' subtitles: only the video's name and a dot are kept.
        d = FakeGoogleDrive([{'files': [drive_file('s1', "Movie's.srt", 'text/plain'), drive_file('x', "Movie's.nfo", 'text/plain'),
                                        drive_file('s2', "movie's.EN.vtt", 'text/vtt'), drive_file('y', "Movie's 2.srt", 'text/plain')]}])
        subtitles = d.get_subtitles('folder', "Movie's.mkv")
        self.assertEqual([s['id'] for s in subtitles], ['s1', 's2'])
        self.assertEqual(d.calls[0][1]['q'], "name contains 'Movie\\'s' and not trashed and 'folder' in parents")

    def test_folders_are_listed_a_page_at_a_time(self):
        d = FakeGoogleDrive([
            {'kind': 'drive#fileList', 'files': [drive_file('a', 'a.mp4')], 'nextPageToken': 'p2'},
            {'kind': 'drive#fileList', 'files': [drive_file('b', 'b.mp4')]}])
        items, next_page_token = d.get_folder_page(item_id='folder', page_size=500)
        self.assertEqual(([i['id'] for i in items], next_page_token), (['a'], 'p2'))
        self.assertEqual((d.calls[0][1]['pageSize'], d.calls[0][1]['orderBy']), (500, 'folder,name'))
        self.assertNotIn('pageToken', d.calls[0][1])
        items, next_page_token = d.get_folder_page(item_id='folder', page_size=500, page_token='p2')
        self.assertEqual(([i['id'] for i in items], next_page_token), (['b'], None))
        self.assertEqual((len(d.calls), d.calls[1][1]['pageToken']), (2, 'p2'))

    def test_shared_with_me_and_starred_are_not_paged(self):
        d = FakeGoogleDrive([
            {'kind': 'drive#fileList', 'files': [drive_file('a', 'a.mp4')], 'nextPageToken': 'p2'},
            {'kind': 'drive#fileList', 'files': [drive_file('b', 'b.mp4')]}])
        items, next_page_token = d.get_folder_page(path='starred', page_size=1)
        self.assertEqual(([i['id'] for i in items], next_page_token), (['a', 'b'], None))

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


class SharedDriveThroughShortcutTest(unittest.TestCase):
    """A My Drive shortcut to a folder in a shared drive: its files are listed only with that drive's parameters."""

    class Drive(FakeGoogleDrive):
        def __init__(self):
            super(SharedDriveThroughShortcutTest.Drive, self).__init__([])
            self.files = {'team': [drive_file('t', 'team.mp4', parents=['team'])], 'empty': []}

        def get(self, url, parameters=None, **kwargs):
            import re
            self.calls.append((url, dict(parameters or {})))
            if url != '/files':
                return {'driveId': 'shared'} if url == '/files/team' else {}
            parent = re.findall(r"'([^']+)' in parents", parameters['q'])[0]
            in_drive = parameters.get('driveId') == 'shared' and parameters.get('includeItemsFromAllDrives') == 'true'
            name = re.findall(r"name = '([^']+)'", parameters['q'])
            files = self.files.get(parent, []) if in_drive or parent != 'team' else []
            if name:
                files = [f for f in files if f['name'] == name[0]]
            return {'kind': 'drive#fileList', 'files': files}

    def test_browsing_the_shortcut_lists_the_shared_folder(self):
        d = self.Drive()
        self.assertEqual([i['id'] for i in d.get_folder_items(item_id='team')], ['t'])
        self.assertEqual([c[0] for c in d.calls], ['/files', '/files/team', '/files'])

    def test_empty_my_drive_folders_cost_one_more_request(self):
        d = self.Drive()
        self.assertEqual(d.get_folder_items(item_id='empty'), [])
        self.assertEqual([c[0] for c in d.calls], ['/files', '/files/empty'])

    def test_pages_of_the_shared_folder_stay_in_its_drive(self):
        class Paged(self.Drive):
            def get(self, url, parameters=None, **kwargs):
                files = super(Paged, self).get(url, parameters, **kwargs)
                if url == '/files' and files['files']:
                    first = 'pageToken' not in parameters
                    files['files'] = files['files'][:1] if first else files['files'][1:]
                    if first:
                        files['nextPageToken'] = 'n'
                return files
        d = Paged()
        d.files['team'].append(drive_file('u', 'zz.mp4', parents=['team']))
        items, next_page_token = d.get_folder_page(item_id='team', page_size=1)
        self.assertEqual(([i['id'] for i in items], next_page_token), (['t'], 'drive:shared:n'))
        items, next_page_token = d.get_folder_page(item_id='team', page_size=1, page_token=next_page_token)
        self.assertEqual(([i['id'] for i in items], next_page_token), (['u'], None))
        self.assertEqual((d.calls[-1][1]['pageToken'], d.calls[-1][1]['driveId']), ('n', 'shared'))
        self.assertEqual([c[0] for c in d.calls], ['/files', '/files/team', '/files', '/files'], 'the next page needs no lookup')

    def test_exports_and_paths_through_the_shortcut(self):
        d = self.Drive()
        self.assertEqual([i['id'] for i in d.list_subtree('me', 'team')['team']], ['t'])
        self.assertEqual(d.list_subtree('me', 'empty'), {'empty': []})
        d = self.Drive()
        d._items_cache = unittest.mock.MagicMock(get=lambda key: None)
        d.files['root'] = [drive_file('team', 'Team', 'application/vnd.google-apps.shortcut', parents=['root'],
                                      shortcutDetails={'targetId': 'team', 'targetMimeType': FOLDER})]
        self.assertEqual(d.get_item_by_path('/Team/team.mp4')['id'], 't')


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
