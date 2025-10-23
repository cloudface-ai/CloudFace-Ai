"""
Pricing and Plan Management System for Facetak
Separate module to handle subscriptions without affecting core functionality
"""
import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from enum import Enum

class PlanType(Enum):
    FREE = "free"
    STANDARD = "standard"
    PRO = "pro"
    PRO_PLUS = "pro_plus"
    EVERYTHING = "everything"
    ENTERPRISE = "enterprise"

class PricingManager:
    """Manages user plans, usage tracking, and limits"""
    
    def __init__(self, data_dir: str = "storage/pricing"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        # Plan configurations
        self.plans = {
            PlanType.FREE: {
                'name': 'Starter',
                'images': 500,
                'videos': 0,
                'price_inr': 0,
                'price_usd': 0,
                'features': ['Basic face recognition', 'Google Drive integration', 'Up to 500 images']
            },
            PlanType.STANDARD: {
                'name': 'Personal',
                'images': 20000,
                'videos': 20,
                'price_inr': 3999,
                'price_usd': 49,
                'features': ['Advanced face recognition', 'Video processing', 'Priority support', 'Smart caching']
            },
            PlanType.PRO: {
                'name': 'Professional',
                'images': 50000,
                'videos': 50,
                'price_inr': 6999,
                'price_usd': 85,
                'features': ['Professional accuracy', 'Bulk processing', 'API access', 'Custom thresholds']
            },
            PlanType.PRO_PLUS: {
                'name': 'Business',
                'images': 100000,
                'videos': 100,
                'price_inr': 11999,
                'price_usd': 145,
                'features': ['Enterprise features', 'Unlimited folders', 'Advanced analytics', 'White-label option']
            },
            PlanType.EVERYTHING: {
                'name': 'Business Plus',
                'images': 250000,
                'videos': 250,
                'price_inr': 15999,
                'price_usd': 195,
                'features': ['All features', 'Maximum limits', 'Priority support', 'Custom integrations', 'Advanced analytics']
            },
            PlanType.ENTERPRISE: {
                'name': 'Enterprise',
                'images': 550000,
                'videos': 500,
                'price_inr': 24999,
                'price_usd': 300,
                'features': ['Government-grade', 'Unlimited processing', 'Dedicated support', 'Custom deployment']
            }
        }
    
    def _get_user_file(self, user_id: str) -> str:
        """Get user's pricing data file path"""
        return os.path.join(self.data_dir, f"{user_id}_plan.json")
    
    def get_user_plan(self, user_id: str) -> Dict[str, Any]:
        """Get user's current plan and usage"""
        try:
            user_file = self._get_user_file(user_id)
            
            if not os.path.exists(user_file):
                # New user - create free plan
                return self._create_free_plan(user_id)
            
            with open(user_file, 'r') as f:
                user_data = json.load(f)
            
            # Check if plan expired
            if self._is_plan_expired(user_data):
                return self._downgrade_to_free(user_id, user_data)
            
            return user_data
            
        except Exception as e:
            print(f"❌ Error getting user plan: {e}")
            return self._create_free_plan(user_id)
    
    def _create_free_plan(self, user_id: str) -> Dict[str, Any]:
        """Create new free plan for user"""
        plan_data = {
            'user_id': user_id,
            'plan_type': PlanType.FREE.value,
            'plan_name': 'Starter',
            'created_at': datetime.now().isoformat(),
            'expires_at': None,  # Free plan doesn't expire
            'usage': {
                'images_processed': 0,
                'videos_processed': 0,
                'last_reset': datetime.now().isoformat()
            },
            'limits': self.plans[PlanType.FREE].copy(),
            'payment_history': []
        }
        
        self._save_user_plan(user_id, plan_data)
        return plan_data
    
    def _save_user_plan(self, user_id: str, plan_data: Dict[str, Any]) -> bool:
        """Save user plan data"""
        try:
            user_file = self._get_user_file(user_id)
            with open(user_file, 'w') as f:
                json.dump(plan_data, f, indent=2)
            return True
        except Exception as e:
            print(f"❌ Error saving user plan: {e}")
            return False
    
    def can_process_images(self, user_id: str, image_count: int) -> Dict[str, Any]:
        """Check if user can process specified number of images"""
        user_plan = self.get_user_plan(user_id)
        
        current_usage = user_plan['usage']['images_processed']
        limit = user_plan['limits']['images']
        remaining = limit - current_usage
        
        if image_count <= remaining:
            return {
                'allowed': True,
                'remaining': remaining,
                'limit': limit,
                'current_usage': current_usage
            }
        else:
            return {
                'allowed': False,
                'remaining': remaining,
                'limit': limit,
                'current_usage': current_usage,
                'overage': image_count - remaining,
                'suggested_plan': self._suggest_upgrade_plan(current_usage + image_count)
            }
    
    def track_image_usage(self, user_id: str, image_count: int) -> bool:
        """Track image processing usage"""
        try:
            user_plan = self.get_user_plan(user_id)
            user_plan['usage']['images_processed'] += image_count
            user_plan['usage']['last_activity'] = datetime.now().isoformat()
            
            return self._save_user_plan(user_id, user_plan)
            
        except Exception as e:
            print(f"❌ Error tracking usage: {e}")
            return False
    
    def _suggest_upgrade_plan(self, needed_images: int) -> Dict[str, Any]:
        """Suggest appropriate plan upgrade"""
        for plan_type, plan_config in self.plans.items():
            if plan_config['images'] >= needed_images:
                return {
                    'plan_type': plan_type.value,
                    'plan_name': plan_config['name'],
                    'price_inr': plan_config['price_inr'],
                    'price_usd': plan_config['price_usd'],
                    'images': plan_config['images']
                }
        
        # If no plan is sufficient, suggest enterprise
        return {
            'plan_type': PlanType.ENTERPRISE.value,
            'plan_name': self.plans[PlanType.ENTERPRISE]['name'],
            'price_inr': self.plans[PlanType.ENTERPRISE]['price_inr'],
            'price_usd': self.plans[PlanType.ENTERPRISE]['price_usd'],
            'images': self.plans[PlanType.ENTERPRISE]['images']
        }
    
    def _is_plan_expired(self, user_data: Dict[str, Any]) -> bool:
        """Check if user's plan has expired"""
        expires_at = user_data.get('expires_at')
        if not expires_at:
            return False  # Free plan or lifetime plan
        
        try:
            expiry_date = datetime.fromisoformat(expires_at)
            return datetime.now() > expiry_date
        except:
            return False
    
    def _downgrade_to_free(self, user_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Downgrade expired user to free plan"""
        user_data['plan_type'] = PlanType.FREE.value
        user_data['plan_name'] = 'Starter'
        user_data['expires_at'] = None
        user_data['limits'] = self.plans[PlanType.FREE].copy()
        user_data['downgraded_at'] = datetime.now().isoformat()
        
        self._save_user_plan(user_id, user_data)
        print(f"⬇️ Downgraded expired user {user_id} to Starter plan")
        return user_data
    
    def get_all_plans(self, currency: str = 'inr') -> Dict[str, Any]:
        """Get all available plans for pricing page"""
        price_key = f'price_{currency.lower()}'
        currency_symbol = '₹' if currency.lower() == 'inr' else '$'
        
        plans_data = {}
        for plan_type, plan_config in self.plans.items():
            plans_data[plan_type.value] = {
                'name': plan_config['name'],
                'images': plan_config['images'],
                'videos': plan_config['videos'],
                'price': plan_config[price_key],
                'currency_symbol': currency_symbol,
                'features': plan_config['features'],
                'recommended': plan_type == PlanType.PRO  # Mark Pro as recommended
            }
        
        return plans_data
    
    def upgrade_user_plan(self, user_id: str, new_plan_type: str, payment_data: Dict[str, Any]) -> bool:
        """Upgrade user to new plan after successful payment"""
        try:
            user_plan = self.get_user_plan(user_id)
            
            # Update plan
            new_plan = PlanType(new_plan_type)
            user_plan['plan_type'] = new_plan_type
            user_plan['plan_name'] = self.plans[new_plan]['name']
            user_plan['limits'] = self.plans[new_plan].copy()
            user_plan['upgraded_at'] = datetime.now().isoformat()
            
            # Set expiry (1 year from now for paid plans)
            if new_plan != PlanType.FREE:
                expiry_date = datetime.now() + timedelta(days=365)
                user_plan['expires_at'] = expiry_date.isoformat()
            
            # Add payment record
            user_plan['payment_history'].append({
                'plan': new_plan_type,
                'amount': payment_data.get('amount', 0),
                'currency': payment_data.get('currency', 'INR'),
                'payment_id': payment_data.get('payment_id', ''),
                'payment_method': payment_data.get('method', ''),
                'timestamp': datetime.now().isoformat()
            })
            
            return self._save_user_plan(user_id, user_plan)
            
        except Exception as e:
            print(f"❌ Error upgrading user plan: {e}")
            return False
    
    def get_usage_stats(self, user_id: str) -> Dict[str, Any]:
        """Get detailed usage statistics for user"""
        user_plan = self.get_user_plan(user_id)
        
        images_used = user_plan['usage']['images_processed']
        images_limit = user_plan['limits']['images']
        images_remaining = max(0, images_limit - images_used)
        images_percentage = min(100, (images_used / images_limit) * 100) if images_limit > 0 else 0
        
        videos_used = user_plan['usage'].get('videos_processed', 0)
        videos_limit = user_plan['limits']['videos']
        videos_remaining = max(0, videos_limit - videos_used)
        videos_percentage = min(100, (videos_used / videos_limit) * 100) if videos_limit > 0 else 0
        
        return {
            'plan_name': user_plan['plan_name'],
            'plan_type': user_plan['plan_type'],
            'images': {
                'used': images_used,
                'limit': images_limit,
                'remaining': images_remaining,
                'percentage': round(images_percentage, 1),
                'unlimited': images_limit >= 500000
            },
            'videos': {
                'used': videos_used,
                'limit': videos_limit,
                'remaining': videos_remaining,
                'percentage': round(videos_percentage, 1),
                'unlimited': videos_limit >= 500
            },
            'expires_at': user_plan.get('expires_at'),
            'is_expired': self._is_plan_expired(user_plan)
        }
    
    def make_user_pro(self, user_id: str) -> bool:
        """Quick function to make a user Professional for testing"""
        try:
            user_plan = {
                'user_id': user_id,
                'plan_type': PlanType.PRO.value,
                'plan_name': 'Professional',
                'created_at': datetime.now().isoformat(),
                'expires_at': (datetime.now() + timedelta(days=365)).isoformat(),  # 1 year
                'payment_info': {
                    'amount': 0,
                    'currency': 'FREE_UPGRADE',
                    'payment_id': 'ADMIN_UPGRADE',
                    'method': 'manual'
                },
                'usage': {
                    'images_processed': 0,
                    'videos_processed': 0,
                    'last_activity': datetime.now().isoformat()
                },
                'limits': self.plans[PlanType.PRO]
            }
            
            # Save user plan
            user_file = os.path.join(self.data_dir, f"{user_id}.json")
            with open(user_file, 'w') as f:
                json.dump(user_plan, f, indent=2)
            
            print(f"✅ User {user_id} upgraded to Professional plan (50,000 images)")
            return True
            
        except Exception as e:
            print(f"❌ Failed to upgrade user {user_id}: {e}")
            return False
    
    def make_user_enterprise(self, user_id: str) -> bool:
        """Quick function to make a user Enterprise for testing"""
        try:
            user_plan = {
                'user_id': user_id,
                'plan_type': PlanType.ENTERPRISE.value,
                'plan_name': 'Enterprise',
                'created_at': datetime.now().isoformat(),
                'expires_at': (datetime.now() + timedelta(days=365)).isoformat(),  # 1 year
                'upgraded_at': datetime.now().isoformat(),
                'usage': {
                    'images_processed': 0,
                    'videos_processed': 0,
                    'last_reset': datetime.now().isoformat(),
                    'last_activity': datetime.now().isoformat()
                },
                'limits': self.plans[PlanType.ENTERPRISE].copy(),
                'payment_history': [{
                    'plan': PlanType.ENTERPRISE.value,
                    'amount': 0,
                    'currency': 'FREE_UPGRADE',
                    'payment_id': 'ADMIN_ENTERPRISE_UPGRADE',
                    'payment_method': 'manual',
                    'timestamp': datetime.now().isoformat()
                }]
            }
            
            # Save user plan using the existing method
            return self._save_user_plan(user_id, user_plan)
            
        except Exception as e:
            print(f"❌ Failed to upgrade user {user_id} to Enterprise: {e}")
            return False

# Global pricing manager instance
pricing_manager = PricingManager()
