import os
import anthropic
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class ClaudeService:
    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=os.getenv('CLAUDE_API_KEY')
        )
        self.model = "claude-3-5-sonnet-20241022"
        
        # 業務改善助成金の専門知識を含むシステムプロンプト
        self.system_prompt = """
あなたは業務改善助成金の専門家です。社会保険労務士として、企業の助成金申請をサポートします。

業務改善助成金について：
- 事業場内最低賃金を30円以上引き上げ、生産性向上のための設備投資等を行う事業者を支援
- 助成率：30万円以上の設備投資で、引き上げる労働者数に応じて15万円～600万円を助成
- 対象設備：POSレジシステム、モバイルPOS、券売機等の機械設備、コンサルティング導入、人材育成・教育訓練等
- 申請は計画申請と支給申請の2段階
- 就業規則の整備が必要

企業情報を基に、以下の観点で回答してください：
1. 助成金の適用可能性
2. 必要な条件と手続き
3. 具体的な申請手順
4. 注意点とリスク
5. 他の助成金との併用可能性

必ず具体的で実用的なアドバイスを提供し、申請の成功率を高めるためのポイントを説明してください。
"""
    
    def get_grant_consultation(self, company_info: Dict, question: str) -> str:
        """
        企業情報と質問を基に、助成金相談の回答を生成
        """
        try:
            # 企業情報を整理
            company_context = self._format_company_info(company_info)
            
            # プロンプトを構築
            user_prompt = f"""
企業情報：
{company_context}

質問：
{question}

上記の企業情報を踏まえて、業務改善助成金に関する専門的なアドバイスをお願いします。
"""
            
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.3,
                system=self.system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ]
            )
            
            return message.content[0].text
            
        except Exception as e:
            logger.error(f"Claude API error: {str(e)}")
            return "申し訳ございません。現在システムに問題が発生しています。しばらく時間をおいて再度お試しください。"
    
    def check_available_grants(self, company_info: Dict) -> List[Dict]:
        """
        企業情報を基に利用可能な助成金をチェック
        """
        try:
            company_context = self._format_company_info(company_info)
            
            prompt = f"""
以下の企業情報を分析して、利用可能な助成金を判定してください：

{company_context}

以下の形式でJSON形式で回答してください：
{{
  "業務改善助成金": {{
    "適用可能性": "高い/中程度/低い",
    "理由": "理由の説明",
    "必要条件": ["条件1", "条件2"],
    "推定助成額": "金額範囲"
  }}
}}
"""
            
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.2,
                system=self.system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # 簡単な解析結果を返す（本来はJSONパースが必要）
            response_text = message.content[0].text
            
            return [{
                "name": "業務改善助成金",
                "description": response_text,
                "status": "分析完了"
            }]
            
        except Exception as e:
            logger.error(f"Grant check error: {str(e)}")
            return [{
                "name": "エラー",
                "description": "助成金の分析中にエラーが発生しました。",
                "status": "エラー"
            }]
    
    def _format_company_info(self, company_info: Dict) -> str:
        """
        企業情報を整理された文字列に変換
        """
        formatted = []
        
        if company_info.get('company_name'):
            formatted.append(f"会社名: {company_info['company_name']}")
        
        if company_info.get('industry'):
            formatted.append(f"業種: {company_info['industry']}")
        
        if company_info.get('employee_count'):
            formatted.append(f"従業員数: {company_info['employee_count']}人")
        
        if company_info.get('annual_revenue'):
            formatted.append(f"年間売上: {company_info['annual_revenue']}")
        
        if company_info.get('current_min_wage'):
            formatted.append(f"現在の最低賃金: {company_info['current_min_wage']}円")
        
        if company_info.get('planned_investment'):
            formatted.append(f"設備投資予定: {company_info['planned_investment']}")
        
        if company_info.get('business_goals'):
            formatted.append(f"事業目標: {company_info['business_goals']}")
        
        return "\n".join(formatted) if formatted else "企業情報が提供されていません"