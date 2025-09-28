import stripe
import os
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class StripeService:
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        
        # 料金設定
        self.CURRENCY = 'jpy'
        
        # サブスクリプションプラン料金
        self.LIGHT_PLAN_PRICE = 1480  # ライト: 1,480円/月
        self.REGULAR_PLAN_PRICE = 3300  # レギュラー: 3,300円/月
        self.HEAVY_PLAN_PRICE = 5500  # ヘビー: 5,500円/月
        
        # 追加パック料金
        self.PACK_20_PRICE = 1480  # 20回パック: 1,480円
        self.PACK_40_PRICE = 2680  # 40回パック: 2,680円
        self.PACK_90_PRICE = 5500  # 90回パック: 5,500円
        
        # サブスクリプションプラン商品ID
        self.LIGHT_PLAN_PRODUCT_ID = 'prod_SxZi2RoMUuSYPx'
        self.REGULAR_PLAN_PRODUCT_ID = 'prod_SujKOCieVMHURs'
        self.HEAVY_PLAN_PRODUCT_ID = 'prod_SxZnP56JdS3sAO'
        
        # サブスクリプションプラン価格ID（正しいSubscriptionオブジェクト生成用）
        self.LIGHT_PLAN_PRICE_ID = 'price_1S1eZFJcdIKryf6lLOaoQDuk'
        self.REGULAR_PLAN_PRICE_ID = 'price_1Ryts6JcdIKryf6lsvgm1q98'
        self.HEAVY_PLAN_PRICE_ID = 'price_1S1edcJcdIKryf6lhohuXrjN'
        
        # 追加パック商品ID
        self.PACK_20_PRODUCT_ID = 'prod_SxabdJImg6JtmO'
        self.PACK_40_PRODUCT_ID = 'prod_SxachRVt6fDEBe'
        self.PACK_90_PRODUCT_ID = 'prod_SxadRgOEp2KQEh'
        
        # 後方互換性のため（既存コードで使用されている可能性）
        self.BASIC_PLAN_PRODUCT_ID = self.REGULAR_PLAN_PRODUCT_ID
        self.ADDITIONAL_PACK_PRODUCT_ID = self.PACK_90_PRODUCT_ID

        # 専門家相談料金設定（税込）
        self.CONSULTATION_BASIC_PRICE = 14300    # 基本相談 (30分): 14,300円（税込）

        # 専門家相談用固定商品ID
        self.CONSULTATION_PRICE_ID = 'price_1S9ggFJcdIKryf6lQjHhlUz6'  # 14,300円の固定Price ID
    
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
                mode='subscription' if any('recurring' in item.get('price_data', {}) for item in line_items) else 'payment',
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
    
    # ===== サブスクリプションプランチェックアウト =====
    
    def create_light_plan_checkout(self, customer_id: str, user_id: str, success_url: str, cancel_url: str) -> Dict[str, Any]:
        """ライトプラン（1,480円/月 20回）のチェックアウトを作成"""
        return self._create_subscription_checkout(
            customer_id, user_id, success_url, cancel_url,
            self.LIGHT_PLAN_PRODUCT_ID, 'light'
        )
    
    def create_regular_plan_checkout(self, customer_id: str, user_id: str, success_url: str, cancel_url: str) -> Dict[str, Any]:
        """レギュラープラン（3,300円/月 50回）のチェックアウトを作成"""
        return self._create_subscription_checkout(
            customer_id, user_id, success_url, cancel_url,
            self.REGULAR_PLAN_PRODUCT_ID, 'regular'
        )
    
    def create_heavy_plan_checkout(self, customer_id: str, user_id: str, success_url: str, cancel_url: str) -> Dict[str, Any]:
        """ヘビープラン（5,500円/月 90回）のチェックアウトを作成"""
        return self._create_subscription_checkout(
            customer_id, user_id, success_url, cancel_url,
            self.HEAVY_PLAN_PRODUCT_ID, 'heavy'
        )
    
    def _create_subscription_checkout(self, customer_id: str, user_id: str, success_url: str, cancel_url: str, product_id: str, plan_type: str) -> Dict[str, Any]:
        """サブスクリプションチェックアウトの共通処理"""
        try:
            # プラン別のPrice IDを取得
            price_id = self._get_plan_price_id(plan_type)
            if not price_id:
                raise ValueError(f"Invalid plan type: {plan_type}")
            
            # Stripeセッションを作成（Price IDを使用）
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,  # Price IDを直接使用
                    'quantity': 1
                }],
                mode='subscription',
                success_url=success_url,  # Stripeが{CHECKOUT_SESSION_ID}を自動置換
                cancel_url=cancel_url,
                metadata={'user_id': user_id, 'plan_type': plan_type}
            )
            
            logger.info(f"{plan_type.capitalize()} plan checkout session created: {session.id}")
            return {
                'id': session.id,
                'url': session.url
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"{plan_type.capitalize()} plan checkout creation error: {str(e)}")
            raise
    
    # ===== 追加パックチェックアウト =====
    
    def create_pack_20_checkout(self, customer_id: str, user_id: str, success_url: str, cancel_url: str) -> Dict[str, Any]:
        """20回追加パック（1,480円）のチェックアウトを作成"""
        return self._create_pack_checkout(
            customer_id, user_id, success_url, cancel_url,
            self.PACK_20_PRODUCT_ID, self.PACK_20_PRICE, 'pack_20', 20
        )
    
    def create_pack_40_checkout(self, customer_id: str, user_id: str, success_url: str, cancel_url: str) -> Dict[str, Any]:
        """40回追加パック（2,680円）のチェックアウトを作成"""
        return self._create_pack_checkout(
            customer_id, user_id, success_url, cancel_url,
            self.PACK_40_PRODUCT_ID, self.PACK_40_PRICE, 'pack_40', 40
        )
    
    def create_pack_90_checkout(self, customer_id: str, user_id: str, success_url: str, cancel_url: str) -> Dict[str, Any]:
        """90回追加パック（5,500円）のチェックアウトを作成"""
        return self._create_pack_checkout(
            customer_id, user_id, success_url, cancel_url,
            self.PACK_90_PRODUCT_ID, self.PACK_90_PRICE, 'pack_90', 90
        )
    
    def _create_pack_checkout(self, customer_id: str, user_id: str, success_url: str, cancel_url: str, product_id: str, price: int, pack_type: str, questions_count: int) -> Dict[str, Any]:
        """追加パックチェックアウトの共通処理"""
        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': self.CURRENCY,
                        'product': product_id,
                        'unit_amount': price
                    },
                    'quantity': 1
                }],
                mode='payment',
                success_url=success_url,  # Stripeが{CHECKOUT_SESSION_ID}を自動置換
                cancel_url=cancel_url,
                metadata={
                    'user_id': user_id, 
                    'plan_type': pack_type,
                    'questions_count': str(questions_count)
                }
            )
            
            logger.info(f"{pack_type} checkout session created: {session.id}")
            return {
                'id': session.id,
                'url': session.url
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"{pack_type} checkout creation error: {str(e)}")
            raise
    
    def _get_plan_price(self, plan_type: str) -> int:
        """プランタイプから料金を取得"""
        price_map = {
            'light': self.LIGHT_PLAN_PRICE,
            'regular': self.REGULAR_PLAN_PRICE,
            'heavy': self.HEAVY_PLAN_PRICE
        }
        return price_map.get(plan_type, self.REGULAR_PLAN_PRICE)
    
    def _get_plan_price_id(self, plan_type: str) -> str:
        """プラン別のPrice IDを取得"""
        price_ids = {
            'light': self.LIGHT_PLAN_PRICE_ID,
            'regular': self.REGULAR_PLAN_PRICE_ID,
            'heavy': self.HEAVY_PLAN_PRICE_ID,
            'basic': self.REGULAR_PLAN_PRICE_ID  # 後方互換性
        }
        return price_ids.get(plan_type, '')
    
    # ===== 後方互換性のためのメソッド =====
    
    def create_basic_plan_checkout(self, customer_id: str, user_id: str, success_url: str, cancel_url: str) -> Dict[str, Any]:
        """既存コードとの互換性のため - レギュラープランにリダイレクト"""
        return self.create_regular_plan_checkout(customer_id, user_id, success_url, cancel_url)
    
    def create_additional_pack_checkout(self, customer_id: str, user_id: str, success_url: str, cancel_url: str) -> Dict[str, Any]:
        """既存コードとの互換性のため - 90回パックにリダイレクト"""
        return self.create_pack_90_checkout(customer_id, user_id, success_url, cancel_url)
    
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
    
    def get_subscription_from_session(self, session_id: str) -> Optional[str]:
        """Session IDからSubscription IDを取得"""
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            subscription_id = session.get('subscription')
            
            if subscription_id:
                logger.info(f"Retrieved subscription ID {subscription_id} from session {session_id}")
                return subscription_id
            else:
                logger.warning(f"No subscription found in session {session_id}")
                return None
                
        except stripe.error.StripeError as e:
            logger.error(f"Session retrieval error: {str(e)}")
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
            payment_type = metadata.get('payment_type')
            consultation_id = metadata.get('consultation_id')

            if not user_id:
                return {'status': 'error', 'error': 'Missing user_id in metadata'}

            # 専門家相談の決済完了処理
            if payment_type == 'expert_consultation' and consultation_id:
                temp_reservation_id = metadata.get('temp_reservation_id')
                return {
                    'status': 'success',
                    'action': 'expert_consultation_paid',
                    'consultation_id': consultation_id,
                    'user_id': user_id,
                    'session_id': session.get('id'),
                    'payment_intent_id': session.get('payment_intent'),
                    'temp_reservation_id': temp_reservation_id if temp_reservation_id else None
                }

            # 通常のサブスクリプション・パック決済
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

    # ===== 専門家相談決済関連メソッド =====

    def create_consultation_payment(self, customer_id: str, plan_type: str, consultation_category: str,
                                   user_info: Dict[str, Any], success_url: str, cancel_url: str) -> Dict[str, Any]:
        """専門家相談の決済セッションを作成"""
        try:
            # プランタイプから料金を取得
            price_map = {
                'basic': self.CONSULTATION_BASIC_PRICE,
                'standard': self.CONSULTATION_STANDARD_PRICE,
                'premium': self.CONSULTATION_PREMIUM_PRICE
            }

            if plan_type not in price_map:
                raise ValueError(f"Invalid consultation plan type: {plan_type}")

            amount = price_map[plan_type]

            # プラン名マッピング
            plan_names = {
                'basic': '基本相談 (30分)',
                'standard': '詳細相談 (60分)',
                'premium': '包括相談 (90分)'
            }

            # カテゴリ名マッピング
            category_names = {
                'business_improvement': '業務改善助成金',
                'career_up': 'キャリアアップ助成金',
                'human_development': '人材開発支援助成金',
                'comprehensive': '総合相談'
            }

            plan_name = plan_names.get(plan_type, plan_type)
            category_name = category_names.get(consultation_category, consultation_category)

            # Checkout セッションを作成（固定Price ID使用）
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': self.CONSULTATION_PRICE_ID,
                    'quantity': 1
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'user_id': user_info.get('user_id', ''),
                    'payment_type': 'consultation',
                    'plan_type': plan_type,
                    'consultation_category': consultation_category,
                    'user_email': user_info.get('email', ''),
                    'user_name': user_info.get('displayName', '')
                }
            )

            logger.info(f"Consultation payment session created: {session.id} for {plan_type} - {consultation_category}")
            return {
                'id': session.id,
                'url': session.url,
                'amount': amount,
                'plan_name': plan_name,
                'category_name': category_name
            }

        except stripe.error.StripeError as e:
            logger.error(f"Consultation payment creation error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Consultation payment error: {str(e)}")
            raise

    def create_expert_consultation_checkout(self, consultation_id, user_id, user_name, user_email, success_url, cancel_url, temp_reservation_id=None):
        """専門家相談用のStripe決済セッションを作成"""
        try:
            # 専門家相談の料金
            EXPERT_CONSULTATION_PRICE = 14300  # 30分 14,300円

            # Checkout セッションを作成
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': self.CURRENCY,
                        'product_data': {
                            'name': '専門家相談（30分）',
                            'description': '助成金専門家との1対1オンライン相談'
                        },
                        'unit_amount': EXPERT_CONSULTATION_PRICE
                    },
                    'quantity': 1
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'consultation_id': consultation_id,
                    'user_id': user_id,
                    'user_name': user_name,
                    'user_email': user_email,
                    'payment_type': 'expert_consultation',
                    'service_type': 'expert_consultation_30min',
                    'temp_reservation_id': temp_reservation_id or ''
                }
            )

            logger.info(f"Expert consultation payment session created: {session.id} for consultation {consultation_id}")
            return {
                'id': session.id,
                'url': session.url,
                'amount': EXPERT_CONSULTATION_PRICE
            }

        except stripe.error.StripeError as e:
            logger.error(f"Expert consultation payment creation error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Expert consultation payment error: {str(e)}")
            raise