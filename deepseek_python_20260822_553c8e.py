import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/database.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('Database')

class Database:
    def __init__(self, db_path: str = 'data/bot.db'):
        os.makedirs('data', exist_ok=True)
        os.makedirs('logs', exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.init_db()
        logger.info("Database initialized")
    
    def init_db(self):
        """Initialize all tables"""
        self.cursor.executescript('''
            -- Users table
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                is_admin BOOLEAN DEFAULT 0,
                is_banned BOOLEAN DEFAULT 0,
                total_reports INTEGER DEFAULT 0,
                joined_date TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Reports table
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                target_url TEXT,
                target_username TEXT,
                reason TEXT,
                status TEXT DEFAULT 'pending',
                accounts_used INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            
            -- Instagram accounts table
            CREATE TABLE IF NOT EXISTS instagram_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                proxy TEXT,
                is_active BOOLEAN DEFAULT 1,
                health_score INTEGER DEFAULT 100,
                reports_today INTEGER DEFAULT 0,
                max_daily_reports INTEGER DEFAULT 5,
                total_reports INTEGER DEFAULT 0,
                last_report_time TEXT,
                consecutive_failures INTEGER DEFAULT 0
            );
            
            -- Proxies table
            CREATE TABLE IF NOT EXISTS proxies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proxy TEXT UNIQUE,
                is_active BOOLEAN DEFAULT 1,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0
            );
            
            -- Logs table
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                details TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Broadcast messages table
            CREATE TABLE IF NOT EXISTS broadcast_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                message TEXT,
                sent_count INTEGER DEFAULT 0,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        self.conn.commit()
        logger.info("Tables created")
    
    # ============ USER METHODS ============
    def add_user(self, user_id: int, username: str, first_name: str):
        """Add or update user"""
        self.cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
        ''', (user_id, username, first_name))
        self.conn.commit()
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else None
    
    def get_all_users(self) -> List[Dict]:
        """Get all users"""
        self.cursor.execute('SELECT * FROM users')
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]
    
    def ban_user(self, user_id: int):
        """Ban user"""
        self.cursor.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (user_id,))
        self.conn.commit()
    
    def unban_user(self, user_id: int):
        """Unban user"""
        self.cursor.execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (user_id,))
        self.conn.commit()
    
    def update_user_reports(self, user_id: int):
        """Increment user report count"""
        self.cursor.execute('UPDATE users SET total_reports = total_reports + 1 WHERE user_id = ?', (user_id,))
        self.conn.commit()
    
    # ============ REPORT METHODS ============
    def add_report(self, user_id: int, target_url: str, reason: str) -> int:
        """Add new report"""
        target_username = self.extract_username(target_url)
        self.cursor.execute('''
            INSERT INTO reports (user_id, target_url, target_username, reason)
            VALUES (?, ?, ?, ?)
        ''', (user_id, target_url, target_username, reason))
        self.conn.commit()
        report_id = self.cursor.lastrowid
        self.update_user_reports(user_id)
        return report_id
    
    def update_report(self, report_id: int, status: str, accounts_used: int = 0, success_count: int = 0):
        """Update report status"""
        self.cursor.execute('''
            UPDATE reports 
            SET status = ?, accounts_used = ?, success_count = ?, completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (status, accounts_used, success_count, report_id))
        self.conn.commit()
    
    def get_user_reports(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get user's reports"""
        self.cursor.execute('''
            SELECT * FROM reports WHERE user_id = ? ORDER BY created_at DESC LIMIT ?
        ''', (user_id, limit))
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_all_reports(self, limit: int = 50) -> List[Dict]:
        """Get all reports (admin)"""
        self.cursor.execute('SELECT * FROM reports ORDER BY created_at DESC LIMIT ?', (limit,))
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]
    
    @staticmethod
    def extract_username(url: str) -> str:
        """Extract username from Instagram URL"""
        url = url.rstrip('/')
        if 'instagram.com/' in url:
            parts = url.split('instagram.com/')
            if len(parts) > 1:
                username = parts[1].split('/')[0]
                return username.replace('@', '')
        return url.replace('@', '')
    
    # ============ ACCOUNT METHODS ============
    def add_account(self, username: str, password: str, proxy: str = "") -> bool:
        """Add Instagram account"""
        try:
            self.cursor.execute('''
                INSERT OR IGNORE INTO instagram_accounts (username, password, proxy)
                VALUES (?, ?, ?)
            ''', (username, password, proxy))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to add account: {e}")
            return False
    
    def remove_account(self, username: str) -> bool:
        """Remove Instagram account"""
        self.cursor.execute('DELETE FROM instagram_accounts WHERE username = ?', (username,))
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    def get_account(self, username: str) -> Optional[Dict]:
        """Get account by username"""
        self.cursor.execute('SELECT * FROM instagram_accounts WHERE username = ?', (username,))
        row = self.cursor.fetchone()
        return dict(row) if row else None
    
    def get_active_accounts(self) -> List[Dict]:
        """Get all active accounts"""
        self.cursor.execute('SELECT * FROM instagram_accounts WHERE is_active = 1')
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_all_accounts(self) -> List[Dict]:
        """Get all accounts"""
        self.cursor.execute('SELECT * FROM instagram_accounts')
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]
    
    def update_account_stats(self, username: str, success: bool):
        """Update account statistics"""
        account = self.get_account(username)
        if not account:
            return
        
        new_reports_today = account['reports_today'] + 1
        new_total_reports = account['total_reports'] + 1
        
        if success:
            new_health = min(100, account['health_score'] + 1)
            new_failures = 0
        else:
            new_health = max(0, account['health_score'] - 10)
            new_failures = account['consecutive_failures'] + 1
        
        is_active = 1
        if new_failures >= 3:
            is_active = 0
        
        self.cursor.execute('''
            UPDATE instagram_accounts 
            SET reports_today = ?, total_reports = ?, health_score = ?, 
                consecutive_failures = ?, is_active = ?, last_report_time = CURRENT_TIMESTAMP
            WHERE username = ?
        ''', (new_reports_today, new_total_reports, new_health, new_failures, is_active, username))
        self.conn.commit()
    
    def reset_daily_reports(self):
        """Reset daily report counts"""
        self.cursor.execute('UPDATE instagram_accounts SET reports_today = 0')
        self.conn.commit()
        logger.info("Daily report counts reset")
    
    # ============ PROXY METHODS ============
    def add_proxy(self, proxy: str) -> bool:
        """Add proxy"""
        try:
            self.cursor.execute('INSERT OR IGNORE INTO proxies (proxy) VALUES (?)', (proxy,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to add proxy: {e}")
            return False
    
    def remove_proxy(self, proxy: str) -> bool:
        """Remove proxy"""
        self.cursor.execute('DELETE FROM proxies WHERE proxy = ?', (proxy,))
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    def get_all_proxies(self) -> List[Dict]:
        """Get all proxies"""
        self.cursor.execute('SELECT * FROM proxies')
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]
    
    # ============ LOG METHODS ============
    def add_log(self, user_id: int, action: str, details: str):
        """Add activity log"""
        self.cursor.execute('''
            INSERT INTO activity_logs (user_id, action, details)
            VALUES (?, ?, ?)
        ''', (user_id, action, details))
        self.conn.commit()
    
    def get_logs(self, limit: int = 100) -> List[Dict]:
        """Get recent logs"""
        self.cursor.execute('SELECT * FROM activity_logs ORDER BY timestamp DESC LIMIT ?', (limit,))
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]
    
    # ============ BROADCAST METHODS ============
    def add_broadcast(self, admin_id: int, message: str) -> int:
        """Save broadcast message"""
        self.cursor.execute('''
            INSERT INTO broadcast_messages (admin_id, message)
            VALUES (?, ?)
        ''', (admin_id, message))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def update_broadcast_count(self, broadcast_id: int, sent_count: int):
        """Update broadcast sent count"""
        self.cursor.execute('UPDATE broadcast_messages SET sent_count = ? WHERE id = ?', 
                           (sent_count, broadcast_id))
        self.conn.commit()
    
    # ============ STATS METHODS ============
    def get_stats(self) -> Dict:
        """Get bot statistics"""
        stats = {}
        
        self.cursor.execute('SELECT COUNT(*) as count FROM users')
        stats['total_users'] = self.cursor.fetchone()['count']
        
        self.cursor.execute('SELECT COUNT(*) as count FROM users WHERE is_banned = 0')
        stats['active_users'] = self.cursor.fetchone()['count']
        
        self.cursor.execute('SELECT COUNT(*) as count FROM users WHERE is_banned = 1')
        stats['banned_users'] = self.cursor.fetchone()['count']
        
        self.cursor.execute('SELECT COUNT(*) as count FROM reports')
        stats['total_reports'] = self.cursor.fetchone()['count']
        
        self.cursor.execute('SELECT COUNT(*) as count FROM reports WHERE status = "completed"')
        stats['completed_reports'] = self.cursor.fetchone()['count']
        
        self.cursor.execute('SELECT COUNT(*) as count FROM reports WHERE status = "pending"')
        stats['pending_reports'] = self.cursor.fetchone()['count']
        
        self.cursor.execute('SELECT COUNT(*) as count FROM instagram_accounts WHERE is_active = 1')
        stats['active_accounts'] = self.cursor.fetchone()['count']
        
        self.cursor.execute('SELECT COUNT(*) as count FROM proxies WHERE is_active = 1')
        stats['active_proxies'] = self.cursor.fetchone()['count']
        
        return stats
    
    def close(self):
        """Close database connection"""
        self.conn.close()