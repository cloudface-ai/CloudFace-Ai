# Razorpay Setup Guide for CloudFace AI

This guide helps you configure Razorpay payment gateway for CloudFace AI with the updated pricing plans.

## Step 1: Create Razorpay Account

1. Go to [Razorpay Dashboard](https://dashboard.razorpay.com/)
2. Sign up or log in to your account
3. Complete KYC verification if not done already

## Step 2: Get API Keys

1. Go to **Settings** → **API Keys**
2. Copy your **Key ID** and **Key Secret**
3. Add them to your `.env` file:
   ```bash
   RAZORPAY_KEY_ID=rzp_live_xxxxxxxxxxxxx
   RAZORPAY_KEY_SECRET=your_secret_key_here
   ```

## Step 3: Create Subscription Plans

Create the following plans in your Razorpay dashboard:

### Plan 1: Personal
- **Plan ID**: `plan_RREZTkjH48VB3r`
- **Name**: Personal Plan
- **Description**: 20,000 images, 20 videos, advanced features
- **Amount**: ₹3,999 (399900 paise)
- **Billing Period**: Yearly
- **Currency**: INR

### Plan 2: Professional  
- **Plan ID**: `plan_RREa2fgPuIQV44`
- **Name**: Professional Plan
- **Description**: 50,000 images, 50 videos, API access
- **Amount**: ₹6,999 (699900 paise)
- **Billing Period**: Yearly
- **Currency**: INR

### Plan 3: Business
- **Plan ID**: `plan_RREac0AtZQ8IQH`
- **Name**: Business Plan
- **Description**: 100,000 images, 100 videos, enterprise features
- **Amount**: ₹11,999 (1199900 paise)
- **Billing Period**: Yearly
- **Currency**: INR

### Plan 4: Business Plus
- **Plan ID**: `plan_RREb5LiLKoAvgl`
- **Name**: Business Plus Plan
- **Description**: 250,000 images, 250 videos, all features
- **Amount**: ₹15,999 (1599900 paise)
- **Billing Period**: Yearly
- **Currency**: INR

### Plan 5: Enterprise
- **Plan ID**: `plan_RREbW2fUEwSe3y`
- **Name**: Enterprise Plan
- **Description**: 550,000 images, 500 videos, government-grade
- **Amount**: ₹24,999 (2499900 paise)
- **Billing Period**: Yearly
- **Currency**: INR

## Step 4: Configure Webhooks

1. Go to **Settings** → **Webhooks**
2. Add webhook endpoint: `https://yourdomain.com/razorpay/webhook`
3. Select events:
   - `subscription.charged`
   - `subscription.cancelled`
   - `subscription.paused`
   - `subscription.resumed`
4. Copy webhook secret and add to `.env`:
   ```bash
   RAZORPAY_WEBHOOK_SECRET=your_webhook_secret_here
   ```

## Step 5: Environment Variables

Add these to your `.env` file:

```bash
# Razorpay Configuration
RAZORPAY_KEY_ID=rzp_live_xxxxxxxxxxxxx
RAZORPAY_KEY_SECRET=your_secret_key_here
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret_here

# Plan IDs
RAZORPAY_PLAN_PERSONAL=plan_RREZTkjH48VB3r
RAZORPAY_PLAN_PROFESSIONAL=plan_RREa2fgPuIQV44
RAZORPAY_PLAN_BUSINESS=plan_RREac0AtZQ8IQH
RAZORPAY_PLAN_BUSINESS_PLUS=plan_RREb5LiLKoAvgl
RAZORPAY_PLAN_ENTERPRISE=plan_RREbW2fUEwSe3y
```

## Step 6: Test Integration

1. Start with **Test Mode** to verify everything works
2. Switch to **Live Mode** when ready for production
3. Test payment flow with small amounts first

## Important Notes

- **Paise Conversion**: Razorpay uses paise (₹1 = 100 paise)
- **Plan IDs**: Must match exactly between code and dashboard
- **Webhook Security**: Always verify webhook signatures
- **Error Handling**: Implement proper error handling for failed payments
- **Testing**: Use Razorpay test cards for development

## Troubleshooting

### Common Issues:
1. **Invalid Plan ID**: Check plan ID matches dashboard
2. **Webhook not working**: Verify endpoint URL and events
3. **Payment failures**: Check API keys and plan configuration
4. **Amount mismatch**: Ensure amounts are in paise

### Support:
- Razorpay Documentation: https://razorpay.com/docs/
- Razorpay Support: https://razorpay.com/support/
