import os
import anthropic
from typing import Dict, List
import logging
from forms_manager import FormsManager

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
        
        # Forms Manager初期化
        self.forms_manager = FormsManager()
        
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

【申請様式について - 重要】
申請様式が必要な場合の対応：
- **絶対にURLを自分で生成しないでください**
- 「申請様式については以下でご案内します」とだけ回答してください
- システムが自動的に正しい公式URLを追加します
- 様式番号と用途は説明してOK
- 記入方法や注意点は詳しく解説してOK

【厳守事項】
- URLは絶対に生成しない（例：https://www.mhlw.go.jp/... などは書かない）
- 「厚生労働省のホームページで」などの具体的なサイト名も書かない
- 申請様式のダウンロード方法を聞かれたら「以下でご案内します」とだけ答える
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
    
    def _select_system_prompt_by_agent(self, agent_type: str, question: str) -> str:
        """エージェントタイプに応じてシステムプロンプトを選択"""
        if agent_type == 'gyoumukaizen':
            return self.business_improvement_prompt
        elif agent_type.startswith('career-up'):
            # キャリアアップ助成金のコース別対応
            return self._get_career_up_prompt(agent_type)
        elif agent_type.startswith('jinzai-kaihatsu'):
            # 人材開発支援助成金の各コースに対応
            course = agent_type.replace('jinzai-kaihatsu_', '') if '_' in agent_type else ''
            return self._get_jinzai_kaihatsu_prompt(course)
        else:
            # その他のエージェントは既存のロジックを使用
            return self._select_system_prompt(question)
    
    def _get_jinzai_kaihatsu_prompt(self, course: str) -> str:
        """人材開発支援助成金の各コース用プロンプトを生成"""
        course_info = {
            'jinzai-ikusei': '人材育成支援コース',
            'kyoiku-kunren-kyuka': '教育訓練休暇等付与コース',
            'hito-toshi': '人への投資促進コース',
            'reskilling': '事業展開等リスキリング支援コース',
            'sonota': 'その他のコース'
        }
        
        course_name = course_info.get(course, '人材開発支援助成金')
        
        return f"""
あなたは{course_name}の専門AIエージェントです。

【専門分野】
- {course_name}に関する質問のみ回答
- 研修・教育訓練・人材育成に関する助成金制度
- 申請手続き、要件、支給額の詳細説明

【回答方針】
1. {course_name}に特化した正確な情報を提供
2. 申請要件を詳しく説明
3. 支給額・助成率を具体的に記載
4. 申請手続きの流れを説明
5. よくある質問にも対応

【注意事項】
- 厚生労働省管轄の助成金のみ対応
- 補助金についての質問には「専門外です」と回答
- 不明な点は最新の公式情報の確認を推奨

質問者の企業情報を踏まえ、{course_name}について専門的で実用的なアドバイスを提供してください。
"""
    
    def _get_career_up_prompt(self, agent_type: str) -> str:
        """キャリアアップ助成金のコース別プロンプトを生成"""
        course_map = {
            'career-up_seishain': ('正社員化コース', 'career-up_seishain.txt'),
            'career-up_shogaisha': ('障害者正社員化コース', 'career-up_shogaisha.txt'),
            'career-up_chingin': ('賃金規定等改定コース', 'career-up_chingin.txt'),
            'career-up_kyotsu': ('賃金規定等共通化コース', 'career-up_kyotsu.txt'),
            'career-up_shoyo': ('賞与・退職金制度導入コース', 'career-up_shoyo.txt'),
            'career-up_shahoken': ('社会保険適用時処遇改善コース', 'career-up_shahoken.txt'),
            'career-up_tanshuku': ('短時間労働者労働時間延長支援コース', 'career-up_tanshuku.txt')
        }
        
        if agent_type not in course_map:
            return self.general_prompt
            
        course_name, file_name = course_map[agent_type]
        
        try:
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # 共通部分を読み込み
            common_file_path = os.path.join(base_dir, 'career-up_common.txt')
            with open(common_file_path, 'r', encoding='utf-8') as f:
                common_content = f.read()
            
            # コース固有部分を読み込み
            course_file_path = os.path.join(base_dir, file_name)
            with open(course_file_path, 'r', encoding='utf-8') as f:
                course_content = f.read()
                
            # 共通部分とコース固有部分を結合
            full_content = f"{common_content}\n\n=== {course_name} 詳細 ===\n{course_content}"
                
            return f"""
あなたはキャリアアップ助成金の{course_name}専門AIエージェントです。

【専門分野】
- {course_name}に関する質問のみ回答
- 非正規雇用労働者のキャリアアップ支援制度
- 計画申請から支給申請まで全フェーズ対応

【{course_name} 詳細資料】
{full_content}

【回答方針】
1. {course_name}に特化した正確な情報を提供
2. 支給要件を詳しく説明
3. 支給額・助成率を具体的に記載
4. 申請手続きの流れを説明（計画申請→実施→支給申請）
5. 必要書類と添付資料の案内

【構造化された回答形式】
✅ **対象労働者の要件**
- 有期雇用労働者/無期雇用労働者/派遣労働者の区分
- 雇用期間・勤続年数等の条件

📋 **支給対象事業主の要件**
- キャリアアップ計画の作成・提出
- 転換制度の整備
- 賃金増額要件

💰 **支給額の算定**
- 中小企業・大企業別の支給額
- 加算措置の適用条件

📝 **申請手続きの流れ**
- キャリアアップ計画書提出
- 転換・直接雇用の実施
- 支給申請書提出

⚠️ **注意事項・併給調整**
- 他の助成金との関係
- 支給申請期限

【申請様式について - 重要】
申請様式が必要な場合の対応：
- **絶対にURLを自分で生成しないでください**
- 「申請様式については以下でご案内します」とだけ回答してください
- システムが自動的に正しい公式URLを追加します
- 様式番号と用途は説明してOK
- 記入方法や注意点は詳しく解説してOK

【厳守事項】
- URLは絶対に生成しない（例：https://www.mhlw.go.jp/... などは書かない）
- 「厚生労働省のホームページで」などの具体的なサイト名も書かない
- 申請様式のダウンロード方法を聞かれたら「以下でご案内します」とだけ答える

必ず支給要領に基づいて正確な情報を提供し、企業の状況に応じた具体的なアドバイスを行ってください。
"""
        except Exception as e:
            logger.error(f"Error loading career-up course file {file_name}: {str(e)}")
            return f"""
申し訳ございません。{course_name}の詳細資料の読み込みに失敗しました。
キャリアアップ助成金に関する一般的な情報は提供できますが、詳細な要件については厚生労働省の公式サイトをご確認ください。
"""
    
    def _include_form_urls(self, agent_type: str, response: str, original_question: str = "") -> str:
        """
        シンプルな様式URL案内（複雑な自動検出は削除）
        必要な場合はメモセクションの申請書類ページを案内
        """
        # シンプルに：AIが勝手にURLを生成しないよう防止するのみ
        # 申請書類が必要な場合は、ユーザーがメモセクションから確認できるようにする
        return response
    
    def get_grant_consultation(self, company_info: Dict, question: str, agent_type: str = 'gyoumukaizen') -> str:
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
            
            # エージェントタイプに応じてプロンプトを選択
            system_prompt = self._select_system_prompt_by_agent(agent_type, question)
            
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
            
            response = message.content[0].text
            
            # 様式URL情報を追加（必要に応じて）
            response = self._include_form_urls(agent_type, response, question)
            
            return response
            
        except Exception as e:
            logger.error(f"Claude API error: {str(e)}")
            return "申し訳ございません。現在システムに問題が発生しています。しばらく時間をおいて再度お試しください。"
    
    def check_available_grants(self, company_info: Dict) -> List[Dict]:
        """
        企業情報を基に利用可能な助成金をチェック
        """
        try:
            company_context = self._format_company_info(company_info)
            
            # 基本的な助成金チェック結果を生成
            results = []
            
            # 業務改善助成金の詳細判定
            business_improvement_result = self._check_business_improvement(company_info)
            results.append(business_improvement_result)
            
            # キャリアアップ助成金の可能性チェック
            career_up_result = self._check_career_up_possibility(company_info)
            results.append(career_up_result)
            
            return results
            
        except Exception as e:
            logger.error(f"Grant check error: {str(e)}")
            return [{
                "name": "エラー",
                "description": "助成金の分析中にエラーが発生しました。",
                "status": "エラー"
            }]
    
    def _check_business_improvement(self, company_info: Dict) -> Dict:
        """業務改善助成金の詳細判定"""
        # 従業員数チェック
        employee_count = company_info.get('employee_count', 0)
        industry = company_info.get('industry', '')
        
        # 中小企業要件チェック（簡易版）
        is_sme = employee_count <= 300  # 簡易判定
        
        if is_sme:
            return {
                "name": "業務改善助成金",
                "description": "✅ 適用可能性: 高い\n・中小企業要件を満たしています\n・設備投資と最低賃金引上げで最大600万円\n→ 業務改善助成金専門エージェントで詳細相談",
                "status": "適用可能",
                "agent_recommendation": "gyoumukaizen"
            }
        else:
            return {
                "name": "業務改善助成金",
                "description": "❌ 適用可能性: 低い\n・中小企業要件（従業員数）を超えている可能性があります",
                "status": "要件不適合"
            }
    
    def _check_career_up_possibility(self, company_info: Dict) -> Dict:
        """キャリアアップ助成金の可能性チェック"""
        employee_count = company_info.get('employee_count', 0)
        
        # 従業員がいる企業なら可能性あり
        if employee_count > 0:
            description = """🔍 可能性あり（要件によっては適用可能）
以下に該当する場合、各コースが利用できる可能性があります：

【主要コース】
✓ 正社員化コース: 非正規雇用者を正社員に転換する場合
✓ 賃金規定等改定コース: 賃金制度を見直し・改善する場合  
✓ 賞与・退職金制度導入コース: 福利厚生制度を新設する場合
✓ 社会保険適用時処遇改善コース: 社保適用拡大への対応が必要な場合

💡 詳細な要件や支給額については、キャリアアップ助成金専門エージェントにご相談ください"""
            
            return {
                "name": "キャリアアップ助成金",
                "description": description,
                "status": "可能性あり",
                "agent_recommendation": "career-up"
            }
        else:
            return {
                "name": "キャリアアップ助成金",
                "description": "ℹ️ 従業員情報が不明のため判定できません",
                "status": "情報不足"
            }
    
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