from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from google.cloud.firestore import SERVER_TIMESTAMP
import logging

logger = logging.getLogger(__name__)

class SubscriptionService:
    def __init__(self, firebase_service):
        self.db = firebase_service.get_db()
    
    def get_user_subscription(self, user_id: str) -> Optional[Dict[str, Any]]:
        """ユーザーのアクティブなサブスクリプションを取得"""
        try:
            subscriptions = self.db.collection('subscriptions')\
                .where('user_id', '==', user_id)\
                .where('status', '==', 'active')\
                .order_by('created_at', direction='DESCENDING')\
                .limit(1).get()
            
            if subscriptions:
                sub_doc = subscriptions[0]
                sub_data = sub_doc.to_dict()
                
                # 無効なstripe_subscription_idをクリーンアップ（一時的に無効化）
                # stripe_id = sub_data.get('stripe_subscription_id', '')
                # if stripe_id in ['manual_update', 'pack_purchase', '']:
                #     logger.warning(f"Invalid stripe_subscription_id '{stripe_id}' found for subscription: {sub_doc.id}")
                #     # 有効なIDに修正（一時的に subscription_id を使用）
                #     valid_id = f"sub_{sub_doc.id[:8]}"
                #     self.db.collection('subscriptions').document(sub_doc.id).update({
                #         'stripe_subscription_id': valid_id,
                #         'updated_at': SERVER_TIMESTAMP
                #     })
                #     sub_data['stripe_subscription_id'] = valid_id
                #     logger.info(f"Updated invalid stripe_subscription_id to: {valid_id}")
                
                return {
                    'id': sub_doc.id,
                    **sub_data
                }
            return None
            
        except Exception as e:
            logger.error(f"Subscription fetch error: {str(e)}")
            return None
    
    def create_subscription(self, subscription_data: Dict[str, Any]) -> str:
        """新しいサブスクリプションを作成"""
        try:
            subscription_ref = self.db.collection('subscriptions').document()
            
            # デフォルト値を設定
            default_data = {
                'questions_used': 0,
                'status': 'active',
                'created_at': SERVER_TIMESTAMP,
                'updated_at': SERVER_TIMESTAMP
            }
            
            final_data = {**default_data, **subscription_data}
            subscription_ref.set(final_data)
            
            logger.info(f"Subscription created: {subscription_ref.id}")
            return subscription_ref.id
            
        except Exception as e:
            logger.error(f"Subscription creation error: {str(e)}")
            raise
    
    # ===== サブスクリプションプランアップグレード =====
    
    def upgrade_to_subscription_plan(self, user_id: str, plan_type: str, stripe_subscription_id: str) -> bool:
        """サブスクリプションプランにアップグレード"""
        try:
            # 既存のサブスクリプションを無効化
            self.cancel_user_subscriptions(user_id)
            
            # プラン設定を取得
            plan_config = self._get_plan_config(plan_type)
            if not plan_config:
                logger.error(f"Invalid plan type: {plan_type}")
                return False
            
            # 新しいサブスクリプションを作成
            reset_date = datetime.now() + timedelta(days=30)
            
            subscription_data = {
                'user_id': user_id,
                'plan_type': plan_type,
                'questions_limit': plan_config['questions_limit'],
                'questions_used': 0,
                'reset_date': reset_date,
                'stripe_subscription_id': stripe_subscription_id,
                'status': 'active'
            }
            
            self.create_subscription(subscription_data)
            logger.info(f"Upgraded user {user_id} to {plan_type} plan")
            return True
            
        except Exception as e:
            logger.error(f"Upgrade to {plan_type} plan error: {str(e)}")
            return False
    
    def _get_plan_config(self, plan_type: str) -> Dict[str, Any]:
        """プラン設定を取得"""
        plan_configs = {
            'light': {
                'questions_limit': 20,
                'price': 1480,
                'name': 'ライト'
            },
            'regular': {
                'questions_limit': 50,
                'price': 3300,
                'name': 'レギュラー'
            },
            'heavy': {
                'questions_limit': 90,
                'price': 5500,
                'name': 'ヘビー'
            },
            # 後方互換性
            'basic': {
                'questions_limit': 50,
                'price': 3300,
                'name': 'ベーシック'
            }
        }
        return plan_configs.get(plan_type)
    
    # 後方互換性のためのメソッド
    def upgrade_to_basic_plan(self, user_id: str, stripe_subscription_id: str) -> bool:
        """既存コードとの互換性のため - レギュラープランにリダイレクト"""
        return self.upgrade_to_subscription_plan(user_id, 'regular', stripe_subscription_id)
    
    # ===== 追加パック機能 =====
    
    def add_additional_pack(self, user_id: str, stripe_payment_id: str, questions_count: int = 50) -> bool:
        """追加パック（既存コードとの互換性のため50回デフォルト）"""
        return self.add_pack(user_id, stripe_payment_id, questions_count)
    
    def add_pack(self, user_id: str, stripe_payment_id: str, questions_count: int) -> bool:
        """指定した回数の追加パックを追加"""
        try:
            # 現在のサブスクリプションを取得
            current_sub = self.get_user_subscription(user_id)
            
            if not current_sub:
                logger.error(f"No active subscription found for user: {user_id}")
                return False
            
            # 質問数を指定回数分追加
            new_limit = current_sub['questions_limit'] + questions_count
            
            self.db.collection('subscriptions').document(current_sub['id']).update({
                'questions_limit': new_limit,
                'updated_at': SERVER_TIMESTAMP
            })
            
            # 追加パックの記録を保存
            self.record_additional_pack_purchase(user_id, stripe_payment_id, questions_count)
            
            logger.info(f"Added {questions_count} questions pack for user: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Add pack error: {str(e)}")
            return False
    
    def add_pack_20(self, user_id: str, stripe_payment_id: str) -> bool:
        """２０回追加パックを追加"""
        return self.add_pack(user_id, stripe_payment_id, 20)
    
    def add_pack_40(self, user_id: str, stripe_payment_id: str) -> bool:
        """４０回追加パックを追加"""
        return self.add_pack(user_id, stripe_payment_id, 40)
    
    def add_pack_90(self, user_id: str, stripe_payment_id: str) -> bool:
        """９０回追加パックを追加"""
        return self.add_pack(user_id, stripe_payment_id, 90)
    
    def use_question(self, user_id: str) -> Dict[str, Any]:
        """質問を1つ消費"""
        try:
            subscription = self.get_user_subscription(user_id)
            
            if not subscription:
                return {
                    'success': False,
                    'error': 'アクティブなサブスクリプションが見つかりません'
                }
            
            # 月次リセットチェック（サブスクリプションプランのみ）
            subscription = self._check_and_reset_if_needed(subscription)
            
            current_used = subscription.get('questions_used', 0)
            limit = subscription.get('questions_limit', 0)
            
            if current_used >= limit:
                return {
                    'success': False,
                    'error': '質問回数の上限に達しています',
                    'remaining': 0,
                    'limit': limit
                }
            
            # 使用回数を増加
            new_used = current_used + 1
            
            self.db.collection('subscriptions').document(subscription['id']).update({
                'questions_used': new_used,
                'updated_at': SERVER_TIMESTAMP
            })
            
            remaining = limit - new_used
            
            return {
                'success': True,
                'remaining': remaining,
                'limit': limit,
                'used': new_used
            }
            
        except Exception as e:
            logger.error(f"Use question error: {str(e)}")
            return {
                'success': False,
                'error': 'システムエラーが発生しました'
            }
    
    def get_usage_stats(self, user_id: str) -> Dict[str, Any]:
        """使用状況統計を取得"""
        try:
            subscription = self.get_user_subscription(user_id)
            
            if not subscription:
                return {
                    'questions_used': 0,
                    'questions_limit': 0,
                    'remaining': 0,
                    'plan_type': 'none',
                    'status': 'inactive'
                }
            
            used = subscription.get('questions_used', 0)
            limit = subscription.get('questions_limit', 0)
            
            return {
                'questions_used': used,
                'questions_limit': limit,
                'remaining': max(0, limit - used),
                'plan_type': subscription.get('plan_type', 'none'),
                'status': subscription.get('status', 'inactive'),
                'reset_date': subscription.get('reset_date')
            }
            
        except Exception as e:
            logger.error(f"Usage stats error: {str(e)}")
            return {'error': str(e)}
    
    def cancel_user_subscriptions(self, user_id: str) -> bool:
        """ユーザーのすべてのサブスクリプションをキャンセル"""
        try:
            subscriptions = self.db.collection('subscriptions')\
                .where('user_id', '==', user_id)\
                .where('status', '==', 'active').get()
            
            batch = self.db.batch()
            
            for sub_doc in subscriptions:
                batch.update(sub_doc.reference, {
                    'status': 'cancelled',
                    'updated_at': SERVER_TIMESTAMP
                })
            
            batch.commit()
            return True
            
        except Exception as e:
            logger.error(f"Cancel subscriptions error: {str(e)}")
            return False
    
    def record_additional_pack_purchase(self, user_id: str, stripe_payment_id: str, questions_added: int):
        """追加パック購入記録を保存"""
        try:
            purchase_data = {
                'user_id': user_id,
                'stripe_payment_id': stripe_payment_id,
                'questions_added': questions_added,
                'amount': 2000,  # 追加パック料金
                'created_at': SERVER_TIMESTAMP
            }
            
            self.db.collection('additional_pack_purchases').add(purchase_data)
            
        except Exception as e:
            logger.error(f"Record additional pack purchase error: {str(e)}")
    
    # ===== 月次リセット機能 =====
    
    def _check_and_reset_if_needed(self, subscription: Dict[str, Any]) -> Dict[str, Any]:
        """月次リセットが必要かチェックし、必要であればリセット実行"""
        try:
            reset_date = subscription.get('reset_date')
            plan_type = subscription.get('plan_type', '')
            
            # リセット日が設定されていない場合はリセット不要
            if not reset_date:
                return subscription
            
            # サブスクリプションプラン以外はリセット不要
            if not self._is_subscription_plan(plan_type):
                return subscription
            
            # リセット日が来ているかチェック
            if isinstance(reset_date, str):
                from datetime import datetime
                reset_date = datetime.fromisoformat(reset_date.replace('Z', '+00:00'))
            
            if datetime.now() >= reset_date:
                # リセット実行
                self._reset_monthly_usage(subscription['id'])
                
                # ローカルのサブスクリプション情報も更新
                subscription['questions_used'] = 0
                subscription['reset_date'] = datetime.now() + timedelta(days=30)
                
                logger.info(f"Monthly reset performed for subscription: {subscription['id']}")
            
            return subscription
            
        except Exception as e:
            logger.error(f"Monthly reset check error: {str(e)}")
            return subscription
    
    def _is_subscription_plan(self, plan_type: str) -> bool:
        """サブスクリプションプラン（月次リセット対象）かどうか判定"""
        subscription_plans = ['light', 'regular', 'heavy', 'basic']
        return plan_type in subscription_plans
    
    def _reset_monthly_usage(self, subscription_id: str) -> bool:
        """月次使用量をリセット"""
        try:
            next_reset_date = datetime.now() + timedelta(days=30)
            
            self.db.collection('subscriptions').document(subscription_id).update({
                'questions_used': 0,
                'reset_date': next_reset_date,
                'updated_at': SERVER_TIMESTAMP
            })
            
            logger.info(f"Monthly usage reset for subscription: {subscription_id}")
            return True
            
        except Exception as e:
            logger.error(f"Monthly usage reset error: {str(e)}")
            return False
    
    # ===== サブスクリプション解約機能 =====
    
    def get_subscription_info(self, user_id: str) -> Dict[str, Any]:
        """サブスクリプション情報を取得（Stripe情報含む）"""
        try:
            subscription = self.get_user_subscription(user_id)
            
            if not subscription:
                return None
            
            return {
                'subscription_id': subscription.get('stripe_subscription_id'),
                'plan_type': subscription.get('plan_type'),
                'status': subscription.get('status'),
                'user_id': user_id
            }
            
        except Exception as e:
            logger.error(f"Get subscription info error: {str(e)}")
            return None
    
    def mark_subscription_cancelled(self, user_id: str) -> bool:
        """サブスクリプションを解約済みとしてマーク"""
        try:
            subscription = self.get_user_subscription(user_id)
            
            if not subscription:
                logger.warning(f"No subscription found for user: {user_id}")
                return False
            
            # サブスクリプションを解約状態に更新
            self.db.collection('subscriptions').document(subscription['id']).update({
                'status': 'cancelled',
                'cancelled_at': SERVER_TIMESTAMP,
                'updated_at': SERVER_TIMESTAMP
            })
            
            logger.info(f"Subscription marked as cancelled for user: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Mark subscription cancelled error: {str(e)}")
            return False