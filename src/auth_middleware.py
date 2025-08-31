from functools import wraps
from flask import request, jsonify, g
from firebase_config import firebase_service
from models.user import User
from models.subscription import SubscriptionService
import logging

logger = logging.getLogger(__name__)

def require_auth(f):
    """認証が必要なエンドポイント用のデコレータ"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Authorization ヘッダーから Firebase ID token を取得
            auth_header = request.headers.get('Authorization')
            logger.info(f"Auth header: {auth_header[:50] if auth_header else 'None'}...")
            
            if not auth_header or not auth_header.startswith('Bearer '):
                logger.warning("Missing or invalid Authorization header")
                return jsonify({
                    'error': '認証が必要です',
                    'code': 'AUTH_REQUIRED'
                }), 401
            
            id_token = auth_header.split(' ')[1]
            logger.info(f"Extracted token length: {len(id_token)}")
            
            # Firebase ID token を検証
            logger.info("Attempting to verify Firebase token...")
            decoded_token = firebase_service.verify_token(id_token)
            logger.info(f"Token verification result: {decoded_token is not None}")
            
            if not decoded_token:
                return jsonify({
                    'error': '無効な認証トークン',
                    'code': 'INVALID_TOKEN'
                }), 401
            
            # ユーザー情報を取得
            logger.info(f"Decoded token: {decoded_token}")
            uid = decoded_token.get('uid') or decoded_token.get('user_id') or decoded_token.get('sub')
            logger.info(f"Extracted UID: {uid}")
            user_service = User(firebase_service)
            user = user_service.get_user_by_uid(uid)
            
            if not user:
                # 新規ユーザーの場合は自動作成
                logger.info(f"Creating new user for uid: {uid}")
                user_id = user_service.create_user({
                    'uid': uid,
                    'email': decoded_token.get('email'),
                    'display_name': decoded_token.get('name', '')
                })
                user = user_service.get_user_by_id(user_id)
                logger.info(f"New user created with id: {user_id}")
            
            # グローバル変数に設定
            # user_idフィールドを確実に設定
            if user and 'user_id' not in user:
                user['user_id'] = uid
            g.current_user = user
            g.uid = uid
            
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return jsonify({
                'error': 'サーバーエラー',
                'code': 'SERVER_ERROR'
            }), 500
    
    return decorated_function

def check_usage_limit(f):
    """使用制限をチェックするデコレータ"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            if not hasattr(g, 'current_user') or not g.current_user:
                return jsonify({
                    'error': '認証が必要です',
                    'code': 'AUTH_REQUIRED'
                }), 401
            
            # user_idフィールドを使用（ドキュメントIDではなく）
            user_id = g.current_user.get('user_id') or g.current_user.get('uid') or g.current_user['id']
            subscription_service = SubscriptionService(firebase_service)
            
            # 使用状況を確認
            usage_stats = subscription_service.get_usage_stats(user_id)
            logger.info(f"User {user_id} usage stats: {usage_stats}")
            
            if usage_stats.get('error'):
                logger.error(f"Subscription error for user {user_id}: {usage_stats.get('error')}")
                return jsonify({
                    'error': 'サブスクリプション情報の取得に失敗しました',
                    'code': 'SUBSCRIPTION_ERROR'
                }), 500
            
            # 質問回数の制限チェック
            remaining = usage_stats.get('remaining', 0)
            logger.info(f"User {user_id} has {remaining} questions remaining")
            
            if remaining <= 0:
                return jsonify({
                    'error': '質問回数の上限に達しています',
                    'code': 'LIMIT_EXCEEDED',
                    'usage_stats': usage_stats,
                    'upgrade_required': True
                }), 403
            
            # 使用状況をグローバル変数に設定
            g.usage_stats = usage_stats
            
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Usage limit check error: {str(e)}")
            return jsonify({
                'error': 'サーバーエラー',
                'code': 'SERVER_ERROR'
            }), 500
    
    return decorated_function

def get_current_user():
    """現在認証されているユーザーを取得"""
    return getattr(g, 'current_user', None)

def get_usage_stats():
    """現在のユーザーの使用状況を取得"""
    return getattr(g, 'usage_stats', None)

class AuthService:
    """認証関連のサービス"""
    
    def __init__(self):
        self.firebase_service = firebase_service
        self.user_service = User(firebase_service)
        self.subscription_service = SubscriptionService(firebase_service)
    
    def create_user_with_stripe(self, user_data: dict, stripe_customer_id: str) -> dict:
        """ユーザー作成とStripe連携"""
        try:
            # ユーザー作成
            user_id = self.user_service.create_user(user_data)
            
            # Stripe 顧客IDを更新
            self.user_service.update_stripe_customer_id(user_id, stripe_customer_id)
            
            # 最新のユーザー情報を取得
            user = self.user_service.get_user_by_id(user_id)
            
            return {
                'success': True,
                'user': user
            }
            
        except Exception as e:
            logger.error(f"User creation with Stripe error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def update_stripe_customer_id(self, user_id: str, stripe_customer_id: str) -> bool:
        """ユーザーのStripe顧客IDを更新"""
        try:
            self.user_service.update_stripe_customer_id(user_id, stripe_customer_id)
            return True
        except Exception as e:
            logger.error(f"Update stripe customer ID error: {str(e)}")
            return False
    
    def get_user_with_usage(self, uid: str) -> dict:
        """ユーザー情報と使用状況を取得"""
        try:
            user = self.user_service.get_user_by_uid(uid)
            
            if not user:
                return {'success': False, 'error': 'ユーザーが見つかりません'}
            
            usage_stats = self.subscription_service.get_usage_stats(user['id'])
            
            return {
                'success': True,
                'user': user,
                'usage_stats': usage_stats
            }
            
        except Exception as e:
            logger.error(f"Get user with usage error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }