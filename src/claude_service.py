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
        """業務改善助成金の詳細プロンプトをロード（全4ファイル統合版）"""
        try:
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # 4つのファイルを全て読み込み
            files = [
                'gyoumukaizen07.txt',  # 交付要綱
                'gyoumukaizenmanyual.txt',  # 申請マニュアル
                '業務改善助成金Ｑ＆Ａ.txt',  # Q&A
                '業務改善助成金 交付申請書等の書き方と留意事項 について.txt'  # 申請書の書き方
            ]
            
            all_content = ""
            for file_name in files:
                file_path = os.path.join(base_dir, file_name)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        all_content += f"\n\n【{file_name}】\n{content}\n"
                        logger.info(f"Successfully loaded file: {file_name} ({len(content)} chars)")
                except FileNotFoundError:
                    logger.error(f"File not found: {file_path}")
                    continue
                except Exception as e:
                    logger.error(f"Error reading file {file_path}: {str(e)}")
                    continue
            
            return f"""
あなたは業務改善助成金の専門家です。以下の公式文書を完全に理解した上で、企業からの相談に正確に回答してください。

【業務改善助成金 完全版資料】
{all_content}

以下の形式で構造化された診断を行ってください：

✅ **基本条件チェック**
1. 中小企業事業者の要件
2. 事業場内最低賃金の引上げ要件
3. 生産性向上設備投資の要件

📋 **企業状況の診断**
・業種区分による資本金・従業員数要件
・現在の最低賃金状況
・設備投資計画の妥当性

💰 **助成額の算定**
・申請可能なコース区分
・引上げ労働者数に応じた助成額
・助成率の適用

⚠️ **注意事項・リスク**
・交付対象除外要件の確認
・申請スケジュールの注意点
・必要書類と手続きの流れ

必ず交付要綱に基づいて正確な情報を提供し、企業の状況に応じた具体的なアドバイスを行ってください。
"""
        except FileNotFoundError:
            return self.general_prompt
    
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
            # 企業情報を整理
            company_context = self._format_company_info(company_info)
            
            # 業務改善助成金関連の質問かチェック
            if self._is_business_improvement_question(question):
                # 関連情報のみを抽出してコンパクトなプロンプトを作成
                relevant_info = self._extract_relevant_info(question, company_info)
                system_prompt = f"""
あなたは業務改善助成金の専門家です。以下の情報を基に、企業の相談に正確に回答してください。

【関連する制度情報】
{relevant_info}

【回答の形式】
✅ 基本条件チェック
📋 企業状況の診断  
💰 助成額の算定
⚠️ 注意事項・リスク

具体的で実践的なアドバイスを提供してください。
"""
            else:
                system_prompt = self.general_prompt
            
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
    
    def _is_business_improvement_question(self, question: str) -> bool:
        """業務改善助成金関連の質問かどうか判定"""
        keywords = [
            "業務改善", "最低賃金", "設備投資", "生産性向上",
            "pos", "レジ", "機械装置", "賃金引上げ", "助成額", "申請"
        ]
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in keywords)
    
    def _extract_relevant_info(self, question: str, company_info: Dict) -> str:
        """質問と企業情報に関連する情報のみを抽出"""
        # 簡略化された重要な制度情報
        basic_info = """
【業務改善助成金の基本概要】
目的：中小企業・小規模事業者の生産性向上を図り、事業場内最低賃金の引上げを支援
対象：中小企業・小規模事業者
条件：設備投資を行い、事業場内最低賃金を一定額以上引き上げること

【助成対象と助成額】
・30円以上引上げ：助成率3/4（上限50万円）
・45円以上引上げ：助成率3/4（上限70万円）  
・60円以上引上げ：助成率3/4（上限100万円）
・90円以上引上げ：助成率3/4（上限120万円）

【対象設備の例】
POSシステム、自動釣銭機、キャッシュレス決済端末、顧客管理システム、
業務用ソフトウェア、機械装置、工具、器具備品等

【主な要件】
1. 中小企業事業者であること
2. 賃金引上げ計画を策定し、実行すること
3. 対象設備を導入し、生産性向上を図ること
4. 解雇や賃金引下げ等を行っていないこと
"""
        
        # 企業の業種や規模に応じた追加情報
        additional_info = ""
        
        industry = company_info.get('industry', '')
        if '小売' in industry or '飲食' in industry:
            additional_info += """
【小売・飲食業向け】
特に効果的な設備：POSシステム、自動釣銭機、券売機、予約管理システム
"""
        elif 'サービス' in industry:
            additional_info += """
【サービス業向け】  
特に効果的な設備：顧客管理システム、予約システム、業務効率化ソフト
"""
        
        return basic_info + additional_info