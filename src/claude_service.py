import os
import anthropic
from typing import Dict, List
import logging
from forms_manager import FormsManager

logger = logging.getLogger(__name__)

class ClaudeService:
    def __init__(self):
        # ファイル内容キャッシュ（メモリ使用量削減）
        self._file_cache = {}
        # 業務改善助成金ファイルの強制キャッシュクリア
        self._clear_gyoumukaizen_cache()

    def _clear_gyoumukaizen_cache(self):
        """業務改善助成金ファイルのキャッシュを強制クリア"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        gyoumukaizen_files = [
            'file/業務改善助成金/gyoumukaizen07.txt',
            'file/業務改善助成金/gyoumukaizenmanyual.txt',
            'file/業務改善助成金/業務改善助成金Ｑ＆Ａ.txt',
            'file/業務改善助成金/業務改善助成金 交付申請書等の書き方と留意事項 について.txt',
            'file/業務改善助成金/業務改善助成金交付要領.txt',
            'file/業務改善助成金/最低賃金額以上かどうかを確認する方法.txt'
        ]

        for file_name in gyoumukaizen_files:
            file_path = os.path.join(base_dir, file_name)
            if file_path in self._file_cache:
                del self._file_cache[file_path]
                logger.info(f"Cleared cache for: {file_name}")

    def _read_file_cached(self, file_path: str) -> str:
        """キャッシュ機能付きファイル読み込み"""
        if file_path in self._file_cache:
            logger.info(f"Loaded from cache: {os.path.basename(file_path)}")
            return self._file_cache[file_path]

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self._file_cache[file_path] = content
                logger.info(f"Successfully loaded and cached: {os.path.basename(file_path)} ({len(content)} chars)")
                return content
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {str(e)}")
            return ""

    # 共通プロンプト要素（すべてのエージェントで使用）
    COMMON_TIMELINE_UNDERSTANDING = """
【助成金申請の時系列理解 - 最重要】
質問者が「これから〜する予定」「〜にします」と言った場合：
→ これは将来の計画であり、まだ実施していない
→ 計画申請時点では「実施前」として扱う
→ 「既に実施済み」と誤解しない

例：「1010円から1075円にします」
→ 計画申請時点：1010円（現在）
→ 引上げ後：1075円（将来）
→ 差額：65円の引上げ予定

【状態変化の確認原則】
常に以下の3時点を明確に区別：
1. 現在の状態（計画申請時点）
2. 実施中の状態（計画実行期間）
3. 完了後の状態（支給申請時点）"""
    
    COMMON_LOGICAL_OPERATORS = """
【論理演算子の厳密な理解 - 必須】
・「AかつB」= AとBの両方の条件を満たす必要がある
・「AまたはB」= AかBのどちらか一方の条件を満たせばよい
・「AおよびB」= AとBの両方の条件を満たす必要がある
・「AもしくはB」= AかBのどちらか一方の条件を満たせばよい"""
    
    COMMON_DATE_EXPRESSIONS = """
【日付表現の厳密な理解 - 必須】
・「前日」= その日の1日前（例：4月1日の前日 = 3月31日）
・「翌日」= その日の1日後（例：3月31日の翌日 = 4月1日）
・「全日」= その日の0時から24時まで（例：3月31日の全日 = 3月31日の0時～24時）
・日付は絶対に勝手に変更しない"""

    COMMON_DEADLINE_HANDLING = """
【申請期限の厳密な計算 - 最重要】
期限に関する質問を受けた場合は、必ず以下を確認：

0. 【文書の階層確認 - 最優先】
   - 要綱（基本原則）と要領（詳細規定）の両方を必ず確認
   - 要領により詳細な期限情報が記載されている
   - 期限・期日・申請期間については要領を優先的に参照
   - 「要綱では曖昧でも要領に具体的期間が記載」されている場合が多い

1. 【申請種別の確認】
   - 計画申請なのか？支給申請なのか？
   - 明確でない場合は「計画申請と支給申請のどちらについて確認されますか？」と質問

2. 【基準日の特定】
   - 「○○から」の○○が何を指すか厳密に確認
   - 例：「正社員転換から6ヶ月後」→転換日が基準日
   - 例：「賃上げ実施から」→賃上げ実施日が基準日

3. 【期間計算の厳密性】
   - 「6ヶ月経過後2ヶ月以内」= 基準日＋6ヶ月＋1日～基準日＋8ヶ月
   - 「速やかに」= 通常1ヶ月以内（要領で具体的期間を確認）
   - 月数計算は日付ベースで厳密に（2024年1月15日＋6ヶ月 = 2024年7月15日）

4. 【回答前の確認】
   - 要綱・要領の両方から期限情報を確認済みであることを明示
   - 計算過程を明示
   - 「基準日：○年○月○日、期限：○年○月○日～○年○月○日」形式で回答
   - 要領から得た詳細情報を必ず含める

【絶対禁止事項】
- 要領を確認せずに要綱だけで回答
- 曖昧な期限回答
- 基準日を確認せずに回答
- 計画申請と支給申請を混同した回答"""
    
    def __init__(self):
        api_key = os.getenv('CLAUDE_API_KEY') or os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            logger.warning("CLAUDE_API_KEY/ANTHROPIC_API_KEY is not set, using mock responses")
            self.client = None
            self.mock_mode = True
        else:
            self.mock_mode = False
            try:
                self.client = anthropic.Anthropic(
                    api_key=api_key
                )
                logger.info(f"Anthropic client initialized successfully with {'CLAUDE_API_KEY' if os.getenv('CLAUDE_API_KEY') else 'ANTHROPIC_API_KEY'}")
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic client: {str(e)}")
                raise
        
        self.model = "claude-3-5-sonnet-20241022"  # Haikuから最新のSonnet 3.5に変更
        
        # Forms Manager初期化
        self.forms_manager = FormsManager()
        
        
        # 業務改善助成金専門プロンプト（廃止予定・毎回読み込みに変更）
        # self.business_improvement_prompt = self._load_business_improvement_prompt()
    
    def _get_common_prompt_base(self) -> str:
        """すべてのエージェントで使用する共通プロンプトを返す"""
        return f"""
{self.COMMON_LOGICAL_OPERATORS}

