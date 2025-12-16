"""
GLB file format validation module.
Provides memory-efficient validation of GLB headers and structure.
"""

import logging
import struct
from typing import Dict, Any, Optional
from pathlib import Path
from config import GLBConstants, Config

logger = logging.getLogger(__name__)


class GLBValidator:
    """Validates GLB file format and structure"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config
        self.constants = GLBConstants
    
    def validate_file_size(self, file_path: str, file_size: Optional[int] = None) -> Dict[str, Any]:
        """
        Validate file size to prevent DoS attacks and handle edge cases
        """
        try:
            path = Path(file_path)
            
            if not path.exists():
                return {
                    'success': False,
                    'error': 'Input file does not exist',
                    'user_message': 'The uploaded file could not be found.',
                    'category': 'File System Error'
                }
            
            size = file_size if file_size is not None else path.stat().st_size
            
            if size <= 0:
                return {
                    'success': False,
                    'error': 'File is empty or has invalid size',
                    'user_message': 'The uploaded file appears to be empty.',
                    'category': 'File Size Error'
                }
            
            if size < self.config.MIN_FILE_SIZE:
                return {
                    'success': False,
                    'error': f'File too small: {size} bytes',
                    'user_message': f'The file is too small (minimum {self.config.MIN_FILE_SIZE} bytes required).',
                    'category': 'File Size Error'
                }
            
            max_file_size = self.config.MAX_CONTENT_LENGTH
            if size > max_file_size:
                size_mb = size / (1024 * 1024)
                max_size_mb = max_file_size / (1024 * 1024)
                return {
                    'success': False,
                    'error': f'File too large: {size_mb:.1f}MB',
                    'user_message': f'The file is too large ({size_mb:.1f}MB). Maximum size is {max_size_mb:.0f}MB.',
                    'category': 'File Size Error'
                }
            
            return {'success': True, 'file_size': size}
            
        except OSError as e:
            return {
                'success': False,
                'error': f'Cannot read file: {str(e)}',
                'user_message': 'Unable to read the uploaded file.',
                'category': 'File System Error'
            }
    
    def validate_glb_header(self, file_path: str) -> Dict[str, Any]:
        """
        Memory-efficient GLB header validation.
        Reads only the first 12 bytes to validate the GLB magic number and version.
        """
        try:
            path = Path(file_path)
            
            if not path.exists():
                return {
                    'success': False,
                    'error': 'File does not exist',
                    'user_message': 'The uploaded file could not be found.'
                }
            
            file_size = path.stat().st_size
            
            if file_size < self.constants.HEADER_LENGTH:
                return {
                    'success': False,
                    'error': f'File too small for GLB header: {file_size} bytes',
                    'user_message': 'The file is too small to be a valid GLB file.'
                }
            
            with open(file_path, 'rb') as f:
                header = f.read(self.constants.HEADER_LENGTH)
            
            if len(header) < self.constants.HEADER_LENGTH:
                return {
                    'success': False,
                    'error': 'Could not read GLB header',
                    'user_message': 'The file appears to be corrupted.'
                }
            
            magic = header[0:4]
            if magic != self.constants.MAGIC_NUMBER:
                return {
                    'success': False,
                    'error': f'Invalid GLB magic number: {magic}',
                    'user_message': 'This file is not a valid GLB file.'
                }
            
            version = struct.unpack('<I', header[4:8])[0]
            if version != self.constants.SUPPORTED_VERSION:
                return {
                    'success': False,
                    'error': f'Unsupported GLB version: {version}',
                    'user_message': f'GLB version {version} is not supported. Only version 2 is supported.'
                }
            
            reported_length = struct.unpack('<I', header[8:12])[0]
            if reported_length != file_size:
                logger.warning(f'GLB length mismatch: header says {reported_length}, file is {file_size}')
            
            return {
                'success': True,
                'version': version,
                'reported_length': reported_length,
                'actual_length': file_size
            }
            
        except Exception as e:
            logger.error(f'GLB header validation failed: {e}')
            return {
                'success': False,
                'error': str(e),
                'user_message': 'Failed to validate GLB file format.'
            }
    
    def validate_glb_chunks(self, file_path: str) -> Dict[str, Any]:
        """
        Validate GLB chunk structure.
        Reads chunk headers to verify the file structure without loading full content.
        """
        try:
            path = Path(file_path)
            file_size = path.stat().st_size
            
            if file_size < self.constants.MIN_FILE_WITH_CHUNK:
                return {
                    'success': False,
                    'error': 'File too small for GLB chunks',
                    'user_message': 'The file is too small to contain valid GLB data.'
                }
            
            with open(file_path, 'rb') as f:
                f.seek(self.constants.HEADER_LENGTH)
                
                chunk_header = f.read(self.constants.CHUNK_HEADER_LENGTH)
                if len(chunk_header) < self.constants.CHUNK_HEADER_LENGTH:
                    return {
                        'success': False,
                        'error': 'Could not read first chunk header',
                        'user_message': 'The GLB file appears to be corrupted.'
                    }
                
                chunk_length = struct.unpack('<I', chunk_header[0:4])[0]
                chunk_type = chunk_header[4:8]
                
                if chunk_type != self.constants.JSON_CHUNK_TYPE:
                    return {
                        'success': False,
                        'error': f'First chunk is not JSON: {chunk_type}',
                        'user_message': 'The GLB file structure is invalid.'
                    }
                
                return {
                    'success': True,
                    'json_chunk_length': chunk_length,
                    'has_binary_chunk': file_size > self.constants.HEADER_LENGTH + self.constants.CHUNK_HEADER_LENGTH + chunk_length
                }
                
        except Exception as e:
            logger.error(f'GLB chunk validation failed: {e}')
            return {
                'success': False,
                'error': str(e),
                'user_message': 'Failed to validate GLB file structure.'
            }
    
    def validate(self, file_path: str, full_validation: bool = True) -> Dict[str, Any]:
        """
        Perform complete GLB validation.
        
        Args:
            file_path: Path to the GLB file
            full_validation: If True, validates chunks; otherwise only header
        """
        size_result = self.validate_file_size(file_path)
        if not size_result['success']:
            return size_result
        
        header_result = self.validate_glb_header(file_path)
        if not header_result['success']:
            return header_result
        
        if full_validation:
            chunk_result = self.validate_glb_chunks(file_path)
            if not chunk_result['success']:
                return chunk_result
            
            return {
                'success': True,
                'file_size': size_result['file_size'],
                'version': header_result['version'],
                'json_chunk_length': chunk_result.get('json_chunk_length'),
                'has_binary_chunk': chunk_result.get('has_binary_chunk')
            }
        
        return {
            'success': True,
            'file_size': size_result['file_size'],
            'version': header_result['version']
        }


def validate_glb(file_path: str, full_validation: bool = True) -> Dict[str, Any]:
    """Convenience function for GLB validation"""
    validator = GLBValidator()
    return validator.validate(file_path, full_validation)
