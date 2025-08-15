# config.py - Configuration settings

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = "8162377906:AAFkOvczwU6u_rpO9xiZc9D4mjEomdBokSQ"

# Router Configuration
SNMP_COMMUNITY = "community1"
SNMP_PORT = 161

# SNMP OIDs
INTERFACE_NAME_OID = "1.3.6.1.2.1.2.2.1.2"      # ifDescr - Interface description
INTERFACE_STATUS_OID = "1.3.6.1.2.1.2.2.1.8"    # ifOperStatus - Interface operational status
INTERFACE_IP_OID = "1.3.6.1.2.1.4.20.1.1"       # ipAdEntAddr - IP addresses
INTERFACE_IP_INDEX_OID = "1.3.6.1.2.1.4.20.1.2"  # ipAdEntIfIndex - Interface index for IP

# Monitoring Configuration
MONITOR_INTERVAL = 1

# Logging Configuration
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = 'INFO'