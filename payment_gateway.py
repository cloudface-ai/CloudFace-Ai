"""
Payment Gateway Integration for Facetak
Handles Razorpay (India) and PayPal (International) payments
Separate module to keep payment logic isolated
"""
import os
import json
import hashlib
import hmac
import time
from typing import Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables with explicit path and override
load_dotenv('.env', override=True)

class PaymentGateway:
    """Handles payment processing for different regions"""
    
    def __init__(self):
        self.razorpay_key_id = os.getenv('RAZORPAY_KEY_ID', '')
        self.razorpay_key_secret = os.getenv('RAZORPAY_KEY_SECRET', '')
        self.paypal_client_id = os.getenv('PAYPAL_CLIENT_ID', '')
        self.paypal_client_secret = os.getenv('PAYPAL_CLIENT_SECRET', '')
        
        # Debug: Print what was loaded
        print(f"🔧 PaymentGateway initialized:")
        print(f"   Razorpay Key ID: {self.razorpay_key_id}")
        print(f"   Razorpay Key Secret: {'SET' if self.razorpay_key_secret else 'EMPTY'} ({len(self.razorpay_key_secret)} chars)")
        
        # Payment logs directory
        self.logs_dir = "storage/payment_logs"
        os.makedirs(self.logs_dir, exist_ok=True)
    
    def create_razorpay_order(self, amount_inr: int, plan_name: str, user_id: str) -> Dict[str, Any]:
        """Create Razorpay order for Indian customers"""
        try:
            try:
                import razorpay
            except ImportError:
                return {'success': False, 'error': 'Razorpay not installed. Run: pip install razorpay==1.3.0'}
            
            print(f"🔑 Creating Razorpay client with:")
            print(f"   Key ID: {self.razorpay_key_id}")
            print(f"   Key Secret: {self.razorpay_key_secret[:5]}...{self.razorpay_key_secret[-5:] if self.razorpay_key_secret else 'EMPTY'}")
            
            client = razorpay.Client(auth=(self.razorpay_key_id, self.razorpay_key_secret))
            
            order_data = {
                'amount': amount_inr * 100,  # Razorpay expects paise
                'currency': 'INR',
                'receipt': f"cf_{int(time.time())}",  # Max 40 chars
                'notes': {
                    'plan': plan_name,
                    'user_id': user_id,
                    'app': 'cloudface'
                }
            }
            
            print(f"💳 Creating order for {amount_inr} INR")
            order = client.order.create(data=order_data)
            
            # Log order creation
            self._log_payment_event('razorpay_order_created', {
                'user_id': user_id,
                'order_id': order['id'],
                'amount': amount_inr,
                'plan': plan_name
            })
            
            return {
                'success': True,
                'order_id': order['id'],
                'amount': amount_inr,
                'currency': 'INR',
                'key': self.razorpay_key_id
            }
            
        except Exception as e:
            print(f"❌ Razorpay order creation failed: {e}")
            print(f"   Key ID: {self.razorpay_key_id}")
            print(f"   Secret length: {len(self.razorpay_key_secret) if self.razorpay_key_secret else 0}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
    
    def verify_razorpay_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Verify Razorpay payment signature"""
        try:
            order_id = payment_data.get('razorpay_order_id')
            payment_id = payment_data.get('razorpay_payment_id')
            signature = payment_data.get('razorpay_signature')
            
            # Create signature for verification
            message = f"{order_id}|{payment_id}"
            expected_signature = hmac.new(
                self.razorpay_key_secret.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            if hmac.compare_digest(expected_signature, signature):
                # Log successful payment
                self._log_payment_event('razorpay_payment_success', {
                    'order_id': order_id,
                    'payment_id': payment_id,
                    'verified': True
                })
                
                return {
                    'success': True,
                    'payment_id': payment_id,
                    'order_id': order_id,
                    'method': 'razorpay'
                }
            else:
                # Log failed verification
                self._log_payment_event('razorpay_verification_failed', {
                    'order_id': order_id,
                    'payment_id': payment_id,
                    'expected_signature': expected_signature,
                    'received_signature': signature
                })
                
                return {'success': False, 'error': 'Payment verification failed'}
                
        except Exception as e:
            print(f"❌ Razorpay verification error: {e}")
            return {'success': False, 'error': str(e)}
    
    def create_paypal_order(self, amount_usd: float, plan_name: str, user_id: str) -> Dict[str, Any]:
        """Create PayPal order for international customers"""
        try:
            # PayPal API integration would go here
            # For now, return structure for frontend integration
            
            order_id = f"paypal_{user_id}_{int(time.time())}"
            
            # Log order creation
            self._log_payment_event('paypal_order_created', {
                'user_id': user_id,
                'order_id': order_id,
                'amount': amount_usd,
                'plan': plan_name
            })
            
            return {
                'success': True,
                'order_id': order_id,
                'amount': amount_usd,
                'currency': 'USD',
                'client_id': self.paypal_client_id
            }
            
        except Exception as e:
            print(f"❌ PayPal order creation failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def verify_paypal_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Verify PayPal payment"""
        try:
            # PayPal verification logic would go here
            # For now, basic structure
            
            order_id = payment_data.get('orderID')
            payer_id = payment_data.get('payerID')
            
            # Log payment attempt
            self._log_payment_event('paypal_payment_attempt', {
                'order_id': order_id,
                'payer_id': payer_id
            })
            
            # In real implementation, verify with PayPal API
            return {
                'success': True,
                'payment_id': f"paypal_{order_id}",
                'order_id': order_id,
                'method': 'paypal'
            }
            
        except Exception as e:
            print(f"❌ PayPal verification error: {e}")
            return {'success': False, 'error': str(e)}
    
    def _log_payment_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log payment events for audit trail"""
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'event_type': event_type,
                'data': data
            }
            
            log_file = os.path.join(self.logs_dir, f"payments_{datetime.now().strftime('%Y%m')}.json")
            
            # Append to monthly log file
            logs = []
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    logs = json.load(f)
            
            logs.append(log_entry)
            
            with open(log_file, 'w') as f:
                json.dump(logs, f, indent=2)
                
        except Exception as e:
            print(f"⚠️ Payment logging error: {e}")
    
    def get_payment_methods(self, user_location: str = 'IN') -> Dict[str, Any]:
        """Get available payment methods based on user location"""
        if user_location.upper() == 'IN':
            return {
                'primary': 'razorpay',
                'methods': ['UPI', 'Cards', 'Net Banking', 'Wallets'],
                'currency': 'INR',
                'symbol': '₹'
            }
        else:
            return {
                'primary': 'paypal',
                'methods': ['PayPal', 'Credit Card', 'Debit Card'],
                'currency': 'USD',
                'symbol': '$'
            }

# Global payment gateway instance
payment_gateway = PaymentGateway()
