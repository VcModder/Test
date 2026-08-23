# plugins/referral_system.py
"""
Referral System Plugin
- Generate referral link
- Track referrals
- Award credits
"""

import logging
from typing import Optional, Dict
from plugins.credit_system import CreditSystem

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/referral_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ReferralSystem')

class ReferralSystem:
    def __init__(self, credit_system: CreditSystem, bot_username: str = ""):
        self.credit_system = credit_system
        self.bot_username = bot_username
    
    def generate_referral_link(self, user_id: int) -> str:
        """Generate referral link"""
        referral_code = self.credit_system.get_referral_code(user_id)
        if not referral_code:
            return ""
        
        return f"https://t.me/{self.bot_username}?start=ref_{referral_code}"
    
    def parse_referral(self, start_param: str) -> Optional[str]:
        """Parse referral code from start parameter"""
        if start_param and start_param.startswith('ref_'):
            return start_param[4:]
        return None
    
    def process_referral(self, referral_code: str, new_user_id: int) -> bool:
        """Process referral when new user joins"""
        # Find referrer by code
        import sqlite3
        
        conn = sqlite3.connect(self.credit_system.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (referral_code,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            referrer_id = row[0]
            if referrer_id != new_user_id:
                return self.credit_system.process_referral(referrer_id, new_user_id)
        
        return False
    
    def get_referral_stats(self, user_id: int) -> str:
        """Get referral statistics"""
        count = self.credit_system.get_referral_count(user_id)
        code = self.credit_system.get_referral_code(user_id)
        
        text = f"""
👥 *Referral Stats*

🔗 Your Code: `{code}`
📊 Total Referrals: `{count}`
💰 Credits Earned: `{count * 2}`

*Share your referral link:*
`https://t.me/{self.bot_username}?start=ref_{code}`

*Reward:* 2 credits per referral
"""
        return text
