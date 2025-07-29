# monitor.py - Interface monitoring logic

import asyncio
import logging
from config import *
from snmp_manager import get_simplified_interface_name

logger = logging.getLogger(__name__)

# Global monitoring state
monitoring_active = False
chat_id = None
interface_status_cache = {}

async def monitor_interfaces(application, snmp_manager):
    """Background task to monitor interface status"""
    global monitoring_active, chat_id, interface_status_cache
    
    logger.info("Interface monitoring started")
    
    while monitoring_active:
        try:
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
                
                # Send status change alerts
                if status_changes and chat_id:
                    try:
                        alert_message = "INTERFACE STATUS CHANGE ALERT!\n\n" + "\n".join(status_changes) + f"\n\nRouter: {ROUTER_IP}"
                        await application.bot.send_message(chat_id=chat_id, text=alert_message)
                        logger.info(f"Status change alert sent: {', '.join(status_changes)}")
                    except Exception as e:
                        logger.error(f"Failed to send status change alert: {e}")
                
                # Print all down interfaces to console
                print_down_interfaces_to_console(down_interfaces)
                
                # Send periodic report of all down interfaces to Telegram
                await send_down_interfaces_report(application, down_interfaces)
                    
        except Exception as e:
            logger.error(f"Monitor error: {e}")
        
        # Wait before next check
        await asyncio.sleep(MONITOR_INTERVAL)

def print_down_interfaces_to_console(down_interfaces):
    """Print down interfaces to console"""
    if down_interfaces:
        print(f"\n--- DOWN INTERFACES CHECK ({ROUTER_IP}) ---")
        for interface in down_interfaces:
            print(f"DOWN: {interface}")
        print(f"Total down interfaces: {len(down_interfaces)}")
        print("---" + "-" * 45)
    else:
        print(f"\n--- All interfaces UP on {ROUTER_IP} ---")

async def send_down_interfaces_report(application, down_interfaces):
    """Send periodic report of down interfaces to Telegram"""
    global chat_id
    
    if down_interfaces and chat_id:
        try:
            down_report = f"DOWN INTERFACES REPORT\n\nRouter: {ROUTER_IP}\n\nCurrently down interfaces:\n"
            for interface in down_interfaces:
                down_report += f"- {interface}\n"
            down_report += f"\nTotal: {len(down_interfaces)} interfaces down"
            
            await application.bot.send_message(chat_id=chat_id, text=down_report)
            logger.info(f"Down interfaces report sent: {len(down_interfaces)} interfaces")
        except Exception as e:
            logger.error(f"Failed to send down interfaces report: {e}")

def start_monitoring(user_chat_id, snmp_manager):
    """Initialize monitoring with given chat ID"""
    global monitoring_active, chat_id, interface_status_cache
    
    chat_id = user_chat_id
    monitoring_active = True
    
    # Initialize interface status cache
    success, status_data = snmp_manager.get_interface_status_only()
    if success:
        interface_status_cache = status_data
    
    return success

def stop_monitoring():
    """Stop the monitoring process"""
    global monitoring_active
    monitoring_active = False
    logger.info("Monitoring stopped")

def is_monitoring_active():
    """Check if monitoring is currently active"""
    return monitoring_active