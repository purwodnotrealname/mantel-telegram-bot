# bot_handlers.py - Telegram bot command handlers with widget buttons

import asyncio
import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import *
from monitor import monitor_interfaces, start_monitoring, stop_monitoring, is_monitoring_active, get_current_router_ip
from snmp_manager import get_simplified_interface_name, CiscoSNMPManager

logger = logging.getLogger(__name__)

def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("Start Monitoring", callback_data="start_monitoring")],
        [InlineKeyboardButton("Stop Monitoring", callback_data="stop_monitoring")],
        [InlineKeyboardButton("Interface Status", callback_data="show_status")],
        [InlineKeyboardButton("Set Router IP", callback_data="set_router_ip")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE, snmp_manager=None) -> None:
    if not snmp_manager.host:
        await update.message.reply_text(
            "No router IP set. Please use the 'Set Router IP' button to configure the router IP.",
            reply_markup=get_main_menu_keyboard()
        )
        return

    welcome_message = (
        "Cisco SNMP Interface Monitor Bot\n\n"
        f"Router: {snmp_manager.host}\n"
        f"Check interval: {MONITOR_INTERVAL} seconds\n\n"
        "Choose an option:"
    )
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=get_main_menu_keyboard()
    )

async def handle_start_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE, snmp_manager) -> None:
    query = update.callback_query
    await query.answer()
    
    user_chat_id = update.effective_chat.id
    
    if not snmp_manager.host:
        await query.edit_message_text(
            "No router IP set. Please use the 'Set Router IP' button to configure the router IP.",
            reply_markup=get_main_menu_keyboard()
        )
        return

    # Start monitoring
    success = start_monitoring(user_chat_id, snmp_manager)
    
    if success:
        success_message = (
            "Interface monitoring started!\n\n"
            f"Monitoring router: {snmp_manager.host}\n"
            f"Check interval: {MONITOR_INTERVAL} seconds\n"
        )
        
        await query.edit_message_text(
            success_message,
            reply_markup=get_main_menu_keyboard()
        )
        
        # Start monitoring task if not already running
        if not hasattr(context.application, 'monitoring_task') or context.application.monitoring_task.done():
            context.application.monitoring_task = asyncio.create_task(
                monitor_interfaces(context.application, snmp_manager)
            )
    else:
        error_message = (
            f"Failed to connect to router {snmp_manager.host}\n\n"
            "Please check:\n"
            "• Router IP address\n"
            "• SNMP community string\n"
            "• Network connectivity"
        )
        await query.edit_message_text(
            error_message,
            reply_markup=get_main_menu_keyboard()
        )

async def handle_stop_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    if is_monitoring_active():
        stop_monitoring()
        stop_message = (
            "Interface monitoring stopped!\n\n"
            f"Router: {get_current_router_ip()}\n"
        )
        await query.edit_message_text(
            stop_message,
            reply_markup=get_main_menu_keyboard()
        )
        logger.info("Monitoring stopped by user button")
    else:
        await query.edit_message_text(
            "Monitoring is not currently active.",
            reply_markup=get_main_menu_keyboard()
        )

async def handle_set_router_ip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    if is_monitoring_active():
        await query.edit_message_text(
            "Monitoring is active. Please stop monitoring before setting a new router IP.",
            reply_markup=get_main_menu_keyboard()
        )
        return

    await query.edit_message_text(
        "Enter the new router IP address:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="cancel_set_ip")]])
    )
    context.user_data['awaiting_ip'] = True

async def handle_cancel_set_ip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    context.user_data.pop('awaiting_ip', None)
    await query.edit_message_text(
        "IP setting cancelled.",
        reply_markup=get_main_menu_keyboard()
    )

async def handle_show_status(update: Update, context: ContextTypes.DEFAULT_TYPE, snmp_manager) -> None:
    query = update.callback_query
    await query.answer()
    
    if not snmp_manager.host:
        await query.edit_message_text(
            "No router IP set. Please use the 'Set Router IP' button to configure the router IP.",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Show processing message
    await query.edit_message_text("Querying router interfaces...")
    
    try:
        # Get interface data
        success, data = snmp_manager.get_interface_data()
        
        if success and data:
            # Format the response as a table
            response_lines = [
                f"Router Interface Status - {snmp_manager.host}",
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
                f"No interface data found on router {snmp_manager.host}\n\n"
            )
        else:
            response_message = (
                f"Failed to query router at {snmp_manager.host}\n"
                f"Error: {data}\n\n"
            )
        
        # Split message if too long (Telegram 4096 character limit)
        if len(response_message) > 4096: 
            chunks = [response_message[i:i+4096] for i in range(0, len(response_message), 4096)]
            for i, chunk in enumerate(chunks):
                if i == len(chunks) - 1:  # Last chunk gets the keyboard
                    await query.edit_message_text(
                        f"```\n{chunk}\n```",
                        parse_mode='Markdown',
                        reply_markup=get_main_menu_keyboard()
                    )
                else:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"```\n{chunk}\n```",
                        parse_mode='Markdown'
                    )
        else:
            await query.edit_message_text(
                f"```\n{response_message}\n```",
                parse_mode='Markdown',
                reply_markup=get_main_menu_keyboard()
            )
        
    except Exception as e:
        error_message = f"Bot Error: {str(e)}"
        logger.error(error_message)
        await query.edit_message_text(
            error_message,
            reply_markup=get_main_menu_keyboard()
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE, snmp_manager) -> None:
    if context.user_data.get('awaiting_ip'):
        ip_input = update.message.text.strip()
        ip_pattern = re.compile(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")
        
        if not ip_pattern.match(ip_input):
            await update.message.reply_text(
                "Invalid IP address format. Please enter a valid IP (e.g., 192.168.1.1):",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="cancel_set_ip")]])
            )
            return
        
        # Update ROUTER_IP in config and snmp_manager
        global ROUTER_IP
        ROUTER_IP = ip_input
        snmp_manager.host = ip_input
        
        context.user_data.pop('awaiting_ip', None)
        await update.message.reply_text(
            f"Router IP set to {ip_input} successfully!",
            reply_markup=get_main_menu_keyboard()
        )
        logger.info(f"Router IP set to {ip_input} by user")

# Keep these for backward compatibility with /commands
async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if is_monitoring_active():
        stop_monitoring()
        stop_message = (
            "Interface monitoring stopped!\n\n"
            f"Router: {get_current_router_ip()}\n"
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
    if not snmp_manager.host:
        await update.message.reply_text(
            "No router IP set. Please use the 'Set Router IP' button to configure the router IP.",
            reply_markup=get_main_menu_keyboard()
        )
        return

    processing_msg = await update.message.reply_text("Querying router interfaces...")
    
    try:
        # Get interface data
        success, data = snmp_manager.get_interface_data()
        
        if success and data:
            # Format the response as a table
            response_lines = [
                f"Router Interface Status - {snmp_manager.host}",
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
                f"No interface data found on router {snmp_manager.host}\n\n"
            )
        else:
            response_message = (
                f"Failed to query router at {snmp_manager.host}\n"
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
    await update.message.reply_text(
        "Unknown command found.\n\n"
        "Available commands:\n"
        "/start - Start monitoring\n"
        "/stop - Stop monitoring\n"
        "/status - Display interface table\n"
        "/set - Set router IP address"
    )