# dm_config.py
import os


DB_CONFIG = {
    'host': os.getenv('CAMPSIS_DB_HOST', 'localhost'),
    'port': int(os.getenv('CAMPSIS_DB_PORT', '3306')),
    'user': os.getenv('CAMPSIS_DB_USER', 'root'),
    'password': os.getenv('CAMPSIS_DB_PASSWORD', '123456'),
    'database': os.getenv('CAMPSIS_DB_NAME', 'ashare'),
    'charset': os.getenv('CAMPSIS_DB_CHARSET', 'utf8mb4')
}

if os.getenv('CAMPSIS_DB_UNIX_SOCKET'):
    DB_CONFIG['unix_socket'] = os.getenv('CAMPSIS_DB_UNIX_SOCKET')
