#!/usr/bin/env python3
"""
Quick script to manually upgrade a user's plan
"""
from pricing_manager import pricing_manager, PlanType

# User to upgrade
user_email = "smp@glamly.com"

# Available plans:
# PlanType.FREE - Starter (500 images)
# PlanType.STANDARD - Personal (20,000 images)
# PlanType.PRO - Professional (50,000 images)
# PlanType.PRO_PLUS - Business (100,000 images)
# PlanType.EVERYTHING - Business Plus (250,000 images)
# PlanType.ENTERPRISE - Enterprise (550,000 images)

# Upgrade to ENTERPRISE plan (biggest plan)
new_plan = "enterprise"

print(f"🔄 Upgrading {user_email} to {new_plan.upper()} plan...")

# Mock payment data (since it's manual upgrade)
payment_data = {
    'amount': 0,
    'currency': 'INR',
    'payment_id': 'MANUAL_UPGRADE',
    'method': 'admin_manual'
}

success = pricing_manager.upgrade_user_plan(
    user_id=user_email,
    new_plan_type=new_plan,
    payment_data=payment_data
)

if success:
    print(f"✅ Successfully upgraded {user_email} to {new_plan.upper()} plan!")
    
    # Show new plan details
    user_plan = pricing_manager.get_user_plan(user_email)
    print(f"\n📊 New Plan Details:")
    print(f"  Plan: {user_plan['plan_name']}")
    print(f"  Images Limit: {user_plan['limits']['images']:,}")
    print(f"  Videos Limit: {user_plan['limits']['videos']}")
    print(f"  Expires: {user_plan.get('expires_at', 'Never')}")
else:
    print(f"❌ Failed to upgrade {user_email}")

