# Nginx Configuration for YAAAF

This document provides nginx configuration for serving YAAAF with HTTPS support.

## Configuration File

Save this configuration to `/etc/nginx/sites-available/yaaaf`:

```nginx
# /etc/nginx/sites-available/yaaaf
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;

    # SSL Configuration
    ssl_certificate /path/to/your/certificate.pem;
    ssl_certificate_key /path/to/your/private-key.pem;
    
    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;

    # Proxy to YAAAF frontend
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # Proxy to YAAAF backend API
    location /api/ {
        proxy_pass http://127.0.0.1:4000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Enable streaming for chat API
        proxy_buffering off;
        proxy_cache off;
        
        # Timeouts for long-running requests
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 300s;
    }

    # Static assets caching
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
```

## Setup Instructions

### 1. Save the configuration
```bash
sudo nano /etc/nginx/sites-available/yaaaf
```

### 2. Update the configuration
- Replace `your-domain.com` with your actual domain
- Update SSL certificate paths
- Adjust ports if you're running YAAAF on different ports

### 3. Enable the site
```bash
sudo ln -s /etc/nginx/sites-available/yaaaf /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl reload nginx
```

### 4. Start YAAAF services
```bash
# Backend on port 4000
python -m yaaaf backend 4000

# Frontend on port 3000  
python -m yaaaf frontend 3000
```

## SSL Certificate Setup

### Option 1: Let's Encrypt (Recommended)
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

### Option 2: Self-signed certificates (Development only)
```bash
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/ssl/private/yaaaf.key \
    -out /etc/ssl/certs/yaaaf.crt \
    -subj "/C=US/ST=Dev/L=Dev/O=YAAAF/CN=your-domain.com"
```

Then update the SSL paths in the nginx config:
```nginx
ssl_certificate /etc/ssl/certs/yaaaf.crt;
ssl_certificate_key /etc/ssl/private/yaaaf.key;
```

## Features Provided

This configuration provides:
- **HTTPS termination** with modern SSL/TLS settings
- **HTTP to HTTPS redirect** for security
- **Proxy headers** for proper client information forwarding
- **Static asset caching** for improved performance
- **Security headers** (HSTS, XSS protection, etc.)
- **Gzip compression** for reduced bandwidth
- **WebSocket support** for real-time chat streaming
- **Separate routing** for frontend and backend APIs
- **Health check endpoint** for monitoring
- **Long timeout support** for AI processing requests

## Port Configuration

Default ports assumed:
- **Frontend**: `http://127.0.0.1:3000`
- **Backend**: `http://127.0.0.1:4000`
- **Nginx HTTPS**: `443`
- **Nginx HTTP**: `80` (redirects to HTTPS)

Modify the `proxy_pass` URLs if you're using different ports.

## Troubleshooting

### Check nginx status
```bash
sudo systemctl status nginx
sudo nginx -t
```

### Check nginx logs
```bash
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

### Test YAAAF connectivity
```bash
curl http://localhost:3000  # Frontend
curl http://localhost:4000  # Backend
```

### Firewall configuration
```bash
sudo ufw allow 'Nginx Full'
sudo ufw allow ssh
sudo ufw enable
```