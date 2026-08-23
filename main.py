#!/usr/bin/env python3
"""
Instagram Report Bot - Telegram Bot
Complete working bot with admin panel, broadcast, and reporting
FIXED: Python 3.14 Event Loop Error
FIXED: Render Deployment Issues
FIXED: getUpdates Conflict
"""

import os
import asyncio
import logging
import json
import sys
from datetime import datetime
from typing import Optional, Dict, List
import random

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode

from database import Database
from report_engine import ReportEngine

# Optional plugin imports (try/except for compatibility)
try:
    from plugins.account_manager import AccountManager
    from plugins.credit_system import CreditSystem
    from plugins.referral_system import ReferralSystem
    from plugins.channel_force import ChannelForce
    PLUGINS_ENABLED = True
except ImportError:
    PLUGINS_ENABLED = False
    logger = logging.getLogger(__name__)
    logger.warning("Plugins not found, running without plugin system")

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('InstagramReportBot')

# Conversation states
WAITING_FOR_URL = 1

class InstagramReportBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.admin_id = int(os.getenv('ADMIN_USER_ID', '0'))
        self.db = Database()
        self.report_engine = ReportEngine(self.db)
        
        # Initialize plugins if available
        if PLUGINS_ENABLED:
            try:
                self.account_manager = AccountManager(self.db)
                self.credit_system = CreditSystem()
                self.referral_system = ReferralSystem(self.credit_system, "@Instatounfollow_bot")
                self.channel_force = ChannelForce()
                logger.info("✅ Plugins initialized")
            except Exception as e:
                logger.error(f"Plugin initialization error: {e}")
                self.plugins_available = False
            else:
                self.plugins_available = True
        else:
            self.plugins_available = False
        
        self.user_states = {}
        self.report_reasons = {
            'spam': '🚫 Spam',
            'fake_profile': '👤 Fake Profile',
            'harassment': '😠 Harassment/Bullying',
            'violence': '⚡ Violence/Threats',
            'scam': '💰 Scam/Fraud',
            'nudity': '🔞 Nudity/Sexual',
            'drugs': '💊 Drugs',
            'hate_speech': '🚫 Hate Speech',
            'copyright': '©️ Copyright',
            'impersonation': '👤 Impersonation',
            'bullying': '😠 Bullying',
            'threats': '⚠️ Threats',
            'terrorism': '☠️ Terrorism',
            'self_harm': '🆘 Self Harm',
            'underage': '👶 Underage'
        }
    
    # ============ ERROR HANDLER ============
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors caused by updates."""
        logger.error(f"Exception while handling an update: {context.error}")
        
        try:
            if "Conflict" in str(context.error):
                logger.error("⚠️ Bot conflict detected - another instance running!")
                logger.error("Solution: Stop other bot instance")
            elif "Event loop is closed" in str(context.error):
                logger.error("⚠️ Event loop error - Python version issue")
                logger.error("Solution: Use Python 3.11 instead of 3.14")
            elif "NetworkError" in str(context.error):
                logger.error("⚠️ Network error - check internet connection")
            else:
                logger.error(f"Update {update} caused error: {context.error}")
        except:
            pass
    
    # ============ BASIC COMMANDS ============
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        
        # Check channel membership if plugin enabled
        if self.plugins_available and hasattr(self, 'channel_force'):
            try:
                if self.channel_force.is_enabled():
                    is_member = await self.channel_force.check_membership(context, user.id)
                    if not is_member:
                        await update.message.reply_text(
                            self.channel_force.get_welcome_message(),
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=self.channel_force.get_join_keyboard()
                        )
                        return
            except Exception as e:
                logger.error(f"Channel check error: {e}")
        
        # Save user to database
        self.db.add_user(user.id, user.username or '', user.first_name)
        
        # Create credit user if plugin available
        if self.plugins_available:
            try:
                if not self.credit_system.get_user(user.id):
                    self.credit_system.create_user(user.id, user.username or '', user.first_name)
            except:
                pass
        
        # Check referral
        if context.args and context.args[0].startswith('ref_'):
            if self.plugins_available:
                try:
                    referral_code = context.args[0][4:]
                    if self.referral_system.process_referral(referral_code, user.id):
                        await update.message.reply_text("🎉 Referral bonus credited!")
                except:
                    pass
        
        # Get credits
        credits = 0
        if self.plugins_available:
            try:
                credits = self.credit_system.get_credits(user.id)
            except:
                credits = 0
        
        # Create keyboard
        keyboard = [
            [InlineKeyboardButton("🎯 Report Profile", callback_data='menu_report')],
            [InlineKeyboardButton("📊 My Reports", callback_data='menu_myreports')],
        ]
        
        if self.plugins_available:
            keyboard.append([InlineKeyboardButton("💳 Credits", callback_data='menu_credits')])
            keyboard.append([InlineKeyboardButton("👥 Referral", callback_data='menu_referral')])
        
        keyboard.append([InlineKeyboardButton("📈 Status", callback_data='menu_status')])
        keyboard.append([InlineKeyboardButton("ℹ️ Help", callback_data='menu_help')])
        
        # Add admin options
        if user.id == self.admin_id:
            keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data='menu_admin')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = f"""