{self.COMMON_DATE_EXPRESSIONS}

{self.COMMON_DEADLINE_HANDLING}

{self.COMMON_TIMELINE_UNDERSTANDING}
"""
    
    def _load_business_improvement_prompt(self) -> str:
        """業務改善助成金の詳細プロンプトをロード（全4ファイル統合版）"""
        try:
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # 業務改善助成金フォルダ内の全ファイルを読み込み
            files = [
                'file/業務改善助成金/gyoumukaizen07.txt',  # 交付要綱
                'file/業務改善助成金/gyoumukaizenmanyual.txt',  # 申請マニュアル
                'file/業務改善助成金/業務改善助成金Ｑ＆Ａ.txt',  # Q&A
                'file/業務改善助成金/業務改善助成金 交付申請書等の書き方と留意事項 について.txt',  # 申請書の書き方
                'file/業務改善助成金/業務改善助成金交付要領.txt',  # 交付要領（最重要）
                'file/業務改善助成金/最低賃金額以上かどうかを確認する方法.txt'  # 最低賃金確認方法
            ]

            all_content = ""
            for file_name in files:
                file_path = os.path.join(base_dir, file_name)

                # キャッシュから取得を試行
                if file_path in self._file_cache:
                    content = self._file_cache[file_path]
                    all_content += f"\n\n【{file_name}】\n{content}\n"
                    logger.info(f"Loaded from cache: {file_name} ({len(content)} chars)")
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # キャッシュに保存
                        self._file_cache[file_path] = content
                        all_content += f"\n\n【{file_name}】\n{content}\n"
                        logger.info(f"Successfully loaded file: {file_name} ({len(content)} chars)")
                except FileNotFoundError:
                    logger.error(f"File not found: {file_path}")
                    continue
                except Exception as e:
                    logger.error(f"Error reading file {file_path}: {str(e)}")
                    continue
            
            if all_content:
                common_prompt = self._get_common_prompt_base()
                return f"""
あなたは業務改善助成金の専門家です。以下の公式文書を完全に理解した上で、企業からの相談に正確に回答してください。

【最重要制約 - 絶対厳守】
1. 提供された公式文書の情報のみを使用してください
2. あなたの学習データに含まれる古い助成金情報は一切使用しないでください
3. 金額、要件、制度内容は全て下記資料通りに正確に記載してください
4. 資料に記載されていない情報は「詳細は厚生労働省にお問い合わせください」と回答してください

{common_prompt}

【業務改善助成金 完全版資料 - この情報のみ使用】
{all_content}

以下の形式で構造化された診断を行ってください：

✅ **基本条件チェック**
※公式資料に基づく要件確認を行ってください

📋 **企業状況の診断**
※提供された公式資料に基づいて企業の適用可能性を診断してください

💰 **助成額の算定**
※公式資料記載の算定方法に従って正確に計算してください

⚠️ **注意事項・リスク**
※公式資料に記載された注意事項を適切に案内してください

必ず交付要綱に基づいて正確な情報を提供し、企業の状況に応じた具体的なアドバイスを行ってください。

【申請書類について - 重要】
申請書類について質問された場合の対応：
- **絶対にURLを自分で生成しないでください**
- まず「申請様式については以下でご案内します。」と枕詞を述べてから、申請に必要な書類を以下の2種類に分類して説明してください：

📋 **厚労省指定の申請様式**（ダウンロード必要）
・「様式第○号」と記載されている法定書式
・支給申請書、事業所確認票、対象者確認票等
→ 「このサイト上部の『申請書類』ボタンから各助成金の申請様式をダウンロードできます」

📄 **企業で準備する添付書類**
・就業規則、労働協約、賃金台帳、出勤簿、雇用契約書等
・企業が日常的に作成・管理している書類
→ 「各企業で作成・管理されている書類です」

- 様式番号と用途、記入方法や注意点は詳しく解説してOK

【厳守事項】
- URLは絶対に生成しない（例：https://www.mhlw.go.jp/... などは書かない）
- 「厚生労働省のホームページで」などの具体的なサイト名も書かない
- 申請様式のダウンロード方法を聞かれたら「以下でご案内します」とだけ答える
"""
            else:
                # ファイルが読み込めない場合のフォールバック
                return "業務改善助成金の要綱ファイルが読み込めませんでした。"
                
        except Exception as e:
            logger.error(f"Error loading business improvement prompt: {str(e)}")
            return "業務改善助成金の要綱ファイルが読み込めませんでした。"
    
    def _select_system_prompt(self, question: str) -> str:
        """質問内容に応じて適切なシステムプロンプトを選択（廃止予定）"""
        # この関数は専門エージェント方式に移行したため使用されません
        return self.business_improvement_prompt
    
    def _select_system_prompt_by_agent(self, agent_type: str, question: str) -> str:
        """エージェントタイプに応じてシステムプロンプトを選択"""
        # 文字列の前後の空白を削除
        agent_type = agent_type.strip()
        
        if agent_type == 'hanntei':
            # 助成金判定エージェント
            return self._get_hanntei_prompt()
        elif agent_type == 'gyoumukaizen':
            return self._get_business_improvement_prompt()
        elif agent_type.startswith('career-up'):
            # キャリアアップ助成金のコース別対応
            return self._get_career_up_prompt(agent_type)
        elif agent_type.startswith('jinzai-kaihatsu'):
            # 人材開発支援助成金の各コースに対応
            return self._get_jinzai_kaihatsu_prompt(agent_type)
        elif agent_type == '65sai_keizoku':
            # 65歳超雇用推進助成金（65歳超継続雇用促進コース）
            return self._get_65sai_keizoku_prompt()
        else:
            # その他のエージェントは既存のロジックを使用
            logger.warning(f"Unknown agent type: '{agent_type}', falling back to general prompt")
            return self._select_system_prompt(question)
    
    def _get_hanntei_prompt(self) -> str:
        """助成金判定エージェント用のプロンプトを生成"""
        try:
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # 判定システムプロンプトファイルを読み込み
            prompt_file = os.path.join(base_dir, 'file/助成金判定/判定システムプロンプト.txt')
            database_file = os.path.join(base_dir, 'file/助成金判定/助成金データベース2025.txt')
            
            system_prompt = ""
            database_content = ""
            
            if os.path.exists(prompt_file):
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    system_prompt = f.read()
            
            if os.path.exists(database_file):
                with open(database_file, 'r', encoding='utf-8') as f:
                    database_content = f.read()
            
            # 共通プロンプトベースと組み合わせ
            common_prompt = self._get_common_prompt_base()
            
            return f"""{common_prompt}

