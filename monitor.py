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
                print("ERROR: No router IP set")
                await send_monitoring_report(application, [], "Not set")
                await asyncio.sleep(MONITOR_INTERVAL)
                continue

            success, current_status = snmp_manager.get_interface_status_only()
            
            if success:
                down_interfaces = []
                status_changes = []
                
                # Check for status changes and collect all down interfaces
                for index, interface_info in current_status.items():
                    interface_name = interface_info['name']
                    current_status_val = interface_info['status']
                    
                    # Simplify interface name for display
                    display_name = get_simplified_interface_name(interface_name)
                    
                    # Collect all down interfaces
                    if current_status_val == "down":
                        down_interfaces.append(display_name)
                    
                    # Check if interface status changed
                    if index in interface_status_cache:
                        previous_status = interface_status_cache[index]['status']
                        
                        if previous_status == "up" and current_status_val == "down":
                            status_changes.append(f"Interface {display_name} went DOWN")
                        elif previous_status == "down" and current_status_val == "up":
                            status_changes.append(f"Interface {display_name} came UP")
                    
                    # Update cache
                    interface_status_cache[index] = interface_info
                
                # Send status change alerts (separate from monitoring report)
                if status_changes and chat_id:
                    try:
                        alert_message = (
                            "INTERFACE STATUS CHANGE!\n\n" + 
                            "\n".join(status_changes) + 
                            f"\n\nRouter: {snmp_manager.host}"
                        )
                        await application.bot.send_message(chat_id=chat_id, text=alert_message)
                        logger.info(f"Status change alert sent: {', '.join(status_changes)}")
                    except Exception as e:
                        logger.error(f"Failed to send status change alert: {e}")
                
                # Print all down interfaces to console
                print_down_interfaces_to_console(down_interfaces, snmp_manager.host)
                
                # Send/update monitoring report (delete previous message)
                await send_monitoring_report(application, down_interfaces, snmp_manager.host)
            else:
                logger.error(f"Failed to get interface status from {snmp_manager.host}")
                print(f"ERROR: Unable to connect to router {snmp_manager.host}")
                
                # Send error message and delete previous monitoring message
                if chat_id:
                    try:
                        # Delete previous monitoring message
                        if last_monitoring_message_id:
                            try:
                                await application.bot.delete_message(chat_id=chat_id, message_id=last_monitoring_message_id)
                            except Exception as delete_error:
                                logger.warning(f"Could not delete previous message: {delete_error}")
                        
                        # Send new error message
                        error_message = f"MONITORING ERROR\n\nUnable to connect to router {snmp_manager.host}"
                        sent_message = await application.bot.send_message(chat_id=chat_id, text=error_message)
                        last_monitoring_message_id = sent_message.message_id
                    except Exception as e:
                        logger.error(f"Failed to send error message: {e}")
                    
        except Exception as e:
            logger.error(f"Monitor error: {e}")
        
        # Wait before next check
        await asyncio.sleep(MONITOR_INTERVAL)

def print_down_interfaces_to_console(down_interfaces, router_ip):
    if not router_ip:
        print("\n--- NO ROUTER IP SET ---")
        return

    if down_interfaces:
        print(f"\n--- DOWN INTERFACES CHECK ({router_ip}) ---")
        for interface in down_interfaces:
            print(f"DOWN: {interface}")
        print(f"Total: {len(down_interfaces)}")
        print("---" + "-" * 45)
    else:
        print(f"\n--- All interfaces UP on {router_ip} ---")

async def send_monitoring_report(application, down_interfaces, router_ip):
    global chat_id, last_monitoring_message_id
    
    if chat_id:
        try:
            # Delete previous monitoring message if exists
            if last_monitoring_message_id:
                try:
                    await application.bot.delete_message(chat_id=chat_id, message_id=last_monitoring_message_id)
                    logger.debug("Previous monitoring message deleted")
                except Exception as delete_error:
                    logger.warning(f"Could not delete previous message: {delete_error}")
            
            # Create new monitoring report
            if not router_ip:
                monitoring_report = (
                    f"```\n"
                    f"MONITORING STATUS - NO ROUTER IP SET\n\n"
                    f"Please set a router IP using the 'Set Router IP' button.\n"
                    f"```"
                )
            elif down_interfaces:
                monitoring_report = (
                    f"```\n"
                    f"MONITORING STATUS - DOWN INTERFACES\n\n"
                    f"Router: {router_ip}\n\n"
                    f"Currently down interfaces:\n"
                )
                for interface in down_interfaces:
                    monitoring_report += f"{interface}\n"
                monitoring_report += f"\nTotal: {len(down_interfaces)} interfaces down\n"
                monitoring_report += f"```"
            else:
                monitoring_report = (
                    f"```\n"
                    f"MONITORING STATUS - ALL INTERFACES UP\n\n"
                    f"Router: {router_ip}\n\n"
                    f"Might be an error with system, i have not figured it yet\n"
                    f"```"
                    
                )
            
            # Send new monitoring message
            sent_message = await application.bot.send_message(
                chat_id=chat_id, 
                text=monitoring_report,
                parse_mode='Markdown'  # Enable markdown parsing for code blocks
            )
            last_monitoring_message_id = sent_message.message_id
            
            logger.info(f"Monitoring report updated: {len(down_interfaces)} interfaces down")
            
        except Exception as e:
            logger.error(f"Failed to send monitoring report: {e}")

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