# GLB Optimizer Security Documentation

## File Upload Security Implementation

### 1. File Extension Enforcement ✅
- **Strict validation**: Only `.glb` files are accepted
- **Case-insensitive checking**: `model.GLB` and `model.glb` both allowed
- **Double extension protection**: `file.glb.js` is blocked
- **Path traversal protection**: `../../etc/passwd` is blocked

### 2. File Content Validation ✅
- **Magic number verification**: Files must start with `glTF` binary header
- **Header validation**: First 4 bytes must be `0x676C5446` (glTF)
- **Prevents**: Malicious files disguised with .glb extension

### 3. File Size Limits ✅
- **Maximum size**: 100MB configurable via `MAX_FILE_SIZE_MB`
- **Early validation**: Size checked before file content processing
- **Memory protection**: Prevents DoS attacks via large file uploads

### 4. Upload Directory Security ✅
- **Separate directories**: `uploads/` and `output/` isolated from web root
- **No execution context**: Files stored outside static content directory
- **Secure naming**: Server-generated UUIDs prevent filename-based attacks

### 5. Path Validation ✅
- **Command injection protection**: Blocks `;`, `|`, `&`, `$`, `` ` `` characters
- **Directory traversal prevention**: `../` sequences are blocked
- **Whitelist approach**: Only approved directories allowed

## Production Deployment Security

### Web Server Configuration
Use the provided `nginx.conf.example` for production deployment:

```bash
# Copy example configuration
cp nginx.conf.example /etc/nginx/sites-available/glb-optimizer

# Block direct access to upload directories
location ~ ^/(uploads|output)/ {
    deny all;
    return 403;
}
```

### Environment Variables
Set these for production:

```bash
# Security
SESSION_SECRET=your-random-secret-key
MAX_FILE_SIZE_MB=100
SECURE_FILENAME_ENABLED=true

# File management
FILE_RETENTION_HOURS=24
CLEANUP_ENABLED=true

# Logging
LOG_LEVEL=INFO
LOG_TO_FILE=true
```

### File System Permissions
```bash
# Restrict upload directory permissions
chmod 750 uploads/ output/
chown app-user:app-group uploads/ output/

# Prevent script execution
mount -o noexec uploads/
mount -o noexec output/
```

## Security Testing

### Automated Tests
The application includes comprehensive security tests:

- **13 attack vectors tested**
- **Directory traversal attempts**: `../../../etc/passwd`
- **Command injection**: `;rm -rf /`, `&&cat /etc/passwd`
- **File type bypasses**: `.exe`, `.sh`, `.js` files
- **Path validation**: Absolute paths, system directories

### Manual Testing
```bash
# Test file upload restrictions
curl -X POST -F "file=@malicious.exe" http://localhost:5000/upload
# Expected: 400 error "Invalid file type"

# Test size limits  
curl -X POST -F "file=@large-file.glb" http://localhost:5000/upload
# Expected: 400 error "File too large"

# Test direct access to uploads
curl http://localhost:5000/uploads/file.glb
# Expected: 403 Forbidden (with proper Nginx config)
```

## Security Incident Response

### Log Monitoring
Monitor these log patterns for potential attacks:

```bash
# Path validation failures
grep "Path validation failed" logs/
grep "Security violation" logs/

# Upload attempts
grep "Upload error" logs/
grep "Invalid file type" logs/
```

### Emergency Response
If security breach suspected:

1. **Immediate**: Disable file uploads via environment variable
2. **Audit**: Review upload logs and file integrity
3. **Clean**: Run manual cleanup of suspicious files
4. **Update**: Patch vulnerabilities and restart services

## Compliance Notes

- **File quarantine**: Uploaded files are isolated from web-accessible areas
- **Content validation**: Binary header verification prevents disguised malicious files
- **Access logging**: All upload attempts are logged with details
- **Retention policy**: Automatic cleanup prevents indefinite file accumulation
- **Principle of least privilege**: Upload directories have minimal required permissions

## Security Checklist for Production

- [ ] Deploy with production Nginx configuration
- [ ] Set strong session secrets in environment variables
- [ ] Configure file system permissions correctly
- [ ] Enable automatic cleanup scheduling
- [ ] Set up log monitoring and alerting
- [ ] Test security measures with penetration testing
- [ ] Review and update dependencies regularly
- [ ] Implement backup and recovery procedures

## Contact

For security issues or questions:
- Review this documentation
- Check application logs
- Test with provided security validation tools