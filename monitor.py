import asyncio
import logging
from config import *
from snmp_manager import get_simplified_interface_name

logger = logging.getLogger(__name__)

monitoring_active = False
chat_id = None
interface_status_cache = {}
current_snmp_manager = None
last_monitoring_message_id = None  # Track the last monitoring message

async def monitor_interfaces(application, snmp_manager):
    global monitoring_active, chat_id, interface_status_cache, current_snmp_manager, last_monitoring_message_id
    
    monitoring_active = True
    current_snmp_manager = snmp_manager
    logger.info(f"Interface monitoring started for router {snmp_manager.host}")
    
    while monitoring_active:
        try:
            if not snmp_manager.host:
                logger.error("No router IP set in SNMP manager")
                await asyncio.sleep(1)
                continue

            success, current_status = snmp_manager.get_interface_status_only()
            
            if success:
                down_interfaces = []
                status_changes = []
                
                # Check each interface
                for index, interface_info in current_status.items():
                    interface_name = get_simplified_interface_name(interface_info['name'])
                    current_status_val = interface_info['status']
                    
                    if current_status_val == "down":
                        down_interfaces.append(interface_name)
                    
                    # Compare with cache
                    if index in interface_status_cache:
                        prev_status = interface_status_cache[index]['status']
                        if prev_status != current_status_val:
                            if prev_status == "up" and current_status_val == "down":
                                status_changes.append(f"Interface {interface_name} went DOWN")
                            elif prev_status == "down" and current_status_val == "up":
                                status_changes.append(f"Interface {interface_name} came UP")
                    
                    # Update cache
                    interface_status_cache[index] = interface_info

                print_down_interfaces_to_console(down_interfaces, snmp_manager.host)

                if chat_id:
                    if status_changes:  
                        alert_message = (
                            "ALERT INTERFACE STATUS CHANGE!\n\n" +
                            "\n".join(status_changes) +
                            f"\n\nRouter: {snmp_manager.host}\n\n" +
                            f"Currently DOWN: {', '.join(down_interfaces) if down_interfaces else 'None'}"
                        )
                        try:
                            sent = await application.bot.send_message(chat_id=chat_id, text=alert_message)
                            last_monitoring_message_id = sent.message_id
                            logger.info(f"Alert sent: {', '.join(status_changes)}")  
                             #append with status_changes
                        except Exception as e:
                            logger.error(f"Failed to send alert: {e}")
                    
                    elif last_monitoring_message_id is None:  
                        initial_message = (
                            f"Monitoring started for router {snmp_manager.host}\n\n"
                            f"Currently DOWN: {', '.join(down_interfaces) if down_interfaces else 'None'}"
                            f"```"
                        )
                        try:
                            sent = await application.bot.send_message(chat_id=chat_id, text=initial_message, parse_mode="Markdown")
                            
                            last_monitoring_message_id = sent.message_id
                            
                            logger.info("Initial monitoring message sent")
                        except Exception as e:
                            logger.error(f"Failed to send initial message: {e}")
                            

            else:
                logger.error(f"Failed to get interface status from {snmp_manager.host}")

        except Exception as e:
            logger.error(f"Monitor error: {e}")
        
        # Poll every second
        await asyncio.sleep(1)



def print_down_interfaces_to_console(down_interfaces, router_ip):
    if not router_ip:
        print("\nNO ROUTER IP SET")
        return

    if down_interfaces:
        print(f"\nDOWN INTERFACES CHECK ({router_ip}) ---")
        for interface in down_interfaces:
            print(f"DOWN: {interface}")
        print(f"Total: {len(down_interfaces)}")
        print(f"---" + "-" * 45)
    else:
        print(f"```\n--- All interfaces UP on {router_ip} ---")



def start_monitoring(user_chat_id, snmp_manager):
    global monitoring_active, chat_id, interface_status_cache, current_snmp_manager, last_monitoring_message_id
    
    chat_id = user_chat_id
    monitoring_active = True
    current_snmp_manager = snmp_manager
    last_monitoring_message_id = None 
    

    success, status_data = snmp_manager.get_interface_status_only()
    if success:
        interface_status_cache = status_data
        logger.info(f"Monitoring started for {len(status_data)} interfaces on {snmp_manager.host}")
    else:
        logger.error(f"Failed to initialize monitoring for router {snmp_manager.host}")
    
    return success

def stop_monitoring():
    global monitoring_active, current_snmp_manager, last_monitoring_message_id
    monitoring_active = False
    last_monitoring_message_id = None  # Reset message tracking
    if current_snmp_manager:
        logger.info(f"Monitoring stopped for router {current_snmp_manager.host}")
    else:
        logger.info("Monitoring stopped")

def is_monitoring_active():
    return monitoring_active

def get_current_router_ip():
    global current_snmp_manager
    return current_snmp_manager.host if current_snmp_manager else "Not set"