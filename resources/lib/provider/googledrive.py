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

import urllib
import datetime
import copy

from clouddrive.common.remote.provider import Provider
from clouddrive.common.utils import Utils
from clouddrive.common.ui.logger import Logger
from clouddrive.common.cache.cache import Cache
from clouddrive.common.ui.utils import KodiUtils
from clouddrive.common.exception import RequestException
from urllib2 import HTTPError

class GoogleDrive(Provider):
    _default_parameters = {'spaces': 'drive', 'prettyPrint': 'false'}
    _file_fileds = 'id,name,mimeType,description,hasThumbnail,thumbnailLink,modifiedTime,owners(permissionId),parents,size,imageMediaMetadata(width),videoMediaMetadata'
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
    _user = None

    def __init__(self):
        super(GoogleDrive, self).__init__('googledrive')
        self._items_cache = Cache(KodiUtils.get_addon_info('id'), 'items', datetime.timedelta(minutes=KodiUtils.get_cache_expiration_time()))
        
        
    def _get_api_url(self):
        return 'https://www.googleapis.com/drive/v3'

    def _get_request_headers(self):
        return None
    
    def get_account(self, request_params=None, access_tokens=None):
        me = self.get('/about', parameters={'fields':'user'}, request_params=request_params, access_tokens=access_tokens)
        if not me or not 'user' in me:
            raise Exception('NoAccountInfo')
        self._user = me['user'] 
        return { 'id' : self._user['permissionId'], 'name' : self._user['displayName']}
    
    def get_drives(self, request_params=None, access_tokens=None):
        drives = [{
            'id' : self._user['permissionId'],
            'name' : '',
            'type' : ''
        }]
        return drives
    
    def get_folder_items(self, item_driveid=None, item_id=None, path=None, on_items_page_completed=None, include_download_info=False):
        item_driveid = Utils.default(item_driveid, self._driveid)
        is_album = item_id and item_id[:6] == 'album-'
        
        if is_album:
            Logger.notice(item_id)
            item_id = item_id[6:]
            Logger.notice(item_id)
        
        parameters = copy.deepcopy(self._default_parameters)
        if item_id:
            parameters['q'] = '\'%s\' in parents' % item_id
        elif path == 'sharedWithMe' or path == 'starred':
            parameters['q'] = path
        elif path != 'photos':
            if path == '/':
                parameters['q'] = '\'root\' in parents'
            elif not is_album:
                item = self.get_item_by_path(path, include_download_info)
                parameters['q'] = '\'%s\' in parents' % item['id']
                
        parameters['fields'] = 'files(%s),nextPageToken' % self._file_fileds
        if 'q' in parameters:
            parameters['q'] += ' and not trashed'
        if path == 'photos':
            self._photos_provider = GooglePhotos()
            Logger.notice(self._get_api_url())
            self._photos_provider.configure(self._account_manager, self._driveid)
            files = self._photos_provider.get('/albums')
            files['is_album'] = True
        elif is_album:
            self._photos_provider = GooglePhotos()
            self._photos_provider.configure(self._account_manager, self._driveid)
            files = self._photos_provider.post('/mediaItems:search', parameters = {'albumId': item_id})
            files['is_media_items'] = True
        else:
            self.configure(self._account_manager, self._driveid)
            files = self.get('/files', parameters = parameters)
            files['is_album'] = False
        if self.cancel_operation():
            return
        return self.process_files(files, parameters, on_items_page_completed, include_download_info)
    
    def search(self, query, item_driveid=None, item_id=None, on_items_page_completed=None):
        item_driveid = Utils.default(item_driveid, self._driveid)
        parameters = copy.deepcopy(self._default_parameters)
        parameters['fields'] = 'files(%s)' % self._file_fileds
        query = 'fullText contains \'%s\'' % Utils.str(query)
        if item_id:
            query += ' and \'%s\' in parents' % item_id
        parameters['q'] = query + ' and not trashed'
        files = self.get('/files', parameters = parameters)
        if self.cancel_operation():
            return
        return self.process_files(files, parameters, on_items_page_completed)
    
    def process_files(self, files, parameters, on_items_page_completed=None, include_download_info=False):
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
                    item = self._extract_item(f, include_download_info)
                    items.append(item)
                if on_items_page_completed:
                    on_items_page_completed(items)
            if 'nextPageToken' in files:
                parameters['pageToken'] = files['nextPageToken']
                next_files = self.get('/files', parameters = parameters)
                if self.cancel_operation():
                    return
                next_files['is_album'] = is_album
                items.extend(self.process_files(next_files, parameters, on_items_page_completed, include_download_info))
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
            item['id'] = 'album-' + item['id']
        if include_download_info:
            if is_media_items:
                item['download_info'] =  {
                    'url' : f['baseUrl']
                }
            else:
                parameters = {
                    'alt': 'media',
                    'access_token': self.get_access_tokens()['access_token']
                }
                url = self._get_api_url() + '/files/%s' % item['id']
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
        parameters = copy.deepcopy(self._default_parameters)
        if path[-1:] == '/':
            path = path[:-1]
        Logger.debug(path + ' <- Target')
        key = '%s%s' % (self._driveid, path,)
        Logger.debug('Testing item from cache: %s' % key)
        item = self._items_cache.get(key)
        if not item:
            parameters['fields'] = 'files(%s)' % self._file_fileds
            index = path.rfind('/')
            filename = urllib.unquote(path[index+1:])
            parent = path[0:index]
            if not parent:
                parent = 'root'
            else:
                parent = self.get_item_by_path(parent, include_download_info)['id']
            item = None
            parameters['q'] = '\'%s\' in parents and name = \'%s\'' % (Utils.str(parent), Utils.str(filename))
            files = self.get('/files', parameters = parameters)
            if (len(files['files']) > 0):
                for f in files['files']:
                    item = self._extract_item(f, include_download_info)
                    break
        else:
            Logger.debug('Found in cache.')
        if not item:
            raise RequestException('Not found by path', HTTPError(path, 404, 'Not found', None, None), 'Request URL: %s' % path, None)
        
        else:
            self._items_cache.set(key, item)
        return item
    
    def get_item(self, item_driveid=None, item_id=None, path=None, find_subtitles=False, include_download_info=False):
        parameters = copy.deepcopy(self._default_parameters)
        item_driveid = Utils.default(item_driveid, self._driveid)
        parameters['fields'] = self._file_fileds
        if not item_id and path == '/':
            item_id = 'root'
        if item_id:
            f = self.get('/files/%s' % item_id, parameters = parameters)
            item = self._extract_item(f, include_download_info)
        else:
            item = self.get_item_by_path(path, include_download_info)
        
        if find_subtitles:
            subtitles = []
            parameters['fields'] = 'files(' + self._file_fileds + ')'
            parameters['q'] = 'name contains \'%s\'' % Utils.str(Utils.remove_extension(item['name'])).replace("'","\\'")
            files = self.get('/files', parameters = parameters)
            for f in files['files']:
                subtitle = self._extract_item(f, include_download_info)
                if subtitle['name_extension'] == 'srt' or subtitle['name_extension'] == 'sub' or subtitle['name_extension'] == 'sbv':
                    subtitles.append(subtitle)
            if subtitles:
                item['subtitles'] = subtitles
        return item

class GooglePhotos(GoogleDrive):
    def _get_api_url(self):
        return 'https://photoslibrary.googleapis.com/v1'
            
