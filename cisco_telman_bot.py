import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pysnmp.hlapi import *

TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  
ROUTER_IP = "192.168.137.130"
SNMP_COMMUNITY = "public"  
SNMP_PORT = 161

# OID
INTERFACE_NAME_OID = "1.3.6.1.2.1.2.2.1.2"      # ifDescr - Interface description
INTERFACE_STATUS_OID = "1.3.6.1.2.1.2.2.1.8"    # ifOperStatus - Interface operational status
INTERFACE_IP_OID = "1.3.6.1.2.1.4.20.1.1"       # ipAdEntAddr - IP addresses
INTERFACE_IP_INDEX_OID = "1.3.6.1.2.1.4.20.1.2"  # ipAdEntIfIndex - Interface index for IP

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class CiscoSNMPManager:
    def __init__(self, host, community="public", port=161):
        self.host = host
        self.community = community
        self.port = port
    
    def snmp_walk(self, oid):
        results = {}
        try:
            for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
                SnmpEngine(),
                CommunityData(self.community),
                UdpTransportTarget((self.host, self.port)),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False,
                ignoreNonIncreasingOid=True,
                maxRows=50):
                
                if errorIndication:
                    logger.error(f"SNMP Walk Error: {errorIndication}")
                    break
                elif errorStatus:
                    logger.error(f"SNMP Walk Error: {errorStatus.prettyPrint()}")
                    break
                else:
                    for varBind in varBinds:
                        oid_key = str(varBind[0])
                        value = str(varBind[1])
                        # Extract interface index from OID
                        index = oid_key.split('.')[-1]
                        results[index] = value
                        
        except Exception as e:
            logger.error(f"SNMP Walk Exception: {str(e)}")
            return {}
        
        return results
    
    def snmp_walk_ip_addresses(self):
        results = {}
        try:
            for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
                SnmpEngine(),
                CommunityData(self.community),
                UdpTransportTarget((self.host, self.port)),
                ContextData(),
                ObjectType(ObjectIdentity(INTERFACE_IP_OID)),
                lexicographicMode=False,
                ignoreNonIncreasingOid=True,
                maxRows=50):
                
                if errorIndication:
                    logger.error(f"SNMP Walk Error: {errorIndication}")
                    break
                elif errorStatus:
                    logger.error(f"SNMP Walk Error: {errorStatus.prettyPrint()}")
                    break
                else:
                    for varBind in varBinds:
                        oid_key = str(varBind[0])
                        ip_address = str(varBind[1])
                        # For IP addresses, the IP is the value, not derived from OID
                        results[ip_address] = ip_address
                        
        except Exception as e:
            logger.error(f"SNMP Walk Exception: {str(e)}")
            return {}
        
        return results
    
    def snmp_walk_ip_to_interface(self):
        results = {}
        try:
            for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
                SnmpEngine(),
                CommunityData(self.community),
                UdpTransportTarget((self.host, self.port)),
                ContextData(),
                ObjectType(ObjectIdentity(INTERFACE_IP_INDEX_OID)),
                lexicographicMode=False,
                ignoreNonIncreasingOid=True,
                maxRows=50):
                
                if errorIndication:
                    logger.error(f"SNMP Walk Error: {errorIndication}")
                    break
                elif errorStatus:
                    logger.error(f"SNMP Walk Error: {errorStatus.prettyPrint()}")
                    break
                else:
                    for varBind in varBinds:
                        oid_key = str(varBind[0])
                        interface_index = str(varBind[1])
                        # Extract IP from OID
                        oid_parts = oid_key.split('.')
                        if len(oid_parts) >= 4:
                            ip_address = '.'.join(oid_parts[-4:])
                            results[ip_address] = interface_index
                        
        except Exception as e:
            logger.error(f"SNMP Walk Exception: {str(e)}")
            return {}
        
        return results
    
    def get_interface_data(self):
        """Get comprehensive interface information"""
        try:
            # Get interface names
            interface_names = self.snmp_walk(INTERFACE_NAME_OID)
            
            # Get interface status
            interface_status = self.snmp_walk(INTERFACE_STATUS_OID)
            
            # Get IP associated interface
            ip_to_interface = self.snmp_walk_ip_to_interface()
            
            # mapping interface index to IP
            interface_ips = {}
            for ip, interface_idx in ip_to_interface.items():
                if interface_idx in interface_ips:
                    interface_ips[interface_idx].append(ip)
                else:
                    interface_ips[interface_idx] = [ip]
            
            # Combine
            interfaces = []
            for index in interface_names.keys():
                interface_name = interface_names.get(index, f"Interface{index}")
                
                # Convert status number
                status_code = interface_status.get(index, "0")
                if status_code == "1":
                    status = "up"
                elif status_code == "2":
                    status = "down"
                elif status_code == "3":
                    status = "testing"
                else:
                    status = "unknown"
                
                # Get IP
                ips = interface_ips.get(index, ["No IP"])
                ip_str = ", ".join(ips) if ips != ["No IP"] else "No IP"
                
                # Filter out loopback
                if not interface_name.lower().startswith(('lo', 'null', 'voi')):
                    interfaces.append({
                        'name': interface_name,
                        'ip': ip_str,
                        'status': status,
                        'index': index
                    })
            
            return True, interfaces
            
        except Exception as e:
            logger.error(f"Error getting interface data: {str(e)}")
            return False, str(e)

