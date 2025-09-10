from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from google.cloud.firestore import DocumentReference, SERVER_TIMESTAMP
import logging

logger = logging.getLogger(__name__)

class User:
    def __init__(self, firebase_service):
        self.db = firebase_service.get_db()
    
    def create_user(self, user_data: Dict[str, Any]) -> str:
        """新規ユーザーを作成"""
        try:
            user_ref = self.db.collection('users').document()
            
            user_record = {
                'user_id': user_data.get('uid'),
                'email': user_data.get('email'),
                'display_name': user_data.get('display_name', ''),
                'stripe_customer_id': None,
                'subscription_status': 'trial',  # trial, active, cancelled, expired
                'created_at': SERVER_TIMESTAMP,
                'updated_at': SERVER_TIMESTAMP
            }
            
            user_ref.set(user_record)
            
            # 初回サブスクリプションも作成（Firebase UIDを使用）
            self.create_initial_subscription(user_data.get('uid'))
            
            logger.info(f"User created successfully: {user_ref.id}")
            return user_ref.id
            
        except Exception as e:
            logger.error(f"User creation error: {str(e)}")
            raise
    
    def get_user_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        """UIDでユーザーを取得"""
        try:
            users = self.db.collection('users').where('user_id', '==', uid).limit(1).get()
            
            if users:
                user_doc = users[0]
                return {
                    'id': user_doc.id,
                    **user_doc.to_dict()
                }
            return None
            
        except Exception as e:
            logger.error(f"User fetch error: {str(e)}")
            return None
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """ドキュメントIDでユーザーを取得"""
        try:
            user_doc = self.db.collection('users').document(user_id).get()
            
            if user_doc.exists:
                return {
                    'id': user_doc.id,
                    **user_doc.to_dict()
                }
            return None
            
        except Exception as e:
            logger.error(f"User fetch error: {str(e)}")
            return None
    
    def update_user(self, user_id: str, update_data: Dict[str, Any]) -> bool:
        """ユーザー情報を更新"""
        try:
            update_data['updated_at'] = SERVER_TIMESTAMP
            
            self.db.collection('users').document(user_id).update(update_data)
            
            logger.info(f"User updated successfully: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"User update error: {str(e)}")
            return False
    
    def update_stripe_customer_id(self, user_id: str, stripe_customer_id: str) -> bool:
        """Stripe顧客IDを更新"""
        return self.update_user(user_id, {
            'stripe_customer_id': stripe_customer_id
        })
    
    def is_admin_user(self, user_id: str) -> bool:
        """管理者ユーザーかどうかを判定"""
        # 管理者のUIDまたはメールアドレスのリスト
        admin_uids = [
            # あなたのFirebase UIDをここに追加
        ]
        admin_emails = [
            'naoota12345678@gmail.com',  # あなたの管理者メールアドレス
        ]
        
        try:
            user = self.get_user_by_uid(user_id)
            if user and user.get('email') in admin_emails:
                return True
            if user_id in admin_uids:
                return True
            return False
        except:
            return False
    
    def create_initial_subscription(self, user_id: str):
        """初回サブスクリプションを作成"""
        try:
            # 既存のアクティブなサブスクリプションがあるかチェック
            existing_subs = self.db.collection('subscriptions')\
                .where('user_id', '==', user_id)\
                .where('status', '==', 'active')\
                .limit(1).get()
            
            if existing_subs:
                logger.info(f"Active subscription already exists for user {user_id}, skipping creation")
                return
            
            # 管理者の場合は無制限プランを作成
            if self.is_admin_user(user_id):
                subscription_data = {
                    'user_id': user_id,
                    'plan_type': 'admin',         # 管理者専用プラン
                    'questions_limit': 999999,    # 実質無制限
                    'questions_used': 0,
                    'reset_date': None,
                    'stripe_subscription_id': None,
                    'status': 'active',
                    'created_at': SERVER_TIMESTAMP,
                    'updated_at': SERVER_TIMESTAMP
                }
                logger.info(f"Admin subscription created for user {user_id}")
            else:
                # 通常のトライアルプラン
                subscription_data = {
                    'user_id': user_id,
                    'plan_type': 'trial',         # trial, basic, additional_pack
                    'questions_limit': 5,         # トライアル：生涯5質問
                    'questions_used': 0,
                    'reset_date': None,           # トライアルはリセットなし
                    'stripe_subscription_id': None,
                    'status': 'active',
                    'created_at': SERVER_TIMESTAMP,
                    'updated_at': SERVER_TIMESTAMP
                }
            
            self.db.collection('subscriptions').add(subscription_data)
            logger.info(f"Initial subscription created for user {user_id}")
            
        except Exception as e:
            logger.error(f"Initial subscription creation error: {str(e)}")
            raise