{system_prompt}

【2025年度助成金データベース】
{database_content}
"""
        except Exception as e:
            logger.error(f"Error loading hanntei prompt: {str(e)}")
            return "助成金判定エージェントのファイルが読み込めませんでした。"
    
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
        common_prompt = self._get_common_prompt_base()
        
        return f"""
あなたは{course_name}の専門AIエージェントです。

【最重要制約 - 絶対厳守】
1. 提供された公式文書の情報のみを使用してください
2. あなたの学習データに含まれる古い助成金情報は一切使用しないでください
3. 金額、要件、制度内容は全て下記資料通りに正確に記載してください
4. 資料に記載されていない情報は「詳細は厚生労働省にお問い合わせください」と回答してください

{common_prompt}

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
    
    def _get_business_improvement_prompt(self) -> str:
        """業務改善助成金の詳細プロンプトをロード（毎回読み込み版）"""
        try:
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            logger.info(f"=== 業務改善助成金エージェント: ファイル読み込み開始 ===")
            logger.info(f"Base directory: {base_dir}")

            # 業務改善助成金フォルダ内の全ファイルを読み込み
            files = [
                'file/業務改善助成金/gyoumukaizen07.txt',  # 交付要綱
                'file/業務改善助成金/gyoumukaizenmanyual.txt',  # 申請マニュアル
                'file/業務改善助成金/業務改善助成金Ｑ＆Ａ.txt',  # Q&A
                'file/業務改善助成金/業務改善助成金 交付申請書等の書き方と留意事項 について.txt',  # 申請書の書き方
                'file/業務改善助成金/業務改善助成金交付要領.txt',  # 交付要領（最重要）
                'file/業務改善助成金/最低賃金額以上かどうかを確認する方法.txt'  # 最低賃金確認方法
            ]

            all_content = ""
            logger.info(f"Loading {len(files)} files...")

            for file_name in files:
                file_path = os.path.join(base_dir, file_name)
                logger.info(f"Trying to load: {file_path}")

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        all_content += f"\n\n【{file_name}】\n{content}\n"
                        logger.info(f"✓ Successfully loaded: {file_name} ({len(content)} chars)")
                except FileNotFoundError:
                    logger.error(f"✗ File not found: {file_path}")
                    continue
                except Exception as e:
                    logger.error(f"✗ Error reading file {file_path}: {str(e)}")
                    continue

            if not all_content:
                logger.error("No files were loaded successfully")
                return "業務改善助成金の詳細資料の読み込みに失敗しました。"

            logger.info(f"Total content loaded: {len(all_content)} characters")

            # 共通プロンプトベースを取得
            common_base = self._get_common_prompt_base()

            return f"""
{common_base}

あなたは業務改善助成金の専門エージェントです。

{all_content}

重要な指示:
- 必ず上記の公式資料に基づいて回答してください
- 特に交付要領ファイルに記載された申請期間情報を正確に提供してください
- 申請様式のダウンロード方法を聞かれたら「以下でご案内します」とだけ答える
- 企業の状況に応じた具体的なアドバイスを行ってください

必ず支給要領に基づいて正確な情報を提供し、企業の状況に応じた具体的なアドバイスを行ってください。
"""
        except Exception as e:
            logger.error(f"Error in _get_business_improvement_prompt: {str(e)}")
            return "業務改善助成金の詳細資料の読み込みに失敗しました。"

    def _get_career_up_prompt(self, agent_type: str) -> str:
        """キャリアアップ助成金のコース別プロンプトを生成"""
        course_map = {
            'career-up_seishain': ('正社員化コース', 'file/キャリアアップ助成金/1000 正社員化コース.txt'),
            'career-up_shogaisha': ('障害者正社員化コース', 'file/キャリアアップ助成金/2000 障害者正社員化コース.txt'),
            'career-up_chingin': ('賃金規定等改定コース', 'file/キャリアアップ助成金/3000 賃金規定等改定コース.txt'),
            'career-up_kyotsu': ('賃金規定等共通化コース', 'file/キャリアアップ助成金/4000 賃金規定等共通化コース.txt'),
            'career-up_shoyo': ('賞与・退職金制度導入コース', 'file/キャリアアップ助成金/5000 賞与・退職金制度導入コース.txt'),
            'career-up_shahoken': ('社会保険適用時処遇改善コース', 'file/キャリアアップ助成金/6000 社会保険適用時処遇改善コース.txt'),
            'career-up_tanshuku': ('短時間労働者労働時間延長支援コース', 'file/キャリアアップ助成金/7000 短時間労働者労働時間延長支援コース.txt')
        }
        
        if agent_type not in course_map:
            logger.warning(f"Agent type {agent_type} not found in course_map")
            return f"エージェントタイプ {agent_type} は定義されていません。"
            
        course_name, file_name = course_map[agent_type]
        try:
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # 共通部分を読み込み
            common_file_path = os.path.join(base_dir, 'file/キャリアアップ助成金/共通部分キャリアアップjyoseikin支給要領_共通.txt')
            with open(common_file_path, 'r', encoding='utf-8') as f:
                common_content = f.read()
            
            # コース固有部分を読み込み
            course_file_path = os.path.join(base_dir, file_name)
            with open(course_file_path, 'r', encoding='utf-8') as f:
                course_content = f.read()
                
            # 共通部分とコース固有部分を結合
            full_content = f"{common_content}\n\n=== {course_name} 詳細 ===\n{course_content}"
            common_prompt = self._get_common_prompt_base()
                
            return f"""
あなたはキャリアアップ助成金の{course_name}専門AIエージェントです。

【最重要制約 - 絶対厳守】
1. 提供された公式文書の情報のみを使用してください
2. あなたの学習データに含まれる古い助成金情報は一切使用しないでください
3. 金額、要件、制度内容は全て下記資料通りに正確に記載してください
4. 資料に記載されていない情報は「詳細は厚生労働省にお問い合わせください」と回答してください

{common_prompt}

【専門分野】
- {course_name}に関する質問のみ回答
- 非正規雇用労働者のキャリアアップ支援制度
- 計画申請から支給申請まで全フェーズ対応

【{course_name} 詳細資料 - この情報のみ使用】
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

【申請書類について - 重要】
申請書類について質問された場合の対応：
- **絶対にURLを自分で生成しないでください**
- まず「申請様式については以下でご案内します。」と枕詞を述べてから、申請に必要な書類を以下の2種類に分類して説明してください：

📋 **厚労省指定の申請様式**（ダウンロード必要）
・「様式第○号」と記載されている法定書式
・支給申請書、事業所確認票、対象者確認票等
→ 「このサイト上部の『申請書類』ボタンから各助成金の申請様式をダウンロードできます」

📄 **企業で準備する添付書類**
・就業規則、労働協約、賃金台帳、出勤簿、雇用契約書等
・企業が日常的に作成・管理している書類
→ 「各企業で作成・管理されている書類です」

- 様式番号と用途、記入方法や注意点は詳しく解説してOK

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
    
    def _get_65sai_keizoku_prompt(self) -> str:
        """65歳超雇用推進助成金（65歳超継続雇用促進コース）のプロンプトを生成"""
        try:
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            file_path = os.path.join(base_dir, 'file/65歳超雇用推進助成金/65歳超継続雇用促進コース.txt')

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 共通プロンプトベースを取得
            common_base = self._get_common_prompt_base()

            return f"""
{common_base}

