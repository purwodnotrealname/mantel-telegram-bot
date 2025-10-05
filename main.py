# main.py - Main application entry point with widget buttons

import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram import Update
from config import *
from snmp_manager import CiscoSNMPManager

def setup_logging():
    logging.basicConfig(
        format=LOG_FORMAT,
        level=getattr(logging, LOG_LEVEL)
    )

def validate_configuration():
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("ERROR: No valid Telegram bot token found in config.py")
        return False
    return True

def print_startup_info():
    print(f"Starting Cisco SNMP Monitor Bot...")
    print(f"Monitoring Interface Information:")
    print(f"- Names: {INTERFACE_NAME_OID}")
    print(f"- Status: {INTERFACE_STATUS_OID}") 
    print(f"- IP Addresses: {INTERFACE_IP_OID}")
    print("Bot is starting... Press Ctrl+C to stop")

def create_command_handlers(snmp_manager):
    from bot_handlers import (
        start_command, status_command, unknown_command,
        handle_start_monitoring, handle_stop_monitoring, handle_show_status,
        handle_set_router_ip, handle_cancel_set_ip, handle_text
    )
    
    async def start_wrapper(update: Update, context):
        await start_command(update, context, snmp_manager)
    
    async def status_wrapper(update: Update, context):
        await status_command(update, context, snmp_manager)
    
    async def set_wrapper(update: Update, context):
        await handle_set_router_ip(update, context)
    
    async def text_wrapper(update: Update, context):
        await handle_text(update, context, snmp_manager)
    
    async def unknown_command_wrapper(update: Update, context):
        await unknown_command(update, context)
    
    # Widget button handlers
    async def callback_start_monitoring(update: Update, context):
        await handle_start_monitoring(update, context, snmp_manager)
    
    async def callback_stop_monitoring(update: Update, context):
        await handle_stop_monitoring(update, context)
    
    async def callback_show_status(update: Update, context):
        await handle_show_status(update, context, snmp_manager)
    
    async def callback_set_router_ip(update: Update, context):
        await handle_set_router_ip(update, context)
    
    async def callback_cancel_set_ip(update: Update, context):
        await handle_cancel_set_ip(update, context)
    
    return (start_wrapper, status_wrapper, set_wrapper, text_wrapper, unknown_command_wrapper,
            callback_start_monitoring, callback_stop_monitoring, callback_show_status,
            callback_set_router_ip, callback_cancel_set_ip)

def main() -> None:
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Validate configuration
    if not validate_configuration():
        return
    
    # Print startup information
    print_startup_info()
    
    # Initialize SNMP manager with no initial IP
    snmp_manager = CiscoSNMPManager(None, SNMP_COMMUNITY, SNMP_PORT)
    
    # Create Telegram application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Create command handlers with dependency injection
    (start_wrapper, status_wrapper, set_wrapper, text_wrapper, unknown_command_wrapper,
     callback_start_monitoring, callback_stop_monitoring, callback_show_status,
     callback_set_router_ip, callback_cancel_set_ip) = create_command_handlers(snmp_manager)
    
    # Import stop_command here to avoid circular import
    from bot_handlers import stop_command
    
    # Create stop wrapper
    async def stop_wrapper(update: Update, context):
        await stop_command(update, context)
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start_wrapper))
    application.add_handler(CommandHandler("stop", stop_wrapper))
    application.add_handler(CommandHandler("status", status_wrapper))
    application.add_handler(CommandHandler("set", set_wrapper))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_wrapper))

    # Register callback query handlers for widget buttons
    application.add_handler(CallbackQueryHandler(callback_start_monitoring, pattern="^start_monitoring$"))
    application.add_handler(CallbackQueryHandler(callback_stop_monitoring, pattern="^stop_monitoring$"))
    application.add_handler(CallbackQueryHandler(callback_show_status, pattern="^show_status$"))
    application.add_handler(CallbackQueryHandler(callback_set_router_ip, pattern="^set_router_ip$"))
    application.add_handler(CallbackQueryHandler(callback_cancel_set_ip, pattern="^cancel_set_ip$"))

    # Add handler for unknown commands
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command_wrapper))
    
    # Run the bot
    try:
        logger.info("Starting Telegram bot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        from monitor import stop_monitoring
        stop_monitoring()
        print("\nBot stopped by user")
        logger.info("Bot stopped by user interrupt")
    except Exception as e:
        from monitor import stop_monitoring
        stop_monitoring()
        print(f"Bot error: {e}")
        logger.error(f"Bot error: {e}")

if __name__ == '__main__':
    main()