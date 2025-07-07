# Production Deployment Guide for GLB Optimizer

## Pre-Deployment Security Checklist

### 1. Run Security Audit
```bash
python security_audit.py
```
Ensure all critical issues are resolved before deployment.

### 2. Environment Configuration
```bash
# Copy production environment template
cp .env.production.example .env

# Generate strong secret key (64+ characters)
python -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits + '!@#$%^&*') for _ in range(64)))"

# Update .env with generated secret and your settings
nano .env
```

### 3. Dependency Security
```bash
# Install and run security scanners
pip install pip-audit
pip-audit

# Update Node.js dependencies
npm audit fix
```

## Production Deployment Steps

### 1. Server Setup
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y nginx redis-server python3-pip nodejs npm

# Create application user
sudo useradd -m -s /bin/bash glb-optimizer
sudo usermod -aG www-data glb-optimizer
```

### 2. Application Installation
```bash
# Clone and setup application
sudo -u glb-optimizer git clone <repository> /opt/glb-optimizer
cd /opt/glb-optimizer

# Install Python dependencies
sudo -u glb-optimizer pip install -r requirements.txt

# Install Node.js dependencies
sudo -u glb-optimizer npm install
```

### 3. File Permissions Setup
```bash
# Set secure permissions
sudo chmod 750 /opt/glb-optimizer
sudo chmod 640 /opt/glb-optimizer/.env
sudo chmod 644 /opt/glb-optimizer/static/*

# Create and secure upload directories
sudo mkdir -p /opt/glb-optimizer/{uploads,output}
sudo chown glb-optimizer:www-data /opt/glb-optimizer/{uploads,output}
sudo chmod 750 /opt/glb-optimizer/{uploads,output}

# Create log directory
sudo mkdir -p /var/log/glb-optimizer
sudo chown glb-optimizer:www-data /var/log/glb-optimizer
sudo chmod 755 /var/log/glb-optimizer
```

### 4. Redis Configuration
```bash
# Secure Redis configuration
sudo nano /etc/redis/redis.conf

# Add these security settings:
# bind 127.0.0.1
# requirepass YOUR_REDIS_PASSWORD
# maxmemory 256mb
# maxmemory-policy allkeys-lru

sudo systemctl restart redis-server
sudo systemctl enable redis-server
```

### 5. Nginx Configuration
```bash
# Copy configuration
sudo cp nginx.conf.example /etc/nginx/sites-available/glb-optimizer

# Update domain and SSL certificate paths
sudo nano /etc/nginx/sites-available/glb-optimizer

# Enable site
sudo ln -s /etc/nginx/sites-available/glb-optimizer /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 6. SSL/TLS Setup
```bash
# Install Certbot for Let's Encrypt
sudo apt install certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com

# Test automatic renewal
sudo certbot renew --dry-run
```

### 7. Systemd Service Setup
```bash
# Create systemd service files
sudo tee /etc/systemd/system/glb-optimizer.service << EOF
[Unit]
Description=GLB Optimizer Web Application
After=network.target redis.service

[Service]
Type=notify
User=glb-optimizer
Group=www-data
WorkingDirectory=/opt/glb-optimizer
Environment=PATH=/opt/glb-optimizer/.venv/bin
ExecStart=/opt/glb-optimizer/.venv/bin/gunicorn -c gunicorn.conf.py main:app
ExecReload=/bin/kill -s HUP \$MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Create Celery worker service
sudo tee /etc/systemd/system/glb-optimizer-worker.service << EOF
[Unit]
Description=GLB Optimizer Celery Worker
After=network.target redis.service

[Service]
Type=forking
User=glb-optimizer
Group=www-data
WorkingDirectory=/opt/glb-optimizer
Environment=PATH=/opt/glb-optimizer/.venv/bin
ExecStart=/opt/glb-optimizer/.venv/bin/celery -A celery_app worker --loglevel=info --detach
ExecStop=/opt/glb-optimizer/.venv/bin/celery -A celery_app control shutdown
ExecReload=/opt/glb-optimizer/.venv/bin/celery -A celery_app control reload

[Install]
WantedBy=multi-user.target
EOF

# Create Celery beat service for cleanup
sudo tee /etc/systemd/system/glb-optimizer-beat.service << EOF
[Unit]
Description=GLB Optimizer Celery Beat Scheduler
After=network.target redis.service

[Service]
Type=simple
User=glb-optimizer
Group=www-data
WorkingDirectory=/opt/glb-optimizer
Environment=PATH=/opt/glb-optimizer/.venv/bin
ExecStart=/opt/glb-optimizer/.venv/bin/celery -A celery_app beat --loglevel=info

[Install]
WantedBy=multi-user.target
EOF

# Enable and start services
sudo systemctl daemon-reload
sudo systemctl enable glb-optimizer glb-optimizer-worker glb-optimizer-beat
sudo systemctl start glb-optimizer glb-optimizer-worker glb-optimizer-beat
```

## Security Hardening

### 1. Firewall Configuration
```bash
# Configure UFW firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

### 2. Fail2Ban Setup
```bash
# Install fail2ban
sudo apt install fail2ban

# Create custom jail for nginx
sudo tee /etc/fail2ban/jail.d/nginx.local << EOF
[nginx-http-auth]
enabled = true

[nginx-limit-req]
enabled = true
logpath = /var/log/nginx/error.log
findtime = 600
bantime = 3600
maxretry = 10
EOF

sudo systemctl restart fail2ban
```

### 3. Log Rotation
```bash
# Setup log rotation
sudo tee /etc/logrotate.d/glb-optimizer << EOF
/var/log/glb-optimizer/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 glb-optimizer www-data
    postrotate
        systemctl reload glb-optimizer
    endscript
}
EOF
```

## Monitoring and Maintenance

### 1. Health Checks
```bash
# Application health
curl -f http://localhost:5000/ || echo "App down"

# Redis health
redis-cli ping

# Service status
sudo systemctl status glb-optimizer glb-optimizer-worker glb-optimizer-beat
```

### 2. Monitoring Scripts
Create `/opt/glb-optimizer/monitor.sh`:
```bash
#!/bin/bash
# Basic monitoring script

# Check disk space
df -h | awk '$5 >= 80 {print "Disk space warning: " $0}'

# Check service status
systemctl is-active --quiet glb-optimizer || echo "GLB Optimizer service is down"
systemctl is-active --quiet redis-server || echo "Redis service is down"

# Check log errors
grep -i error /var/log/glb-optimizer/error.log | tail -5
```

### 3. Backup Strategy
```bash
# Database backup (if using persistent storage)
# Application configuration backup
sudo tar -czf /backup/glb-optimizer-config-$(date +%Y%m%d).tar.gz /opt/glb-optimizer/.env /etc/nginx/sites-available/glb-optimizer

# Automated cleanup logs
find /var/log/glb-optimizer -name "*.log" -mtime +30 -delete
```

## Security Maintenance

### 1. Regular Updates
```bash
# Weekly security updates
sudo apt update && sudo apt upgrade -y

# Monthly dependency updates
cd /opt/glb-optimizer
pip-audit
npm audit
```

### 2. Certificate Renewal
```bash
# Certbot auto-renewal (setup in cron)
0 0,12 * * * /usr/bin/certbot renew --quiet
```

### 3. Security Monitoring
```bash
# Monitor failed login attempts
sudo grep "Failed password" /var/log/auth.log

# Check SSL configuration
sudo nginx -t
sudo ssl-test your-domain.com
```

## Troubleshooting

### Common Issues

1. **Service won't start**
   ```bash
   sudo journalctl -u glb-optimizer -f
   ```

2. **File permission errors**
   ```bash
   sudo chown -R glb-optimizer:www-data /opt/glb-optimizer
   ```

3. **Redis connection errors**
   ```bash
   redis-cli ping
   sudo systemctl status redis-server
   ```

4. **SSL certificate issues**
   ```bash
   sudo certbot certificates
   sudo nginx -t
   ```

### Emergency Procedures

1. **Disable file uploads**
   ```bash
   # Set MAX_FILE_SIZE_MB=0 in .env
   sudo systemctl restart glb-optimizer
   ```

2. **Scale down workers**
   ```bash
   sudo systemctl stop glb-optimizer-worker
   ```

3. **Emergency restart**
   ```bash
   sudo systemctl restart glb-optimizer glb-optimizer-worker redis-server nginx
   ```

## Performance Optimization

### 1. Gunicorn Tuning
- Adjust worker count based on CPU cores
- Monitor memory usage per worker
- Set appropriate timeout values

### 2. Redis Optimization
- Configure memory limits
- Enable persistence if needed
- Monitor key expiration

### 3. Nginx Caching
- Enable static file caching
- Configure gzip compression
- Set appropriate cache headers

This deployment guide ensures a secure, scalable, and maintainable production environment for the GLB Optimizer application.