import stripe
import os
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class StripeService:
    def __init__(self):
        self.stripe_secret_key = os.getenv('STRIPE_SECRET_KEY')
        if not self.stripe_secret_key:
            logger.error("STRIPE_SECRET_KEY environment variable is not set")
            raise ValueError("STRIPE_SECRET_KEY is required but not set")
        
        stripe.api_key = self.stripe_secret_key
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        
        # 料金設定
        self.BASIC_PLAN_PRICE = 3000  # 3,000円
        self.ADDITIONAL_PACK_PRICE = 3000  # 3,000円
        self.CURRENCY = 'jpy'
        
        # Stripe商品ID
        self.BASIC_PLAN_PRODUCT_ID = 'prod_SujKOCieVMHURs'
        self.ADDITIONAL_PACK_PRODUCT_ID = 'prod_SujMCgf719WkIX'
        
        # Stripe価格ID
        self.BASIC_PLAN_PRICE_ID = 'price_1Ryts6JcdIKryf6lsvgm1q98'
        self.ADDITIONAL_PACK_PRICE_ID = 'price_1RyttOJcdIKryf6l8GuUjVJC'
    
    def create_customer(self, email: str, name: str = '', metadata: Dict[str, str] = None) -> str:
        """Stripe顧客を作成"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            
            logger.info(f"Stripe customer created: {customer.id}")
            return customer.id
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe customer creation error: {str(e)}")
            raise
    
    def create_subscription(self, customer_id: str, price_id: str, metadata: Dict[str, str] = None) -> Dict[str, Any]:
        """定期サブスクリプションを作成（基本プラン用）"""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                metadata=metadata or {},
                expand=['latest_invoice.payment_intent']
            )
            
            logger.info(f"Stripe subscription created: {subscription.id}")
            return {
                'id': subscription.id,
                'status': subscription.status,
                'client_secret': subscription.latest_invoice.payment_intent.client_secret if subscription.latest_invoice else None
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe subscription creation error: {str(e)}")
            raise
    
    def create_one_time_payment(self, customer_id: str, amount: int, description: str, metadata: Dict[str, str] = None) -> Dict[str, Any]:
        """一回限りの支払いを作成（追加パック用）"""
        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=self.CURRENCY,
                customer=customer_id,
                description=description,
                metadata=metadata or {},
                automatic_payment_methods={'enabled': True}
            )
            
            logger.info(f"Payment intent created: {payment_intent.id}")
            return {
                'id': payment_intent.id,
                'client_secret': payment_intent.client_secret,
                'status': payment_intent.status
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Payment intent creation error: {str(e)}")
            raise
    
    def create_checkout_session(self, customer_id: str, success_url: str, cancel_url: str, 
                               line_items: list, metadata: Dict[str, str] = None) -> Dict[str, Any]:
        """Checkout セッションを作成"""
        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=line_items,
                mode='subscription' if any(item.get('price') == self.BASIC_PLAN_PRICE_ID for item in line_items) else 'payment',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata or {}
            )
            
            logger.info(f"Checkout session created: {session.id}")
            return {
                'id': session.id,
                'url': session.url
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Checkout session creation error: {str(e)}")
            raise
    
    def create_basic_plan_checkout(self, customer_id: str, user_id: str, success_url: str, cancel_url: str) -> Dict[str, Any]:
        """基本プラン（月額3,000円）のチェックアウトを作成"""
        line_items = [{
            'price': self.BASIC_PLAN_PRICE_ID,
            'quantity': 1
        }]
        
        return self.create_checkout_session(
            customer_id=customer_id,
            success_url=success_url,
            cancel_url=cancel_url,
            line_items=line_items,
            metadata={'user_id': user_id, 'plan_type': 'basic'}
        )
    
    def create_additional_pack_checkout(self, customer_id: str, user_id: str, success_url: str, cancel_url: str) -> Dict[str, Any]:
        """追加パック（3,000円）のチェックアウトを作成"""
        line_items = [{
            'price': self.ADDITIONAL_PACK_PRICE_ID,
            'quantity': 1
        }]
        
        return self.create_checkout_session(
            customer_id=customer_id,
            success_url=success_url,
            cancel_url=cancel_url,
            line_items=line_items,
            metadata={'user_id': user_id, 'plan_type': 'additional_pack'}
        )
    
    def cancel_subscription(self, subscription_id: str) -> bool:
        """サブスクリプションをキャンセル"""
        try:
            stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            
            logger.info(f"Subscription cancelled: {subscription_id}")
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Subscription cancellation error: {str(e)}")
            return False
    
    def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Stripe顧客情報を取得"""
        try:
            customer = stripe.Customer.retrieve(customer_id)
            return customer
            
        except stripe.error.StripeError as e:
            logger.error(f"Customer retrieval error: {str(e)}")
            return None
    
    def verify_webhook_signature(self, payload: str, signature: str) -> bool:
        """Webhookの署名を検証"""
        try:
            stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            return True
        except (ValueError, stripe.error.SignatureVerificationError):
            return False
    
    def handle_webhook_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Webhookイベントを処理"""
        try:
            event_type = event['type']
            
            if event_type == 'checkout.session.completed':
                return self._handle_checkout_completed(event['data']['object'])
            
            elif event_type == 'customer.subscription.updated':
                return self._handle_subscription_updated(event['data']['object'])
            
            elif event_type == 'invoice.payment_succeeded':
                return self._handle_payment_succeeded(event['data']['object'])
            
            elif event_type == 'customer.subscription.deleted':
                return self._handle_subscription_deleted(event['data']['object'])
            
            return {'status': 'unhandled', 'event_type': event_type}
            
        except Exception as e:
            logger.error(f"Webhook handling error: {str(e)}")
            return {'status': 'error', 'error': str(e)}
    
    def _handle_checkout_completed(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """チェックアウト完了時の処理"""
        try:
            metadata = session.get('metadata', {})
            user_id = metadata.get('user_id')
            plan_type = metadata.get('plan_type')
            
            if not user_id:
                return {'status': 'error', 'error': 'Missing user_id in metadata'}
            
            return {
                'status': 'success',
                'action': 'checkout_completed',
                'user_id': user_id,
                'plan_type': plan_type,
                'session_id': session.get('id'),
                'customer_id': session.get('customer')
            }
            
        except Exception as e:
            logger.error(f"Checkout completion handling error: {str(e)}")
            return {'status': 'error', 'error': str(e)}
    
    def _handle_subscription_updated(self, subscription: Dict[str, Any]) -> Dict[str, Any]:
        """サブスクリプション更新時の処理"""
        return {
            'status': 'success',
            'action': 'subscription_updated',
            'subscription_id': subscription.get('id'),
            'status_new': subscription.get('status')
        }
    
    def _handle_payment_succeeded(self, invoice: Dict[str, Any]) -> Dict[str, Any]:
        """支払い成功時の処理"""
        return {
            'status': 'success',
            'action': 'payment_succeeded',
            'invoice_id': invoice.get('id'),
            'customer_id': invoice.get('customer')
        }
    
    def _handle_subscription_deleted(self, subscription: Dict[str, Any]) -> Dict[str, Any]:
        """サブスクリプション削除時の処理"""
        return {
            'status': 'success',
            'action': 'subscription_deleted',
            'subscription_id': subscription.get('id')
        }