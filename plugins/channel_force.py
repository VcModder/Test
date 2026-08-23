# plugins/channel_force.py
"""
Channel Force Plugin
- Force users to join channel before using bot
- Admin can set/change channel
- Check membership status
"""

import os
import json
import logging
from typing import Optional, Dict, List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/channel_force.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ChannelForce')

class ChannelForce:
    def __init__(self):
        self.config_file = 'config/channel_config.json'
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """Load channel configuration"""
        os.makedirs('config', exist_ok=True)
        
        default_config = {
            "channels": [],
            "enabled": False,
            "welcome_message": "⚠️ *Join Required!*\n\nPlease join our channel to use this bot.",
            "join_button_text": "📢 Join Channel",
            "check_button_text": "✅ I've Joined"
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                return default_config
        else:
            with open(self.config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            return default_config
    
    def save_config(self):
        """Save channel configuration"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def add_channel(self, channel_username: str) -> bool:
        """Add channel to force join list"""
        channel_username = channel_username.replace('@', '')
        
        if channel_username not in self.config['channels']:
            self.config['channels'].append(channel_username)
            self.config['enabled'] = True
            self.save_config()
            logger.info(f"✅ Channel added: {channel_username}")
            return True
        return False
    
    def remove_channel(self, channel_username: str) -> bool:
        """Remove channel from force join list"""
        channel_username = channel_username.replace('@', '')
        
        if channel_username in self.config['channels']:
            self.config['channels'].remove(channel_username)
            if not self.config['channels']:
                self.config['enabled'] = False
            self.save_config()
            logger.info(f"✅ Channel removed: {channel_username}")
            return True
        return False
    
    def list_channels(self) -> List[str]:
        """List all channels"""
        return self.config['channels']
    
    def is_enabled(self) -> bool:
        """Check if force join is enabled"""
        return self.config['enabled'] and len(self.config['channels']) > 0
    
    async def check_membership(self, context, user_id: int) -> bool:
        """Check if user is member of all channels"""
        if not self.is_enabled():
            return True
        
        for channel in self.config['channels']:
            try:
                member = await context.bot.get_chat_member(
                    chat_id=f"@{channel}",
                    user_id=user_id
                )
                
                if member.status in ['left', 'kicked', 'banned']:
                    return False
                    
            except Exception as e:
                logger.error(f"Failed to check membership for {channel}: {e}")
                return False
        
        return True
    
    def get_join_keyboard(self) -> InlineKeyboardMarkup:
        """Get keyboard with channel join buttons"""
        keyboard = []
        
        for channel in self.config['channels']:
            keyboard.append([
                InlineKeyboardButton(
                    f"📢 Join @{channel}",
                    url=f"https://t.me/{channel}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton(
                self.config['check_button_text'],
                callback_data='check_membership'
            )
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_welcome_message(self) -> str:
        """Get welcome/join required message"""
        channels_text = "\n".join([f"• @{ch}" for ch in self.config['channels']])
        
        message = (
            f"{self.config['welcome_message']}\n\n"
            f"*Channels:*\n{channels_text}\n\n"
            f"Join all channels then click 'I've Joined' button."
        )
        
        return message