あなたは65歳超雇用推進助成金（65歳超継続雇用促進コース）の専門エージェントです。

【65歳超雇用推進助成金（65歳超継続雇用促進コース）支給要領】
{content}

必ず支給要領に基づいて正確な情報を提供し、企業の状況に応じた具体的なアドバイスを行ってください。
定年引上げ、定年廃止、継続雇用制度の導入について、要件や支給額、申請手続きを詳しく説明してください。
"""
        except Exception as e:
            logger.error(f"Error loading 65sai_keizoku file: {str(e)}")
            return f"""
申し訳ございません。65歳超雇用推進助成金（65歳超継続雇用促進コース）の詳細資料の読み込みに失敗しました。
65歳超雇用推進助成金に関する一般的な情報は提供できますが、詳細な要件については厚生労働省の公式サイトをご確認ください。
"""

    def _get_jinzai_kaihatsu_prompt(self, agent_type: str) -> str:
        """人材開発支援助成金のコース別プロンプトを生成"""
        course_map = {
            # 人材育成支援コースの3つのサブコース
            'jinzai-kaihatsu_jinzai-ikusei_kunren': ('人材育成支援コース（人材育成訓練）', 'file/人材開発支援助成金/人材育成支援コース/0600 人材育成訓練.txt'),
            'jinzai-kaihatsu_jinzai-ikusei_nintei': ('人材育成支援コース（認定実習併用職業訓練）', 'file/人材開発支援助成金/人材育成支援コース/0700 認定実習併用職業訓練.txt'),
            'jinzai-kaihatsu_jinzai-ikusei_yuki': ('人材育成支援コース（有期実習型訓練）', 'file/人材開発支援助成金/人材育成支援コース/0800 有期実習型訓練.txt'),
            
            # 他のコース
            'jinzai-kaihatsu_kyoiku-kyuka': ('教育訓練休暇等付与コース', 'file/人材開発支援助成金/教育訓練休暇等付与コース/教育訓練休暇等付与コース.txt'),
            
            # 人への投資促進コースの4つのサブコース
            'jinzai-kaihatsu_toushi_teigaku': ('人への投資促進コース（定額制訓練）', 'file/人材開発支援助成金/人への投資促進コース/0600 定額制訓練.txt'),
            'jinzai-kaihatsu_toushi_jihatsu': ('人への投資促進コース（自発的職業能力開発訓練）', 'file/人材開発支援助成金/人への投資促進コース/0700 自発的職業能力開発訓練.txt'),
            'jinzai-kaihatsu_toushi_digital': ('人への投資促進コース（高度デジタル人材等訓練）', 'file/人材開発支援助成金/人への投資促進コース/0800 高度デジタル人材等訓練.txt'),
            'jinzai-kaihatsu_toushi_it': ('人への投資促進コース（情報技術分野認定実習併用職業訓練）', 'file/人材開発支援助成金/人への投資促進コース/0900 情報技術分野認定実習併用職業訓練.txt'),
            'jinzai-kaihatsu_toushi': ('人への投資促進コース', ''),
            'jinzai-kaihatsu_reskilling': ('事業展開等リスキリング支援コース', 'file/人材開発支援助成金/リスキリングコース/リスキリングコース_20250906_160343_AI_plain.txt'),
            'reskilling': ('事業展開等リスキリング支援コース', 'file/人材開発支援助成金/リスキリングコース/リスキリングコース_20250906_160343_AI_plain.txt'),
            'jinzai-kaihatsu_kensetsu-nintei': ('建設労働者認定訓練コース', ''),
            'jinzai-kaihatsu_kensetsu-gino': ('建設労働者技能実習コース', ''),
            'jinzai-kaihatsu_shogai': ('障害者職業能力開発コース', '')
        }
        
        if agent_type not in course_map:
            logger.warning(f"Agent type {agent_type} not found in jinzai-kaihatsu course_map")
            return f"エージェントタイプ {agent_type} は定義されていません。"
            
        course_name, file_name = course_map[agent_type]
        
        # ファイルが設定されていない場合（準備中のコース）
        if not file_name:
            return f"""
