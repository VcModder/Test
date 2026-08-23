import asyncio
import random
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from instagram_api import InstagramAPI
from database import Database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/report_engine.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ReportEngine')

class ReportEngine:
    """Main report execution engine"""
    
    def __init__(self, database: Database):
        self.db = database
        self.api = InstagramAPI()
        self.active_jobs = {}
    
    async def execute_report(self, target_url: str, reason: str, user_id: int) -> Dict:
        """Execute complete report workflow"""
        
        # Extract username from URL
        target_username = self.db.extract_username(target_url)
        
        if not target_username:
            return {'success': False, 'error': 'Invalid Instagram URL'}
        
        logger.info(f"Starting report for {target_username} - Reason: {reason}")
        
        # Add report to database
        report_id = self.db.add_report(user_id, target_url, reason)
        
        # Get available accounts
        accounts = self.db.get_active_accounts()
        
        if not accounts:
            self.db.update_report(report_id, 'failed')
            return {'success': False, 'error': 'No active accounts available'}
        
        # Filter accounts that can report
        available_accounts = []
        for account in accounts:
            if account['reports_today'] < account['max_daily_reports']:
                if account['health_score'] >= 5:
                    available_accounts.append(account)
        
        if not available_accounts:
            self.db.update_report(report_id, 'failed')
            return {'success': False, 'error': 'All accounts reached daily limit'}
        
        # Select 2-5 accounts
        num_accounts = min(random.randint(2, 5), len(available_accounts))
        selected_accounts = random.sample(available_accounts, num_accounts)
        
        logger.info(f"Selected {num_accounts} accounts for reporting")
        
        # Execute reports
        results = []
        success_count = 0
        
        for i, account in enumerate(selected_accounts):
            try:
                # Human-like delay
                await asyncio.sleep(random.uniform(1, 1.5))
                
                # Login to Instagram
                session_data = self.api.login(
                    account['username'],
                    account['password'],
                    account['proxy'] if account['proxy'] else None
                )
                
                if not session_data:
                    self.db.update_account_stats(account['username'], False)
                    results.append({
                        'account': account['username'],
                        'success': False,
                        'error': 'Login failed'
                    })
                    continue
                
                # Submit report
                success = self.api.report_user(
                    target_username,
                    reason,
                    session_data
                )
                
                if success:
                    success_count += 1
                
                # Update account stats
                self.db.update_account_stats(account['username'], success)
                
                results.append({
                    'account': account['username'],
                    'success': success,
                    'timestamp': datetime.now().isoformat()
                })
                
                # Delay between accounts (avoid detection)
                if i < len(selected_accounts) - 1:
                    inter_delay = random.uniform(2, 5)
                    logger.info(f"Waiting {inter_delay:.1f}s before next account...")
                    await asyncio.sleep(inter_delay)
                
            except Exception as e:
                logger.error(f"Error with account {account['username']}: {e}")
                self.db.update_account_stats(account['username'], False)
                results.append({
                    'account': account['username'],
                    'success': False,
                    'error': str(e)
                })
        
        # Update report status
        status = 'completed' if success_count > 0 else 'failed'
        self.db.update_report(report_id, status, num_accounts, success_count)
        
        # Check target status
        target_status = {'status': 'unknown'}
        if selected_accounts:
            session_data = self.api.login(
                selected_accounts[0]['username'],
                selected_accounts[0]['password'],
                selected_accounts[0]['proxy'] if selected_accounts[0]['proxy'] else None
            )
            if session_data:
                target_status = self.api.check_profile_status(target_username, session_data)
        
        # Log activity
        self.db.add_log(user_id, 'report_completed', 
                       f'Target: {target_username}, Reason: {reason}, Success: {success_count}/{num_accounts}')
        
        return {
            'success': True,
            'target': target_username,
            'reason': reason,
            'accounts_used': num_accounts,
            'success_count': success_count,
            'results': results,
            'target_status': target_status
        }
