"""
Quick script to upgrade user to Enterprise plan for testing
"""
from pricing_manager import pricing_manager

def upgrade_user_to_enterprise(email):
    """Upgrade a user to Enterprise plan"""
    print(f"🚀 Upgrading {email} to Enterprise plan...")
    
    success = pricing_manager.make_user_enterprise(email)
    
    if success:
        print(f"✅ Successfully upgraded {email} to Enterprise plan!")
        print(f"📊 Plan details:")
        
        # Get and display the user's plan
        user_plan = pricing_manager.get_user_plan(email)
        print(f"   Plan: {user_plan.get('plan_name')}")
        print(f"   Images limit: {user_plan.get('limits', {}).get('images', 'N/A'):,}")
        print(f"   Videos limit: {user_plan.get('limits', {}).get('videos', 'N/A')}")
        print(f"   Expires: {user_plan.get('expires_at')}")
        print(f"   Features: {', '.join(user_plan.get('limits', {}).get('features', []))}")
    else:
        print(f"❌ Failed to upgrade {email}")
    
    return success

if __name__ == "__main__":
    # Your email
    user_email = "spvinodmandan@gmail.com"
    upgrade_user_to_enterprise(user_email)

