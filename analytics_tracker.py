"""
CloudFace AI Analytics Tracker
Real-time user behavior and engagement analytics
"""

import json
import time
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import hashlib
import ipaddress
import requests

@dataclass
class UserSession:
    """User session data"""
    session_id: str
    user_id: str
    ip_address: str
    user_agent: str
    country: str
    region: str
    city: str
    device_type: str
    os: str
    start_time: datetime
    last_activity: datetime
    page_views: int
    total_time_spent: int  # seconds
    current_page: str
    referrer: str
    utm_source: str
    utm_medium: str
    utm_campaign: str

@dataclass
class PageView:
    """Page view event"""
    session_id: str
    user_id: str
    page_url: str
    page_title: str
    timestamp: datetime
    time_spent: int  # seconds on page
    referrer: str
    is_bounce: bool

@dataclass
class UserAction:
    """User action event"""
    session_id: str
    user_id: str
    action_type: str  # 'photo_processed', 'link_shared', 'photo_downloaded', 'search_performed'
    action_data: Dict[str, Any]
    timestamp: datetime
    page_url: str

@dataclass
class ShareEvent:
    """Share event tracking"""
    session_id: str
    user_id: str
    share_type: str  # 'whatsapp', 'email', 'copy_link', 'qr_download'
    share_data: Dict[str, Any]
    timestamp: datetime
    recipient_count: int

