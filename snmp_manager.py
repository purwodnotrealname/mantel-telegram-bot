import logging
from pysnmp.hlapi import *
from config import *
from dotenv import load_dotenv

load_dotenv() 

logger = logging.getLogger(__name__)

class CiscoSNMPManager:
    def __init__(self, host=None, community=None , port=None):
        self.host = host
        self.community = community or os.getenv('SNMP_COMMUNITY', '')
        self.port = port or os.getenv('SNMP_PORT', '')
    
    def _check_host(self):
        if not self.host:
            logger.error("No router IP set. Please use the 'Set Router IP' button to configure the router IP.")
            return False
        return True
    
    def snmp_walk(self, oid):
        if not self._check_host():
            return {}
            
        results = {}
        try:
            for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
                SnmpEngine(),
                CommunityData(self.community),
                UdpTransportTarget((self.host, self.port)),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False,
                ignoreNonIncreasingOid=True):
                
                if errorIndication:
                    logger.error(f"SNMP Walk Error for {self.host}: {errorIndication}")
                    break
                elif errorStatus:
                    logger.error(f"SNMP Walk Error for {self.host}: {errorStatus.prettyPrint()}")
                    break
                else:
                    for varBind in varBinds:
                        oid_key = str(varBind[0])
                        value = str(varBind[1])
                        # Extract
                        index = oid_key.split('.')[-1]
                        results[index] = value
                        
        except Exception as e:
            logger.error(f"SNMP Walk Exception for {self.host}: {str(e)}")
            return {}
        
        return results
    
    def snmp_walk_ip_addresses(self):
        if not self._check_host():
            return {}
            
        results = {}
        try:
            for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
                SnmpEngine(),
                CommunityData(self.community),
                UdpTransportTarget((self.host, self.port)),
                ContextData(),
                ObjectType(ObjectIdentity(INTERFACE_IP_OID)),
                lexicographicMode=False,
                ignoreNonIncreasingOid=True):
                
                if errorIndication:
                    logger.error(f"SNMP Walk Error for {self.host}: {errorIndication}")
                    break
                elif errorStatus:
                    logger.error(f"SNMP Walk Error for {self.host}: {errorStatus.prettyPrint()}")
                    break
                else:
                    for varBind in varBinds:
                        oid_key = str(varBind[0])
                        ip_address = str(varBind[1])
                        results[ip_address] = ip_address
                        
        except Exception as e:
            logger.error(f"SNMP Walk Exception for {self.host}: {str(e)}")
            return {}
        
        return results
    

    def snmp_SYSUPTIME(self):
        if not self.host:
            return False, "Router IP not set"

        try:
            iterator = getCmd(
                SnmpEngine(),
                CommunityData(self.community, mpModel=0),
                UdpTransportTarget((self.host, self.port)),
                ContextData(),
                ObjectType(ObjectIdentity("1.3.6.1.2.1.1.3.0"))  # sysUpTime OID
            )

            errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

            if errorIndication:
                return False, f"SNMP error: {errorIndication}"
            elif errorStatus:
                return False, f"SNMP error: {errorStatus.prettyPrint()}"
            else:
                for varBind in varBinds:
                    return True, f"{varBind[1]}"  # uptime value as string

        except Exception as e:
            return False, f"Exception: {e}"

        # safety return in case none of the above runs
        return False, "Unknown error"

    
    def snmp_walk_ip_to_interface(self):
        if not self._check_host():
            return {}
            
        results = {}
        try:
            for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
                SnmpEngine(),
                CommunityData(self.community),
                UdpTransportTarget((self.host, self.port)),
                ContextData(),
                ObjectType(ObjectIdentity(INTERFACE_IP_INDEX_OID)),
                lexicographicMode=False,
                ignoreNonIncreasingOid=True):
                
                if errorIndication:
                    logger.error(f"SNMP Walk Error for {self.host}: {errorIndication}")
                    break
                elif errorStatus:
                    logger.error(f"SNMP Walk Error for {self.host}: {errorStatus.prettyPrint()}")
                    break
                else:
                    for varBind in varBinds:
                        oid_key = str(varBind[0])
                        interface_index = str(varBind[1])
                        # Extract IP from OID
                        ip_address = ".".join(oid_key.split(".")[-4:])
                        results[ip_address] = interface_index
                        
        except Exception as e:
            logger.error(f"SNMP Walk Exception for {self.host}: {str(e)}")
            return {}
        
        return results
    
    def get_interface_data(self):
        if not self._check_host():
            return False, "No router IP set. Please use the 'Set Router IP' button to configure the router IP."
            
        try:
            # names
            interface_names = self.snmp_walk(INTERFACE_NAME_OID)
            
            # status
            interface_status = self.snmp_walk(INTERFACE_STATUS_OID)
            
            # interface
            ip_to_interface = self.snmp_walk_ip_to_interface()
            
            # Mapping if index to IP
            interface_ips = {}
            for ip, interface_idx in ip_to_interface.items():
                if interface_idx in interface_ips:
                    interface_ips[interface_idx].append(ip)
                else:
                    interface_ips[interface_idx] = [ip]
            
            # Combine data
            interfaces = []
            for index in interface_names.keys():
                interface_name = interface_names.get(index, f"Interface{index}")
                
                #  Format status number
                status_code = interface_status.get(index, "0")
                if status_code == "1":
                    status = "up"
                elif status_code == "2":
                    status = "down"
                elif status_code == "3":
                    status = "testing"
                else:
                    status = "unknown"
                
                # Get IP addresses
                ips = interface_ips.get(index, ["No IP"])
                ip_str = ", ".join(ips) if ips != ["No IP"] else "No IP"
                
                # Filter out loopback and null interfaces
                if not interface_name.lower().startswith(('lo', 'null', 'voi')):
                    interfaces.append({
                        'name': interface_name,
                        'ip': ip_str,
                        'status': status,
                        'index': index
                    })
            
            return True, interfaces
            
        except Exception as e:
            logger.error(f"Error getting interface data for {self.host}: {str(e)}")
            return False, str(e)
    
    def get_interface_status_only(self):
        if not self._check_host():
            return False, {}
            
        try:
            interface_names = self.snmp_walk(INTERFACE_NAME_OID)
            interface_status = self.snmp_walk(INTERFACE_STATUS_OID)
            
            status_data = {}
            for index in interface_names.keys():
                interface_name = interface_names.get(index, f"Interface{index}")
                
                # Filter loopback and system interfaces
                if not interface_name.lower().startswith(('lo', 'null', 'voi')):
                    status_code = interface_status.get(index, "0")
                    if status_code == "1":
                        status = "up"
                    elif status_code == "2":
                        status = "down"
                    elif status_code == "3":
                        status = "testing"
                    else:
                        status = "unknown"
                    
                    status_data[index] = {
                        'name': interface_name,
                        'status': status
                    }

            return True, status_data
            
        except Exception as e:
            logger.error(f"Error getting interface status for {self.host}: {str(e)}")
            return False, {}

def get_simplified_interface_name(interface_name):
    if interface_name.startswith('GigabitEthernet'):
        return interface_name.replace('GigabitEthernet', 'Gi')
    elif interface_name.startswith('FastEthernet'):
        return interface_name.replace('FastEthernet', 'Fa')
    elif interface_name.startswith('TenGigabitEthernet'):
        return interface_name.replace('TenGigabitEthernet', 'Te')
    elif interface_name.startswith('Serial'):
        return interface_name.replace('Serial', 'Se')
    elif interface_name.startswith('Ethernet'):
        return interface_name.replace('Ethernet', 'Et')
    else:
        return interface_name