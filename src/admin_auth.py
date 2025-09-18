"""
管理者専用認証システム
既存のFirebase認証とは独立した管理者認証
"""

import hashlib
import secrets
import time
from functools import wraps
from flask import request, jsonify, session
from firebase_config import firebase_service
import logging

logger = logging.getLogger(__name__)

class AdminAuth:
    def __init__(self):
        self.admin_email = "rescue@jyoseikin.jp"
        self.initial_password = "rescue3737"
        self.session_timeout = 24 * 60 * 60  # 24時間

    def _hash_password(self, password):
        """パスワードをハッシュ化"""
        salt = secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac('sha256',
                                           password.encode('utf-8'),
                                           salt.encode('utf-8'),
                                           100000)
        return f"{salt}:{password_hash.hex()}"

    def _verify_password(self, password, stored_hash):
        """パスワード検証"""
        try:
            salt, hash_hex = stored_hash.split(':')
            password_hash = hashlib.pbkdf2_hmac('sha256',
                                               password.encode('utf-8'),
                                               salt.encode('utf-8'),
                                               100000)
            return secrets.compare_digest(password_hash.hex(), hash_hex)
        except Exception as e:
            logger.error(f"パスワード検証エラー: {e}")
            return False

    def initialize_admin(self):
        """管理者アカウントの初期化"""
        try:
            db = firebase_service.get_firestore_client()
            admin_ref = db.collection('admin_auth').document('admin')

            # 既存の管理者データ確認
            admin_doc = admin_ref.get()

            if not admin_doc.exists:
                # 初期管理者アカウント作成
                password_hash = self._hash_password(self.initial_password)

                admin_data = {
                    'email': self.admin_email,
                    'password_hash': password_hash,
                    'created_at': time.time(),
                    'last_login': None,
                    'password_changed_at': None,
                    'login_attempts': 0,
                    'locked_until': None
                }

                admin_ref.set(admin_data)
                logger.info(f"管理者アカウント初期化完了: {self.admin_email}")
                return True
            else:
                logger.info("管理者アカウントは既に存在します")
                return True

        except Exception as e:
            logger.error(f"管理者アカウント初期化エラー: {e}")
            return False

    def authenticate_admin(self, email, password):
        """管理者認証"""
        try:
            if email != self.admin_email:
                logger.warning(f"無効な管理者メールアドレス: {email}")
                return False

            db = firebase_service.get_firestore_client()
            admin_ref = db.collection('admin_auth').document('admin')
            admin_doc = admin_ref.get()

            if not admin_doc.exists:
                logger.error("管理者アカウントが存在しません")
                return False

            admin_data = admin_doc.to_dict()

            # アカウントロック確認
            if admin_data.get('locked_until') and admin_data['locked_until'] > time.time():
                logger.warning("管理者アカウントがロックされています")
                return False

            # パスワード検証
            if self._verify_password(password, admin_data['password_hash']):
                # ログイン成功
                admin_ref.update({
                    'last_login': time.time(),
                    'login_attempts': 0,
                    'locked_until': None
                })
                logger.info(f"管理者ログイン成功: {email}")
                return True
            else:
                # ログイン失敗
                login_attempts = admin_data.get('login_attempts', 0) + 1
                update_data = {'login_attempts': login_attempts}

                # 5回失敗でアカウントロック（1時間）
                if login_attempts >= 5:
                    update_data['locked_until'] = time.time() + 3600  # 1時間
                    logger.warning(f"管理者アカウントをロック: {login_attempts}回失敗")

                admin_ref.update(update_data)
                logger.warning(f"管理者ログイン失敗: {email} (試行回数: {login_attempts})")
                return False

        except Exception as e:
            logger.error(f"管理者認証エラー: {e}")
            return False

    def change_admin_password(self, current_password, new_password):
        """管理者パスワード変更"""
        try:
            db = firebase_service.get_firestore_client()
            admin_ref = db.collection('admin_auth').document('admin')
            admin_doc = admin_ref.get()

            if not admin_doc.exists:
                return False, "管理者アカウントが存在しません"

            admin_data = admin_doc.to_dict()

            # 現在のパスワード確認
            if not self._verify_password(current_password, admin_data['password_hash']):
                return False, "現在のパスワードが正しくありません"

            # 新しいパスワードの検証
            if len(new_password) < 8:
                return False, "新しいパスワードは8文字以上である必要があります"

            # パスワード更新
            new_password_hash = self._hash_password(new_password)
            admin_ref.update({
                'password_hash': new_password_hash,
                'password_changed_at': time.time()
            })

            logger.info("管理者パスワード変更完了")
            return True, "パスワードが正常に変更されました"

        except Exception as e:
            logger.error(f"パスワード変更エラー: {e}")
            return False, f"システムエラー: {str(e)}"

    def is_admin_logged_in(self):
        """管理者ログイン状態確認"""
        try:
            admin_session = session.get('admin_auth')
            if not admin_session:
                return False

            # セッション期限確認
            if admin_session.get('expires_at', 0) < time.time():
                session.pop('admin_auth', None)
                return False

            return admin_session.get('email') == self.admin_email

        except Exception as e:
            logger.error(f"管理者セッション確認エラー: {e}")
            return False

    def create_admin_session(self):
        """管理者セッション作成"""
        session['admin_auth'] = {
            'email': self.admin_email,
            'logged_in_at': time.time(),
            'expires_at': time.time() + self.session_timeout
        }
        logger.info("管理者セッション作成完了")

    def destroy_admin_session(self):
        """管理者セッション破棄"""
        session.pop('admin_auth', None)
        logger.info("管理者セッション破棄完了")

# グローバルインスタンス
admin_auth = AdminAuth()

def require_admin(f):
    """管理者権限が必要なエンドポイント用のデコレータ"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            if not admin_auth.is_admin_logged_in():
                return jsonify({
                    'error': '管理者権限が必要です',
                    'code': 'ADMIN_AUTH_REQUIRED',
                    'redirect': '/admin/login'
                }), 403

            return f(*args, **kwargs)

        except Exception as e:
            logger.error(f"管理者権限チェックエラー: {e}")
            return jsonify({
                'error': 'システムエラーが発生しました',
                'code': 'SYSTEM_ERROR'
            }), 500

    return decorated_function

def is_admin_user():
    """現在のユーザーが管理者かどうか確認（ダッシュボード表示用）"""
    return admin_auth.is_admin_logged_in()