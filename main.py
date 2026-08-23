#!/usr/bin/env python3
"""
Instagram Report Bot - Complete with Plugins
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
from plugins.account_manager import AccountManager
from plugins.credit_system import CreditSystem
from plugins.referral_system import ReferralSystem
from plugins.channel_force import ChannelForce

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('InstagramReportBot')
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

WAITING_FOR_URL = 1

class InstagramReportBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.admin_id = int(os.getenv('ADMIN_USER_ID', '0'))
        self.db = Database()
        self.report_engine = ReportEngine(self.db)
        
        # Initialize plugins
        self.account_manager = AccountManager(self.db)
        self.credit_system = CreditSystem()
        self.referral_system = ReferralSystem(self.credit_system, "@Instatounfollow_bot")
        self.channel_force = ChannelForce()
        
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
            BotCommand("add", "📱 Add Instagram account"),
            BotCommand("credits", "💳 Check credits"),
            BotCommand("referral", "👥 Referral system"),
            BotCommand("myreports", "📊 View my reports"),
            BotCommand("status", "📈 Bot status"),
            BotCommand("help", "ℹ️ Help"),
            BotCommand("admin", "⚙️ Admin panel"),
            BotCommand("givecredits", "💰 Give credits"),
            BotCommand("removecredits", "💸 Remove credits"),
            BotCommand("channel", "📢 Channel settings"),
            BotCommand("broadcast", "📢 Broadcast"),
            BotCommand("logs", "📋 View logs"),
            BotCommand("stats", "📊 Statistics"),
            BotCommand("ban", "🚫 Ban user"),
            BotCommand("unban", "✅ Unban user")
        ]
        await app.bot.set_my_commands(commands)
    
    # ============ START ============
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start"""
        user = update.effective_user
        
        # Check channel membership
        if self.channel_force.is_enabled():
            is_member = await self.channel_force.check_membership(context, user.id)
            if not is_member:
                await update.message.reply_text(
                    self.channel_force.get_welcome_message(),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=self.channel_force.get_join_keyboard()
                )
                return
        
        # Save user
        self.db.add_user(user.id, user.username or '', user.first_name)
        
        # Create credit user
        if not self.credit_system.get_user(user.id):
            self.credit_system.create_user(user.id, user.username or '', user.first_name)
        
        # Check referral
        if context.args and context.args[0].startswith('ref_'):
            referral_code = context.args[0][4:]
            if self.referral_system.process_referral(referral_code, user.id):
                await update.message.reply_text("🎉 Referral bonus credited!")
        
        credits = self.credit_system.get_credits(user.id)
        
        keyboard = [
            [InlineKeyboardButton("🎯 Report Profile", callback_data='menu_report')],
            [InlineKeyboardButton("📊 My Reports", callback_data='menu_myreports')],
            [InlineKeyboardButton("💳 Credits", callback_data='menu_credits')],
            [InlineKeyboardButton("👥 Referral", callback_data='menu_referral')],
            [InlineKeyboardButton("📈 Status", callback_data='menu_status')],
            [InlineKeyboardButton("ℹ️ Help", callback_data='menu_help')],
        ]
        
        if user.id == self.admin_id:
            keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data='menu_admin')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = f"""
🎯 *Instagram Report Bot*

Welcome {user.first_name}!

💳 Your Credits: `{credits}`

*Commands:*
/report - Report profile (4 credits)
/add - Add account (4 credits)
/credits - Check credits
/referral - Referral link (2 credits)

⚠️ *Only report genuine violations!*
"""
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
        self.db.add_log(user.id, 'start', 'User started bot')
    
    # ============ HELP ============
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help"""
        help_text = """
📚 *Help & Commands*

*User Commands:*
/start - Start bot
/report - Report profile (4 credits)
/add - Add account (4 credits)
/credits - Check credits
/referral - Referral link
/myreports - View reports
/status - Bot status

*How to Report:*
1. /report
2. Enter Instagram URL
3. Select reason

*How to Add Account:*
/add username password

