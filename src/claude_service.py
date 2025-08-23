import os
import anthropic
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class ClaudeService:
    def __init__(self):
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY is not set, using mock responses")
            self.client = None
            self.mock_mode = True
        else:
            self.mock_mode = False
            try:
                self.client = anthropic.Anthropic(
                    api_key=api_key
                )
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic client: {str(e)}")
                raise
        
        self.model = "claude-3-5-sonnet-20241022"
        
        # 業務改善助成金専門外の質問への対応プロンプト
        self.general_prompt = """
申し訳ございませんが、このサービスは「業務改善助成金」に特化した専門相談サービスです。

【対応可能な内容】
✅ 業務改善助成金の制度説明
✅ 申請要件の確認
✅ 助成額の算定
✅ 対象設備・機器の相談
✅ 申請手続きの流れ
✅ 必要書類の説明

【対応できない内容】
❌ 他の助成金・補助金（キャリアアップ助成金、ものづくり補助金等）
❌ 業務改善助成金以外の制度

業務改善助成金についてご質問がございましたら、お気軽にお聞かせください。
詳細で正確な専門アドバイスを提供いたします。

その他の助成金・補助金については、専門の社会保険労務士または中小企業診断士にご相談いただくことをお勧めします。
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
            
            if all_content:
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
            else:
                # ファイルが読み込めない場合のフォールバック
                return self.general_prompt
                
        except Exception as e:
            logger.error(f"Error loading business improvement prompt: {str(e)}")
            return self.general_prompt
    
    def _select_system_prompt(self, question: str) -> str:
        """質問内容に応じて適切なシステムプロンプトを選択"""
        question_lower = question.lower()
        
        # 業務改善助成金関連のキーワード
        business_keywords = [
            "業務改善", "最低賃金", "設備投資", "生産性向上",
            "pos", "レジ", "機械装置", "賃金引上げ"
        ]
        
        # 他の助成金・補助金のキーワード（除外対象）
        other_grants = [
            "キャリアアップ", "ものづくり補助金", "小規模事業者持続化", 
            "it導入補助金", "人材開発支援", "雇用調整助成金",
            "創業補助金", "事業再構築"
        ]
        
        # 他の助成金・補助金の質問は専門外として処理
        if any(keyword in question_lower for keyword in other_grants):
            return self.general_prompt
        
        # 業務改善助成金関連の質問
        if any(keyword in question_lower for keyword in business_keywords):
            return self.business_improvement_prompt
        
        # 曖昧な質問は専門外として処理
        return self.general_prompt
    
    def get_grant_consultation(self, company_info: Dict, question: str) -> str:
        """
        企業情報と質問を基に、助成金相談の回答を生成
        """
        try:
            # モックモードの場合
            if self.mock_mode:
                return f"""
【業務改善助成金 - AI相談サービス】

ご質問: {question}

業務改善助成金について回答いたします。

**制度概要**
業務改善助成金は、中小企業・小規模事業者が生産性向上のために設備投資等を行い、事業場内最低賃金を引き上げた場合に、その設備投資等にかかった費用の一部を助成する制度です。

**主な要件**
- 設備投資による業務改善
- 最低賃金の引き上げ
- 生産性向上の実現

**助成額**
引き上げる労働者数と引上げ額に応じて、30万円～600万円まで

詳細な申請要件や手続きについては、最新の交付要綱をご確認ください。

※現在はテストモードで動作中です。正式版では最新の公式情報に基づいた詳細な回答を提供いたします。
"""
            
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
    
    def chat(self, prompt: str, context: str = "") -> str:
        """
        一般的なチャット機能（助成金診断用）
        """
        try:
            # モックモードの場合
            if self.mock_mode:
                return f"""
【助成金診断結果 - テストモード】

{prompt}

申し訳ございませんが、現在はテスト環境で動作中です。
ANTHROPIC_API_KEYが設定されていないため、実際のAI診断は行えません。

実際の運用時には、Claude AIが以下のような詳細な診断を行います：
- 29カテゴリーの助成金から該当するものを抽出
- 具体的な支給額の算定
- 申請要件の詳細説明
- 専門エージェントの推奨

本格運用には環境変数の設定が必要です。
"""
            
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.3,
                messages=[
                    {
                        "role": "user", 
                        "content": f"{context}\n\n{prompt}"
                    }
                ]
            )
            
            return message.content[0].text
            
        except Exception as e:
            logger.error(f"Claude chat error: {str(e)}")
            return f"申し訳ございません。AI診断中にエラーが発生しました: {str(e)}"