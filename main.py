#!/usr/bin/env python3
"""
Instagram Report Bot - Telegram Bot
Complete working bot with admin panel, broadcast, and reporting
"""

import os
import asyncio
import logging
import json
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
WAITING_FOR_REASON = 2
WAITING_FOR_BROADCAST = 3
WAITING_FOR_ACCOUNT = 4
WAITING_FOR_PROXY = 5

class InstagramReportBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.admin_id = int(os.getenv('8170807285', '0'))
        self.db = Database()
        self.report_engine = ReportEngine(self.db)
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
    
    async def setup_commands(self, app: Application):
        """Setup bot commands"""
        commands = [
            BotCommand("start", "🚀 Start the bot"),
            BotCommand("report", "🎯 Report Instagram profile"),
            BotCommand("myreports", "📊 View my reports"),
            BotCommand("status", "📈 Bot status"),
            BotCommand("help", "ℹ️ Help"),
            BotCommand("admin", "⚙️ Admin panel"),
            BotCommand("broadcast", "📢 Broadcast message"),
            BotCommand("logs", "📋 View logs"),
            BotCommand("stats", "📊 Statistics"),
            BotCommand("accounts", "📱 Manage accounts"),
            BotCommand("proxies", "🌐 Manage proxies"),
            BotCommand("ban", "🚫 Ban user"),
            BotCommand("unban", "✅ Unban user")
        ]
        await app.bot.set_my_commands(commands)
    
    # ============ BASIC COMMANDS ============
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        
        # Save user to database
        self.db.add_user(user.id, user.username or '', user.first_name)
        
        # Create keyboard
        keyboard = [
            [InlineKeyboardButton("🎯 Report Profile", callback_data='menu_report')],
            [InlineKeyboardButton("📊 My Reports", callback_data='menu_myreports')],
            [InlineKeyboardButton("📈 Status", callback_data='menu_status')],
            [InlineKeyboardButton("ℹ️ Help", callback_data='menu_help')],
        ]
        
        # Add admin options
        if user.id == self.admin_id:
            keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data='menu_admin')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = f"""
🎯 *Instagram Report Bot*

Welcome {user.first_name}!

I can help you report Instagram accounts that violate policies.

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
    
    # ============ REPORT COMMANDS ============
    
    async def report_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /report command"""
        user = update.effective_user
        
        # Check if user is banned
        user_data = self.db.get_user(user.id)
        if user_data and user_data['is_banned']:
            await update.message.reply_text("❌ You are banned from using this bot.")
            return
        
        if context.args:
            # URL provided with command
            target_url = context.args[0]
            context.user_data['target_url'] = target_url
            await self.show_reason_selection(update, context)
        else:
            # Ask for URL
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
        
        # Create 2 columns of reasons
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
    
    # ============ ADMIN COMMANDS ============
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /admin command"""
        user_id = update.effective_user.id
        
        if user_id != self.admin_id:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        keyboard = [
            [InlineKeyboardButton("📊 Statistics", callback_data='admin_stats')],
            [InlineKeyboardButton("👥 Users List", callback_data='admin_users')],
            [InlineKeyboardButton("📱 Accounts", callback_data='admin_accounts')],
            [InlineKeyboardButton("🌐 Proxies", callback_data='admin_proxies')],
            [InlineKeyboardButton("📋 Logs", callback_data='admin_logs')],
            [InlineKeyboardButton("📢 Broadcast", callback_data='admin_broadcast')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⚙️ *Admin Panel*\n\nSelect an option:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command (admin)"""
        user_id = update.effective_user.id
        
        if user_id != self.admin_id:
            await update.message.reply_text("❌ Admin only command.")
            return
        
        stats = self.db.get_stats()
        
        stats_text = f"""
📊 *Bot Statistics*

*Users:*
👥 Total: {stats['total_users']}
✅ Active: {stats['active_users']}
🚫 Banned: {stats['banned_users']}

*Reports:*
📝 Total: {stats['total_reports']}
✅ Completed: {stats['completed_reports']}
⏳ Pending: {stats['pending_reports']}

*Resources:*
📱 Active Accounts: {stats['active_accounts']}
🌐 Active Proxies: {stats['active_proxies']}
"""
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    
    async def accounts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /accounts command (admin)"""
        user_id = update.effective_user.id
        
        if user_id != self.admin_id:
            await update.message.reply_text("❌ Admin only command.")
            return
        
        if not context.args:
            # Show accounts list
            accounts = self.db.get_all_accounts()
            
            if not accounts:
                await update.message.reply_text("📱 No accounts configured.")
                return
            
            account_text = "📱 *Instagram Accounts:*\n\n"
            
            for acc in accounts[:10]:
                status = "✅" if acc['is_active'] else "❌"
                account_text += f"{status} `{acc['username']}`\n"
                account_text += f"   Health: {acc['health_score']}% | Reports: {acc['reports_today']}/{acc['max_daily_reports']}\n\n"
            
            account_text += "\n*Commands:*\n"
            account_text += "/accounts add [username] [password]\n"
            account_text += "/accounts remove [username]\n"
            account_text += "/accounts list\n"
            
            await update.message.reply_text(account_text, parse_mode=ParseMode.MARKDOWN)
        
        elif context.args[0].lower() == 'add':
            if len(context.args) >= 3:
                username = context.args[1]
                password = context.args[2]
                
                if self.db.add_account(username, password):
                    await update.message.reply_text(f"✅ Account added: {username}")
                else:
                    await update.message.reply_text(f"❌ Failed to add account: {username}")
            else:
                await update.message.reply_text("Usage: /accounts add [username] [password]")
        
        elif context.args[0].lower() == 'remove':
            if len(context.args) >= 2:
                username = context.args[1]
                
                if self.db.remove_account(username):
                    await update.message.reply_text(f"✅ Account removed: {username}")
                else:
                    await update.message.reply_text(f"❌ Account not found: {username}")
            else:
                await update.message.reply_text("Usage: /accounts remove [username]")
        
        elif context.args[0].lower() == 'list':
            accounts = self.db.get_all_accounts()
            
            if not accounts:
                await update.message.reply_text("📱 No accounts configured.")
                return
            
            account_text = "📱 *All Accounts:*\n\n"
            for acc in accounts:
                status = "✅" if acc['is_active'] else "❌"
                account_text += f"{status} {acc['username']} (Health: {acc['health_score']}%)\n"
            
            await update.message.reply_text(account_text, parse_mode=ParseMode.MARKDOWN)
    
    async def proxies_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /proxies command (admin)"""
        user_id = update.effective_user.id
        
        if user_id != self.admin_id:
            await update.message.reply_text("❌ Admin only command.")
            return
        
        if not context.args:
            proxies = self.db.get_all_proxies()
            
            if not proxies:
                await update.message.reply_text("🌐 No proxies configured.")
                return
            
            proxy_text = "🌐 *Proxies:*\n\n"
            for proxy in proxies[:20]:
                status = "✅" if proxy['is_active'] else "❌"
                proxy_text += f"{status} `{proxy['proxy']}`\n"
            
            proxy_text += "\n*Commands:*\n"
            proxy_text += "/proxies add [proxy]\n"
            proxy_text += "/proxies remove [proxy]\n"
            proxy_text += "/proxies list\n"
            
            await update.message.reply_text(proxy_text, parse_mode=ParseMode.MARKDOWN)
        
        elif context.args[0].lower() == 'add':
            if len(context.args) >= 2:
                proxy = context.args[1]
                
                if self.db.add_proxy(proxy):
                    await update.message.reply_text(f"✅ Proxy added: {proxy}")
                else:
                    await update.message.reply_text(f"❌ Failed to add proxy")
            else:
                await update.message.reply_text("Usage: /proxies add [proxy]")
        
        elif context.args[0].lower() == 'remove':
            if len(context.args) >= 2:
                proxy = context.args[1]
                
                if self.db.remove_proxy(proxy):
                    await update.message.reply_text(f"✅ Proxy removed: {proxy}")
                else:
                    await update.message.reply_text(f"❌ Proxy not found")
            else:
                await update.message.reply_text("Usage: /proxies remove [proxy]")
        
        elif context.args[0].lower() == 'list':
            proxies = self.db.get_all_proxies()
            
            if not proxies:
                await update.message.reply_text("🌐 No proxies configured.")
                return
            
            proxy_text = "🌐 *All Proxies:*\n\n"
            for proxy in proxies:
                status = "✅" if proxy['is_active'] else "❌"
                proxy_text += f"{status} {proxy['proxy']}\n"
            
            await update.message.reply_text(proxy_text, parse_mode=ParseMode.MARKDOWN)
    
    async def logs_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /logs command (admin)"""
        user_id = update.effective_user.id
        
        if user_id != self.admin_id:
            await update.message.reply_text("❌ Admin only command.")
            return
        
        logs = self.db.get_logs(limit=20)
        
        if not logs:
            await update.message.reply_text("📋 No logs available.")
            return
        
        log_text = "📋 *Recent Activity Logs:*\n\n"
        
        for log in logs[:15]:
            log_text += f"🕐 `{log['timestamp']}`\n"
            log_text += f"👤 User: {log['user_id']}\n"
            log_text += f"🔧 Action: {log['action']}\n"
            log_text += f"📝 Details: {log['details']}\n"
            log_text += "---\n"
        
        await update.message.reply_text(log_text, parse_mode=ParseMode.MARKDOWN)
    
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /broadcast command (admin)"""
        user_id = update.effective_user.id
        
        if user_id != self.admin_id:
            await update.message.reply_text("❌ Admin only command.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "📢 *Broadcast Message*\n\n"
                "Send the message to broadcast to all users:\n"
                "Usage: /broadcast [message]",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        message = ' '.join(context.args)
        
        # Get all users
        users = self.db.get_all_users()
        sent_count = 0
        failed_count = 0
        
        # Save broadcast
        broadcast_id = self.db.add_broadcast(user_id, message)
        
        # Send to all users
        progress_msg = await update.message.reply_text("📢 Broadcasting...")
        
        for user in users:
            if not user['is_banned']:
                try:
                    await context.bot.send_message(
                        user['user_id'],
                        f"📢 *Announcement*\n\n{message}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    sent_count += 1
                    await asyncio.sleep(0.05)  # Rate limiting
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to send to {user['user_id']}: {e}")
        
        # Update broadcast count
        self.db.update_broadcast_count(broadcast_id, sent_count)
        
        await progress_msg.edit_text(
            f"✅ *Broadcast Complete*\n\n"
            f"📤 Sent: {sent_count}\n"
            f"❌ Failed: {failed_count}\n"
            f"👥 Total Users: {len(users)}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def ban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /ban command (admin)"""
        user_id = update.effective_user.id
        
        if user_id != self.admin_id:
            await update.message.reply_text("❌ Admin only command.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /ban [user_id]")
            return
        
        try:
            target_user_id = int(context.args[0])
            self.db.ban_user(target_user_id)
            await update.message.reply_text(f"✅ User {target_user_id} banned.")
            
            # Log
            self.db.add_log(user_id, 'ban_user', f'Banned user {target_user_id}')
            
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")
    
    async def unban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /unban command (admin)"""
        user_id = update.effective_user.id
        
        if user_id != self.admin_id:
            await update.message.reply_text("❌ Admin only command.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /unban [user_id]")
            return
        
        try:
            target_user_id = int(context.args[0])
            self.db.unban_user(target_user_id)
            await update.message.reply_text(f"✅ User {target_user_id} unbanned.")
            
            # Log
            self.db.add_log(user_id, 'unban_user', f'Unbanned user {target_user_id}')
            
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")
    
    # ============ CALLBACK HANDLERS ============
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if data == 'menu_report':
            await query.edit_message_text(
                "🔗 *Report Instagram Profile*\n\n"
                "Send the Instagram profile URL:\n"
                "Example: `https://instagram.com/username`",
                parse_mode=ParseMode.MARKDOWN
            )
            context.user_data['state'] = WAITING_FOR_URL
        
        elif data == 'menu_myreports':
            reports = self.db.get_user_reports(user_id, limit=5)
            
            if not reports:
                await query.edit_message_text("📊 You have no reports yet.")
                return
            
            report_text = "📊 *Your Recent Reports:*\n\n"
            for report in reports:
                status_emoji = {'completed': '✅', 'pending': '⏳', 'failed': '❌'}.get(report['status'], '❓')
                report_text += f"{status_emoji} `{report['target_username']}` - {report['reason']}\n"
            
            await query.edit_message_text(report_text, parse_mode=ParseMode.MARKDOWN)
        
        elif data == 'menu_status':
            stats = self.db.get_stats()
            await query.edit_message_text(
                f"📊 *Bot Status*\n\n"
                f"👥 Users: {stats['total_users']}\n"
                f"📝 Reports: {stats['total_reports']}\n"
                f"📱 Accounts: {stats['active_accounts']}\n"
                f"🌐 Proxies: {stats['active_proxies']}\n\n"
                f"🟢 Online",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data == 'menu_help':
            await query.edit_message_text(
                "📚 *Help*\n\n"
                "/report - Report profile\n"
                "/myreports - View reports\n"
                "/status - Bot status\n"
                "/help - Help\n\n"
                "⚠️ Only report genuine violations!",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data == 'menu_admin' and user_id == self.admin_id:
            keyboard = [
                [InlineKeyboardButton("📊 Statistics", callback_data='admin_stats')],
                [InlineKeyboardButton("📱 Accounts", callback_data='admin_accounts')],
                [InlineKeyboardButton("🌐 Proxies", callback_data='admin_proxies')],
                [InlineKeyboardButton("📋 Logs", callback_data='admin_logs')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "⚙️ *Admin Panel*\n\nSelect an option:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        
        elif data == 'admin_stats':
            stats = self.db.get_stats()
            await query.edit_message_text(
                f"📊 *Statistics*\n\n"
                f"👥 Users: {stats['total_users']}\n"
                f"📝 Reports: {stats['total_reports']}\n"
                f"✅ Completed: {stats['completed_reports']}\n"
                f"📱 Accounts: {stats['active_accounts']}\n"
                f"🌐 Proxies: {stats['active_proxies']}",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data == 'admin_logs':
            logs = self.db.get_logs(limit=10)
            log_text = "📋 *Recent Logs:*\n\n"
            for log in logs[:5]:
                log_text += f"🕐 {log['timestamp']} - {log['action']}\n"
            
            await query.edit_message_text(log_text, parse_mode=ParseMode.MARKDOWN)
        
        elif data.startswith('reason_'):
            await self.handle_reason_selection(update, context)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        user_id = update.effective_user.id
        text = update.message.text
        
        state = context.user_data.get('state')
        
        if state == WAITING_FOR_URL:
            await self.handle_report_url(update, context)
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel command"""
        context.user_data.clear()
        await update.message.reply_text("❌ Operation cancelled.")
        return ConversationHandler.END
    
    # ============ MAIN RUN ============
    
    def run(self):
        """Run the bot"""
        if not self.token:
            logger.error("No bot token found! Set TELEGRAM_BOT_TOKEN in .env")
            return
        
        # Create application
        app = Application.builder().token(self.token).build()
        
        # Setup commands
        asyncio.get_event_loop().run_until_complete(self.setup_commands(app))
        
        # Add handlers
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(CommandHandler("status", self.status_command))
        app.add_handler(CommandHandler("report", self.report_command))
        app.add_handler(CommandHandler("myreports", self.myreports_command))
        app.add_handler(CommandHandler("admin", self.admin_command))
        app.add_handler(CommandHandler("stats", self.stats_command))
        app.add_handler(CommandHandler("accounts", self.accounts_command))
        app.add_handler(CommandHandler("proxies", self.proxies_command))
        app.add_handler(CommandHandler("logs", self.logs_command))
        app.add_handler(CommandHandler("broadcast", self.broadcast_command))
        app.add_handler(CommandHandler("ban", self.ban_command))
        app.add_handler(CommandHandler("unban", self.unban_command))
        app.add_handler(CommandHandler("cancel", self.cancel_command))
        app.add_handler(CallbackQueryHandler(self.button_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Start bot
        logger.info("🤖 Bot started!")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    bot = InstagramReportBot()
    bot.run()
