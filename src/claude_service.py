import os
import anthropic
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class ClaudeService:
    def __init__(self):
        api_key = os.getenv('CLAUDE_API_KEY')
        if not api_key:
            logger.error("CLAUDE_API_KEY is not set in environment variables")
            raise ValueError("CLAUDE_API_KEY is required")
        
        try:
            self.client = anthropic.Anthropic(
                api_key=api_key
            )
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {str(e)}")
            raise
        
        self.model = "claude-3-5-sonnet-20241022"
        
        # 助成金専門のシステムプロンプト（汎用版）
        self.general_prompt = """
あなたは助成金の専門家です。社会保険労務士として、企業の助成金申請をサポートします。

企業情報を基に、以下の観点で回答してください：
1. 助成金の適用可能性
2. 必要な条件と手続き
3. 具体的な申請手順
4. 注意点とリスク
5. 他の助成金との併用可能性

質問された助成金について詳細に説明し、企業の状況に最適な助成金を提案してください。
"""
        
        # 業務改善助成金専門プロンプト
        self.business_improvement_prompt = self._load_business_improvement_prompt()
    
    def _load_business_improvement_prompt(self) -> str:
        """業務改善助成金の要約版プロンプトを返す"""
        return """
あなたは業務改善助成金の専門家です。以下の公式情報に基づいて、企業からの相談に正確に回答してください。

【業務改善助成金制度概要】
目的：中小企業等の生産性向上と賃金引上げ支援
対象：中小企業事業者、小規模事業者
条件：設備投資により生産性向上を図り、事業場内最低賃金を引き上げる

【助成額・助成率】
引上額30円：上限50万円（助成率3/4）
引上額45円：上限70万円（助成率3/4）
引上額60円：上限100万円（助成率3/4）
引上額90円：上限120万円（助成率3/4）

【対象設備例】
POSシステム、自動釣銭機、キャッシュレス決済端末、券売機、
顧客管理システム、予約システム、会計ソフト、業務ソフト、
PC・タブレット端末、機械装置、測定工具、器具備品等

【中小企業の定義】
・小売業：資本金5千万円以下または従業員50人以下
・サービス業：資本金5千万円以下または従業員100人以下  
・卸売業：資本金1億円以下または従業員100人以下
・製造業：資本金3億円以下または従業員300人以下

【申請要件】
1. 賃金引上げ計画の策定・実行
2. 対象設備の導入による生産性向上
3. 解雇・賃金引下げ等の禁止
4. 申請前に設備導入・賃金引上げを実施

【除外要件】
・過去3年間に不正受給歴
・労働関係法令違反
・賃金引下げ、解雇等の実施
・風俗営業関連事業

以下の形式で構造化された診断を行ってください：

✅ **基本条件チェック**
📋 **企業状況の診断**  
💰 **助成額の算定**
⚠️ **注意事項・リスク**

具体的で実践的なアドバイスを提供してください。
"""
    
    def _select_system_prompt(self, question: str) -> str:
        """質問内容に応じて適切なシステムプロンプトを選択"""
        question_lower = question.lower()
        
        # 業務改善助成金関連のキーワード
        business_keywords = [
            "業務改善", "最低賃金", "設備投資", "生産性向上",
            "pos", "レジ", "機械装置", "賃金引上げ"
        ]
        
        if any(keyword in question_lower for keyword in business_keywords):
            return self.business_improvement_prompt
        
        # デフォルトは汎用プロンプト
        return self.general_prompt
    
    def get_grant_consultation(self, company_info: Dict, question: str) -> str:
        """
        企業情報と質問を基に、助成金相談の回答を生成
        """
        try:
            # 質問内容に応じてプロンプトを選択
            system_prompt = self._select_system_prompt(question)
            
            # 企業情報を整理
            company_context = self._format_company_info(company_info)
            
            # プロンプトを構築
            user_prompt = f"""
企業情報：
{company_context}

質問：
{question}

上記の企業情報を踏まえて、専門的なアドバイスをお願いします。
"""
            
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.3,
                system=system_prompt,
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
                system=self.general_prompt,
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