申し訳ございません。{course_name}は現在準備中です。
人材開発支援助成金の他のコースをお試しください。
"""
        
        try:
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # 教育訓練休暇等付与コースの特別処理
            if agent_type == 'jinzai-kaihatsu_kyoiku-kyuka':
                # 教育訓練休暇等付与コース専用のファイル読み込み
                course_file_path = os.path.join(base_dir, file_name)
                with open(course_file_path, 'r', encoding='utf-8') as f:
                    course_content = f.read()
                
                # 3つのQ&Aファイルを読み込み
                qa_files = [
                    'file/人材開発支援助成金/教育訓練休暇等付与コース/人材開発支援助成金事業主様向け Q&A_20250906_094600_AI_plain.txt',
                    'file/人材開発支援助成金/教育訓練休暇等付与コース/賃金要件・資格等手当要件についてQ&A_20250906_095243_AI_plain.txt'
                ]
                
                qa_content = ""
                for qa_file in qa_files:
                    qa_file_path = os.path.join(base_dir, qa_file)
                    if os.path.exists(qa_file_path):
                        with open(qa_file_path, 'r', encoding='utf-8') as f:
                            qa_content += f"\n\n【{os.path.basename(qa_file)}】\n{f.read()}\n"
                
                common_content = ""  # 教育訓練休暇等付与コースは独自の構成
                
            elif agent_type.startswith('jinzai-kaihatsu_toushi_'):
                # 人への投資促進コースの特別処理（4つのサブコース）
                # コース固有部分を読み込み
                course_file_path = os.path.join(base_dir, file_name)
                with open(course_file_path, 'r', encoding='utf-8') as f:
                    course_content = f.read()
                
                # 共通ファイルを読み込み
                common_file_path = os.path.join(base_dir, 'file/人材開発支援助成金/人への投資促進コース/人への投資促進コース_共通.txt')
                with open(common_file_path, 'r', encoding='utf-8') as f:
                    common_content = f.read()
                
                # 2つのQ&Aファイルを読み込み
                qa_files = [
                    'file/人材開発支援助成金/人への投資促進コース/人への投資促進コースQ&A_20250906_134400_AI_plain.txt',
                    'file/人材開発支援助成金/人への投資促進コース/賃金要件資格手当要件Q&A_20250906_135838_AI_plain.txt'
                ]
                
                qa_content = ""
                for qa_file in qa_files:
                    qa_file_path = os.path.join(base_dir, qa_file)
                    if os.path.exists(qa_file_path):
                        with open(qa_file_path, 'r', encoding='utf-8') as f:
                            qa_content += f"\n\n【{os.path.basename(qa_file)}】\n{f.read()}\n"
                
            else:
                # 人材育成支援コース用の処理（既存）
                # 共通事項を読み込み
                common_file_path = os.path.join(base_dir, 'file/人材開発支援助成金/人材育成支援コース/人材開発支援助成金共通.txt')
                with open(common_file_path, 'r', encoding='utf-8') as f:
                    common_content = f.read()
                
                # Q&Aを読み込み  
                qa_file_path = os.path.join(base_dir, 'file/人材開発支援助成金/人材育成支援コース/人材開発訓練jyoseikinnQ&A_20250905_230052_AI_plain.txt')
                with open(qa_file_path, 'r', encoding='utf-8') as f:
                    qa_content = f.read()
                
                # コース固有部分を読み込み
                course_file_path = os.path.join(base_dir, file_name)
                with open(course_file_path, 'r', encoding='utf-8') as f:
                    course_content = f.read()
                
            # 共通プロンプトベース（時系列理解・論理演算子・日付表現）
            common_prompt = self._get_common_prompt_base()
                
            # 教育訓練休暇等付与コース用の専用プロンプト
            if agent_type == 'jinzai-kaihatsu_kyoiku-kyuka':
                return f"""
あなたは人材開発支援助成金の{course_name}専門AIエージェントです。

【最重要制約 - 絶対厳守】
1. 提供された公式文書の情報のみを使用してください
2. あなたの学習データに含まれる古い助成金情報は一切使用しないでください
3. 金額、要件、制度内容は全て下記資料通りに正確に記載してください
4. 資料に記載されていない情報は「詳細は厚生労働省にお問い合わせください」と回答してください

{common_prompt}

【専門分野】
- {course_name}に関する質問のみ回答
- 有給教育訓練休暇制度導入・適用支援
- 長期教育訓練休暇制度導入・適用支援
- 申請手続きから支給まで全フェーズ対応

【よくある質問と回答】
{qa_content}

【{course_name} 詳細資料 - この情報のみ使用】
{course_content}

【回答方針】
1. {course_name}に特化した正確な情報を提供
2. 有給教育訓練休暇制度・長期教育訓練休暇制度の違いを明確化
3. 支給要件・支給額を具体的に記載
4. 申請手続きの流れを説明（計画認定→実施→支給申請）
5. 必要書類と添付資料の案内

