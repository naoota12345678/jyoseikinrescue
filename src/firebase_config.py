import firebase_admin
from firebase_admin import credentials, firestore, auth
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class FirebaseService:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.initialize_firebase()
            self._initialized = True
    
    def initialize_firebase(self):
        """Firebase Admin SDKを初期化"""
        try:
            # Firebase Admin SDK の初期化
            if not firebase_admin._apps:
                # サービスアカウントキーのパス
                cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
                
                if cred_path and os.path.exists(cred_path):
                    # サービスアカウントキーファイルを使用
                    cred = credentials.Certificate(cred_path)
                else:
                    # 環境変数からサービスアカウント情報を取得
                    service_account_info = {
                        "type": "service_account",
                        "project_id": os.getenv('FIREBASE_PROJECT_ID'),
                        "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
                        "private_key": os.getenv('FIREBASE_PRIVATE_KEY', '').replace('\\n', '\n'),
                        "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
                        "client_id": os.getenv('FIREBASE_CLIENT_ID'),
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{os.getenv('FIREBASE_CLIENT_EMAIL')}"
                    }
                    cred = credentials.Certificate(service_account_info)
                
                firebase_admin.initialize_app(cred)
                logger.info("Firebase Admin SDK initialized successfully")
            
            # Firestore クライアントを取得
            self.db = firestore.client()
            
        except Exception as e:
            logger.error(f"Firebase initialization error: {str(e)}")
            raise
    
    def get_db(self):
        """Firestoreデータベースのインスタンスを取得"""
        return self.db
    
    def verify_token(self, id_token: str) -> Optional[dict]:
        """Firebase ID tokenを検証"""
        try:
            decoded_token = auth.verify_id_token(id_token)
            return decoded_token
        except Exception as e:
            logger.error(f"Token verification error: {str(e)}")
            return None
    
    def create_custom_token(self, uid: str) -> str:
        """カスタムトークンを作成"""
        try:
            custom_token = auth.create_custom_token(uid)
            return custom_token.decode('utf-8')
        except Exception as e:
            logger.error(f"Custom token creation error: {str(e)}")
            raise

# シングルトンインスタンス
firebase_service = FirebaseService()