🎯 *Instagram Report Bot*

Welcome {user.first_name}!

💳 Your Credits: `{credits}`

*Features:*
✅ Multi-account reporting (2-5 accounts)
✅ Proxy rotation
✅ Human-like delays
✅ Account health monitoring
✅ Target status tracking

*Commands:*
/report - Report a profile
/myreports - View your reports
/status - Bot status
/help - Help

⚠️ *Only report genuine violations!*
"""
        
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
        # Log activity
        self.db.add_log(user.id, 'start', 'User started the bot')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
📚 *Help & Commands*

*User Commands:*
/start - Start bot
/report - Report Instagram profile
/myreports - View your reports
/status - Bot status
/help - Show this help

*How to Report:*
1. Send /report
2. Enter Instagram profile URL
3. Select reason
4. Wait for processing

*Example:*
/report https://instagram.com/username

⚠️ *Only report genuine violations!*
"""
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        try:
            stats = self.db.get_stats()
            
            status_text = f"""
📊 *Bot Status*

👥 Users: {stats['total_users']}
📝 Total Reports: {stats['total_reports']}
✅ Completed: {stats['completed_reports']}
⏳ Pending: {stats['pending_reports']}
📱 Active Accounts: {stats['active_accounts']}
🌐 Active Proxies: {stats['active_proxies']}

*System:* 🟢 Online
"""
            await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Status error: {e}")
            await update.message.reply_text("📊 *Bot Status*\n\n🟢 Online", parse_mode=ParseMode.MARKDOWN)
    
    # ============ REPORT COMMANDS ============
    
    async def report_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /report command"""
        user = update.effective_user
        
        # Check if user is banned
        user_data = self.db.get_user(user.id)
        if user_data and user_data['is_banned']:
            await update.message.reply_text("❌ You are banned from using this bot.")
            return
        
        # Check channel membership
        if self.plugins_available and hasattr(self, 'channel_force'):
            try:
                if self.channel_force.is_enabled():
                    is_member = await self.channel_force.check_membership(context, user.id)
                    if not is_member:
                        await update.message.reply_text(
                            self.channel_force.get_welcome_message(),
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=self.channel_force.get_join_keyboard()
                        )
                        return
            except:
                pass
        
        # Check credits
        if self.plugins_available:
            try:
                credits = self.credit_system.get_credits(user.id)
                if credits < 4:
                    await update.message.reply_text(
                        f"❌ *Insufficient Credits*\n\n"
                        f"You need 4 credits to report.\n"
                        f"Your credits: {credits}\n\n"
                        f"Earn credits via referral: /referral",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
            except:
                pass
        
        if context.args:
            target_url = context.args[0]
            context.user_data['target_url'] = target_url
            await self.show_reason_selection(update, context)
        else:
            await update.message.reply_text(
                "🔗 *Report Instagram Profile*\n\n"
                "Send the Instagram profile URL:\n"
                "Example: `https://instagram.com/username`\n\n"
                "Or send /cancel to cancel.",
                parse_mode=ParseMode.MARKDOWN
            )
            context.user_data['state'] = WAITING_FOR_URL
    
    async def handle_report_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle URL input for report"""
        target_url = update.message.text.strip()
        
        # Validate URL
        if 'instagram.com' not in target_url and '/' in target_url:
            await update.message.reply_text(
                "❌ Invalid URL. Please send Instagram profile URL:\n"
                "Example: `https://instagram.com/username`",
                parse_mode=ParseMode.MARKDOWN
            )
            return WAITING_FOR_URL
        
        context.user_data['target_url'] = target_url
        await self.show_reason_selection(update, context)
        return ConversationHandler.END
    
    async def show_reason_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show reason selection keyboard"""
        keyboard = []
        
        reasons_list = list(self.report_reasons.items())
        for i in range(0, len(reasons_list), 2):
            row = []
            for reason_key, reason_label in reasons_list[i:i+2]:
                row.append(InlineKeyboardButton(
                    reason_label, 
                    callback_data=f'reason_{reason_key}'
                ))
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data='cancel')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        target_url = context.user_data.get('target_url', 'Unknown')
        
        await update.message.reply_text(
            f"🎯 *Target:* `{target_url}`\n\n"
            "Select report reason:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def handle_reason_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle reason selection"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'cancel':
            await query.edit_message_text("❌ Report cancelled.")
            return
        
        reason = query.data.replace('reason_', '')
        target_url = context.user_data.get('target_url', '')
        user_id = query.from_user.id
        
        # Spend credits
        if self.plugins_available:
            try:
                if not self.credit_system.spend_credits(user_id, 4, f"Report: {target_url}"):
                    await query.edit_message_text("❌ Insufficient credits!")
                    return
            except:
                pass
        
        reason_label = self.report_reasons.get(reason, reason)
        
        await query.edit_message_text(
            f"🔄 *Processing Report*\n\n"
            f"🎯 Target: `{target_url}`\n"
            f"📋 Reason: {reason_label}\n\n"
            f"⏳ This may take a few minutes...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Execute report in background
        asyncio.create_task(self.process_report(query, target_url, reason, user_id))
    
    async def process_report(self, query, target_url: str, reason: str, user_id: int):
        """Process report in background"""
        try:
            result = await self.report_engine.execute_report(target_url, reason, user_id)
            
            if result['success']:
                success_count = result.get('success_count', 0)
                accounts_used = result.get('accounts_used', 0)
                target_status = result.get('target_status', {}).get('status', 'unknown')
                
                status_emoji = {
                    'removed': '✅',
                    'disabled': '✅',
                    'active': '⚠️',
                    'unknown': '❓'
                }.get(target_status, '❓')
                
                await query.edit_message_text(
                    f"✅ *Report Completed!*\n\n"
                    f"🎯 Target: `{target_url}`\n"
                    f"📋 Reason: {reason}\n"
                    f"📱 Accounts Used: {accounts_used}\n"
                    f"✅ Success: {success_count}/{accounts_used}\n\n"
                    f"📊 Target Status: {status_emoji} {target_status}",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                # Refund credits
                if self.plugins_available:
                    try:
                        self.credit_system.add_credits(user_id, 4, "Refund - Failed")
                    except:
                        pass
                
                await query.edit_message_text(
                    f"❌ *Report Failed*\n\n"
                    f"Error: {result.get('error', 'Unknown error')}",
                    parse_mode=ParseMode.MARKDOWN
                )
                
        except Exception as e:
            logger.error(f"Report processing error: {e}")
            try:
                await query.edit_message_text(f"❌ Error: {str(e)}")
            except:
                pass
    
    async def myreports_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /myreports command"""
        user_id = update.effective_user.id
        reports = self.db.get_user_reports(user_id, limit=10)
        
        if not reports:
            await update.message.reply_text("📊 You have no reports yet.")
            return
        
        report_text = "📊 *Your Recent Reports:*\n\n"
        
        for report in reports[:5]:
            status_emoji = {
                'completed': '✅',
                'pending': '⏳',
                'failed': '❌'
            }.get(report['status'], '❓')
            
            report_text += f"{status_emoji} `{report['target_username']}` - {report['reason']}\n"
            report_text += f"   📅 {report['created_at']}\n\n"
        
        await update.message.reply_text(report_text, parse_mode=ParseMode.MARKDOWN)
    
    # ============ PLUGIN COMMANDS ============
    
    async def add_account_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /add command"""
        if not self.plugins_available:
            await update.message.reply_text("❌ Plugin system not available.")
            return
        
        user = update.effective_user
        
        # Check banned
        user_data = self.db.get_user(user.id)
        if user_data and user_data['is_banned']:
            await update.message.reply_text("❌ You are banned.")
            return
        
        # Check credits
        try:
            credits = self.credit_system.get_credits(user.id)
            if credits < 4:
                await update.message.reply_text(
                    f"❌ *Insufficient Credits*\n\n"
                    f"You need 4 credits.\n"
                    f"Your credits: {credits}\n\n"
                    f"Get credits: /referral",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
        except:
            pass
        
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "📱 *Add Instagram Account*\n\n"
                "Usage: `/add username password`\n\n"
                "Example: `/add myuser mypass123`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        username = context.args[0].replace('@', '')
        password = context.args[1]
        
        status_msg = await update.message.reply_text(
            f"⏳ *Verifying Account...*\n\n"
            f"Username: `{username}`\n"
            f"Password: `{password}`\n\n"
            f"Please wait...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            result = self.account_manager.add_account(username, password)
            
            if result['success']:
                self.credit_system.spend_credits(user.id, 4, f"Added: {username}")
            
            await status_msg.edit_text(result['message'], parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await status_msg.edit_text(f"❌ Error: {str(e)}")
    
    async def remove_account_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /removeacc command"""
        if update.effective_user.id != self.admin_id:
            await update.message.reply_text("❌ Admin only.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /removeacc username")
            return
        
        try:
            result = self.account_manager.remove_account(context.args[0])
            await update.message.reply_text(result['message'], parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def list_accounts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /myacc command"""
        if update.effective_user.id != self.admin_id:
            await update.message.reply_text("❌ Admin only.")
            return
        
        try:
            text = self.account_manager.list_accounts()
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def credits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /credits command"""
        if not self.plugins_available:
            await update.message.reply_text("❌ Plugin system not available.")
            return
        
        user = update.effective_user
        
        try:
            if not self.credit_system.get_user(user.id):
                self.credit_system.create_user(user.id, user.username or '', user.first_name)
            
            summary = self.credit_system.get_credit_summary(user.id)
            await update.message.reply_text(summary, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def give_credits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /givecredits command"""
        if update.effective_user.id != self.admin_id:
            await update.message.reply_text("❌ Admin only.")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /givecredits user_id amount")
            return
        
        try:
            target_id = int(context.args[0])
            amount = int(context.args[1])
            
            if not self.credit_system.get_user(target_id):
                self.credit_system.create_user(target_id, '', '')
            
            self.credit_system.add_credits(target_id, amount, "Admin grant")
            await update.message.reply_text(f"✅ Added {amount} credits to {target_id}")
        except ValueError:
            await update.message.reply_text("❌ Invalid ID or amount.")
    
    async def remove_credits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /removecredits command"""
        if update.effective_user.id != self.admin_id:
            await update.message.reply_text("❌ Admin only.")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /removecredits user_id amount")
            return
        
        try:
            target_id = int(context.args[0])
            amount = int(context.args[1])
            
            if self.credit_system.remove_credits(target_id, amount, "Admin removed"):
                await update.message.reply_text(f"✅ Removed {amount} from {target_id}")
            else:
                await update.message.reply_text("❌ Failed.")
        except ValueError:
            await update.message.reply_text("❌ Invalid.")
    
    async def referral_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /referral command"""
        if not self.plugins_available:
            await update.message.reply_text("❌ Plugin system not available.")
            return
        
        user = update.effective_user
        
        try:
            if not self.credit_system.get_user(user.id):
                self.credit_system.create_user(user.id, user.username or '', user.first_name)
            
            stats = self.referral_system.get_referral_stats(user.id)
            await update.message.reply_text(stats, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def channel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /channel command"""
        if update.effective_user.id != self.admin_id:
            await update.message.reply_text("❌ Admin only.")
            return
        
        if not context.args:
            try:
                channels = self.channel_force.list_channels()
                status = "✅ Enabled" if self.channel_force.is_enabled() else "❌ Disabled"
                
                text = f"📢 *Channel Settings*\n\nStatus: {status}\n\n*Channels:*\n"
                for ch in channels:
                    text += f"• @{ch}\n"
                
                text += "\n/channel add @username\n/channel remove @username"
                await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
            except:
                await update.message.reply_text("❌ Channel system not available.")
        
        elif context.args[0].lower() == 'add':
            if len(context.args) < 2:
                await update.message.reply_text("Usage: /channel add @username")
                return
            
            channel = context.args[1].replace('@', '')
            try:
                if self.channel_force.add_channel(channel):
                    await update.message.reply_text(f"✅ @{channel} added!")
                else:
                    await update.message.reply_text("❌ Exists!")
            except:
                await update.message.reply_text("❌ Channel system not available.")
    
    # ============ ADMIN COMMANDS ============
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /admin command"""
        if update.effective_user.id != self.admin_id:
            await update.message.reply_text("❌ Unauthorized.")
            return
        
        keyboard = [
            [InlineKeyboardButton("📊 Stats", callback_data='admin_stats')],
            [InlineKeyboardButton("📋 Logs", callback_data='admin_logs')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⚙️ *Admin Panel*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        if update.effective_user.id != self.admin_id:
            return
        
        try:
            stats = self.db.get_stats()
            text = f"""
📊 *Stats*

👥 Users: {stats['total_users']}
📝 Reports: {stats['total_reports']}
📱 Accounts: {stats['active_accounts']}
🌐 Proxies: {stats['active_proxies']}
"""
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        except:
            await update.message.reply_text("❌ Stats error.")
    
    async def logs_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /logs command"""
        if update.effective_user.id != self.admin_id:
            return
        
        try:
            logs = self.db.get_logs(limit=10)
            text = "📋 *Recent Logs:*\n\n"
            for log in logs[:5]:
                text += f"🕐 {log['timestamp']} - {log['action']}\n"
            
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        except:
            await update.message.reply_text("❌ No logs.")
    
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /broadcast command"""
        if update.effective_user.id != self.admin_id:
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /broadcast message")
            return
        
        message = ' '.join(context.args)
        users = self.db.get_all_users()
        
        sent = 0
        for user in users:
            if not user['is_banned']:
                try:
                    await context.bot.send_message(
                        user['user_id'],
                        f"📢 {message}"
                    )
                    sent += 1
                    await asyncio.sleep(0.05)
                except:
                    pass
        
        await update.message.reply_text(f"✅ Sent to {sent} users")
    
    async def ban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /ban command"""
        if update.effective_user.id != self.admin_id:
            return
        
        if context.args:
            try:
                self.db.ban_user(int(context.args[0]))
                await update.message.reply_text("✅ Banned")
            except:
                await update.message.reply_text("❌ Invalid")
    
    async def unban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /unban command"""
        if update.effective_user.id != self.admin_id:
            return
        
        if context.args:
            try:
                self.db.unban_user(int(context.args[0]))
                await update.message.reply_text("✅ Unbanned")
            except:
                await update.message.reply_text("❌ Invalid")
    
    # ============ CALLBACK HANDLERS ============
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        try:
            if data == 'menu_report':
                await query.edit_message_text(
                    "🔗 Send Instagram URL:\nExample: `https://instagram.com/username`",
                    parse_mode=ParseMode.MARKDOWN
                )
                context.user_data['state'] = WAITING_FOR_URL
            
            elif data == 'menu_myreports':
                reports = self.db.get_user_reports(user_id, 5)
                
                if not reports:
                    await query.edit_message_text("📊 No reports.")
                    return
                
                text = "📊 *Reports:*\n\n"
                for r in reports:
                    emoji = {'completed': '✅', 'pending': '⏳', 'failed': '❌'}.get(r['status'], '❓')
                    text += f"{emoji} `{r['target_username']}`\n"
                
                await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
            
            elif data == 'menu_credits':
                if self.plugins_available:
                    if not self.credit_system.get_user(user_id):
                        self.credit_system.create_user(user_id, '', '')
                    summary = self.credit_system.get_credit_summary(user_id)
                    await query.edit_message_text(summary, parse_mode=ParseMode.MARKDOWN)
                else:
                    await query.edit_message_text("💳 Credits: 0")
            
            elif data == 'menu_referral':
                if self.plugins_available:
                    if not self.credit_system.get_user(user_id):
                        self.credit_system.create_user(user_id, '', '')
                    stats = self.referral_system.get_referral_stats(user_id)
                    await query.edit_message_text(stats, parse_mode=ParseMode.MARKDOWN)
                else:
                    await query.edit_message_text("👥 Referral system not available.")
            
            elif data == 'menu_status':
                stats = self.db.get_stats()
                await query.edit_message_text(
                    f"📊 Users: {stats['total_users']}\n"
                    f"📝 Reports: {stats['total_reports']}\n"
                    f"🟢 Online",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            elif data == 'menu_help':
                await query.edit_message_text(
                    "📚 /report - Report\n/add - Add account\n/credits - Credits\n/referral - Referral",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            elif data == 'menu_admin' and user_id == self.admin_id:
                keyboard = [
                    [InlineKeyboardButton("📊 Stats", callback_data='admin_stats')],
                    [InlineKeyboardButton("📋 Logs", callback_data='admin_logs')],
                ]
                await query.edit_message_text(
                    "⚙️ *Admin Panel*",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            
            elif data == 'admin_stats':
                stats = self.db.get_stats()
                await query.edit_message_text(
                    f"👥 Users: {stats['total_users']}\n📝 Reports: {stats['total_reports']}",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            elif data == 'admin_logs':
                logs = self.db.get_logs(5)
                text = "📋 *Logs:*\n\n"
                for log in logs[:3]:
                    text += f"🕐 {log['action']}\n"
                await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
            
            elif data == 'check_membership':
                if self.plugins_available:
                    is_member = await self.channel_force.check_membership(context, user_id)
                    if is_member:
                        await query.edit_message_text("✅ Verified!")
                    else:
                        await query.answer("❌ Join all channels first!", show_alert=True)
            
            elif data.startswith('reason_'):
                await self.handle_reason_selection(update, context)
        
        except Exception as e:
            logger.error(f"Button handler error: {e}")
            try:
                await query.edit_message_text("❌ Error. Try again.")
            except:
                pass
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        state = context.user_data.get('state')
        
        if state == WAITING_FOR_URL:
            await self.handle_report_url(update, context)
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel command"""
        context.user_data.clear()
        await update.message.reply_text("❌ Cancelled.")
        return ConversationHandler.END
    
    # ============ MAIN RUN ============
    
    def run(self):
        """Run the bot - Python 3.14 compatible"""
        if not self.token:
            logger.error("No bot token found! Set TELEGRAM_BOT_TOKEN in .env")
            return
        
        # Create application
        app = Application.builder().token(self.token).build()
        
        # Add error handler
        app.add_error_handler(self.error_handler)
        
        # Add all handlers
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(CommandHandler("status", self.status_command))
        app.add_handler(CommandHandler("report", self.report_command))
        app.add_handler(CommandHandler("myreports", self.myreports_command))
        app.add_handler(CommandHandler("add", self.add_account_command))
        app.add_handler(CommandHandler("removeacc", self.remove_account_command))
        app.add_handler(CommandHandler("myacc", self.list_accounts_command))
        app.add_handler(CommandHandler("credits", self.credits_command))
        app.add_handler(CommandHandler("givecredits", self.give_credits_command))
        app.add_handler(CommandHandler("removecredits", self.remove_credits_command))
        app.add_handler(CommandHandler("referral", self.referral_command))
        app.add_handler(CommandHandler("channel", self.channel_command))
        app.add_handler(CommandHandler("admin", self.admin_command))
        app.add_handler(CommandHandler("stats", self.stats_command))
        app.add_handler(CommandHandler("logs", self.logs_command))
        app.add_handler(CommandHandler("broadcast", self.broadcast_command))
        app.add_handler(CommandHandler("ban", self.ban_command))
        app.add_handler(CommandHandler("unban", self.unban_command))
        app.add_handler(CommandHandler("cancel", self.cancel_command))
        app.add_handler(CallbackQueryHandler(self.button_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Start bot
        logger.info("🤖 Bot started!")
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


# ============ MAIN ENTRY POINT ============

if __name__ == '__main__':
    # Python 3.14 compatible startup
    try:
        bot = InstagramReportBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
