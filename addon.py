#-------------------------------------------------------------------------------
# Copyright (C) 2017 Carlos Guzman (cguZZman) carlosguzmang@protonmail.com
# 
# This file is part of Google Drive for Kodi
# 
# Google Drive for Kodi is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Cloud Drive Common Module for Kodi is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------

import datetime
import urllib
from urllib2 import HTTPError
import urlparse

from clouddrive.common.cache.simplecache import SimpleCache
from clouddrive.common.remote.request import Request
from clouddrive.common.ui.addon import CloudDriveAddon
from clouddrive.common.ui.utils import KodiUtils
from clouddrive.common.utils import Utils
from resources.lib.provider.googledrive import GoogleDrive
from resources.lib.provider.googlephotos import GooglePhotos


class GoogleDriveAddon(CloudDriveAddon):
    _provider = GoogleDrive()
    _photos_provider = GooglePhotos()
    _parameters = {'spaces': 'drive', 'prettyPrint': 'false'}
    _file_fileds = 'id,name,mimeType,description,hasThumbnail,thumbnailLink,modifiedTime,owners(permissionId),parents,size,imageMediaMetadata(width),videoMediaMetadata'
    _cache = None
    _child_count_supported = False
    _change_token = None
    _extension_map = {
        'html' : 'text/html',
        'htm' : 'text/html',
        'txt' : 'text/plain',
        'rtf' : 'application/rtf',
        'odf' : 'application/vnd.oasis.opendocument.text',
        'pdf' : 'application/pdf',
        'doc' : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'docx' : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'epub' : 'application/epub+zip',
        'xls' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'sxc' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'csv' : 'text/csv',
        'ppt' : 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'pptx' : 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'sxi' : 'application/vnd.oasis.opendocument.presentation',
        'json' : 'application/vnd.google-apps.script+json'
    }    
    def __init__(self):
        self._cache = SimpleCache()
        super(GoogleDriveAddon, self).__init__()
        
    def get_provider(self):
        return self._provider
    
    def get_my_files_menu_name(self):
        return self._addon.getLocalizedString(32013)
    
    def get_custom_drive_folders(self, driveid):
        self._account_manager.load()
        drive_folders = []
        drive_folders.append({'name' : self._common_addon.getLocalizedString(32058), 'path' : 'sharedWithMe'})
        if self._content_type == 'image':
            drive_folders.append({'name' : self._addon.getLocalizedString(32007), 'path' : 'photos'})
        drive_folders.append({'name' : self._addon.getLocalizedString(32014), 'path' : 'starred'})
        return drive_folders

    def new_change_token_slideshow(self, change_token, driveid, item_driveid=None, item_id=None, path=None):
        self._provider.configure(self._account_manager, driveid)
        if not change_token:
            response = self._provider.get('/changes/startPageToken', parameters = self._parameters)
            self._change_token = Utils.get_safe_value(response, 'startPageToken')
            change_token = 1
        else:
            page_token = self._change_token
            while page_token:
                self._parameters['pageToken'] = page_token
                self._parameters['fields'] = 'nextPageToken,newStartPageToken,changes(file(id,name,parents))'
                response = self._provider.get('/changes', parameters = self._parameters)
                if self.cancel_operation():
                    return
                self._change_token = Utils.get_safe_value(response, 'newStartPageToken', self._change_token)
                changes = Utils.get_safe_value(response, 'changes', [])
                for change in changes:
                    f = Utils.get_safe_value(change, 'file', {})
                    parents = Utils.get_safe_value(f, 'parents', [])
                    parents.append(f['id'])
                    if item_id in parents:
                        return change_token + 1
                page_token = Utils.get_safe_value(response, 'nextPageToken')
        return change_token
    
    def get_folder_items(self, driveid, item_driveid=None, item_id=None, path=None, on_items_page_completed=None):
        self._provider.configure(self._account_manager, driveid)
        item_driveid = Utils.default(item_driveid, driveid)
        is_album = self._addon_params and 'is_album' in self._addon_params
        if item_id:
            self._parameters['q'] = '\'%s\' in parents' % item_id
        elif path == 'sharedWithMe' or path == 'starred':
            self._parameters['q'] = path
        elif path != 'photos':
            if path == '/':
                self._parameters['q'] = '\'root\' in parents'
            elif not is_album:
                item = self.get_item_by_path(path)
                self._parameters['q'] = '\'%s\' in parents' % item['id']
                
        self._parameters['fields'] = 'files(%s),nextPageToken' % self._file_fileds
        if 'q' in self._parameters:
            self._parameters['q'] += ' and not trashed'
        if path == 'photos':
            self._photos_provider.configure(self._account_manager, driveid)
            files = self._photos_provider.get('/albums')
            files['is_album'] = True
        elif is_album:
            self._photos_provider.configure(self._account_manager, driveid)
            files = self._photos_provider.post('/mediaItems:search', parameters = {'pageSize': '1000', 'albumId': item_id})
            files['is_media_items'] = True
        else:
            self._provider.configure(self._account_manager, driveid)
            files = self._provider.get('/files', parameters = self._parameters)
            files['is_album'] = False
        if self.cancel_operation():
            return
        return self.process_files(driveid, files, on_items_page_completed)
    
    def search(self, query, driveid, item_driveid=None, item_id=None, on_items_page_completed=None):
        self._provider.configure(self._account_manager, driveid)
        item_driveid = Utils.default(item_driveid, driveid)
        self._parameters['fields'] = 'files(%s)' % self._file_fileds
        query = 'fullText contains \'%s\'' % Utils.str(query)
        if item_id:
            query += ' and \'%s\' in parents' % item_id
        self._parameters['q'] = query
        files = self._provider.get('/files', parameters = self._parameters)
        if self.cancel_operation():
            return
        return self.process_files(driveid, files, on_items_page_completed)
    
    def process_files(self, driveid, files, on_items_page_completed=None):
        items = []
        if files:
            is_album = Utils.get_safe_value(files, 'is_album', False)
            is_media_items = Utils.get_safe_value(files, 'is_media_items', False)
            if is_album:
                collection = 'albums'
            elif is_media_items:
                collection = 'mediaItems'
            else:
                collection = 'files'
            if collection in files:
                for f in files[collection]:
                    f['is_album'] = is_album
                    f['is_media_items'] = is_media_items
                    item = self._extract_item(f)
                    cache_key = self._addonid+'-drive-'+Utils.str(driveid)+'-item_driveid-'+Utils.str(item['drive_id'])+'-item_id-'+Utils.str(item['id'])+'-path-None'
                    self._cache.set(cache_key, f, expiration=datetime.timedelta(minutes=1))
                    items.append(item)
                if on_items_page_completed:
                    on_items_page_completed(items)
            if 'nextPageToken' in files:
                self._parameters['pageToken'] = files['nextPageToken']
                next_files = self._provider.get('/files', parameters = self._parameters)
                if self.cancel_operation():
                    return
                next_files['is_album'] = is_album
                items.extend(self.process_files(driveid, next_files, on_items_page_completed))
            elif 'pageToken' in self._parameters:
                del self._parameters['pageToken']
        return items
    
    def _extract_item(self, f, include_download_info=False):
        size = long('%s' % Utils.get_safe_value(f, 'size', 0))
        is_album = Utils.get_safe_value(f, 'is_album', False)
        is_media_items = Utils.get_safe_value(f, 'is_media_items', False)
        if is_album:
            mimetype = 'application/vnd.google-apps.folder'
            name = f['title']
        else:
            mimetype = Utils.get_safe_value(f, 'mimeType', '')
            name = Utils.get_safe_value(f, 'name', '')
        if is_media_items:
            name = Utils.get_safe_value(f, 'id', '')
        item = {
            'id': f['id'],
            'name': name,
            'name_extension' : Utils.get_extension(name),
            'drive_id' : Utils.get_safe_value(Utils.get_safe_value(f, 'owners', [{}])[0], 'permissionId'),
            'mimetype' : mimetype,
            'last_modified_date' : Utils.get_safe_value(f,'modifiedTime'),
            'size': size,
            'description': Utils.get_safe_value(f, 'description', '')
        }
        if item['mimetype'] == 'application/vnd.google-apps.folder':
            item['folder'] = {
                'child_count' : 0
            }
        if is_media_items:
            item['url'] = f['baseUrl']
            if 'mediaMetadata' in f:
                metadata = f['mediaMetadata']
                item['video'] = {
                    'width' : Utils.get_safe_value(metadata, 'width'),
                    'height' : Utils.get_safe_value(metadata, 'height')
                }
        if 'videoMediaMetadata' in f:
            video = f['videoMediaMetadata']
            item['video'] = {
                'width' : Utils.get_safe_value(video, 'width'),
                'height' : Utils.get_safe_value(video, 'height'),
                'duration' : long('%s' % Utils.get_safe_value(video, 'durationMillis', 0)) / 1000
            }
        if 'imageMediaMetadata' in f or 'mediaMetadata' in f:
            item['image'] = {
                'size' : size
            }
        if 'hasThumbnail' in f and f['hasThumbnail']:
            item['thumbnail'] = Utils.get_safe_value(f, 'thumbnailLink')
        if is_album:
            item['thumbnail'] = Utils.get_safe_value(f, 'coverPhotoBaseUrl')
            item['extra_params'] = {'is_album' : True}
        if include_download_info:
            if is_media_items:
                item['download_info'] =  {
                    'url' : f['baseUrl']
                }
            else:
                parameters = {
                    'alt': 'media',
                    'access_token': self._provider.get_access_tokens()['access_token']
                }
                url = self._provider._get_api_url() + '/files/%s' % item['id']
                if 'size' not in f and item['mimetype'] == 'application/vnd.google-apps.document':
                    url += '/export'
                    parameters['mimeType'] = self.get_mimetype_by_extension(item['name_extension'])
                item['download_info'] =  {
                    'url' : url + '?%s' % urllib.urlencode(parameters)
                }
        return item
    
    def get_mimetype_by_extension(self, extension):
        if extension and extension in self._extension_map:
            return self._extension_map[extension]
        return self._extension_map['pdf']
    
    def get_item_by_path(self, path, include_download_info=False):
        if path[:1] == '/':
            path = path[1:]
        if path[-1:] == '/':
            path = path[:-1]
        parts = path.split('/')
        parent = 'root'
        current_path = ''
        item = None
        self._parameters['fields'] = 'files(%s)' % self._file_fileds
        for part in parts:
            part = urllib.unquote(part)
            current_path += '/%s' % part
            self._parameters['q'] = '\'%s\' in parents and name = \'%s\'' % (Utils.str(parent), Utils.str(part))
            files = self._provider.get('/files', parameters = self._parameters)
            if (len(files['files']) > 0):
                for f in files['files']:
                    item = self._extract_item(f, include_download_info)
                    parent = item['id']
                    cache_key = self._addonid+'-drive-None-item_driveid-None-item_id-None-path-'+Utils.str(current_path)
                    self._cache.set(cache_key, f, expiration=datetime.timedelta(minutes=1))
                    break
            else:
                item = None
                break
        if not item:
            raise HTTPError(path, 404, 'Not found', None, None)
        return item
    
    def get_item(self, driveid, item_driveid=None, item_id=None, path=None, find_subtitles=False, include_download_info=False):
        self._provider.configure(self._account_manager, driveid)
        item_driveid = Utils.default(item_driveid, driveid)
        all_cache_key = self._addonid+'-drive-'+Utils.str(driveid)+'-item_driveid-'+Utils.str(item_driveid)+'-item_id-'+Utils.str(item_id)+'-path-'+Utils.str(path)
        f = self._cache.get(all_cache_key)
        if f:
            item = self._extract_item(f, include_download_info)
        else:
            path_cache_key = self._addonid+'-drive-None-item_driveid-None-item_id-None-path-'+Utils.str(path)
            f = self._cache.get(path_cache_key)
            if f:
                item = self._extract_item(f, include_download_info)
            else:
                self._parameters['fields'] = self._file_fileds
                if not item_id and path == '/':
                    item_id = 'root'
                if item_id:
                    f = self._provider.get('/files/%s' % item_id, parameters = self._parameters)
                    self._cache.set(all_cache_key, f, expiration=datetime.timedelta(seconds=59))
                    item = self._extract_item(f, include_download_info)
                else:
                    item = self.get_item_by_path(path, include_download_info)
        
        if find_subtitles:
            subtitles = []
            self._parameters['fields'] = 'files(' + self._file_fileds + ')'
            self._parameters['q'] = 'name contains \'%s\'' % Utils.str(Utils.remove_extension(item['name'])).replace("'","\\'")
            files = self._provider.get('/files', parameters = self._parameters)
            for f in files['files']:
                subtitle = self._extract_item(f, include_download_info)
                if subtitle['name_extension'] == 'srt' or subtitle['name_extension'] == 'sub' or subtitle['name_extension'] == 'sbv':
                    subtitles.append(subtitle)
            if subtitles:
                item['subtitles'] = subtitles
        return item
    
    def _get_item_play_url(self, file_name, driveid, item_driveid=None, item_id=None):
        url = None
        if KodiUtils.get_addon_setting('ask_stream_format') == 'true':
            url = self._select_stream_format(driveid, item_driveid, item_id)
        if not url:
            url = super(GoogleDriveAddon, self)._get_item_play_url(file_name, driveid, item_driveid, item_id)
        return url
    
    def _select_stream_format(self, driveid, item_driveid=None, item_id=None):
        url = None
        self._progress_dialog.update(0, self._addon.getLocalizedString(32009))
        self._provider.configure(self._account_manager, driveid)
        self.get_item(driveid, item_driveid, item_id)
        request = Request('https://drive.google.com/get_video_info', urllib.urlencode({'docid' : item_id}), {'authorization': 'Bearer %s' % self._provider.get_access_tokens()['access_token']})
        response_text = request.request()
        response_params = dict(urlparse.parse_qsl(response_text))
        self._progress_dialog.close()
        if Utils.get_safe_value(response_params, 'status', '') == 'ok':
            fmt_list = Utils.get_safe_value(response_params, 'fmt_list', '').split(',')
            stream_formats = [self._addon.getLocalizedString(32015)]
            for fmt in fmt_list:
                data = fmt.split('/')
                stream_formats.append(data[1])
            select = self._dialog.select(self._addon.getLocalizedString(32016), stream_formats, 8000)
            if select > 0:
                data = fmt_list[select-1].split('/')
                fmt_stream_map = Utils.get_safe_value(response_params, 'fmt_stream_map', '').split(',')
                
                for fmt in fmt_stream_map:
                    stream_data = fmt.split('|')
                    if stream_data[0] == data[0]:
                        url = stream_data[1]
                        break
                if url:
                    cookie_header = ''
                    for cookie in request.response_cookies:
                        if cookie_header: cookie_header += ';'
                        cookie_header += cookie.name + '=' + cookie.value;
                    url += '|cookie=' + urllib.quote(cookie_header)
        return url;
    
if __name__ == '__main__':
    GoogleDriveAddon().route()

