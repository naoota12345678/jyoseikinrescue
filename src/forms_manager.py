"""
助成金様式URL管理システム
エージェントごとのURL管理と動的な追加・削除に対応
"""
import json
import os
from typing import Dict, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class FormsManager:
    def __init__(self, json_path: str = None):
        """
        初期化
        Args:
            json_path: subsidy_forms.jsonのパス（デフォルトはプロジェクトルート）
        """
        if json_path is None:
            # プロジェクトルートのsubsidy_forms.jsonを参照
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            json_path = os.path.join(base_dir, 'subsidy_forms.json')
        
        self.json_path = json_path
        self.data = self._load_json()
    
    def _load_json(self) -> Dict:
        """JSONファイルを読み込む"""
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Forms JSON file not found: {self.json_path}")
            return {"agents": {}}
        except Exception as e:
            logger.error(f"Error loading forms JSON: {str(e)}")
            return {"agents": {}}
    
    def reload(self):
        """JSONファイルを再読み込み（ホットリロード用）"""
        self.data = self._load_json()
        logger.info("Forms data reloaded")
    
    def get_active_agents(self) -> List[str]:
        """アクティブなエージェントのIDリストを取得"""
        return [
            agent_id 
            for agent_id, agent_data in self.data.get("agents", {}).items()
            if agent_data.get("active", False)
        ]
    
    def get_agent_info(self, agent_id: str) -> Optional[Dict]:
        """
        特定エージェントの情報を取得
        Args:
            agent_id: エージェントID（例: 'gyoumukaizen'）
        Returns:
            エージェント情報のdict、存在しない場合はNone
        """
        return self.data.get("agents", {}).get(agent_id)
    
    def get_form_url(self, agent_id: str, form_key: str) -> Optional[Dict]:
        """
        様式のURL情報を取得
        Args:
            agent_id: エージェントID
            form_key: 様式キー（例: '様式第1号'）
        Returns:
            URL情報のdict、存在しない場合はNone
        """
        agent = self.get_agent_info(agent_id)
        if not agent:
            return None
        
        forms = agent.get("urls", {}).get("forms", {})
        return forms.get(form_key)
    
    def get_all_forms(self, agent_id: str) -> Dict:
        """
        エージェントの全様式を取得
        Args:
            agent_id: エージェントID
        Returns:
            様式一覧のdict
        """
        agent = self.get_agent_info(agent_id)
        if not agent:
            return {}
        
        return agent.get("urls", {}).get("forms", {})
    
    def get_guide_url(self, agent_id: str, guide_name: str) -> Optional[Dict]:
        """
        ガイド・マニュアルのURL情報を取得
        Args:
            agent_id: エージェントID
            guide_name: ガイド名（例: '申請マニュアル'）
        Returns:
            URL情報のdict
        """
        agent = self.get_agent_info(agent_id)
        if not agent:
            return None
        
        guides = agent.get("urls", {}).get("guides", {})
        return guides.get(guide_name)
    
    def get_main_page(self, agent_id: str) -> Optional[Dict]:
        """
        エージェントのメインページURL情報を取得
        Args:
            agent_id: エージェントID
        Returns:
            メインページ情報のdict
        """
        agent = self.get_agent_info(agent_id)
        if not agent:
            return None
        
        return agent.get("urls", {}).get("main_page")
    
    def format_url_message(self, agent_id: str, phase: str = None) -> str:
        """
        ユーザー向けのURL案内メッセージを生成
        Args:
            agent_id: エージェントID
            phase: 申請フェーズ（例: '交付申請', '実績報告'）
        Returns:
            フォーマット済みメッセージ
        """
        agent = self.get_agent_info(agent_id)
        if not agent:
            return "該当する助成金の情報が見つかりません。"
        
        message = f"【{agent['name']}の様式・資料】\\n\\n"
        
        # メインページ
        main_page = self.get_main_page(agent_id)
        if main_page:
            message += f"📌 **公式ページ**\\n"
            message += f"・{main_page['name']}: {main_page['url']}\\n\\n"
        
        # 特定フェーズの様式を表示
        if phase:
            message += f"📝 **{phase}に必要な様式**\\n"
            forms = self.get_all_forms(agent_id)
            phase_forms = {k: v for k, v in forms.items() if v.get('phase') == phase}
            
            if phase_forms:
                for form_key, form_info in phase_forms.items():
                    message += f"・{form_key} {form_info['name']}: {form_info['url']}\\n"
                    message += f"  ({form_info['description']})\\n"
            else:
                message += f"・該当する様式が登録されていません\\n"
        else:
            # 全様式を表示
            forms = self.get_all_forms(agent_id)
            if forms:
                message += "📝 **申請様式一覧**\\n"
                for form_key, form_info in forms.items():
                    message += f"・{form_key} {form_info['name']}: {form_info['url']}\\n"
                    message += f"  ({form_info['description']})\\n"
                message += "\\n"
        
        # ガイド・マニュアル
        guides = agent.get("urls", {}).get("guides", {})
        if guides:
            message += "📚 **参考資料**\\n"
            for guide_name, guide_info in guides.items():
                message += f"・{guide_name}: {guide_info['url']}\\n"
            message += "\\n"
        
        # 最終確認日
        last_checked = agent.get("last_checked", "不明")
        message += f"⚠️ **注意事項**\\n"
        message += f"・最新の様式は必ず厚生労働省の公式サイトでご確認ください\\n"
        message += f"・URL最終確認日: {last_checked}\\n"
        
        if agent.get("notes"):
            message += f"・備考: {agent['notes']}\\n"
        
        return message
    
    def check_outdated_urls(self, days: int = 30) -> List[Dict]:
        """
        指定日数以上更新されていないエージェントをチェック
        Args:
            days: チェック日数（デフォルト30日）
        Returns:
            期限切れエージェントのリスト
        """
        outdated = []
        today = datetime.now()
        
        for agent_id, agent_data in self.data.get("agents", {}).items():
            if not agent_data.get("active"):
                continue
                
            last_checked = agent_data.get("last_checked")
            if last_checked:
                try:
                    checked_date = datetime.strptime(last_checked, "%Y-%m-%d")
                    days_diff = (today - checked_date).days
                    
                    if days_diff > days:
                        outdated.append({
                            "agent_id": agent_id,
                            "name": agent_data.get("name"),
                            "last_checked": last_checked,
                            "days_old": days_diff
                        })
                except ValueError:
                    logger.error(f"Invalid date format for agent {agent_id}: {last_checked}")
        
        return outdated
    
    def get_agent_data_files(self, agent_id: str) -> List[str]:
        """
        エージェントが使用するデータファイルのリストを取得
        Args:
            agent_id: エージェントID
        Returns:
            データファイル名のリスト
        """
        agent = self.get_agent_info(agent_id)
        if not agent:
            return []
        
        return agent.get("data_files", [])