class AnalyticsTracker:
    """Main analytics tracking class"""
    
    def __init__(self, data_dir: str = "storage/analytics", retention_days: int = 365):
        self.data_dir = data_dir
        self.retention_days = retention_days
        self.sessions_file = os.path.join(data_dir, "sessions.json")
        self.pageviews_file = os.path.join(data_dir, "pageviews.json")
        self.actions_file = os.path.join(data_dir, "actions.json")
        self.shares_file = os.path.join(data_dir, "shares.json")
        self.daily_stats_file = os.path.join(data_dir, "daily_stats.json")
        self.prune_state_file = os.path.join(data_dir, "prune_state.json")
        
        # Create directories
        os.makedirs(data_dir, exist_ok=True)
        
        # Initialize files if they don't exist
        self._init_files()
        self._maybe_prune_old_data()
    
    def _init_files(self):
        """Initialize JSON files if they don't exist"""
        files = [
            self.sessions_file,
            self.pageviews_file,
            self.actions_file,
            self.shares_file,
            self.daily_stats_file,
            self.prune_state_file
        ]
        
        for file_path in files:
            if not os.path.exists(file_path):
                with open(file_path, 'w') as f:
                    json.dump([] if file_path != self.prune_state_file else {}, f)
    
    def _load_data(self, file_path: str) -> List[Dict]:
        """Load data from JSON file"""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def _save_data(self, file_path: str, data: List[Dict]):
        """Save data to JSON file"""
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def _get_geolocation(self, ip_address: str, user_agent: str = "") -> Dict[str, str]:
        """Get country and region (state) only."""
        try:
            country = 'Unknown'
            region = 'Unknown'
            city = 'Unknown'

            if ip_address and self._is_public_ip(ip_address):
                try:
                    response = requests.get(f"https://ipapi.co/{ip_address}/json/", timeout=2)
                    if response.ok:
                        data = response.json()
                        country = data.get('country_name') or data.get('country') or 'Unknown'
                        region = data.get('region') or data.get('region_code') or 'Unknown'
                except Exception:
                    pass

            if country == 'Unknown':
                if 'en-US' in user_agent or 'en_US' in user_agent:
                    country = 'United States'
                elif 'en-GB' in user_agent or 'en_GB' in user_agent:
                    country = 'United Kingdom'
                elif 'en-IN' in user_agent or 'en_IN' in user_agent:
                    country = 'India'
                elif 'en-CA' in user_agent or 'en_CA' in user_agent:
                    country = 'Canada'
                elif 'en-AU' in user_agent or 'en_AU' in user_agent:
                    country = 'Australia'
                else:
                    country = 'Global'
            
            return {
                'country': country,
                'region': region,
                'city': city
            }
        except Exception as e:
            print(f"Browser geolocation error: {e}")
        
        return {'country': 'Unknown', 'city': 'Unknown', 'region': 'Unknown'}

    def _is_public_ip(self, ip_address: str) -> bool:
        try:
            ip_obj = ipaddress.ip_address(ip_address)
            return not (ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved or ip_obj.is_multicast)
        except Exception:
            return False

    def _anonymize_ip(self, ip_address: str) -> str:
        try:
            ip_obj = ipaddress.ip_address(ip_address)
            if ip_obj.version == 4:
                parts = ip_address.split('.')
                return '.'.join(parts[:3] + ['0'])
            if ip_obj.version == 6:
                return ip_address.split(':', 1)[0] + '::'
        except Exception:
            pass
        return 'anonymized'

    def _parse_user_agent(self, user_agent: str) -> Dict[str, str]:
        ua = (user_agent or '').lower()
        device_type = 'desktop'
        if 'mobile' in ua or 'iphone' in ua or 'android' in ua:
            device_type = 'mobile'
        if 'ipad' in ua or 'tablet' in ua:
            device_type = 'tablet'

        os_name = 'Unknown'
        if 'android' in ua:
            os_name = 'Android'
        elif 'iphone' in ua or 'ipad' in ua or 'ios' in ua:
            os_name = 'iOS'
        elif 'windows' in ua:
            os_name = 'Windows'
        elif 'mac os' in ua or 'macintosh' in ua:
            os_name = 'macOS'
        elif 'linux' in ua:
            os_name = 'Linux'

        return {'device_type': device_type, 'os': os_name}

    def _maybe_prune_old_data(self):
        """Prune analytics older than retention window at most once per day."""
        try:
            state = self._load_state()
            last_pruned = state.get('last_pruned')
            if last_pruned:
                last_dt = datetime.fromisoformat(last_pruned)
                if datetime.now() - last_dt < timedelta(hours=24):
                    return
            self._prune_old_data(self.retention_days)
            state['last_pruned'] = datetime.now().isoformat()
            self._save_state(state)
        except Exception as e:
            print(f"⚠️ Analytics prune failed: {e}")

    def _prune_old_data(self, days: int):
        cutoff_date = datetime.now() - timedelta(days=days)
        self._save_data(self.sessions_file, [
            s for s in self._load_data(self.sessions_file)
            if datetime.fromisoformat(s.get('start_time')) >= cutoff_date
        ])
        self._save_data(self.pageviews_file, [
            p for p in self._load_data(self.pageviews_file)
            if datetime.fromisoformat(p.get('timestamp')) >= cutoff_date
        ])
        self._save_data(self.actions_file, [
            a for a in self._load_data(self.actions_file)
            if datetime.fromisoformat(a.get('timestamp')) >= cutoff_date
        ])
        self._save_data(self.shares_file, [
            s for s in self._load_data(self.shares_file)
            if datetime.fromisoformat(s.get('timestamp')) >= cutoff_date
        ])

    def _load_state(self) -> Dict[str, Any]:
        try:
            with open(self.prune_state_file, 'r') as f:
                return json.load(f) or {}
        except Exception:
            return {}

    def _save_state(self, state: Dict[str, Any]):
        with open(self.prune_state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def reset_data(self):
        """Reset all analytics data."""
        self._save_data(self.sessions_file, [])
        self._save_data(self.pageviews_file, [])
        self._save_data(self.actions_file, [])
        self._save_data(self.shares_file, [])
        self._save_data(self.daily_stats_file, [])
        self._save_state({})
    
    def _extract_utm_params(self, referrer: str) -> Dict[str, str]:
        """Extract UTM parameters from referrer"""
        utm_params = {
            'utm_source': '',
            'utm_medium': '',
            'utm_campaign': ''
        }
        
        if '?' in referrer:
            params = referrer.split('?')[1]
            for param in params.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    if key in utm_params:
                        utm_params[key] = value
        
        return utm_params
    
    def start_session(self, user_id: str, ip_address: str, user_agent: str, 
                     referrer: str = "", current_page: str = "") -> str:
        """Start a new user session"""
        session_id = hashlib.md5(f"{user_id}_{ip_address}_{time.time()}".encode()).hexdigest()[:12]
        
        # Get geolocation from browser (free method)
        geo_data = self._get_geolocation(ip_address, user_agent)
        device_info = self._parse_user_agent(user_agent)
        
        # Extract UTM parameters
        utm_params = self._extract_utm_params(referrer)
        
        session = UserSession(
            session_id=session_id,
            user_id=user_id,
            ip_address=self._anonymize_ip(ip_address),
            user_agent=user_agent,
            country=geo_data['country'],
            region=geo_data['region'],
            city=geo_data['city'],
            device_type=device_info['device_type'],
            os=device_info['os'],
            start_time=datetime.now(),
            last_activity=datetime.now(),
            page_views=0,
            total_time_spent=0,
            current_page=current_page,
            referrer=referrer,
            utm_source=utm_params['utm_source'],
            utm_medium=utm_params['utm_medium'],
            utm_campaign=utm_params['utm_campaign']
        )
        
        # Save session
        sessions = self._load_data(self.sessions_file)
        sessions.append(asdict(session))
        self._save_data(self.sessions_file, sessions)
        
        return session_id
    
    def track_page_view(self, session_id: str, user_id: str, page_url: str, 
                       page_title: str, referrer: str = "", time_spent: int = 0):
        """Track a page view"""
        pageview = PageView(
            session_id=session_id,
            user_id=user_id,
            page_url=page_url,
            page_title=page_title,
            timestamp=datetime.now(),
            time_spent=time_spent,
            referrer=referrer,
            is_bounce=time_spent < 5  # Less than 5 seconds is a bounce
        )
        
        # Save pageview
        pageviews = self._load_data(self.pageviews_file)
        pageviews.append(asdict(pageview))
        self._save_data(self.pageviews_file, pageviews)
        
        # Update session
        self._update_session_activity(session_id, page_url, time_spent)
    
    def track_action(self, session_id: str, user_id: str, action_type: str, 
                    action_data: Dict[str, Any], page_url: str = ""):
        """Track a user action"""
        action = UserAction(
            session_id=session_id,
            user_id=user_id,
            action_type=action_type,
            action_data=action_data,
            timestamp=datetime.now(),
            page_url=page_url
        )
        
        # Save action
        actions = self._load_data(self.actions_file)
        actions.append(asdict(action))
        self._save_data(self.actions_file, actions)

    def track_error(self, session_id: str, user_id: str, error_data: Dict[str, Any], page_url: str = ""):
        """Track an error event"""
        self.track_action(session_id, user_id, 'error', error_data, page_url)
    
    def track_share(self, session_id: str, user_id: str, share_type: str, 
                   share_data: Dict[str, Any], recipient_count: int = 1):
        """Track a share event"""
        share_event = ShareEvent(
            session_id=session_id,
            user_id=user_id,
            share_type=share_type,
            share_data=share_data,
            timestamp=datetime.now(),
            recipient_count=recipient_count
        )
        
        # Save share event
        shares = self._load_data(self.shares_file)
        shares.append(asdict(share_event))
        self._save_data(self.shares_file, shares)
    
    def _update_session_activity(self, session_id: str, current_page: str, time_spent: int):
        """Update session activity"""
        sessions = self._load_data(self.sessions_file)
        
        for session in sessions:
            if session['session_id'] == session_id:
                session['last_activity'] = datetime.now().isoformat()
                session['page_views'] += 1
                session['total_time_spent'] += time_spent
                session['current_page'] = current_page
                break
        
        self._save_data(self.sessions_file, sessions)
    
    def get_user_analytics(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get analytics for a specific user"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Load all data
        sessions = self._load_data(self.sessions_file)
        pageviews = self._load_data(self.pageviews_file)
        actions = self._load_data(self.actions_file)
        shares = self._load_data(self.shares_file)
        
        # Filter by user and date
        user_sessions = [s for s in sessions if s['user_id'] == user_id and 
                        datetime.fromisoformat(s['start_time']) >= cutoff_date]
        user_pageviews = [p for p in pageviews if p['user_id'] == user_id and 
                         datetime.fromisoformat(p['timestamp']) >= cutoff_date]
        user_actions = [a for a in actions if a['user_id'] == user_id and 
                       datetime.fromisoformat(a['timestamp']) >= cutoff_date]
        user_shares = [s for s in shares if s['user_id'] == user_id and 
                      datetime.fromisoformat(s['timestamp']) >= cutoff_date]
        
        # Calculate metrics
        total_sessions = len(user_sessions)
        total_page_views = len(user_pageviews)
        total_time_spent = sum(s['total_time_spent'] for s in user_sessions)
        
        # Action counts
        photos_processed = len([a for a in user_actions if a['action_type'] == 'photo_processed'])
        links_created = len([a for a in user_actions if a['action_type'] == 'link_created'])
        searches_performed = len([a for a in user_actions if a['action_type'] == 'search_performed'])
        photos_downloaded = len([a for a in user_actions if a['action_type'] == 'photo_downloaded'])
        
        # Share counts
        total_shares = len(user_shares)
        whatsapp_shares = len([s for s in user_shares if s['share_type'] == 'whatsapp'])
        email_shares = len([s for s in user_shares if s['share_type'] == 'email'])
        qr_downloads = len([s for s in user_shares if s['share_type'] == 'qr_download'])
        
        # Page popularity
        page_stats = {}
        for pv in user_pageviews:
            page = pv['page_url']
            if page not in page_stats:
                page_stats[page] = {'views': 0, 'time_spent': 0}
            page_stats[page]['views'] += 1
            page_stats[page]['time_spent'] += pv['time_spent']
        
        # Most popular pages
        popular_pages = sorted(page_stats.items(), key=lambda x: x[1]['views'], reverse=True)[:5]
        
        return {
            'user_id': user_id,
            'period_days': days,
            'total_sessions': total_sessions,
            'total_page_views': total_page_views,
            'total_time_spent': total_time_spent,
            'avg_session_duration': total_time_spent / max(total_sessions, 1),
            'photos_processed': photos_processed,
            'links_created': links_created,
            'searches_performed': searches_performed,
            'photos_downloaded': photos_downloaded,
            'total_shares': total_shares,
            'whatsapp_shares': whatsapp_shares,
            'email_shares': email_shares,
            'qr_downloads': qr_downloads,
            'popular_pages': popular_pages,
            'last_activity': max([s['last_activity'] for s in user_sessions], default='Never')
        }
    
    def get_overall_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Get overall analytics for all users"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Load all data
        sessions = self._load_data(self.sessions_file)
        pageviews = self._load_data(self.pageviews_file)
        actions = self._load_data(self.actions_file)
        shares = self._load_data(self.shares_file)
        
        # Filter by date
        recent_sessions = [s for s in sessions if 
                          datetime.fromisoformat(s['start_time']) >= cutoff_date]
        recent_pageviews = [p for p in pageviews if 
                           datetime.fromisoformat(p['timestamp']) >= cutoff_date]
        recent_actions = [a for a in actions if 
                         datetime.fromisoformat(a['timestamp']) >= cutoff_date]
        recent_shares = [s for s in shares if 
                        datetime.fromisoformat(s['timestamp']) >= cutoff_date]
        
        # Calculate metrics
        unique_users = len(set(s['user_id'] for s in recent_sessions))
        total_sessions = len(recent_sessions)
        total_page_views = len(recent_pageviews)
        total_time_spent = sum(s['total_time_spent'] for s in recent_sessions)
        
        # Action counts
        photos_processed = sum([a.get('action_data', {}).get('processed_count', 0) for a in recent_actions if a['action_type'] == 'photo_processed'])
        links_created = len([a for a in recent_actions if a['action_type'] == 'link_created'])
        searches_performed = len([a for a in recent_actions if a['action_type'] == 'search_performed'])
        photos_downloaded = len([a for a in recent_actions if a['action_type'] == 'photo_downloaded'])
        
        # Share counts
        total_shares = len(recent_shares)
        whatsapp_shares = len([s for s in recent_shares if s['share_type'] == 'whatsapp'])
        email_shares = len([s for s in recent_shares if s['share_type'] == 'email'])
        qr_downloads = len([s for s in recent_shares if s['share_type'] == 'qr_download'])
        
        # Geographic distribution
        country_stats = {}
        region_stats = {}
        device_stats = {}
        os_stats = {}
        for session in recent_sessions:
            country = session['country']
            country_stats[country] = country_stats.get(country, 0) + 1
            region = session.get('region', 'Unknown')
            region_stats[region] = region_stats.get(region, 0) + 1
            device = session.get('device_type', 'unknown')
            device_stats[device] = device_stats.get(device, 0) + 1
            os_name = session.get('os', 'unknown')
            os_stats[os_name] = os_stats.get(os_name, 0) + 1
        
        # Traffic sources
        source_stats = {}
        for session in recent_sessions:
            source = session['utm_source'] or 'Direct'
            source_stats[source] = source_stats.get(source, 0) + 1
        
        # Page popularity
        page_stats = {}
        for pv in recent_pageviews:
            page = pv['page_url']
            if page not in page_stats:
                page_stats[page] = {'views': 0, 'unique_users': set()}
            page_stats[page]['views'] += 1
            page_stats[page]['unique_users'].add(pv['user_id'])
        
        # Convert unique_users sets to counts
        for page in page_stats:
            page_stats[page]['unique_users'] = len(page_stats[page]['unique_users'])
        
        popular_pages = sorted(page_stats.items(), key=lambda x: x[1]['views'], reverse=True)[:10]
        
        # Calculate weekly metrics
        week_ago = datetime.now() - timedelta(days=7)
        week_actions = [a for a in actions if 
                       datetime.fromisoformat(a['timestamp']) >= week_ago]
        week_pageviews = [p for p in pageviews if 
                         datetime.fromisoformat(p['timestamp']) >= week_ago]
        
        photos_this_week = sum([a.get('action_data', {}).get('processed_count', 0) for a in week_actions if a['action_type'] == 'photo_processed'])
        links_this_week = len([a for a in week_actions if a['action_type'] == 'link_created'])
        downloads_this_week = len([a for a in week_actions if a['action_type'] == 'photo_downloaded'])
        views_this_week = len(week_pageviews)

        return {
            'period_days': days,
            'unique_users': unique_users,
            'total_sessions': total_sessions,
            'total_page_views': total_page_views,
            'total_time_spent': total_time_spent,
            'avg_session_duration': total_time_spent / max(total_sessions, 1),
            'photos_processed': photos_processed,
            'links_created': links_created,
            'searches_performed': searches_performed,
            'photos_downloaded': photos_downloaded,
            'total_shares': total_shares,
            'whatsapp_shares': whatsapp_shares,
            'email_shares': email_shares,
            'qr_downloads': qr_downloads,
            'country_distribution': dict(sorted(country_stats.items(), key=lambda x: x[1], reverse=True)[:10]),
            'region_distribution': dict(sorted(region_stats.items(), key=lambda x: x[1], reverse=True)[:10]),
            'device_distribution': dict(sorted(device_stats.items(), key=lambda x: x[1], reverse=True)),
            'os_distribution': dict(sorted(os_stats.items(), key=lambda x: x[1], reverse=True)),
            'traffic_sources': dict(sorted(source_stats.items(), key=lambda x: x[1], reverse=True)[:10]),
            'popular_pages': popular_pages,
            'photos_this_week': photos_this_week,
            'links_this_week': links_this_week,
            'downloads_this_week': downloads_this_week,
            'views_this_week': views_this_week
        }

    def get_superadmin_analytics(self, days: int = 365) -> Dict[str, Any]:
        """Extended analytics for superadmin."""
        cutoff_date = datetime.now() - timedelta(days=days)
        sessions = self._load_data(self.sessions_file)
        actions = self._load_data(self.actions_file)
        shares = self._load_data(self.shares_file)
        pageviews = self._load_data(self.pageviews_file)

        recent_sessions = [s for s in sessions if datetime.fromisoformat(s['start_time']) >= cutoff_date]
        recent_actions = [a for a in actions if datetime.fromisoformat(a['timestamp']) >= cutoff_date]
        recent_shares = [s for s in shares if datetime.fromisoformat(s['timestamp']) >= cutoff_date]
        recent_pageviews = [p for p in pageviews if datetime.fromisoformat(p['timestamp']) >= cutoff_date]

        def sum_action(action_type, key):
            total = 0
            for a in recent_actions:
                if a['action_type'] == action_type:
                    total += a.get('action_data', {}).get(key, 0) or 0
            return total

        def count_action(action_type, source=None):
            count = 0
            for a in recent_actions:
                if a['action_type'] != action_type:
                    continue
                if source and a.get('action_data', {}).get('source') != source:
                    continue
                count += 1
            return count

        errors = [a for a in recent_actions if a['action_type'] == 'error']

        blog_views = len([p for p in recent_pageviews if p.get('page_url', '').startswith('/blog')])

        country_stats = {}
        region_stats = {}
        device_stats = {}
        os_stats = {}
        for session in recent_sessions:
            country_stats[session.get('country', 'Unknown')] = country_stats.get(session.get('country', 'Unknown'), 0) + 1
            region_stats[session.get('region', 'Unknown')] = region_stats.get(session.get('region', 'Unknown'), 0) + 1
            device_stats[session.get('device_type', 'unknown')] = device_stats.get(session.get('device_type', 'unknown'), 0) + 1
            os_stats[session.get('os', 'unknown')] = os_stats.get(session.get('os', 'unknown'), 0) + 1

        return {
            'period_days': days,
            'unique_users': len(set(s['user_id'] for s in recent_sessions)),
            'total_sessions': len(recent_sessions),
            'total_time_spent': sum(s.get('total_time_spent', 0) for s in recent_sessions),
            'drive_processed_files': sum_action('photo_processed', 'processed_count'),
            'drive_total_files': sum_action('photo_processed', 'total_files'),
            'drive_bytes': sum_action('photo_processed', 'total_bytes'),
            'local_processed_files': sum_action('photo_processed_local', 'processed_count'),
            'local_total_files': sum_action('photo_processed_local', 'total_files'),
            'local_bytes': sum_action('photo_processed_local', 'total_bytes'),
            'searches': count_action('search_performed'),
            'downloads': count_action('photo_downloaded'),
            'downloads_shared': count_action('photo_downloaded', 'shared'),
            'downloads_admin': count_action('photo_downloaded', 'admin'),
            'shares': len(recent_shares),
            'watermark_batches': count_action('watermark_batch'),
            'watermark_images': sum_action('watermark_batch', 'total_files'),
            'blog_views': blog_views,
            'errors_count': len(errors),
            'errors': errors[:20],
            'country_distribution': dict(sorted(country_stats.items(), key=lambda x: x[1], reverse=True)[:10]),
            'region_distribution': dict(sorted(region_stats.items(), key=lambda x: x[1], reverse=True)[:10]),
            'device_distribution': dict(sorted(device_stats.items(), key=lambda x: x[1], reverse=True)),
            'os_distribution': dict(sorted(os_stats.items(), key=lambda x: x[1], reverse=True))
        }
    
    def get_realtime_stats(self) -> Dict[str, Any]:
        """Get real-time statistics"""
        now = datetime.now()
        last_hour = now - timedelta(hours=1)
        last_24h = now - timedelta(hours=24)
        
        # Load recent data
        sessions = self._load_data(self.sessions_file)
        pageviews = self._load_data(self.pageviews_file)
        actions = self._load_data(self.actions_file)
        
        # Filter recent data
        recent_sessions = [s for s in sessions if 
                          datetime.fromisoformat(s['start_time']) >= last_24h]
        recent_pageviews = [p for p in pageviews if 
                           datetime.fromisoformat(p['timestamp']) >= last_hour]
        recent_actions = [a for a in actions if 
                         datetime.fromisoformat(a['timestamp']) >= last_hour]
        
        # Calculate real-time metrics
        active_users_24h = len(set(s['user_id'] for s in recent_sessions))
        active_users_1h = len(set(p['user_id'] for p in recent_pageviews))
        page_views_1h = len(recent_pageviews)
        photos_processed_1h = len([a for a in recent_actions if a['action_type'] == 'photo_processed'])
        
        return {
            'active_users_24h': active_users_24h,
            'active_users_1h': active_users_1h,
            'page_views_1h': page_views_1h,
            'photos_processed_1h': photos_processed_1h,
            'last_updated': now.isoformat()
        }
    
    def get_chart_data(self, days: int = 30, user_id: str = None) -> Dict[str, Any]:
        """Get chart data for the last N days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Load all data
            actions = self._load_data(self.actions_file)
            shares = self._load_data(self.shares_file)
            
            # Filter by user if specified
            if user_id:
                actions = [a for a in actions if a.get('user_id') == user_id]
                shares = [s for s in shares if s.get('user_id') == user_id]
            
            # Filter by date
            recent_actions = [a for a in actions if 
                            datetime.fromisoformat(a['timestamp']) >= cutoff_date]
            recent_shares = [s for s in shares if 
                           datetime.fromisoformat(s['timestamp']) >= cutoff_date]
            
            # Generate daily data for the last 30 days
            daily_data = {}
            for i in range(days):
                date = datetime.now() - timedelta(days=i)
                date_str = date.strftime('%Y-%m-%d')
                daily_data[date_str] = {
                    'photos_processed': 0,
                    'links_created': 0,
                    'downloads': 0
                }
            
            # Count actions by day
            for action in recent_actions:
                action_date = datetime.fromisoformat(action['timestamp']).strftime('%Y-%m-%d')
                if action_date in daily_data:
                    if action['action_type'] == 'photo_processed':
                        daily_data[action_date]['photos_processed'] += 1
                    elif action['action_type'] == 'link_created':
                        daily_data[action_date]['links_created'] += 1
                    elif action['action_type'] == 'photo_downloaded':
                        daily_data[action_date]['downloads'] += 1
            
            # Generate chart data (last 30 days, most recent first)
            chart_data = {
                'labels': [],
                'photos_data': [],
                'links_data': [],
                'downloads_data': []
            }
            
            for i in range(days-1, -1, -1):  # Reverse order (oldest to newest)
                date = datetime.now() - timedelta(days=i)
                date_str = date.strftime('%Y-%m-%d')
                day_data = daily_data[date_str]
                
                chart_data['labels'].append(f"Day {days-i}")
                chart_data['photos_data'].append(day_data['photos_processed'])
                chart_data['links_data'].append(day_data['links_created'])
                chart_data['downloads_data'].append(day_data['downloads'])
            
            # Share sources data
            whatsapp_shares = len([s for s in recent_shares if s['share_type'] == 'whatsapp'])
            email_shares = len([s for s in recent_shares if s['share_type'] == 'email'])
            qr_downloads = len([s for s in recent_shares if s['share_type'] == 'qr_download'])
            other_shares = len(recent_shares) - whatsapp_shares - email_shares - qr_downloads
            
            chart_data['sources_labels'] = ['WhatsApp', 'Email', 'QR Download', 'Other']
            chart_data['sources_data'] = [whatsapp_shares, email_shares, qr_downloads, other_shares]
            
            return chart_data
            
        except Exception as e:
            print(f"Error getting chart data: {e}")
            return {
                'labels': [],
                'photos_data': [],
                'links_data': [],
                'downloads_data': [],
                'sources_labels': ['WhatsApp', 'Email', 'QR Download', 'Other'],
                'sources_data': [0, 0, 0, 0]
            }
    
    def get_recent_activity(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent activity feed"""
        try:
            # Load all data
            actions = self._load_data(self.actions_file)
            shares = self._load_data(self.shares_file)
            
            # Combine and sort by timestamp
            all_activities = []
            
            # Add actions
            for action in actions:
                all_activities.append({
                    'type': action['action_type'],
                    'description': self._get_action_description(action),
                    'timestamp': action['timestamp'],
                    'user_id': action['user_id']
                })
            
            # Add shares
            for share in shares:
                all_activities.append({
                    'type': f"share_{share['share_type']}",
                    'description': self._get_share_description(share),
                    'timestamp': share['timestamp'],
                    'user_id': share['user_id']
                })
            
            # Sort by timestamp (most recent first)
            all_activities.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return all_activities[:limit]
            
        except Exception as e:
            print(f"Error getting recent activity: {e}")
            return []
    
    def _get_action_description(self, action: Dict[str, Any]) -> str:
        """Generate human-readable action description"""
        action_type = action['action_type']
        metadata = action.get('metadata', {})
        
        if action_type == 'photo_processed':
            count = metadata.get('processed_count', 0)
            return f"Processed {count} photos"
        elif action_type == 'link_created':
            return "Created a shareable link"
        elif action_type == 'search_performed':
            return "Performed a face search"
        elif action_type == 'photo_downloaded':
            filename = metadata.get('filename', 'photo')
            return f"Downloaded {filename}"
        else:
            return f"Performed {action_type.replace('_', ' ')}"
    
    def _get_share_description(self, share: Dict[str, Any]) -> str:
        """Generate human-readable share description"""
        share_type = share['share_type']
        metadata = share.get('metadata', {})
        
        if share_type == 'whatsapp':
            return "Shared via WhatsApp"
        elif share_type == 'email':
            return "Shared via Email"
        elif share_type == 'qr_download':
            return "Downloaded QR code"
        else:
            return f"Shared via {share_type}"

# Global analytics tracker instance
analytics = AnalyticsTracker()