# Initialize SNMP manager
snmp_manager = CiscoSNMPManager(ROUTER_IP, SNMP_COMMUNITY, SNMP_PORT)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    welcome_message = (
        "/start - start\n"
        "/status - Display interface table\n"
    )
    await update.message.reply_text(welcome_message)


async def get_router_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    processing_msg = await update.message.reply_text("Querying router interfaces...")
    
    try:
        # Get interface data
        success, data = snmp_manager.get_interface_data()
        
        if success and data:
            # Format the response as a table
            response_lines = [
                f"Router Interface Status - {ROUTER_IP}",
                "=" * 45,
                f"{'Interface':<12} | {'IP Address':<20} | {'Status':<8}"
            ]
            response_lines.append("-" * 45)
            
            # Add interface data
            for interface in data:
                interface_name = interface['name']
                # Simplifcation
                if interface_name.startswith('GigabitEthernet'):
                    interface_name = interface_name.replace('GigabitEthernet', 'Gi')
                elif interface_name.startswith('FastEthernet'):
                    interface_name = interface_name.replace('FastEthernet', 'Fa')
                elif interface_name.startswith('TenGigabitEthernet'):
                    interface_name = interface_name.replace('TenGigabitEthernet', 'Te')
                elif interface_name.startswith('Serial'):
                    interface_name = interface_name.replace('Serial', 'Se')
                elif interface_name.startswith('Ethernet'):
                    interface_name = interface_name.replace('Ethernet', 'Et')
                
                # Keep full IP address - no truncation
                ip_address = interface['ip']
                status = interface['status']
                
                response_lines.append(
                    f"{interface_name:<12} | {ip_address:<20} | {status:<8}"
                )
            
            response_message = "\n".join(response_lines)
            
        elif success and not data:
            response_message = (
                f"No interface data found on router {ROUTER_IP}\n\n"
            )
        else:
            response_message = (
                f"Failed to query router at {ROUTER_IP}\n"
                f"Error: {data}\n\n"
            )
        
        await processing_msg.delete()
        
        # Spliting telegram msg (4096 max lenght)
        if len(response_message) > 4096:
            chunks = [response_message[i:i+4096] for i in range(0, len(response_message), 4096)]
            for chunk in chunks:
                await update.message.reply_text(f"```\n{chunk}\n```", parse_mode='Markdown')
        else:
            await update.message.reply_text(f"```\n{response_message}\n```", parse_mode='Markdown')
        
    except Exception as e:
        await processing_msg.delete()
        error_message = f"Bot Error: {str(e)}"
        logger.error(error_message)
        await update.message.reply_text(error_message)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Unknown command found."
    )

def main() -> None:
    # Validation
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("ERROR: no token found")
        return
    
    # show target
    print(f"Starting Cisco SNMP Monitor Bot...")
    print(f"Target Router: {ROUTER_IP}")
    print(f"Monitoring Interface Information:")
    print(f"- Names: {INTERFACE_NAME_OID}")
    print(f"- Status: {INTERFACE_STATUS_OID}") 
    print(f"- IP Addresses: {INTERFACE_IP_OID}")
    print("Bot is starting... Press Ctrl+C to stop")
    
    # Create Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", get_router_status))
    
    # Run the bot
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Bot error: {e}")

if __name__ == '__main__':
    main()