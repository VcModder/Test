# plugins/commands.py
"""
Command Handlers for all plugins
Copy these methods into your main bot class
"""

async def add_account_command(self, update, context):
    """Handle /add command - Add Instagram account"""
    user = update.effective_user
    
    # Check if user is banned
    user_data = self.db.get_user(user.id)
    if user_data and user_data['is_banned']:
        await update.message.reply_text("❌ You are banned.")
        return
    
    # Check credits
    credits = self.credit_system.get_credits(user.id)
    if credits < 4:
        await update.message.reply_text(
            f"❌ *Insufficient Credits*\n\n"
            f"You need 4 credits to add account.\n"
            f"Your credits: {credits}\n\n"
            f"Get credits via referral: /referral",
            parse_mode='Markdown'
        )
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "📱 *Add Instagram Account*\n\n"
            "Usage: `/add username password`\n\n"
            "Example: `/add myuser mypass123`\n\n"
            "⚠️ Account will be verified before adding.",
            parse_mode='Markdown'
        )
        return
    
    username = context.args[0].replace('@', '')
    password = context.args[1]
    
    # Check if account already exists
    if self.account_manager.check_account_exists(username):
        await update.message.reply_text(
            f"❌ Account `{username}` already exists!",
            parse_mode='Markdown'
        )
        return
    
    # Send verifying message
    status_msg = await update.message.reply_text(
        f"⏳ *Verifying Account...*\n\n"
        f"Username: `{username}`\n"
        f"Password: `{password}`\n\n"
        f"Please wait...",
        parse_mode='Markdown'
    )
    
    # Verify and add account
    result = self.account_manager.add_account(username, password)
    
    if result['success']:
        # Spend credits
        self.credit_system.spend_credits(user.id, 4, f"Added account: {username}")
        
        await status_msg.edit_text(
            result['message'],
            parse_mode='Markdown'
        )
    else:
        await status_msg.edit_text(
            result['message'],
            parse_mode='Markdown'
        )
    
    # Log
    self.db.add_log(user.id, 'add_account', f"Added account: {username} - Success: {result['success']}")

async def remove_account_command(self, update, context):
    """Handle /removeacc command"""
    user = update.effective_user
    
    # Only admin can remove
    if user.id != self.admin_id:
        await update.message.reply_text("❌ Admin only command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /removeacc username")
        return
    
    username = context.args[0]
    result = self.account_manager.remove_account(username)
    
    await update.message.reply_text(result['message'], parse_mode='Markdown')

async def list_accounts_command(self, update, context):
    """Handle /myacc command"""
    user = update.effective_user
    
    # Only admin can see all accounts
    if user.id != self.admin_id:
        await update.message.reply_text("❌ Admin only command.")
        return
    
    accounts_text = self.account_manager.list_accounts()
    await update.message.reply_text(accounts_text, parse_mode='Markdown')

async def credits_command(self, update, context):
    """Handle /credits command"""
    user = update.effective_user
    
    # Create user if not exists
    if not self.credit_system.get_user(user.id):
        self.credit_system.create_user(user.id, user.username or '', user.first_name)
    
    summary = self.credit_system.get_credit_summary(user.id)
    await update.message.reply_text(summary, parse_mode='Markdown')

async def give_credits_command(self, update, context):
    """Handle /givecredits command - Admin"""
    user = update.effective_user
    
    if user.id != self.admin_id:
        await update.message.reply_text("❌ Admin only command.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /givecredits user_id amount")
        return
    
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        
        # Ensure user exists
        if not self.credit_system.get_user(target_id):
            self.credit_system.create_user(target_id, '', '')
        
        self.credit_system.add_credits(target_id, amount, f"Admin granted")
        
        await update.message.reply_text(
            f"✅ *Credits Added*\n\n"
            f"User: `{target_id}`\n"
            f"Amount: `{amount}`\n"
            f"Description: Admin grant",
            parse_mode='Markdown'
        )
        
        # Log
        self.db.add_log(user.id, 'give_credits', f'Gave {amount} credits to {target_id}')
        
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or amount.")

async def remove_credits_command(self, update, context):
    """Handle /removecredits command - Admin"""
    user = update.effective_user
    
    if user.id != self.admin_id:
        await update.message.reply_text("❌ Admin only command.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /removecredits user_id amount")
        return
    
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        
        success = self.credit_system.remove_credits(target_id, amount, "Admin removed")
        
        if success:
            await update.message.reply_text(
                f"✅ *Credits Removed*\n\n"
                f"User: `{target_id}`\n"
                f"Amount: `{amount}`",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Failed to remove credits. Check balance.")
        
        # Log
        self.db.add_log(user.id, 'remove_credits', f'Removed {amount} credits from {target_id}')
        
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or amount.")

async def referral_command(self, update, context):
    """Handle /referral command"""
    user = update.effective_user
    
    # Create user if not exists
    if not self.credit_system.get_user(user.id):
        self.credit_system.create_user(user.id, user.username or '', user.first_name)
    
    stats = self.referral_system.get_referral_stats(user.id)
    await update.message.reply_text(stats, parse_mode='Markdown')

async def channel_command(self, update, context):
    """Handle /channel command - Admin"""
    user = update.effective_user
    
    if user.id != self.admin_id:
        await update.message.reply_text("❌ Admin only command.")
        return
    
    if not context.args:
        channels = self.channel_force.list_channels()
        status = "Enabled" if self.channel_force.is_enabled() else "Disabled"
        
        text = f"📢 *Channel Settings*\n\nStatus: {status}\n\n*Channels:*\n"
        for ch in channels:
            text += f"• @{ch}\n"
        
        text += "\n*Commands:*\n"
        text += "/channel add @username\n"
        text += "/channel remove @username\n"
        text += "/channel list\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    elif context.args[0].lower() == 'add':
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /channel add @username")
            return
        
        channel = context.args[1]
        if self.channel_force.add_channel(channel):
            await update.message.reply_text(f"✅ Channel @{channel} added!")
        else:
            await update.message.reply_text(f"❌ Channel already exists!")
    
    elif context.args[0].lower() == 'remove':
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /channel remove @username")
            return
        
        channel = context.args[1]
        if self.channel_force.remove_channel(channel):
            await update.message.reply_text(f"✅ Channel @{channel} removed!")
        else:
            await update.message.reply_text(f"❌ Channel not found!")
    
    elif context.args[0].lower() == 'list':
        channels = self.channel_force.list_channels()
        
        if not channels:
            await update.message.reply_text("No channels added.")
            return
        
        text = "📢 *Channels:*\n\n"
        for ch in channels:
            text += f"• @{ch}\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')

async def check_membership_callback(self, update, context):
    """Handle membership check callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Check membership
    is_member = await self.channel_force.check_membership(context, user_id)
    
    if is_member:
        await query.edit_message_text(
            "✅ *Membership Verified!*\n\n"
            "You can now use the bot.",
            parse_mode='Markdown'
        )
    else:
        await query.answer("❌ Please join all channels first!", show_alert=True)
