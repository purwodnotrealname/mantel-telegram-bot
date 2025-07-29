# bot_handlers.py - Telegram bot command handlers

import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import *
from monitor import monitor_interfaces, start_monitoring, stop_monitoring, is_monitoring_active
from snmp_manager import get_simplified_interface_name

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE, snmp_manager) -> None:
    """Handle /start command"""
    user_chat_id = update.effective_chat.id
    
    # Start monitoring
    success = start_monitoring(user_chat_id, snmp_manager)
    
    if success:
        welcome_message = (
            "Interface monitoring started!\n\n"
            "Commands:\n"
            "/start - Start monitoring\n"
            "/stop - Stop monitoring\n"
            "/status - Display interface table\n\n"
            f"Monitoring router: {ROUTER_IP}\n"
            f"Check interval: {MONITOR_INTERVAL} seconds\n\n"
        )
        
        await update.message.reply_text(welcome_message)
        
        # Start monitoring task if not already running
        if not hasattr(context.application, 'monitoring_task') or context.application.monitoring_task.done():
            context.application.monitoring_task = asyncio.create_task(
                monitor_interfaces(context.application, snmp_manager)
            )
    else:
        error_message = (
            f"Failed to connect to router {ROUTER_IP}\n"
            "Please check:\n"
            "- Router IP address\n"
            "- SNMP community string\n"
            "- Network connectivity"
        )
        await update.message.reply_text(error_message)

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stop command"""
    if is_monitoring_active():
        stop_monitoring()
        stop_message = (
            "Interface monitoring stopped!\n\n"
            f"Router: {ROUTER_IP}\n"
            "Use /start to resume monitoring."
        )
        await update.message.reply_text(stop_message)
        logger.info("Monitoring stopped by user command")
    else:
        await update.message.reply_text(
            "Monitoring is not currently active.\n"
            "Use /start to begin monitoring."
        )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE, snmp_manager) -> None:
    """Handle /status command"""
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
                interface_name = get_simplified_interface_name(interface['name'])
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
        
        # Split message if too long (Telegram 4096 character limit)
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
    """Handle unknown commands"""
    await update.message.reply_text(
        "Unknown command found.\n\n"
        "Available commands:\n"
        "/start - Start monitoring\n"
        "/stop - Stop monitoring\n"
        "/status - Display interface table"
    )