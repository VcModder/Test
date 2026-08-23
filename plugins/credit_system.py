# plugins/credit_system.py
"""
Credit System Plugin
- Per referral: 2 credits
- Per report use: 4 credits
- Admin can give/remove credits
"""

import os
import json
import sqlite3
import logging
from typing import Dict, Optional
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/credit_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('CreditSystem')

class CreditSystem:
    def __init__(self, db_path: str = 'data/bot.db'):
        self.db_path = db_path
        self.ensure_db()
    
    def ensure_db(self):
        """Ensure database exists"""
        os.makedirs('data', exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table with credits
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                credits INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0,
                total_spent INTEGER DEFAULT 0,
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                is_banned BOOLEAN DEFAULT 0,
                joined_date TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Credit transactions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS credit_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                transaction_type TEXT,
                description TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Referrals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER,
                credits_awarded INTEGER DEFAULT 2,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Credit system database ready")
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'user_id': row[0],
                'username': row[1],
                'first_name': row[2],
                'credits': row[3],
                'total_earned': row[4],
                'total_spent': row[5],
                'referral_code': row[6],
                'referred_by': row[7],
                'is_banned': row[8]
            }
        return None
    
    def create_user(self, user_id: int, username: str, first_name: str) -> Dict:
        """Create new user with referral code"""
        import random
        import string
        
        # Generate unique referral code
        referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, referral_code)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, referral_code))
        
        conn.commit()
        conn.close()
        
        return self.get_user(user_id)
    
    def get_credits(self, user_id: int) -> int:
        """Get user credits"""
        user = self.get_user(user_id)
        return user['credits'] if user else 0
    
    def add_credits(self, user_id: int, amount: int, description: str = "Credit added") -> bool:
        """Add credits to user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users 
            SET credits = credits + ?, total_earned = total_earned + ?
            WHERE user_id = ?
        ''', (amount, amount, user_id))
        
        # Log transaction
        cursor.execute('''
            INSERT INTO credit_transactions (user_id, amount, transaction_type, description)
            VALUES (?, ?, 'credit', ?)
        ''', (user_id, amount, description))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Added {amount} credits to user {user_id}")
        return True
    
    def remove_credits(self, user_id: int, amount: int, description: str = "Credit removed") -> bool:
        """Remove credits from user"""
        user = self.get_user(user_id)
        if not user or user['credits'] < amount:
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users 
            SET credits = credits - ?
            WHERE user_id = ?
        ''', (amount, user_id))
        
        # Log transaction
        cursor.execute('''
            INSERT INTO credit_transactions (user_id, amount, transaction_type, description)
            VALUES (?, ?, 'debit', ?)
        ''', (user_id, amount, description))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Removed {amount} credits from user {user_id}")
        return True
    
    def spend_credits(self, user_id: int, amount: int = 4, description: str = "Report used") -> bool:
        """Spend credits for report"""
        user = self.get_user(user_id)
        if not user or user['credits'] < amount:
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users 
            SET credits = credits - ?, total_spent = total_spent + ?
            WHERE user_id = ?
        ''', (amount, amount, user_id))
        
        cursor.execute('''
            INSERT INTO credit_transactions (user_id, amount, transaction_type, description)
            VALUES (?, ?, 'spend', ?)
        ''', (user_id, amount, description))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Spent {amount} credits from user {user_id}")
        return True
    
    def process_referral(self, referrer_id: int, referred_id: int) -> bool:
        """Process referral - give 2 credits to referrer"""
        # Check if already referred
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM referrals WHERE referred_id = ?', (referred_id,))
        existing = cursor.fetchone()
        
        if existing:
            conn.close()
            return False
        
        # Add referral record
        cursor.execute('''
            INSERT INTO referrals (referrer_id, referred_id, credits_awarded)
            VALUES (?, ?, 2)
        ''', (referrer_id, referred_id))
        
        # Update referred_by
        cursor.execute('UPDATE users SET referred_by = ? WHERE user_id = ?', (referrer_id, referred_id))
        
        conn.commit()
        conn.close()
        
        # Give 2 credits to referrer
        self.add_credits(referrer_id, 2, f"Referral bonus - User {referred_id}")
        
        logger.info(f"✅ Referral processed: {referrer_id} referred {referred_id}")
        return True
    
    def get_referral_code(self, user_id: int) -> str:
        """Get user's referral code"""
        user = self.get_user(user_id)
        return user['referral_code'] if user else ''
    
    def get_referral_count(self, user_id: int) -> int:
        """Get count of referrals"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (user_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def get_transaction_history(self, user_id: int, limit: int = 10) -> list:
        """Get credit transaction history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM credit_transactions 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (user_id, limit))
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def get_credit_summary(self, user_id: int) -> str:
        """Get formatted credit summary"""
        user = self.get_user(user_id)
        if not user:
            return "User not found"
        
        referral_count = self.get_referral_count(user_id)
        referral_code = self.get_referral_code(user_id)
        
        text = f"""
💳 *Credit Summary*

👤 User: `{user['first_name']}`
💰 Available Credits: `{user['credits']}`
📈 Total Earned: `{user['total_earned']}`
📉 Total Spent: `{user['total_spent']}`

👥 Referrals: `{referral_count}`
🔗 Referral Code: `{referral_code}`

*Cost:* 4 credits per report
*Earn:* 2 credits per referral
"""
        return text
