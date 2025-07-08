"""
Test suite to verify that there are no duplicate function definitions
and that all key functions are properly accessible.
"""

import pytest
import inspect
from optimizer import (
    run_gltfpack_geometry_parallel, 
    run_draco_compression_parallel, 
    run_gltf_transform_optimize_parallel,
    GLBOptimizer
)


class TestFunctionUniqueness:
    """Test that functions are defined only once and are accessible"""
    
    def test_parallel_functions_exist(self):
        """Test that parallel processing functions exist and are callable"""
        assert run_gltfpack_geometry_parallel is not None
        assert run_draco_compression_parallel is not None
        assert run_gltf_transform_optimize_parallel is not None
        
        # Verify they are callable
        assert callable(run_gltfpack_geometry_parallel)
        assert callable(run_draco_compression_parallel)
        assert callable(run_gltf_transform_optimize_parallel)
    
    def test_parallel_functions_signatures(self):
        """Test that parallel functions have correct signatures"""
        # All should take input_path and output_path parameters
        sig_gltfpack = inspect.signature(run_gltfpack_geometry_parallel)
        sig_draco = inspect.signature(run_draco_compression_parallel)
        sig_gltf_transform = inspect.signature(run_gltf_transform_optimize_parallel)
        
        # Check parameter names
        assert list(sig_gltfpack.parameters.keys()) == ['input_path', 'output_path']
        assert list(sig_draco.parameters.keys()) == ['input_path', 'output_path']
        assert list(sig_gltf_transform.parameters.keys()) == ['input_path', 'output_path']
    
    def test_select_compression_methods_exists(self):
        """Test that _select_compression_methods is accessible on GLBOptimizer"""
        optimizer = GLBOptimizer('high')
        assert hasattr(optimizer, '_select_compression_methods')
        assert callable(optimizer._select_compression_methods)
    
    def test_select_compression_methods_signature(self):
        """Test that _select_compression_methods has correct signature"""
        optimizer = GLBOptimizer('high')
        sig = inspect.signature(optimizer._select_compression_methods)
        
        # Should take 'analysis' parameter
        assert list(sig.parameters.keys()) == ['analysis']
    
    def test_no_duplicate_function_names_in_module(self):
        """Test that there are no duplicate function names in the optimizer module"""
        import optimizer
        import ast
        
        # Read the source code
        with open('optimizer.py', 'r') as f:
            source = f.read()
        
        # Parse AST to find all function definitions
        tree = ast.parse(source)
        function_names = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                function_names.append((node.name, node.lineno))
        
        # Count occurrences of each function name
        from collections import Counter
        name_counts = Counter([name for name, _ in function_names])
        
        # Assert no duplicates
        duplicates = {name: count for name, count in name_counts.items() if count > 1}
        assert len(duplicates) == 0, f"Found duplicate function definitions: {duplicates}"
    
    def test_parallel_functions_are_top_level(self):
        """Test that parallel functions are defined at module level, not inside classes"""
        import optimizer
        import ast
        
        # Read the source code
        with open('optimizer.py', 'r') as f:
            source = f.read()
        
        # Parse AST to find function definitions and their context
        tree = ast.parse(source)
        
        target_functions = {
            'run_gltfpack_geometry_parallel',
            'run_draco_compression_parallel', 
            'run_gltf_transform_optimize_parallel'
        }
        
        # Find all top-level function definitions
        top_level_functions = set()
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                top_level_functions.add(node.name)
        
        # Assert all target functions are at top level
        for func_name in target_functions:
            assert func_name in top_level_functions, f"Function {func_name} is not defined at top level"
    
    def test_function_docstrings_exist(self):
        """Test that all key functions have docstrings"""
        # Check parallel functions
        assert run_gltfpack_geometry_parallel.__doc__ is not None
        assert run_draco_compression_parallel.__doc__ is not None
        assert run_gltf_transform_optimize_parallel.__doc__ is not None
        
        # Check method on GLBOptimizer
        optimizer = GLBOptimizer('high')
        assert optimizer._select_compression_methods.__doc__ is not None
        
        # Verify docstrings are meaningful (not empty)
        assert len(run_gltfpack_geometry_parallel.__doc__.strip()) > 0
        assert len(run_draco_compression_parallel.__doc__.strip()) > 0
        assert len(run_gltf_transform_optimize_parallel.__doc__.strip()) > 0
        assert len(optimizer._select_compression_methods.__doc__.strip()) > 0
    
    def test_parallel_functions_use_secure_subprocess(self):
        """Test that parallel functions use secure subprocess wrapper"""
        import optimizer
        import ast
        
        # Read the source code
        with open('optimizer.py', 'r') as f:
            source = f.read()
        
        # Parse AST to analyze function implementations
        tree = ast.parse(source)
        
        target_functions = {
            'run_gltfpack_geometry_parallel',
            'run_draco_compression_parallel', 
            'run_gltf_transform_optimize_parallel'
        }
        
        # Find function definitions and check they use GLBOptimizer for security
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in target_functions:
                # Convert AST back to source to check for security patterns
                func_source = ast.unparse(node)
                
                # Should use GLBOptimizer context manager for security
                assert 'GLBOptimizer' in func_source, f"Function {node.name} should use GLBOptimizer for security"
                assert 'with' in func_source, f"Function {node.name} should use context manager pattern"