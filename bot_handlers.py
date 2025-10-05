import asyncio
import logging
import re
import html 
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
        [InlineKeyboardButton("Set IP Target", callback_data="set_router_ip")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE, snmp_manager=None) -> None:
    if not snmp_manager.host:
        await update.message.reply_text(
            "No router IP set. Please use the 'Set Router IP' button to configure the router IP.",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    if snmp_manager and snmp_manager.host:
        ok, uptime_text = snmp_manager.snmp_SYSUPTIME()
        if not ok:
            uptime_text = f"{uptime_text}"
        
    else:
        uptime_text = "No uptime available"

    welcome_message = (
        "Cisco SNMP Interface Monitor Bot\n\n"
        f"Router: {snmp_manager.host}\n"
        f"System Uptime: {uptime_text}\n"
        "Choose an option:"
        
    )
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=get_main_menu_keyboard()
    )


async def send_main_menu(context, chat_id: int, text: str = "Choose an option:"):
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
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

    # Start
    success = start_monitoring(user_chat_id, snmp_manager)
    
    if success:
        success_message = (
            "Interface monitoring started!\n\n"
            f"Monitoring router: {snmp_manager.host}\n"
        )
        
        await query.edit_message_text(
            success_message,
            reply_markup=get_main_menu_keyboard()
        )
        
        #Start
        if not hasattr(context.application, 'monitoring_task') or context.application.monitoring_task.done():
            context.application.monitoring_task = asyncio.create_task(
                monitor_interfaces(context.application, snmp_manager)
            )

        #splitting
        chunks = _split_by_lines_for_tg(success_message, max_len=3500)

        first_html = f"<pre>{html.escape(chunks[0])}</pre>"
        await query.edit_message_text(first_html, parse_mode='HTML')

        # Send remaining
        for chunk in chunks[1:]:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"<pre>{html.escape(chunk)}</pre>",
                parse_mode='HTML',
                disable_web_page_preview=True
            )

        await send_main_menu(context, update.effective_chat.id, "Interface status retrieved.")

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

def _split_by_lines_for_tg(text: str, max_len: int = 3500) -> list[str]:
    chunks, buf, cur_len = [], [], 0
    for line in text.splitlines():
        ln = len(line) + 1  # + newline
        if buf and cur_len + ln > max_len:
            chunks.append("\n".join(buf))
            buf, cur_len = [line], ln
        else:
            buf.append(line)
            cur_len += ln
    if buf:
        chunks.append("\n".join(buf))
    return chunks

async def handle_show_status(update: Update, context: ContextTypes.DEFAULT_TYPE, snmp_manager) -> None:
    query = update.callback_query
    await query.answer()
    
    if not snmp_manager.host:
        await query.edit_message_text(
            "No router IP set. Please use the 'Set Router IP' button to configure the router IP.",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    await query.edit_message_text("Querying router interfaces...")
    
    try:
        # Get if
        success, data = snmp_manager.get_interface_data()
        
        if success and data:
            # Format
            response_lines = [
                f"Router Interface Status - {snmp_manager.host}",
                "-" * 45,
                f"{'Interface':<12} | {'IP Address':<20} | {'Status':<8}"
            ]
            response_lines.append("-" * 45)
            
            # Add if
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
        
        # Split
        chunks = _split_by_lines_for_tg(response_message, max_len=3500)

        first_html = f"<pre>{html.escape(chunks[0])}</pre>"
        await query.edit_message_text(first_html, parse_mode='HTML')

        for chunk in chunks[1:]:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"<pre>{html.escape(chunk)}</pre>",
                parse_mode='HTML',
                disable_web_page_preview=True
            )

        await send_main_menu(context, update.effective_chat.id, "Interface status retrieved.")


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
        
        global ROUTER_IP
        ROUTER_IP = ip_input
        snmp_manager.host = ip_input
        
        context.user_data.pop('awaiting_ip', None)
        await update.message.reply_text(
            f"Router IP set to {ip_input} successfully!",
            reply_markup=get_main_menu_keyboard()
        )
        logger.info(f"Router IP set to {ip_input} by user")

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
    query = update.callback_query
    await query.answer()   
    
    if not snmp_manager.host:
        await update.message.reply_text(
            "No router IP set. Please use the 'Set Router IP' button to configure the router IP.",
            reply_markup=get_main_menu_keyboard()
        )
        return

    processing_msg = await update.message.reply_text("Querying router interfaces...")
    
    try:
        # Get if data
        success, data = snmp_manager.get_interface_data()
        
        if success and data:
            # Format
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
        
        # Split message
        lines = response_message.splitlines()
        chunks = []
        chunk = []
        for line in lines:
            if sum(len(l) + 1 for l in chunk) + len(line) + 1 > 4000:
                chunks.append("\n".join(chunk))
                chunk = []
            chunk.append(line)
        if chunk:
            chunks.append("\n".join(chunk))
        
        for i, chunk in enumerate(chunks):
            text = f"```\n{chunk}\n```"
            if i == 0:
                await query.edit_message_text(text, parse_mode='Markdown')
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=text,
                    parse_mode='Markdown'
                )
        
        await send_main_menu(context, update.effective_chat.id, "Interface status retrieved.")

        
    except Exception as e:
        error_message = f"Bot Error: {str(e)}"
        logger.error(error_message)
        await query.edit_message_text(
            error_message,
            reply_markup=get_main_menu_keyboard()
        )

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Unknown command found.\n\n"
        "Available commands:\n"
        "/start - Start monitoring\n"
        "/stop - Stop monitoring\n"
        "/status - Display interface table\n"
        "/set - Set router IP address"
    )