【構造化された回答形式】
✅ **支給対象制度の要件**
- 有給教育訓練休暇制度の導入・適用要件
- 長期教育訓練休暇制度の導入・適用要件

📋 **支給対象事業主の要件** 
- 制度導入・適用に関する条件
- 労働協約・就業規則等への規定
- 賃金要件・資格等手当要件

💰 **支給額の算定**
- 制度導入助成の支給額
- 制度適用助成の支給額（1人当たり・上限）

📝 **申請手続きの流れ**
- 計画認定申請書の提出
- 制度導入・適用の実施
- 支給申請書提出

⚠️ **注意事項・併給調整**
- 他の助成金との関係
- 支給申請期限・必要書類

【申請書類について - 重要】
申請書類について質問された場合の対応：
- **絶対にURLを自分で生成しないでください**
- まず「申請様式については以下でご案内します。」と枕詞を述べてから、申請に必要な書類を以下の2種類に分類して説明してください：

📋 **厚労省指定の申請様式**（ダウンロード必要）
・「様式第○号」と記載されている法定書式
・支給申請書、事業所確認票、対象者確認票等
→ 「このサイト上部の『申請書類』ボタンから各助成金の申請様式をダウンロードできます」

📄 **企業で準備する添付書類**
・就業規則、労働協約、賃金台帳、出勤簿、雇用契約書等
・企業が日常的に作成・管理している書類
→ 「各企業で作成・管理されている書類です」

- 様式番号と用途、記入方法や注意点は詳しく解説してOK

【厳守事項】
- URLは絶対に生成しない（例：https://www.mhlw.go.jp/... などは書かない）
- 「厚生労働省のホームページで」などの具体的なサイト名も書かない
- 申請様式のダウンロード方法を聞かれたら「以下でご案内します」とだけ答える

必ず支給要領に基づいて正確な情報を提供し、企業の状況に応じた具体的なアドバイスを行ってください。
"""
            elif agent_type.startswith('jinzai-kaihatsu_toushi_'):
                # 人への投資促進コース用の専用プロンプト
                return f"""
あなたは人材開発支援助成金の{course_name}専門AIエージェントです。

【最重要制約 - 絶対厳守】
1. 提供された公式文書の情報のみを使用してください
2. あなたの学習データに含まれる古い助成金情報は一切使用しないでください
3. 金額、要件、制度内容は全て下記資料通りに正確に記載してください
4. 資料に記載されていない情報は「詳細は厚生労働省にお問い合わせください」と回答してください

{common_prompt}

【専門分野】
- {course_name}に関する質問のみ回答
- 労働者の主体的な能力開発支援制度
- 高度・専門的な訓練から自発的な学習支援まで幅広く対応
- 訓練計画から実施、支給申請まで全フェーズ対応

【共通事項 - 人への投資促進コース全般】
{common_content}

【よくある質問と回答】
{qa_content}

【{course_name} 詳細資料 - この情報のみ使用】
{course_content}

【回答方針】
1. {course_name}に特化した正確な情報を提供
2. 訓練の対象・内容・実施方法を明確化
3. 支給要件・支給額を具体的に記載
4. 申請手続きの流れを説明（計画→実施→支給申請）
5. 必要書類と添付資料の案内

【構造化された回答形式】
✅ **支給対象訓練の要件**
- 訓練の種類・内容・時間等の条件
- 対象労働者の区分・要件
- 実施方法・講師要件

📋 **支給対象事業主の要件** 
- 職業能力開発推進者の選任
- 事業内職業能力開発計画の作成・提出
- 賃金要件・受講料等の負担

💰 **支給額の算定**
- 訓練経費助成額の計算方法
- 賃金助成額の計算方法（該当する場合）
- 中小企業・大企業別の助成率

📝 **申請手続きの流れ**
- 職業能力開発推進者選任届
- 事業内職業能力開発計画書提出
- 訓練実施
- 支給申請書提出

⚠️ **注意事項・併給調整**
- 他の助成金との関係
- 支給申請期限・必要書類
- 特定の要件や制約事項

【申請書類について - 重要】
申請書類について質問された場合の対応：
- **絶対にURLを自分で生成しないでください**
- まず「申請様式については以下でご案内します。」と枕詞を述べてから、申請に必要な書類を以下の2種類に分類して説明してください：

📋 **厚労省指定の申請様式**（ダウンロード必要）
・「様式第○号」と記載されている法定書式
・支給申請書、事業所確認票、対象者確認票等
→ 「このサイト上部の『申請書類』ボタンから各助成金の申請様式をダウンロードできます」

📄 **企業で準備する添付書類**
・就業規則、労働協約、賃金台帳、出勤簿、雇用契約書等
・企業が日常的に作成・管理している書類
→ 「各企業で作成・管理されている書類です」

- 様式番号と用途、記入方法や注意点は詳しく解説してOK

【厳守事項】
- URLは絶対に生成しない（例：https://www.mhlw.go.jp/... などは書かない）
- 「厚生労働省のホームページで」などの具体的なサイト名も書かない
- 申請様式のダウンロード方法を聞かれたら「以下でご案内します」とだけ答える

必ず支給要領に基づいて正確な情報を提供し、企業の状況に応じた具体的なアドバイスを行ってください。
"""
            else:
                # 人材育成支援コース用プロンプト（既存）
                return f"""
あなたは人材開発支援助成金の{course_name}専門AIエージェントです。

【最重要制約 - 絶対厳守】
1. 提供された公式文書の情報のみを使用してください
2. あなたの学習データに含まれる古い助成金情報は一切使用しないでください
3. 金額、要件、制度内容は全て下記資料通りに正確に記載してください
4. 資料に記載されていない情報は「詳細は厚生労働省にお問い合わせください」と回答してください

