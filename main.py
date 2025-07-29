# main.py - Main application entry point

import logging
from telegram.ext import Application, CommandHandler
from telegram import Update
from config import *
from snmp_manager import CiscoSNMPManager
from bot_handlers import start_command, stop_command, status_command, unknown_command
from monitor import stop_monitoring

def setup_logging():
    """Configure logging settings"""
    logging.basicConfig(
        format=LOG_FORMAT,
        level=getattr(logging, LOG_LEVEL)
    )

def validate_configuration():
    """Validate configuration settings"""
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("ERROR: No valid Telegram bot token found in config.py")
        return False
    
    if not ROUTER_IP:
        print("ERROR: No router IP specified in config.py")
        return False
    
    return True

def print_startup_info():
    """Display startup information"""
    print(f"Starting Cisco SNMP Monitor Bot...")
    print(f"Target Router: {ROUTER_IP}")
    print(f"Monitor Interval: {MONITOR_INTERVAL} seconds")
    print(f"Monitoring Interface Information:")
    print(f"- Names: {INTERFACE_NAME_OID}")
    print(f"- Status: {INTERFACE_STATUS_OID}") 
    print(f"- IP Addresses: {INTERFACE_IP_OID}")
    print("Bot is starting... Press Ctrl+C to stop")

def create_command_handlers(snmp_manager):
    """Create command handlers with SNMP manager dependency injection"""
    async def start_wrapper(update: Update, context):
        await start_command(update, context, snmp_manager)
    
    async def status_wrapper(update: Update, context):
        await status_command(update, context, snmp_manager)
    
    return start_wrapper, status_wrapper

def main() -> None:
    """Main application function"""
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Validate configuration
    if not validate_configuration():
        return
    
    # Print startup information
    print_startup_info()
    
    # Initialize SNMP manager
    snmp_manager = CiscoSNMPManager(ROUTER_IP, SNMP_COMMUNITY, SNMP_PORT)
    
    # Test initial connection
    print("Testing SNMP connection...")
    success, test_data = snmp_manager.get_interface_status_only()
    if not success:
        print(f"WARNING: Could not connect to router {ROUTER_IP}")
        print("Bot will start anyway - connection will be retried when monitoring starts")
    else:
        print(f"Successfully connected to router {ROUTER_IP}")
        print(f"Found {len(test_data)} interfaces")
    
    # Create Telegram application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Create command handlers with dependency injection
    start_wrapper, status_wrapper = create_command_handlers(snmp_manager)
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start_wrapper))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("status", status_wrapper))
    
    # Add handler for unknown commands
    from telegram.ext import MessageHandler, filters
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    
    # Run the bot
    try:
        logger.info("Starting Telegram bot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        stop_monitoring()
        print("\nBot stopped by user")
        logger.info("Bot stopped by user interrupt")
    except Exception as e:
        stop_monitoring()
        print(f"Bot error: {e}")
        logger.error(f"Bot error: {e}")

if __name__ == '__main__':
    main()