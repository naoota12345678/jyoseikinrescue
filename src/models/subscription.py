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
                return {
                    'id': sub_doc.id,
                    **sub_doc.to_dict()
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
    
    def upgrade_to_basic_plan(self, user_id: str, stripe_subscription_id: str) -> bool:
        """基本プランにアップグレード"""
        try:
            # 既存のサブスクリプションを無効化
            self.cancel_user_subscriptions(user_id)
            
            # 新しい基本プランを作成
            reset_date = datetime.now() + timedelta(days=30)
            
            subscription_data = {
                'user_id': user_id,
                'plan_type': 'basic',
                'questions_limit': 50,
                'questions_used': 0,
                'reset_date': reset_date,
                'stripe_subscription_id': stripe_subscription_id,
                'status': 'active'
            }
            
            self.create_subscription(subscription_data)
            return True
            
        except Exception as e:
            logger.error(f"Upgrade to basic plan error: {str(e)}")
            return False
    
    def add_additional_pack(self, user_id: str, stripe_payment_id: str) -> bool:
        """追加パック（50質問）を追加"""
        try:
            # 現在のサブスクリプションを取得
            current_sub = self.get_user_subscription(user_id)
            
            if not current_sub:
                logger.error(f"No active subscription found for user: {user_id}")
                return False
            
            # 質問数を50問追加
            new_limit = current_sub['questions_limit'] + 50
            
            self.db.collection('subscriptions').document(current_sub['id']).update({
                'questions_limit': new_limit,
                'updated_at': SERVER_TIMESTAMP
            })
            
            # 追加パックの記録を保存
            self.record_additional_pack_purchase(user_id, stripe_payment_id, 50)
            
            logger.info(f"Additional pack added for user: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Add additional pack error: {str(e)}")
            return False
    
    def use_question(self, user_id: str) -> Dict[str, Any]:
        """質問を1つ消費"""
        try:
            subscription = self.get_user_subscription(user_id)
            
            if not subscription:
                return {
                    'success': False,
                    'error': 'アクティブなサブスクリプションが見つかりません'
                }
            
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