⚠️ *Only report genuine violations!*
"""
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    # ============ STATUS ============
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status"""
        stats = self.db.get_stats()
        
        status_text = f"""
📊 *Bot Status*

👥 Users: {stats['total_users']}
📝 Reports: {stats['total_reports']}
✅ Completed: {stats['completed_reports']}
⏳ Pending: {stats['pending_reports']}
📱 Accounts: {stats['active_accounts']}
🌐 Proxies: {stats['active_proxies']}

🟢 Online
"""
        await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
    
    # ============ REPORT ============
    
    async def report_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /report"""
        user = update.effective_user
        
        user_data = self.db.get_user(user.id)
        if user_data and user_data['is_banned']:
            await update.message.reply_text("❌ You are banned.")
            return
        
        # Check channel
        if self.channel_force.is_enabled():
            is_member = await self.channel_force.check_membership(context, user.id)
            if not is_member:
                await update.message.reply_text(
                    self.channel_force.get_welcome_message(),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=self.channel_force.get_join_keyboard()
                )
                return
        
        # Check credits
        credits = self.credit_system.get_credits(user.id)
        if credits < 4:
            await update.message.reply_text(
                f"❌ *Insufficient Credits*\n\n"
                f"Need 4 credits. You have: {credits}\n"
                f"Earn via /referral",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        if context.args:
            target_url = context.args[0]
            context.user_data['target_url'] = target_url
            await self.show_reason_selection(update, context)
        else:
            await update.message.reply_text(
                "🔗 *Report Instagram Profile*\n\n"
                "Send Instagram URL:\n"
                "Example: `https://instagram.com/username`",
                parse_mode=ParseMode.MARKDOWN
            )
            context.user_data['state'] = WAITING_FOR_URL
    
    async def handle_report_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle URL input"""
        target_url = update.message.text.strip()
        
        if 'instagram.com' not in target_url and '/' in target_url:
            await update.message.reply_text(
                "❌ Invalid URL. Example: `https://instagram.com/username`",
                parse_mode=ParseMode.MARKDOWN
            )
            return WAITING_FOR_URL
        
        context.user_data['target_url'] = target_url
        await self.show_reason_selection(update, context)
        return ConversationHandler.END
    
    async def show_reason_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show reasons"""
        keyboard = []
        reasons_list = list(self.report_reasons.items())
        
        for i in range(0, len(reasons_list), 2):
            row = []
            for reason_key, reason_label in reasons_list[i:i+2]:
                row.append(InlineKeyboardButton(reason_label, callback_data=f'reason_{reason_key}'))
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data='cancel')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        target_url = context.user_data.get('target_url', 'Unknown')
        
        await update.message.reply_text(
            f"🎯 *Target:* `{target_url}`\n\nSelect reason:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def handle_reason_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle reason"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'cancel':
            await query.edit_message_text("❌ Cancelled.")
            return
        
        reason = query.data.replace('reason_', '')
        target_url = context.user_data.get('target_url', '')
        user_id = query.from_user.id
        
        # Spend credits
        if not self.credit_system.spend_credits(user_id, 4, f"Report: {target_url}"):
            await query.edit_message_text("❌ Insufficient credits!")
            return
        
        reason_label = self.report_reasons.get(reason, reason)
        
        await query.edit_message_text(
            f"🔄 *Processing*\n\n"
            f"Target: `{target_url}`\n"
            f"Reason: {reason_label}\n"
            f"Credits spent: 4\n\n"
            f"⏳ Please wait...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        asyncio.create_task(self.process_report(query, target_url, reason, user_id))
    
    async def process_report(self, query, target_url: str, reason: str, user_id: int):
        """Process report"""
        stop_animation = asyncio.Event()
        animation_task = asyncio.create_task(
            self.animate_processing(query, target_url, reason, stop_animation)
        )
        try:
            result = await self.report_engine.execute_report(target_url, reason, user_id)
            
            if result['success']:
                success_count = result.get('success_count', 0)
                accounts_used = result.get('accounts_used', 0)
                
                await query.edit_message_text(
                    f"✅ *Report Completed!*\n\n"
                    f"Target: `{target_url}`\n"
                    f"Reason: {reason}\n"
                    f"Accounts: {accounts_used}\n"
                    f"Success: {success_count}/{accounts_used}",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                # Refund
                self.credit_system.add_credits(user_id, 4, "Refund - Failed")
                
                await query.edit_message_text(
                    f"❌ *Failed*\n\n"
                    f"Error: {result.get('error', 'Unknown')}\n"
                    f"Credits refunded: 4",
                    parse_mode=ParseMode.MARKDOWN
                )
        except Exception as e:
            self.credit_system.add_credits(user_id, 4, "Refund - Error")
            logger.exception("Unexpected report error for user %s", user_id)
            try:
                await query.edit_message_text(
                    "❌ *Report Error*\n\n"
                    f"`{str(e)}`\n\n"
                    "Credits refunded: 4",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception:
                pass
        finally:
            stop_animation.set()
            animation_task.cancel()
            try:
                await animation_task
            except asyncio.CancelledError:
                pass

    async def animate_processing(self, query, target_url: str, reason: str, stop_event: asyncio.Event):
        """Show lightweight progress feedback while a report is running."""
        frames = ["⏳", "⌛", "🔄"]
        index = 0
        while not stop_event.is_set():
            try:
                await query.edit_message_text(
                    f"{frames[index % len(frames)]} *Processing report...*\n\n"
                    f"Target: `{target_url}`\n"
                    f"Reason: {reason}\n\n"
                    "Please wait while the report is submitted.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception:
                logger.debug("Could not update report progress message", exc_info=True)
                return
            index += 1
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=0.9)
            except asyncio.TimeoutError:
                continue
    
    async def myreports_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /myreports"""
        user_id = update.effective_user.id
        reports = self.db.get_user_reports(user_id, limit=10)
        
        if not reports:
            await update.message.reply_text("📊 No reports yet.")
            return
        
        report_text = "📊 *Your Reports:*\n\n"
        for report in reports[:5]:
            status_emoji = {'completed': '✅', 'pending': '⏳', 'failed': '❌'}.get(report['status'], '❓')
            report_text += f"{status_emoji} `{report['target_username']}` - {report['reason']}\n"
        
        await update.message.reply_text(report_text, parse_mode=ParseMode.MARKDOWN)
    
    # ============ PLUGIN COMMANDS ============
    
    async def add_account_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /add"""
        user = update.effective_user
        
        user_data = self.db.get_user(user.id)
        if user_data and user_data['is_banned']:
            await update.message.reply_text("❌ Banned.")
            return
        
        if self.channel_force.is_enabled():
            is_member = await self.channel_force.check_membership(context, user.id)
            if not is_member:
                await update.message.reply_text(
                    self.channel_force.get_welcome_message(),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=self.channel_force.get_join_keyboard()
                )
                return
        
        credits = self.credit_system.get_credits(user.id)
        if credits < 4:
            await update.message.reply_text(
                f"❌ Need 4 credits. You have: {credits}\n/referral to earn",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "📱 *Add Account*\n\n"
                "Usage: `/add username password`\n"
                "Example: `/add myuser mypass123`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        username = context.args[0].replace('@', '')
        password = context.args[1]
        
        if self.account_manager.check_account_exists(username):
            await update.message.reply_text(f"❌ Account `{username}` exists!", parse_mode=ParseMode.MARKDOWN)
            return
        
        status_msg = await update.message.reply_text(
            f"⏳ *Verifying...*\n\nUsername: `{username}`\nPassword: `{password}`",
            parse_mode=ParseMode.MARKDOWN
        )
        
        result = self.account_manager.add_account(username, password)
        
        if result['success']:
            self.credit_system.spend_credits(user.id, 4, f"Added: {username}")
        
        await status_msg.edit_text(result['message'], parse_mode=ParseMode.MARKDOWN)
        self.db.add_log(user.id, 'add_account', f"Added: {username} - Success: {result['success']}")
    
    async def remove_account_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /removeacc"""
        user = update.effective_user
        
        if user.id != self.admin_id:
            await update.message.reply_text("❌ Admin only.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /removeacc username")
            return
        
        result = self.account_manager.remove_account(context.args[0])
        await update.message.reply_text(result['message'], parse_mode=ParseMode.MARKDOWN)
    
    async def list_accounts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /myacc"""
        user = update.effective_user
        
        if user.id != self.admin_id:
            await update.message.reply_text("❌ Admin only.")
            return
        
        text = self.account_manager.list_accounts()
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    async def credits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /credits"""
        user = update.effective_user
        
        if not self.credit_system.get_user(user.id):
            self.credit_system.create_user(user.id, user.username or '', user.first_name)
        
        summary = self.credit_system.get_credit_summary(user.id)
        await update.message.reply_text(summary, parse_mode=ParseMode.MARKDOWN)
    
    async def give_credits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /givecredits"""
        user = update.effective_user
        
        if user.id != self.admin_id:
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
            self.db.add_log(user.id, 'give_credits', f'{amount} to {target_id}')
        except ValueError:
            await update.message.reply_text("❌ Invalid.")
    
    async def remove_credits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /removecredits"""
        user = update.effective_user
        
        if user.id != self.admin_id:
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
        """Handle /referral"""
        user = update.effective_user
        
        if not self.credit_system.get_user(user.id):
            self.credit_system.create_user(user.id, user.username or '', user.first_name)
        
        stats = self.referral_system.get_referral_stats(user.id)
        await update.message.reply_text(stats, parse_mode=ParseMode.MARKDOWN)
    
    async def channel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /channel"""
        user = update.effective_user
        
        if user.id != self.admin_id:
            await update.message.reply_text("❌ Admin only.")
            return
        
        if not context.args:
            channels = self.channel_force.list_channels()
            status = "✅ Enabled" if self.channel_force.is_enabled() else "❌ Disabled"
            
            text = f"📢 *Channels*\n\nStatus: {status}\n\n"
            for ch in channels:
                text += f"• @{ch}\n"
            
            text += "\n/channel add @username\n/channel remove @username"
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        
        elif context.args[0].lower() == 'add':
            if len(context.args) < 2:
                await update.message.reply_text("Usage: /channel add @username")
                return
            
            channel = context.args[1].replace('@', '')
            if self.channel_force.add_channel(channel):
                await update.message.reply_text(f"✅ @{channel} added!")
            else:
                await update.message.reply_text("❌ Exists!")
        
        elif context.args[0].lower() == 'remove':
            if len(context.args) < 2:
                await update.message.reply_text("Usage: /channel remove @username")
                return
            
            channel = context.args[1].replace('@', '')
            if self.channel_force.remove_channel(channel):
                await update.message.reply_text(f"✅ @{channel} removed!")
            else:
                await update.message.reply_text("❌ Not found!")
    
    # ============ ADMIN ============
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /admin"""
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
        """Handle /stats"""
        if update.effective_user.id != self.admin_id:
            return
        
        stats = self.db.get_stats()
        
        text = f"""
📊 *Stats*

👥 Users: {stats['total_users']}
📝 Reports: {stats['total_reports']}
📱 Accounts: {stats['active_accounts']}
🌐 Proxies: {stats['active_proxies']}
"""
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    async def logs_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /logs"""
        if update.effective_user.id != self.admin_id:
            return
        
        logs = self.db.get_logs(limit=10)
        
        text = "📋 *Recent Logs:*\n\n"
        for log in logs[:5]:
            text += f"🕐 {log['timestamp']} - {log['action']}\n"
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /broadcast"""
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
        """Handle /ban"""
        if update.effective_user.id != self.admin_id:
            return
        
        if context.args:
            try:
                self.db.ban_user(int(context.args[0]))
                await update.message.reply_text("✅ Banned")
            except:
                await update.message.reply_text("❌ Invalid")
    
    async def unban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /unban"""
        if update.effective_user.id != self.admin_id:
            return
        
        if context.args:
            try:
                self.db.unban_user(int(context.args[0]))
                await update.message.reply_text("✅ Unbanned")
            except:
                await update.message.reply_text("❌ Invalid")
    
    # ============ BUTTONS ============
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle buttons"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
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
            if not self.credit_system.get_user(user_id):
                self.credit_system.create_user(user_id, '', '')
            
            summary = self.credit_system.get_credit_summary(user_id)
            await query.edit_message_text(summary, parse_mode=ParseMode.MARKDOWN)
        
        elif data == 'menu_referral':
            if not self.credit_system.get_user(user_id):
                self.credit_system.create_user(user_id, '', '')
            
            stats = self.referral_system.get_referral_stats(user_id)
            await query.edit_message_text(stats, parse_mode=ParseMode.MARKDOWN)
        
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
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back to Menu", callback_data='menu_home')]
                ])
            )

        elif data == 'menu_home':
            credits = self.credit_system.get_credits(user_id)
            keyboard = [
                [InlineKeyboardButton("🎯 Report Profile", callback_data='menu_report')],
                [InlineKeyboardButton("📊 My Reports", callback_data='menu_myreports')],
                [InlineKeyboardButton("💳 Credits", callback_data='menu_credits')],
                [InlineKeyboardButton("👥 Referral", callback_data='menu_referral')],
                [InlineKeyboardButton("📈 Status", callback_data='menu_status')],
                [InlineKeyboardButton("ℹ️ Help", callback_data='menu_help')],
            ]
            if user_id == self.admin_id:
                keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data='menu_admin')])
            await query.edit_message_text(
                f"🎯 *Instagram Report Bot*\n\n"
                f"Welcome back!\n\n"
                f"💳 Your Credits: `{credits}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
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
            is_member = await self.channel_force.check_membership(context, user_id)
            if is_member:
                await query.edit_message_text("✅ Verified!")
            else:
                await query.answer("❌ Join all channels first!", show_alert=True)
        
        elif data.startswith('reason_'):
            await self.handle_reason_selection(update, context)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages"""
        state = context.user_data.get('state')
        
        if state == WAITING_FOR_URL:
            await self.handle_report_url(update, context)
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel"""
        context.user_data.clear()
        await update.message.reply_text("❌ Cancelled.")
        return ConversationHandler.END
    
    # ============ RUN ============
    
    def run(self):
        """Run bot"""
        if not self.token:
            logger.error("No token! Set TELEGRAM_BOT_TOKEN in .env")
            return
        
        app = Application.builder().token(self.token).build()
        asyncio.run(self.setup_commands(app))
        
        # All handlers
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
        
        logger.info("🤖 Bot started!")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    bot = InstagramReportBot()
    bot.run()
