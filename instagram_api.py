import requests
import json
import time
import random
import os
import logging
from typing import Optional, Dict, List
from datetime import datetime
import hashlib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/instagram_api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('InstagramAPI')

class InstagramAPI:
    """Instagram API handler for reporting"""
    
    def __init__(self):
        self.base_url = 'https://www.instagram.com/api/v1'
        self.sessions = {}
        self.report_reasons = {
    'spam': {'code': 'spam', 'label': 'Spam'},
    'fake_profile': {'code': 'impersonation', 'label': 'Fake Profile'},
    'impersonation': {'code': 'impersonation', 'label': 'Impersonation'},
    'harassment': {'code': 'harassment', 'label': 'Harassment/Bullying'},
    'bullying': {'code': 'bullying', 'label': 'Bullying'},
    'threats': {'code': 'threats', 'label': 'Threats'},
    'violence': {'code': 'violence', 'label': 'Violence'},
    'dangerous_org': {'code': 'dangerous_organizations', 'label': 'Dangerous Organizations'},
    'weapons': {'code': 'weapons', 'label': 'Weapons Sale'},
    'scam': {'code': 'scam', 'label': 'Scam/Fraud'},
    'fraud': {'code': 'fraud', 'label': 'Fraud'},
    'phishing': {'code': 'phishing', 'label': 'Phishing'},
    'nudity': {'code': 'nudity', 'label': 'Nudity'},
    'sexual_content': {'code': 'sexual_content', 'label': 'Sexual Content'},
    'drugs': {'code': 'drugs', 'label': 'Drugs'},
    'hate_speech': {'code': 'hate_speech', 'label': 'Hate Speech'},
    'race_hate': {'code': 'race_hate', 'label': 'Racial Hate'},
    'religion_hate': {'code': 'religion_hate', 'label': 'Religious Hate'},
    'copyright': {'code': 'copyright', 'label': 'Copyright'},
    'underage': {'code': 'underage', 'label': 'Underage'},
    'self_harm': {'code': 'self_harm', 'label': 'Self Harm'},
    'terrorism': {'code': 'terrorism', 'label': 'Terrorism'}
        }
    
    def login(self, username: str, password: str, proxy: Optional[str] = None) -> Optional[Dict]:
        """Login to Instagram"""
        try:
            session = requests.Session()
            
            if proxy:
                session.proxies = {'http': proxy, 'https': proxy}
            
            # Set headers
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive'
            })
            
            # Get CSRF token
            response = session.get('https://www.instagram.com/')
            csrf_token = session.cookies.get('csrftoken', '')
            
            if not csrf_token:
                # Generate random CSRF
                csrf_token = hashlib.md5(str(time.time()).encode()).hexdigest()
            
            # Login request
            login_url = f'{self.base_url}/web/accounts/login/ajax/'
            
            login_headers = {
                'X-CSRFToken': csrf_token,
                'X-IG-App-ID': '936619743392459',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': 'https://www.instagram.com/accounts/login/',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            login_data = {
                'username': username,
                'enc_password': f'#PWD_INSTAGRAM_BROWSER:0:{int(time.time())}:{password}',
                'queryParams': '{}',
                'optIntoOneTap': 'false',
                'stopDeletionNonce': '',
                'trustedDeviceRecords': '{}'
            }
            
            response = session.post(login_url, headers=login_headers, data=login_data)
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('authenticated'):
                    logger.info(f"✅ Login successful: {username}")
                    
                    session_data = {
                        'username': username,
                        'session': session,
                        'csrf_token': session.cookies.get('csrftoken', csrf_token),
                        'user_id': result.get('userId', ''),
                        'cookies': session.cookies.get_dict(),
                        'logged_in_at': datetime.now().isoformat()
                    }
                    
                    self.sessions[username] = session_data
                    return session_data
                else:
                    logger.error(f"❌ Login failed for {username}: {result.get('message')}")
                    return None
            else:
                logger.error(f"Login failed with status {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Login error for {username}: {e}")
            return None
    
    def get_user_id(self, username: str, session_data: Dict) -> Optional[str]:
        """Get Instagram user ID"""
        try:
            session = session_data['session']
            
            url = f'{self.base_url}/users/web_profile_info/'
            params = {'username': username}
            
            headers = {
                'X-CSRFToken': session_data['csrf_token'],
                'X-IG-App-ID': '936619743392459',
                'Referer': f'https://www.instagram.com/{username}/'
            }
            
            response = session.get(url, params=params, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                user_data = data.get('data', {}).get('user', {})
                user_id = user_data.get('id')
                
                if user_id:
                    logger.info(f"✅ Got user ID for {username}: {user_id}")
                    return str(user_id)
            
            logger.error(f"Failed to get user ID for {username}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting user ID: {e}")
            return None
    
    def report_user(self, target_username: str, reason: str, session_data: Dict) -> bool:
        """Report Instagram user"""
        try:
            # Get target user ID
            target_user_id = self.get_user_id(target_username, session_data)
            
            if not target_user_id:
                logger.error(f"Could not get user ID for {target_username}")
                return False
            
            session = session_data['session']
            
            # Report endpoint
            url = f'{self.base_url}/users/{target_user_id}/flag/'
            
            headers = {
                'X-CSRFToken': session_data['csrf_token'],
                'X-IG-App-ID': '936619743392459',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': f'https://www.instagram.com/{target_username}/',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            # Report data
            report_code = self.report_reasons.get(reason, {}).get('code', 'spam')
            
            data = {
                'reason': report_code,
                'source_name': 'profile',
                'is_spam': 'true' if report_code == 'spam' else 'false',
                'original_report': 'false'
            }
            
            # Send report
            response = session.post(url, headers=headers, data=data)
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('status') == 'ok':
                    logger.info(f"✅ Report submitted for {target_username} ({reason})")
                    return True
                else:
                    logger.warning(f"Report response: {result}")
                    return False
            else:
                logger.error(f"Report failed with status {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Report error for {target_username}: {e}")
            return False
    
    def check_profile_status(self, username: str, session_data: Dict) -> Dict:
        """Check if target profile still exists"""
        try:
            session = session_data['session']
            
            url = f'https://www.instagram.com/{username}/'
            response = session.get(url)
            
            if response.status_code == 404:
                return {'status': 'removed', 'message': 'Profile has been removed'}
            elif 'account disabled' in response.text.lower() or 'page unavailable' in response.text.lower():
                return {'status': 'disabled', 'message': 'Account has been disabled'}
            elif 'is_private' in response.text or 'followers' in response.text:
                return {'status': 'active', 'message': 'Profile is still active'}
            else:
                return {'status': 'unknown', 'message': 'Could not determine status'}
                
        except Exception as e:
            return {'status': 'unknown', 'message': str(e)}
    
    def human_delay(self, min_seconds: int = 5, max_seconds: int = 20):
        """Human-like random delay"""
        delay = random.uniform(min_seconds, max_seconds)
        logger.info(f"⏳ Waiting {delay:.1f} seconds...")
        time.sleep(delay)
        
        # Random micro-pause
        if random.random() < 0.3:
            micro_delay = random.uniform(0.5, 2)
            time.sleep(micro_delay)
