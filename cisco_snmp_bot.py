import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pysnmp.hlapi import *

TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  
ROUTER_IP = "192.168.137.130"
SNMP_COMMUNITY = "public"  
SNMP_PORT = 161

# Hardcoded OID
TARGET_OID = "1.3.6.1.2.1.1.1.0"

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
    
    def get_snmp_data(self, oid):
        try:
            iterator = getCmd(
                SnmpEngine(),
                CommunityData(self.community),
                UdpTransportTarget((self.host, self.port)),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False
            )
            
            errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
            
            if errorIndication:
                return False, f"SNMP Error: {errorIndication}"
            elif errorStatus:
                return False, f"SNMP Error: {errorStatus.prettyPrint()} at {errorIndex and varBinds[int(errorIndex) - 1][0] or '?'}"
            else:
                # Extract the value from the response
                for varBind in varBinds:
                    oid, value = varBind
                    return True, str(value)
                    
        except Exception as e:
            return False, f"Connection Error: {str(e)}"
        
        return False, "Unknown error occurred"

# Initialize SNMP manager
snmp_manager = CiscoSNMPManager(ROUTER_IP, SNMP_COMMUNITY, SNMP_PORT)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    welcome_message = (
        "/start - Show command\n"
        "/status - Perform\n"
        "/help - welp"
    )
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_message = (
        "Bot Commands:\n\n"
        "/start - Initialize bot and show welcome message\n"
        "/status - Query router system description\n"
        "/help - Display this help message\n\n"
        f"Target Router: {ROUTER_IP}\n"
        f"Monitored OID: {TARGET_OID} (System Description)"
    )
    await update.message.reply_text(help_message)

async def get_router_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Send "processing" message
    processing_msg = await update.message.reply_text("Querying....")
    
    try:
        # Get SNMP data
        success, data = snmp_manager.get_snmp_data(TARGET_OID)
        
        if success:
            response_message = (
                f"Router Status Report\n"
                f"Target: {ROUTER_IP}\n"
                f"OID: {TARGET_OID}\n\n"
                f"System Description:\n{data}"
            )
        else:
            response_message = (
                f"Failed to query router at {ROUTER_IP}\n"
                f"Error: {data}\n\n"
                "Please check:\n"
                "1. Router is powered on and accessible\n"
                "2. SNMP is enabled on the router\n"
                "3. Network connectivity is working"
            )
        
        # Delete processing message and send result
        await processing_msg.delete()
        await update.message.reply_text(response_message)
        
    except Exception as e:
        await processing_msg.delete()
        await update.message.reply_text(f"Bot Error: {str(e)}")

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle unknown commands."""
    await update.message.reply_text(
        "Unknown command. Use /help to see available commands."
    )

def main() -> None:
    # Validate configuration
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("ERROR: Please set your Telegram bot token in the TELEGRAM_BOT_TOKEN variable")
        return
    
    print(f"Starting Cisco SNMP Monitor Bot...")
    print(f"Target Router: {ROUTER_IP}")
    print(f"Monitoring OID: {TARGET_OID}")
    print("Bot is starting... Press Ctrl+C to stop")
    
    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", get_router_status))
    
    # Run the bot until the user presses Ctrl-C
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Bot error: {e}")

if __name__ == '__main__':
    main()