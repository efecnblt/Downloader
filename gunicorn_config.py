import multiprocessing

# Sunucu ayarları
bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gevent"
timeout = 300  # 5 dakika
keepalive = 5

# Logging ayarları
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "info"

# SSL sertifika ayarları (HTTPS için)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# Diğer ayarlar
daemon = False
reload = True
preload_app = True 