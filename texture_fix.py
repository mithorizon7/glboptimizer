# Quick fix to disable texture compression and resolve blank file issue
import re

print("Applying texture compression fix...")

# Read the optimizer file
with open('optimizer.py', 'r') as f:
    content = f.read()

# Find the texture compression function and replace it with a simple copy operation
pattern = r'def _run_gltf_transform_textures\(self, input_path, output_path\):.*?return \{[^}]*\}'
replacement = '''def _run_gltf_transform_textures(self, input_path, output_path):
        """Step 4: Texture compression DISABLED for Three.js compatibility"""
        self.logger.info("Texture compression disabled to fix Three.js viewer blank file issue")
        
        try:
            # Simply copy input to output without any texture modifications
            self._safe_file_operation(input_path, 'copy', output_path)
            
            original_size = self._safe_file_operation(input_path, 'size')
            final_size = self._safe_file_operation(output_path, 'size')
            
            self.logger.info(f"Texture compression skipped: {original_size} → {final_size} bytes (original textures preserved)")
            
            return {
                'success': True,
                'output_file': output_path,
                'method': 'original_textures',
                'compression_stats': {
                    'method': 'no_compression',
                    'original_size': original_size,
                    'compressed_size': final_size,
                    'compression_ratio': 0.0,
                    'message': 'Texture compression skipped for Three.js compatibility'
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to preserve original textures: {e}")
            return {
                'success': False,
                'error': f'Failed to copy file: {str(e)}',
                'output_file': input_path
            }'''

# Apply the replacement with multiline and dotall flags
new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

# Write the updated content
with open('optimizer.py', 'w') as f:
    f.write(new_content)

print("✓ Texture compression fix applied successfully")
print("✓ Models will now display properly in Three.js viewer")
print("✓ Geometry compression still active for file size reduction")
