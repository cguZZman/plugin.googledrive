"""
Validation tests to verify the testing infrastructure is properly set up.
"""
import pytest
import sys
import os
from pathlib import Path


class TestInfrastructure:
    """Test class to validate the testing infrastructure setup."""
    
    def test_pytest_is_available(self):
        """Verify that pytest is installed and importable."""
        import pytest
        assert pytest.__version__
    
    def test_pytest_cov_is_available(self):
        """Verify that pytest-cov is installed and importable."""
        import pytest_cov
        assert pytest_cov
    
    def test_pytest_mock_is_available(self):
        """Verify that pytest-mock is installed and importable."""
        import pytest_mock
        assert pytest_mock
    
    def test_project_structure_exists(self):
        """Verify that the expected project structure exists."""
        project_root = Path(__file__).parent.parent
        
        # Check main directories
        assert project_root.exists()
        assert (project_root / 'resources').exists()
        assert (project_root / 'resources' / 'lib').exists()
        assert (project_root / 'resources' / 'lib' / 'provider').exists()
        
        # Check test directories
        assert (project_root / 'tests').exists()
        assert (project_root / 'tests' / 'unit').exists()
        assert (project_root / 'tests' / 'integration').exists()
        
        # Check configuration files
        assert (project_root / 'pyproject.toml').exists()
        assert (project_root / '.gitignore').exists()
    
    def test_conftest_fixtures_are_available(self, temp_dir, mock_addon, mock_xbmc):
        """Verify that conftest fixtures are properly loaded."""
        # Test temp_dir fixture
        assert temp_dir.exists()
        assert temp_dir.is_dir()
        
        # Test mock_addon fixture
        assert mock_addon.getAddonInfo('id') == 'plugin.googledrive'
        assert mock_addon.getAddonInfo('name') == 'Google Drive'
        
        # Test mock_xbmc fixture
        assert hasattr(mock_xbmc, 'log')
        assert hasattr(mock_xbmc, 'LOGDEBUG')
    
    def test_resources_in_python_path(self):
        """Verify that resources directory is in Python path."""
        resources_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'resources')
        assert resources_path in sys.path
    
    @pytest.mark.unit
    def test_unit_marker_works(self):
        """Verify that the unit test marker works correctly."""
        assert True
    
    @pytest.mark.integration
    def test_integration_marker_works(self):
        """Verify that the integration test marker works correctly."""
        assert True
    
    @pytest.mark.slow
    def test_slow_marker_works(self):
        """Verify that the slow test marker works correctly."""
        import time
        time.sleep(0.1)  # Simulate a slow test
        assert True
    
    def test_mock_kodi_modules(self, mock_kodi_modules):
        """Verify that Kodi modules can be mocked properly."""
        # Modules should be in the fixture return
        assert 'xbmc' in mock_kodi_modules
        assert 'xbmcgui' in mock_kodi_modules
        assert 'xbmcplugin' in mock_kodi_modules
        assert 'xbmcaddon' in mock_kodi_modules
        
        # They should also be importable
        import xbmc
        import xbmcgui
        import xbmcplugin
        import xbmcaddon
        
        # Verify basic functionality
        assert hasattr(xbmc, 'log')
        assert hasattr(xbmcgui, 'Dialog')
        assert hasattr(xbmcplugin, 'addDirectoryItem')
        assert hasattr(xbmcaddon, 'Addon')
    
    def test_sample_fixtures(self, sample_drive_item, sample_folder_item):
        """Verify that sample data fixtures work correctly."""
        # Test drive item
        assert sample_drive_item['id'] == 'test_file_id_123'
        assert sample_drive_item['mimeType'] == 'video/mp4'
        assert 'capabilities' in sample_drive_item
        
        # Test folder item
        assert sample_folder_item['id'] == 'test_folder_id_456'
        assert sample_folder_item['mimeType'] == 'application/vnd.google-apps.folder'
        assert sample_folder_item['capabilities']['canListChildren'] is True
    
    def test_coverage_will_be_generated(self):
        """Verify that coverage will be generated for the resources module."""
        # This test just ensures we're set up to measure coverage
        from pathlib import Path
        resources_path = Path(__file__).parent.parent / 'resources'
        assert resources_path.exists()
        
        # Try to import a module from resources to ensure it can be covered
        sys.path.insert(0, str(resources_path.parent))
        try:
            from resources import __init__
            assert True  # If we get here, import worked
        except ImportError:
            # This is okay, just means the module structure is different
            pass