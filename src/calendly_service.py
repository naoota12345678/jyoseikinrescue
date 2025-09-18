"""
Calendly統合サービス
専門家相談の予約管理
"""

import os
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class CalendlyService:
    def __init__(self):
        # Calendly API設定（環境変数から取得）
        self.api_token = os.environ.get('CALENDLY_API_TOKEN')
        self.base_url = 'https://api.calendly.com'
        self.headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json'
        }

        # 専門家相談用のCalendlyイベントタイプURL
        # 実際のCalendlyアカウント設定後に更新する
        self.expert_consultation_event_type = os.environ.get(
            'CALENDLY_EXPERT_CONSULTATION_EVENT_TYPE',
            'https://calendly.com/your-account/expert-consultation'
        )

    def generate_booking_url(self, consultation_id, user_email, user_name):
        """
        Calendly予約URLを生成
        決済完了後にユーザーに提供するURL
        """
        try:
            # Calendlyの予約URLにパラメータを追加
            params = {
                'name': user_name,
                'email': user_email,
                'a1': consultation_id,  # カスタムフィールドで相談IDを渡す
                'hide_gdpr_banner': '1'
            }

            # URLパラメータを構築
            param_string = '&'.join([f"{key}={value}" for key, value in params.items()])
            booking_url = f"{self.expert_consultation_event_type}?{param_string}"

            logger.info(f"Calendly予約URL生成: {consultation_id}")
            return booking_url

        except Exception as e:
            logger.error(f"Calendly予約URL生成エラー: {e}")
            return self.expert_consultation_event_type

    def create_scheduled_event(self, event_data):
        """
        Calendlyから予約イベント情報を受信
        WebHook経由で呼び出される
        """
        try:
            # Calendly WebHookからのイベントデータを処理
            event_type = event_data.get('event')
            payload = event_data.get('payload', {})

            if event_type == 'invitee.created':
                # 新しい予約が作成された場合
                event_uri = payload.get('uri')
                scheduled_event = payload.get('scheduled_event', {})
                invitee = payload.get('invitee', {})

                # 予約情報を抽出
                event_info = {
                    'event_uri': event_uri,
                    'scheduled_event_uri': scheduled_event.get('uri'),
                    'start_time': scheduled_event.get('start_time'),
                    'end_time': scheduled_event.get('end_time'),
                    'invitee_email': invitee.get('email'),
                    'invitee_name': invitee.get('name'),
                    'consultation_id': None  # カスタムフィールドから取得
                }

                # カスタムフィールドから相談IDを取得
                questions_and_answers = invitee.get('questions_and_answers', [])
                for qa in questions_and_answers:
                    if qa.get('question') == 'consultation_id':
                        event_info['consultation_id'] = qa.get('answer')
                        break

                logger.info(f"Calendly予約イベント受信: {event_info}")
                return event_info

        except Exception as e:
            logger.error(f"Calendlyイベント処理エラー: {e}")
            return None

    def get_user_info(self):
        """Calendlyユーザー情報を取得（設定確認用）"""
        try:
            if not self.api_token:
                return None

            response = requests.get(
                f"{self.base_url}/users/me",
                headers=self.headers
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Calendlyユーザー情報取得失敗: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Calendlyユーザー情報取得エラー: {e}")
            return None

    def get_event_types(self):
        """利用可能なイベントタイプを取得"""
        try:
            if not self.api_token:
                return []

            user_info = self.get_user_info()
            if not user_info:
                return []

            user_uri = user_info['resource']['uri']

            response = requests.get(
                f"{self.base_url}/event_types",
                headers=self.headers,
                params={'user': user_uri}
            )

            if response.status_code == 200:
                return response.json().get('collection', [])
            else:
                logger.error(f"Calendlyイベントタイプ取得失敗: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Calendlyイベントタイプ取得エラー: {e}")
            return []

    def is_configured(self):
        """Calendly統合が正しく設定されているかチェック"""
        return bool(self.api_token and self.expert_consultation_event_type)

    def get_embedded_widget_html(self, consultation_id, user_email, user_name):
        """
        Calendly埋め込みウィジェットのHTMLを生成
        決済完了ページで使用
        """
        booking_url = self.generate_booking_url(consultation_id, user_email, user_name)

        return f'''
        <div id="calendly-inline-widget" style="min-width:320px;height:700px;"></div>
        <script type="text/javascript" src="https://assets.calendly.com/assets/external/widget.js" async></script>
        <script>
        window.addEventListener('DOMContentLoaded', function() {{
            Calendly.initInlineWidget({{
                url: '{booking_url}',
                parentElement: document.getElementById('calendly-inline-widget'),
                prefill: {{
                    name: '{user_name}',
                    email: '{user_email}',
                    customAnswers: {{
                        a1: '{consultation_id}'
                    }}
                }},
                utm: {{
                    utmCampaign: 'Expert Consultation',
                    utmSource: 'jyoseikinrescue',
                    utmMedium: 'website'
                }}
            }});
        }});
        </script>
        '''

# グローバルインスタンス
calendly_service = CalendlyService()