#!/bin/bash

# CloudFace AI Environment Switcher
# Usage: ./switch-env.sh [local|production]

if [ "$1" == "local" ]; then
    echo "🔄 Switching to LOCAL/TEST environment..."
    cp .env.local .env
    echo "✅ Environment switched to LOCAL"
    echo ""
    echo "📋 Test Mode Active:"
    echo "   - Razorpay: TEST MODE"
    echo "   - Test Card: 4111 1111 1111 1111"
    echo "   - CVV: Any 3 digits"
    echo "   - Expiry: Any future date"
    echo ""
    echo "🚀 Start server: python web_server.py"
    
elif [ "$1" == "production" ]; then
    echo "🔄 Switching to PRODUCTION/LIVE environment..."
    cp .env.production .env
    echo "✅ Environment switched to PRODUCTION"
    echo ""
    echo "⚠️  LIVE Mode Active:"
    echo "   - Razorpay: LIVE MODE (real payments!)"
    echo "   - Real cards only"
    echo "   - Actual charges will apply"
    echo ""
    echo "🚀 Deploy to VPS or use with caution locally"
    
else
    echo "❌ Invalid argument!"
    echo ""
    echo "Usage: ./switch-env.sh [local|production]"
    echo ""
    echo "Examples:"
    echo "  ./switch-env.sh local       - Switch to test mode"
    echo "  ./switch-env.sh production  - Switch to live mode"
    exit 1
fi

