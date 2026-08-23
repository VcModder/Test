# plugins/account_manager.py
"""
Account Manager Plugin - Add/Verify Instagram Accounts
User and Admin dono add kar sakte hain
"""

import os
import json
import logging
from typing import Optional, Dict
from datetime import datetime
from instagram_api import InstagramAPI

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/account_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('AccountManager')

class AccountManager:
    def __init__(self, database=None):
        self.database = database
        self.api = InstagramAPI()
        self.accounts_file = 'config/accounts.json'
        self.ensure_file_exists()
    
    def ensure_file_exists(self):
        """Ensure accounts.json exists"""
        os.makedirs('config', exist_ok=True)
        if not os.path.exists(self.accounts_file):
            with open(self.accounts_file, 'w') as f:
                json.dump([], f)
    
    def load_accounts(self) -> list:
        """Load accounts from file"""
        try:
            with open(self.accounts_file, 'r') as f:
                return json.load(f)
        except:
            return []
    
    def save_accounts(self, accounts: list):
        """Save accounts to file"""
        with open(self.accounts_file, 'w') as f:
            json.dump(accounts, f, indent=2)
    
    def verify_login(self, username: str, password: str) -> bool:
        """Verify Instagram login credentials"""
        try:
            logger.info(f"Verifying login for {username}...")
            
            # Try to login
            session_data = self.api.login(username, password)
            
            if session_data:
                logger.info(f"✅ Login verified for {username}")
                return True
            else:
                logger.warning(f"❌ Login failed for {username}")
                return False
                
        except Exception as e:
            logger.error(f"Verification error for {username}: {e}")
            return False
    
    def add_account(self, username: str, password: str, proxy: str = "") -> Dict:
        """Add account after verification"""
        result = {
            'success': False,
            'message': '',
            'username': username
        }
        
        # Load existing accounts
        accounts = self.load_accounts()
        
        # Check if account already exists
        for acc in accounts:
            if acc.get('username') == username:
                result['message'] = f"❌ Account `{username}` already exists!"
                return result
        
        # Verify login
        result['message'] = f"⏳ Verifying login for `{username}`..."
        
        is_valid = self.verify_login(username, password)
        
        if not is_valid:
            result['message'] = f"❌ *Invalid Login!*\n\nUsername: `{username}`\nPassword: `{password}`\n\n⚠️ Please check credentials and try again."
            result['invalid'] = True
            return result
        
        # Create account object
        new_account = {
            "username": username,
            "password": password,
            "proxy": proxy,
            "is_active": True,
            "health_score": 100,
            "reports_today": 0,
            "max_daily_reports": 5,
            "total_reports": 0,
            "last_report_time": None,
            "consecutive_failures": 0,
            "added_by": "user",
            "added_at": datetime.now().isoformat()
        }
        
        # Add to accounts
        accounts.append(new_account)
        self.save_accounts(accounts)
        
        # Also add to database if available
        if self.database:
            try:
                self.database.add_account(username, password, proxy)
            except:
                pass
        
        result['success'] = True
        result['message'] = (
            f"✅ *Account Added Successfully!*\n\n"
            f"📱 Username: `{username}`\n"
            f"🔐 Password: `{password}`\n"
            f"❤️ Health: 100%\n"
            f"📊 Daily Limit: 5 reports\n\n"
            f"Account verified and ready to use!"
        )
        
        logger.info(f"✅ Account added: {username}")
        return result
    
    def remove_account(self, username: str) -> Dict:
        """Remove account"""
        result = {
            'success': False,
            'message': ''
        }
        
        accounts = self.load_accounts()
        
        # Find and remove
        new_accounts = [acc for acc in accounts if acc.get('username') != username]
        
        if len(new_accounts) == len(accounts):
            result['message'] = f"❌ Account `{username}` not found!"
            return result
        
        self.save_accounts(new_accounts)
        
        # Remove from database
        if self.database:
            try:
                self.database.remove_account(username)
            except:
                pass
        
        result['success'] = True
        result['message'] = f"✅ Account `{username}` removed successfully!"
        
        logger.info(f"✅ Account removed: {username}")
        return result
    
    def list_accounts(self) -> str:
        """List all accounts"""
        accounts = self.load_accounts()
        
        if not accounts:
            return "📱 No accounts added yet.\n\nUse /add to add account."
        
        text = "📱 *Instagram Accounts:*\n\n"
        
        for acc in accounts:
            status = "✅" if acc.get('is_active', True) else "❌"
            health = acc.get('health_score', 100)
            reports = acc.get('reports_today', 0)
            max_reports = acc.get('max_daily_reports', 5)
            
            text += f"{status} `{acc['username']}`\n"
            text += f"   ❤️ Health: {health}%\n"
            text += f"   📊 Reports: {reports}/{max_reports}\n\n"
        
        text += f"*Total:* {len(accounts)} accounts"
        return text
    
    def check_account_exists(self, username: str) -> bool:
        """Check if account exists"""
        accounts = self.load_accounts()
        for acc in accounts:
            if acc.get('username') == username:
                return True
        return False