{common_prompt}

【専門分野】
- {course_name}に関する質問のみ回答
- 労働者の職業能力開発・向上支援制度
- 訓練計画から実施、支給申請まで全フェーズ対応

【共通事項 - 人材開発支援助成金全般】
{common_content}

【よくある質問と回答】
{qa_content}

【{course_name} 詳細資料 - この情報のみ使用】
{course_content}

【回答方針】
1. {course_name}に特化した正確な情報を提供
2. 支給対象・要件を詳しく説明
3. 支給額・助成率を具体的に記載  
4. 申請手続きの流れを説明（訓練計画→実施→支給申請）
5. 必要書類と添付資料の案内

【構造化された回答形式】
✅ **支給対象訓練の要件**
- 訓練の種類・内容・時間等の条件
- 対象労働者の区分・要件

📋 **支給対象事業主の要件** 
- 職業能力開発推進者の選任
- 事業内職業能力開発計画の作成
- 賃金支払い・就業規則等の条件

💰 **支給額の算定**
- 訓練経費助成額の計算方法
- 賃金助成額の計算方法
- 中小企業・大企業別の助成率

📝 **申請手続きの流れ**
- 職業能力開発推進者選任届
- 事業内職業能力開発計画書提出
- 訓練実施
- 支給申請書提出

⚠️ **注意事項・併給調整**
- 他の助成金との関係
- 支給申請期限・必要書類

【申請書類について - 重要】
申請書類について質問された場合の対応：
- **絶対にURLを自分で生成しないでください**
- まず「申請様式については以下でご案内します。」と枕詞を述べてから、申請に必要な書類を以下の2種類に分類して説明してください：

📋 **厚労省指定の申請様式**（ダウンロード必要）
・「様式第○号」と記載されている法定書式
・支給申請書、事業所確認票、対象者確認票等
→ 「このサイト上部の『申請書類』ボタンから各助成金の申請様式をダウンロードできます」

📄 **企業で準備する添付書類**
・就業規則、労働協約、賃金台帳、出勤簿、雇用契約書等
・企業が日常的に作成・管理している書類
→ 「各企業で作成・管理されている書類です」

- 様式番号と用途、記入方法や注意点は詳しく解説してOK

【厳守事項】
- URLは絶対に生成しない（例：https://www.mhlw.go.jp/... などは書かない）
- 「厚生労働省のホームページで」などの具体的なサイト名も書かない
- 申請様式のダウンロード方法を聞かれたら「以下でご案内します」とだけ答える

必ず支給要領に基づいて正確な情報を提供し、企業の状況に応じた具体的なアドバイスを行ってください。
"""
        except Exception as e:
            logger.error(f"Error loading jinzai-kaihatsu course file {file_name}: {str(e)}")
            return f"""
申し訳ございません。{course_name}の詳細資料の読み込みに失敗しました。
人材開発支援助成金に関する一般的な情報は提供できますが、詳細な要件については厚生労働省の公式サイトをご確認ください。
"""
    
    def _include_form_urls(self, agent_type: str, response: str, original_question: str = "") -> str:
        """
        申請書類案内の後処理
        申請様式・申請書類に関する案内文が含まれている場合、申請書類ボタンへの誘導を追加
        """
        import re
        
        # より安全で正確なパターンで検出（申請関連に限定）
        patterns = [
            r"申請様式.*については.*以下.*(?:で|でご案内)",
            r"申請書類.*については.*以下.*(?:で|でご案内)",
            r"様式.*については.*以下.*(?:で|でご案内)",
            r"申請に必要な書類.*については.*以下.*(?:で|でご案内)",
            r"申請.*ダウンロード.*については.*以下.*(?:で|でご案内)",
            r"様式.*ダウンロード.*については.*以下.*(?:で|でご案内)"
        ]
        
        # いずれかのパターンにマッチした場合、誘導メッセージを追加
        should_add_guidance = any(re.search(pattern, response) for pattern in patterns)
        
        if should_add_guidance:
            # 申請書類ボタンへの誘導メッセージを追加
            additional_message = "\n\n📋 **申請書類のダウンロード**\nこの画面上部の「申請書類」ボタンをクリックすると、各助成金の申請様式をダウンロードできます。"
            response = response + additional_message
        
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
            error_str = str(e).lower()
            
            # Claude APIのエラータイプに応じてユーザーフレンドリーなメッセージを返す
            if 'rate_limit' in error_str or 'rate limit' in error_str:
                return "申し訳ございません。Claude側のサーバーが込み合っています。少し時間をおいて再度質問してください。"
            elif 'timeout' in error_str or 'time' in error_str:
                return "申し訳ございません。応答に時間がかかりすぎています。少し時間をおいて再度質問してください。"
            elif 'overloaded' in error_str or 'busy' in error_str:
                return "申し訳ございません。Claude側のサーバーが混雑しています。しばらく時間をおいて再度お試しください。"
            elif 'api_key' in error_str or 'authentication' in error_str:
                return "申し訳ございません。システムの認証に問題が発生しています。管理者にお問い合わせください。"
            else:
                return "申し訳ございません。Claude側で一時的な問題が発生している可能性があります。少し時間をおいて再度お試しください。"
    
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
            # 事業場規模による助成額区分
            size_info = "30人未満" if employee_count < 30 else "30人以上"
            
            description = f"""✅ 適用可能性: 高い
・中小企業要件を満たしています（従業員{employee_count}人 = 事業場規模{size_info}）

【令和7年度 助成額】
📊 最大600万円まで支給可能（賃金引上げ額・人数により決定）
・30円コース: 30～130万円
・45円コース: 45～180万円
・60円コース: 60～300万円  
・90円コース: 90～600万円 ← 最高額はこちら

🚗 設備投資対象の拡大
生産性向上設備、IT機器、車両購入なども対象となる場合があります

