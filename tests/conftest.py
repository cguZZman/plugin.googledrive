"""
Shared pytest fixtures and configuration for the Google Drive Kodi plugin tests.
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock
import pytest

# Add the resources directory to the Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'resources'))


@pytest.fixture
def temp_dir():
    """
    Create a temporary directory that is automatically cleaned up after the test.
    
    Returns:
        Path: Path object pointing to the temporary directory
    """
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path)


@pytest.fixture
def mock_addon():
    """
    Create a mock Kodi addon object with common properties and methods.
    
    Returns:
        Mock: Mock addon object
    """
    addon = Mock()
    addon.getAddonInfo = Mock(side_effect=lambda x: {
        'id': 'plugin.googledrive',
        'name': 'Google Drive',
        'version': '1.5.0',
        'path': '/path/to/addon',
        'profile': '/path/to/addon/profile'
    }.get(x, ''))
    
    addon.getSetting = Mock(return_value='')
    addon.setSetting = Mock()
    addon.getLocalizedString = Mock(side_effect=lambda x: f'String {x}')
    
    return addon


@pytest.fixture
def mock_xbmc():
    """
    Create a mock xbmc module with common functions.
    
    Returns:
        Mock: Mock xbmc module
    """
    xbmc = Mock()
    xbmc.log = Mock()
    xbmc.LOGDEBUG = 0
    xbmc.LOGINFO = 1
    xbmc.LOGWARNING = 2
    xbmc.LOGERROR = 3
    xbmc.LOGFATAL = 4
    xbmc.translatePath = Mock(side_effect=lambda x: x)
    
    return xbmc


@pytest.fixture
def mock_xbmcgui():
    """
    Create a mock xbmcgui module with common UI elements.
    
    Returns:
        Mock: Mock xbmcgui module
    """
    xbmcgui = Mock()
    
    # Mock Dialog class
    dialog = Mock()
    dialog.ok = Mock(return_value=True)
    dialog.yesno = Mock(return_value=True)
    dialog.notification = Mock()
    dialog.input = Mock(return_value='test_input')
    dialog.select = Mock(return_value=0)
    dialog.multiselect = Mock(return_value=[0])
    dialog.browse = Mock(return_value='/test/path')
    dialog.browseSingle = Mock(return_value='/test/path')
    dialog.browseMutiple = Mock(return_value=['/test/path'])
    dialog.numeric = Mock(return_value='123')
    
    xbmcgui.Dialog = Mock(return_value=dialog)
    
    # Mock ListItem class
    list_item = Mock()
    list_item.setLabel = Mock()
    list_item.setLabel2 = Mock()
    list_item.setArt = Mock()
    list_item.setInfo = Mock()
    list_item.setProperty = Mock()
    list_item.addContextMenuItems = Mock()
    list_item.setPath = Mock()
    
    xbmcgui.ListItem = Mock(return_value=list_item)
    
    # Mock WindowXML and WindowXMLDialog
    xbmcgui.WindowXML = Mock
    xbmcgui.WindowXMLDialog = Mock
    
    return xbmcgui


@pytest.fixture
def mock_xbmcplugin():
    """
    Create a mock xbmcplugin module with common plugin functions.
    
    Returns:
        Mock: Mock xbmcplugin module
    """
    xbmcplugin = Mock()
    xbmcplugin.addDirectoryItem = Mock(return_value=True)
    xbmcplugin.addDirectoryItems = Mock(return_value=True)
    xbmcplugin.endOfDirectory = Mock()
    xbmcplugin.setResolvedUrl = Mock()
    xbmcplugin.setContent = Mock()
    xbmcplugin.setSetting = Mock()
    xbmcplugin.setPluginCategory = Mock()
    xbmcplugin.setPluginFanart = Mock()
    xbmcplugin.addSortMethod = Mock()
    
    # Sort methods
    xbmcplugin.SORT_METHOD_NONE = 0
    xbmcplugin.SORT_METHOD_LABEL = 1
    xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE = 2
    xbmcplugin.SORT_METHOD_DATE = 3
    xbmcplugin.SORT_METHOD_SIZE = 4
    xbmcplugin.SORT_METHOD_FILE = 5
    xbmcplugin.SORT_METHOD_DRIVE_TYPE = 6
    xbmcplugin.SORT_METHOD_TRACKNUM = 7
    xbmcplugin.SORT_METHOD_DURATION = 8
    xbmcplugin.SORT_METHOD_TITLE = 9
    xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE = 10
    
    return xbmcplugin


@pytest.fixture
def mock_kodi_modules(mock_xbmc, mock_xbmcgui, mock_xbmcplugin, mock_addon):
    """
    Mock all common Kodi modules and make them available in sys.modules.
    
    This fixture combines all Kodi-related mocks and injects them into sys.modules
    so that imports will work correctly in the tested code.
    """
    modules = {
        'xbmc': mock_xbmc,
        'xbmcgui': mock_xbmcgui,
        'xbmcplugin': mock_xbmcplugin,
        'xbmcaddon': Mock(Addon=Mock(return_value=mock_addon))
    }
    
    # Store original modules
    original_modules = {}
    for module_name in modules:
        if module_name in sys.modules:
            original_modules[module_name] = sys.modules[module_name]
    
    # Replace with mocks
    sys.modules.update(modules)
    
    yield modules
    
    # Restore original modules
    for module_name in modules:
        if module_name in original_modules:
            sys.modules[module_name] = original_modules[module_name]
        else:
            del sys.modules[module_name]


@pytest.fixture
def sample_drive_item():
    """
    Create a sample Google Drive item for testing.
    
    Returns:
        dict: Sample drive item data
    """
    return {
        'id': 'test_file_id_123',
        'name': 'test_file.mp4',
        'mimeType': 'video/mp4',
        'size': '1234567890',
        'createdTime': '2023-01-01T00:00:00.000Z',
        'modifiedTime': '2023-06-01T00:00:00.000Z',
        'parents': ['parent_folder_id'],
        'webViewLink': 'https://drive.google.com/file/d/test_file_id_123/view',
        'webContentLink': 'https://drive.google.com/uc?id=test_file_id_123&export=download',
        'thumbnailLink': 'https://drive.google.com/thumbnail?id=test_file_id_123',
        'capabilities': {
            'canDownload': True,
            'canEdit': False,
            'canShare': True
        }
    }


@pytest.fixture
def sample_folder_item():
    """
    Create a sample Google Drive folder for testing.
    
    Returns:
        dict: Sample folder item data
    """
    return {
        'id': 'test_folder_id_456',
        'name': 'Test Folder',
        'mimeType': 'application/vnd.google-apps.folder',
        'createdTime': '2023-01-01T00:00:00.000Z',
        'modifiedTime': '2023-06-01T00:00:00.000Z',
        'parents': ['root'],
        'webViewLink': 'https://drive.google.com/drive/folders/test_folder_id_456',
        'capabilities': {
            'canAddChildren': True,
            'canDelete': True,
            'canDownload': False,
            'canListChildren': True
        }
    }


@pytest.fixture
def mock_settings():
    """
    Create a mock settings dictionary with common plugin settings.
    
    Returns:
        dict: Mock settings dictionary
    """
    return {
        'client_id': 'test_client_id',
        'client_secret': 'test_client_secret',
        'auth_server': 'https://auth.test.com',
        'cache_size': '100',
        'cache_ttl': '3600',
        'items_per_page': '50',
        'video_quality': 'original',
        'audio_quality': 'original',
        'photo_quality': 'original',
        'subtitle_lang': 'en',
        'download_path': '/tmp/downloads',
        'export_to_library': 'false',
        'library_path': '/tmp/library'
    }


@pytest.fixture
def mock_http_response():
    """
    Create a mock HTTP response for testing API calls.
    
    Returns:
        Mock: Mock response object
    """
    response = Mock()
    response.status_code = 200
    response.headers = {'content-type': 'application/json'}
    response.json = Mock(return_value={
        'kind': 'drive#fileList',
        'files': [],
        'nextPageToken': None
    })
    response.text = '{"kind": "drive#fileList", "files": [], "nextPageToken": null}'
    response.content = b'{"kind": "drive#fileList", "files": [], "nextPageToken": null}'
    response.raise_for_status = Mock()
    
    return response


@pytest.fixture(autouse=True)
def reset_modules():
    """
    Automatically reset certain modules between tests to ensure clean state.
    """
    # List of modules that should be removed from sys.modules between tests
    modules_to_reset = [
        'addon',
        'provider',
        'provider.googledrive'
    ]
    
    yield
    
    # Remove specified modules from sys.modules
    for module in modules_to_reset:
        if module in sys.modules:
            del sys.modules[module]


@pytest.fixture
def capture_logs():
    """
    Capture xbmc.log calls for assertion in tests.
    
    Returns:
        list: List of tuples (log_level, message) for each log call
    """
    logs = []
    
    def log_capture(msg, level=0):
        logs.append((level, str(msg)))
    
    return logs, log_capture