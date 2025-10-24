#!/usr/bin/env python3
"""
Test script for CloudFace AI Analytics System
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analytics_tracker import AnalyticsTracker
from datetime import datetime, timedelta
import json

def test_analytics():
    """Test the analytics system"""
    print("🧪 Testing CloudFace AI Analytics System")
    print("=" * 50)
    
    # Create analytics tracker
    analytics = AnalyticsTracker("test_analytics_data")
    
    # Test data
    test_user_id = "test_user_123"
    test_ip = "192.168.1.100"
    test_user_agent = "Mozilla/5.0 (Test Browser)"
    
    print("1. Testing session creation...")
    session_id = analytics.start_session(
        test_user_id, 
        test_ip, 
        test_user_agent, 
        "https://google.com", 
        "/app"
    )
    print(f"   ✅ Session created: {session_id}")
    
    print("2. Testing page view tracking...")
    analytics.track_page_view(
        session_id, 
        test_user_id, 
        "/app", 
        "CloudFace AI - Homepage", 
        "https://google.com", 
        30
    )
    print("   ✅ Page view tracked")
    
    print("3. Testing action tracking...")
    analytics.track_action(
        session_id, 
        test_user_id, 
        "photo_processed", 
        {"processed_count": 150, "total_files": 200}, 
        "/app"
    )
    analytics.track_action(
        session_id, 
        test_user_id, 
        "search_performed", 
        {"matches_found": 25, "threshold_used": 0.5}, 
        "/app"
    )
    analytics.track_action(
        session_id, 
        test_user_id, 
        "link_created", 
        {"session_id": "abc123", "folder_id": "folder456"}, 
        "/admin/link-generator"
    )
    print("   ✅ Actions tracked")
    
    print("4. Testing share tracking...")
    analytics.track_share(
        session_id, 
        test_user_id, 
        "whatsapp", 
        {"link": "https://cloudface-ai.com/s/abc123"}, 
        5
    )
    analytics.track_share(
        session_id, 
        test_user_id, 
        "email", 
        {"link": "https://cloudface-ai.com/s/abc123"}, 
        3
    )
    analytics.track_share(
        session_id, 
        test_user_id, 
        "qr_download", 
        {"link": "https://cloudface-ai.com/s/abc123"}, 
        1
    )
    print("   ✅ Shares tracked")
    
    print("5. Testing user analytics...")
    user_analytics = analytics.get_user_analytics(test_user_id, 30)
    print(f"   ✅ User analytics retrieved:")
    print(f"      - Sessions: {user_analytics['total_sessions']}")
    print(f"      - Page views: {user_analytics['total_page_views']}")
    print(f"      - Photos processed: {user_analytics['photos_processed']}")
    print(f"      - Links created: {user_analytics['links_created']}")
    print(f"      - Total shares: {user_analytics['total_shares']}")
    
    print("6. Testing overall analytics...")
    overall_analytics = analytics.get_overall_analytics(30)
    print(f"   ✅ Overall analytics retrieved:")
    print(f"      - Unique users: {overall_analytics['unique_users']}")
    print(f"      - Total sessions: {overall_analytics['total_sessions']}")
    print(f"      - Photos processed: {overall_analytics['photos_processed']}")
    print(f"      - Total shares: {overall_analytics['total_shares']}")
    
    print("7. Testing real-time stats...")
    realtime_stats = analytics.get_realtime_stats()
    print(f"   ✅ Real-time stats retrieved:")
    print(f"      - Active users (24h): {realtime_stats['active_users_24h']}")
    print(f"      - Active users (1h): {realtime_stats['active_users_1h']}")
    
    print("\n🎉 All analytics tests passed!")
    print("\n📊 Analytics Dashboard URL: http://localhost:8550/admin/analytics")
    print("📈 API Endpoints:")
    print("   - GET /api/analytics/overall?days=30")
    print("   - GET /api/analytics/user/{user_id}?days=30")
    print("   - GET /api/analytics/users?days=30")
    print("   - GET /api/analytics/realtime")
    print("   - POST /api/analytics/track-share")

if __name__ == "__main__":
    test_analytics()