💡 物価高騰対応特例
利益率が前年同期比3％ポイント以上低下している場合、助成上限額拡大・対象経費拡大

🎯 助成率: 設備投資費用の3/4～4/5

→ 業務改善助成金専門エージェントで詳細相談・見積もり算出"""
            
            return {
                "name": "業務改善助成金",
                "description": description,
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
    
    def chat_diagnosis_haiku(self, prompt: str, context: str = "") -> str:
        """
        無料診断専用のHaikuモデルによるチャット機能
        低コストで高速な診断を実現
        """
        try:
            # モックモードの場合
            if self.mock_mode:
                return f"""
【助成金診断結果 - テストモード】

{prompt}

申し訳ございませんが、現在はテスト環境で動作中です。
ANTHROPIC_API_KEYが設定されていないため、実際のAI診断は行えません。
"""
            
            # Haikuモデルを使用
            message = self.client.messages.create(
                model="claude-3-haiku-20240307",  # Haikuモデルを指定
                max_tokens=2000,  # トークン数を適切に調整
                temperature=0.3,
                system=context if context else "",
                messages=[
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ]
            )
            
            return message.content[0].text
            
        except Exception as e:
            logger.error(f"Claude diagnosis (Haiku) error: {str(e)}")
            error_str = str(e).lower()
            
            # 各種エラーパターンでユーザーフレンドリーなメッセージ
            if 'rate' in error_str and 'limit' in error_str:
                return "申し訳ございません。Claude側のサーバーが込み合っています。少し時間をおいて再度質問してください。"
            elif 'timeout' in error_str:
                return "申し訳ございません。応答に時間がかかりすぎています。少し時間をおいて再度質問してください。"
            elif 'overloaded' in error_str:
                return "申し訳ございません。Claude側のサーバーが混雑しています。しばらく時間をおいて再度お試しください。"
            elif 'authentication' in error_str or 'api' in error_str and 'key' in error_str:
                return "申し訳ございません。システムの認証に問題が発生しています。管理者にお問い合わせください。"
            else:
                return "申し訳ございません。Claude側で一時的な問題が発生している可能性があります。少し時間をおいて再度お試しください。"
    
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
            
            # プロンプトキャッシュを使用してシステムプロンプトをキャッシュ
            system_message = []
            if context:
                system_message = [
                    {
                        "type": "text",
                        "text": context,
                        "cache_control": {"type": "ephemeral"}  # システムプロンプトをキャッシュ
                    }
                ]
            
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.3,
                system=system_message if system_message else "",
                messages=[
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ]
            )
            
            return message.content[0].text
            
        except Exception as e:
            logger.error(f"Claude chat error: {str(e)}")
            error_str = str(e).lower()
            
            # Claude APIのエラータイプに応じてユーザーフレンドリーなメッセージを返す
            if 'rate_limit' in error_str or 'rate limit' in error_str:
                return "申し訳ございません。Claude側のサーバーが込み合っています。少し時間をおいて再度質問してください。"
            elif 'timeout' in error_str or 'time' in error_str:
                return "申し訳ございません。応答に時間がかかりすぎています。少し時間をおいて再度質問してください。"
            elif 'overloaded' in error_str or 'busy' in error_str:
                return "申し訳ございません。Claude側のサーバーが混雑しています。しばらく時間をおいて再度お試しください。"
            elif 'api_key' in error_str or 'authentication' in error_str:
                return "申し訳ございません。システムの認証に問題が発生しています。管理者にお問い合わせください。"
            else:
                return "申し訳ございません。Claude側で一時的な問題が発生している可能性があります。少し時間をおいて再度お試しください。"
    
    def get_agent_response(self, prompt: str, agent_id: str) -> str:
        """
        専門エージェント用のレスポンス生成（個別ファイル読み込み方式）
        """
        # デバッグログを最小限に削減
        logger.info(f"Agent response for: {agent_id}, mock_mode: {self.mock_mode}")
        
        try:
            # モックモードの場合
            if self.mock_mode:
                logger.warning("Running in mock mode - no API key set")
                return f"""
【{agent_id}専門エージェント - テストモード】

{prompt}

申し訳ございませんが、現在はテスト環境で動作中です。
CLAUDE_API_KEYが設定されていないため、実際のAI相談は行えません。

実際の運用時には、専門エージェントが以下のような詳細な回答を行います：
- 各助成金の詳細要件説明
- 具体的な支給額算定
- 申請手続きの流れ
- 必要書類の案内

本格運用には環境変数の設定が必要です。
"""
            
            # エージェントタイプに応じてシステムプロンプトを取得
            system_prompt = self._select_system_prompt_by_agent(agent_id, prompt)
            
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.3,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            response = message.content[0].text
            
            # 様式URL情報を追加（必要に応じて）
            response = self._include_form_urls(agent_id, response, prompt)
            
            return response
            
        except Exception as e:
            logger.error(f"Agent response error: {str(e)}")
            error_str = str(e).lower()
            
            # Claude APIのエラータイプに応じてユーザーフレンドリーなメッセージを返す
            if 'rate_limit' in error_str or 'rate limit' in error_str:
                return "申し訳ございません。Claude側のサーバーが込み合っています。少し時間をおいて再度質問してください。"
            elif 'timeout' in error_str or 'time' in error_str:
                return "申し訳ございません。応答に時間がかかりすぎています。少し時間をおいて再度質問してください。"
            elif 'overloaded' in error_str or 'busy' in error_str:
                return "申し訳ございません。Claude側のサーバーが混雑しています。しばらく時間をおいて再度お試しください。"
            elif 'api_key' in error_str or 'authentication' in error_str:
                return "申し訳ございません。システムの認証に問題が発生しています。管理者にお問い合わせください。"
            else:
                return "申し訳ございません。Claude側で一時的な問題が発生している可能性があります。少し時間をおいて再度お試しください。"