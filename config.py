import os 
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
SNMP_COMMUNITY: str = os.getenv('snmp_community', '')
SNMP_PORT: int = os.getenv('SNMP_PORT', '')

# SNMP OIDs
INTERFACE_NAME_OID = "1.3.6.1.2.1.2.2.1.2"      # ifDescr - Interface description
INTERFACE_STATUS_OID = "1.3.6.1.2.1.2.2.1.8"    # ifOperStatus - Interface operational status
INTERFACE_IP_OID = "1.3.6.1.2.1.4.20.1.2"       # ipAdEntAddr - IP addresses
INTERFACE_IP_INDEX_OID = "1.3.6.1.2.1.4.20.1.2"  # ipAdEntIfIndex - Interface index for IP
SYSUPTIME = "1.3.6.1.2.1.1.3.0"

LOG_FORMAT: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
