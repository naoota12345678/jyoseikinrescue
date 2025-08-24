from flask import Flask, render_template, request, jsonify, session, send_from_directory
import os
import sys
from dotenv import load_dotenv
# srcディレクトリをPythonパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from auth_middleware import require_auth, check_usage_limit, get_current_user, get_usage_stats, AuthService
    from stripe_service import StripeService
    from models.subscription import SubscriptionService
    from firebase_config import firebase_service
    AUTH_ENABLED = True
    logger.info("Authentication modules loaded successfully")
except Exception as e:
    logger.warning(f"Authentication modules not available: {str(e)}")
    AUTH_ENABLED = False
    # ダミーのデコレータを提供
    def require_auth(f):
        return f
    def check_usage_limit(f):
        return f

app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Static files route
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('../static', filename)

# サービスの遅延初期化
claude_service = None
auth_service = None
stripe_service = None
subscription_service = None

def get_claude_service():
    global claude_service
    if claude_service is None:
        from claude_service import ClaudeService
        claude_service = ClaudeService()
    return claude_service

def get_auth_service():
    global auth_service
    if auth_service is None:
        auth_service = AuthService()
    return auth_service

def get_stripe_service():
    global stripe_service
    if stripe_service is None:
        stripe_service = StripeService()
    return stripe_service

def get_subscription_service():
    global subscription_service
    if subscription_service is None:
        subscription_service = SubscriptionService(firebase_service)
    return subscription_service

@app.route('/')
def index():
    # 認証機能が有効な場合は認証版ページを表示
    if AUTH_ENABLED:
        return render_template('auth_index.html')
    else:
        return render_template('index.html')

@app.route('/diagnosis')
def diagnosis():
    """助成金診断ページ（認証不要）"""
    return render_template('joseikin_diagnosis.html')

@app.route('/dashboard')
def dashboard():
    """統合ダッシュボード（エージェント選択画面）"""
    # 認証はクライアント側のFirebaseで行う
    return render_template('dashboard.html')

@app.route('/api/chat', methods=['POST'])
@require_auth
@check_usage_limit
def chat():
    try:
        data = request.json
        company_info = data.get('company_info', {})
        question = data.get('question', '')
        
        if not question:
            return jsonify({'error': '質問を入力してください'}), 400
        
        current_user = get_current_user()
        usage_stats = get_usage_stats()
        
        # セッションに会社情報を保存
        session['company_info'] = company_info
        
        # エージェントタイプを取得（フロントエンドから送信される）
        agent_type = data.get('agent_type', 'gyoumukaizen')  # デフォルトは業務改善助成金
        
        # Claude APIに質問を送信（エージェントタイプも渡す）
        response = get_claude_service().get_grant_consultation(company_info, question, agent_type)
        
        # 質問使用回数を増加
        result = get_subscription_service().use_question(current_user['id'])
        
        if not result['success']:
            logger.error(f"Failed to record question usage: {result.get('error')}")
        
        # 最新の使用状況を取得
        updated_usage = get_subscription_service().get_usage_stats(current_user['id'])
        
        return jsonify({
            'response': response,
            'status': 'success',
            'usage_stats': updated_usage
        })
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({'error': 'サーバーエラーが発生しました'}), 500

@app.route('/api/grant-check', methods=['POST'])
def grant_check():
    try:
        data = request.json
        company_info = data.get('company_info', {})
        
        if not company_info:
            return jsonify({'error': '会社情報を入力してください'}), 400
        
        # 利用可能な助成金をチェック
        available_grants = get_claude_service().check_available_grants(company_info)
        
        return jsonify({
            'grants': available_grants,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Error in grant check endpoint: {str(e)}")
        return jsonify({'error': 'サーバーエラーが発生しました'}), 500

def _load_joseikin_knowledge():
    """2025年度助成金データを読み込み"""
    try:
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(base_dir, '2025_jyoseikin_data.txt')
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            logger.info(f"Successfully loaded 2025 subsidy data: {len(content)} chars")
            return content
    except Exception as e:
        logger.error(f"Error loading 2025 subsidy data: {str(e)}")
        return "助成金データの読み込みに失敗しました。"

# 利用制限管理（メモリベース、本格運用時はRedis推奨）
diagnosis_rate_limit = {}

def _check_diagnosis_rate_limit(client_ip):
    """診断の利用制限チェック（1日あたり5回まで）"""
    import time
    current_time = time.time()
    
    # 1日以上前の記録を削除
    if client_ip in diagnosis_rate_limit:
        diagnosis_rate_limit[client_ip] = [
            timestamp for timestamp in diagnosis_rate_limit[client_ip] 
            if current_time - timestamp < 86400  # 1日 = 86400秒
        ]
    
    # 現在の利用回数をチェック
    usage_count = len(diagnosis_rate_limit.get(client_ip, []))
    
    if usage_count >= 5:  # 1日あたり5回制限
        return False
    
    # 利用記録を追加
    if client_ip not in diagnosis_rate_limit:
        diagnosis_rate_limit[client_ip] = []
    diagnosis_rate_limit[client_ip].append(current_time)
    
    return True

def _format_diagnosis_response(text):
    """診断結果の改行を強制的に整理"""
    import re
    
    # 助成金名の前に改行を強制挿入
    text = re.sub(r'(\d+\.)\s*([^-\n]+助成金)', r'\n\n\1 \2\n', text)
    
    # 項目（-で始まる行）の前に適切な改行
    text = re.sub(r'([^\n])\s*-\s*(支給額|適用要件|申請準備|専門エージェント)', r'\1\n- \2', text)
    
    # カテゴリ見出し（【】で囲まれた部分）の前後に改行
    text = re.sub(r'([^\n])【([^】]+)】', r'\1\n\n【\2】\n', text)
    
    # 連続する改行を整理（3個以上の改行を2個に）
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # 先頭と末尾の余分な改行を削除
    text = text.strip()
    
    return text

@app.route('/api/joseikin-diagnosis', methods=['POST'])
def joseikin_diagnosis():
    try:
        # 利用制限チェック
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', ''))
        if not _check_diagnosis_rate_limit(client_ip):
            return jsonify({
                'error': '1日の利用制限（5回）に達しました。明日再度お試しください。',
                'message': 'より詳しい相談は専門AIエージェントをご利用ください。'
            }), 429
        
        data = request.json
        diagnosis_data = data.get('diagnosis_data', {})
        
        # 2025年度助成金データを読み込み
        joseikin_knowledge = _load_joseikin_knowledge()
        
        # Claude AIを使用して包括的な助成金診断
        prompt = f"""
あなたは令和7年度雇用・労働分野の助成金専門のアドバイザーです。

【絶対に守るべき制約】
1. 補助金については一切回答・言及・提案してはいけません
2. IT導入補助金、ものづくり補助金、事業再構築補助金、小規模事業者持続化補助金等の経済産業省・中小企業庁管轄の制度は完全に無視してください
3. ユーザーから補助金について質問されても「このサービスは助成金専門のため、補助金については回答できません」と断ってください
4. 厚生労働省管轄の助成金のみに特化して回答してください

【2025年度助成金データベース】
{joseikin_knowledge}

以下の企業情報を基に、上記の正確なデータベース情報を使用して、該当する可能性のある助成金をすべて判定してください。

【対象となる制度】
■ 厚生労働省管轄の助成金のみ
- 雇用・労働分野の助成金
- 業務改善助成金、キャリアアップ助成金、人材開発支援助成金等

【絶対に回答してはいけない制度】
■ 経済産業省・中小企業庁管轄の補助金
- IT導入補助金、ものづくり補助金、事業再構築補助金
- 小規模事業者持続化補助金、その他すべての補助金制度

【重要】すべての助成金について以下を徹底してください：
- 業務改善助成金：賃金引上げ額の情報がない場合でも、全てのコースオプション（30円〜130円以上の6コース）を必ず記載し、それぞれの上限額（100万円〜230万円）を明記
- キャリアアップ助成金：全てのコース（正社員化、賃金規定等改定等）とそれぞれの支給額を記載
- 人材開発支援助成金：全てのコース（人材育成支援、教育訓練休暇等）とそれぞれの支給額・助成率を記載
- 65歳超雇用推進助成金：50歳以上、60歳以上、65歳以上の労働者がいる場合は必ず該当として判定し、継続雇用制度導入時の支給額を記載
- その他すべての助成金：複数のコースや類型がある場合は、すべてを網羅的に記載すること

【包括的判定ルール - 全29カテゴリー対応】

■ 年齢関連
- 50歳以上 → 特定求職者雇用開発助成金（生涯現役コース70万円）、65歳超雇用推進助成金の検討対象
- 60-64歳 → 65歳超雇用推進助成金（15-160万円）、エイジフレンドリー補助金（上限100万円）を必ず記載
- 65歳以上 → 65歳超雇用推進助成金（20-230万円）を最優先、エイジフレンドリー補助金を必ず記載
- 継続雇用制度 → 65歳超雇用推進助成金を最優先表示

■ 雇用形態関連
- 有期契約労働者 → キャリアアップ助成金正社員化コース（57万円/人）を必ず記載
- 非正規雇用 → キャリアアップ助成金全コースを網羅的に記載
- パート・アルバイト → トライアル雇用助成金（月4-5万円×3ヶ月）も検討

■ 特別な労働者
- 障害者雇用 → 特定求職者雇用開発助成金（120-240万円）＋障害者関係8助成金すべて記載
- 母子家庭等 → 特定求職者雇用開発助成金（60万円）、トライアル雇用（月5万円）
- 女性労働者 → 両立支援等助成金全コース必ず記載
- 外国人労働者 → 人材確保等支援助成金を記載

■ 経営状況
- 売上減少 → 雇用調整助成金（日額8,370-15,000円）を最優先
- 事業再構築 → 事業再構築補助金（100万-7,000万円）を必ず記載
- 人手不足 → 人材確保等支援助成金、地域雇用開発助成金を記載

■ 設備投資・改善
- 設備投資全般 → 業務改善助成金全6コース（100-230万円）必ず記載
- IT・デジタル化 → IT導入補助金（5-450万円）、ものづくり補助金を記載
- 受動喫煙対策 → 受動喫煙防止対策助成金（上限100万円）
- 安全設備 → 高度安全機械等導入支援補助金、エイジフレンドリー補助金

■ 人材育成
- 研修・教育訓練 → 人材開発支援助成金（経費45-75%助成、賃金760円/時）必ず記載
- 資格取得支援 → 人材開発支援助成金を最優先
- 教育訓練休暇 → 教育訓練休暇等付与コース（30万円）

■ 働き方改革
- 時間外労働削減 → 働き方改革推進支援助成金（50-200万円）必ず記載
- 有給取得促進 → 労働時間短縮・年休促進支援コース
- 育児・介護支援 → 両立支援等助成金（28.5-67.5万円）

■ 地域・業種特性
- 過疎地域 → 地域雇用開発助成金（50-800万円）必ず記載
- 製造業 → ものづくり補助金、高度安全機械等導入支援補助金
- 飲食・宿泊業 → 受動喫煙防止対策助成金を優先表示
- 建設業 → 建設労働者確保育成助成金を記載

【重要】該当する可能性がある助成金はすべて記載し、優先順位を明確にすること

【企業情報】
業種: {diagnosis_data.get('industry', 'なし')}
従業員数: {diagnosis_data.get('totalEmployees', 'なし')}
雇用保険被保険者数: {diagnosis_data.get('insuredEmployees', 'なし')}
有期契約労働者数: {diagnosis_data.get('temporaryEmployees', 'なし')}
短時間労働者数: {diagnosis_data.get('partTimeEmployees', 'なし')}
年齢構成: {diagnosis_data.get('ageGroups', 'なし')}
特別配慮労働者: {diagnosis_data.get('specialNeeds', 'なし')}
経営状況: {diagnosis_data.get('businessSituation', 'なし')}
事業場内最低賃金: {diagnosis_data.get('minWage', 'なし')}円/時
賃金・処遇改善: {diagnosis_data.get('wageImprovement', 'なし')}
投資・改善予定: {diagnosis_data.get('investments', 'なし')}
両立支援: {diagnosis_data.get('workLifeBalance', 'なし')}

以下の厚生労働省管轄の助成金カテゴリーから該当するものを判定し、具体的な支給額と適用条件を含めて回答してください：

1. 雇用調整助成金 2. 産業雇用安定助成金 3. 早期再就職支援等助成金 4. 特定求職者雇用開発助成金
5. トライアル雇用助成金 6. 地域雇用開発助成金 7. 人材確保等支援助成金 8. 通年雇用助成金
9. 65歳超雇用推進助成金 10. キャリアアップ助成金 11. 両立支援等助成金 12. 人材開発支援助成金
13. 障害者作業施設設置等助成金 14. 障害者福祉施設設置等助成金 15. 障害者介助等助成金
16. 職場適応援助者助成金 17. 重度障害者等通勤対策助成金 18. 重度障害者多数雇用事業所施設設置等助成金
19. 障害者雇用相談援助助成金 20. 障害者能力開発助成金 21. 職場適応訓練費 22. 業務改善助成金
23. 働き方改革推進支援助成金 24. 受動喫煙防止対策助成金 25. 団体経由産業保健活動推進助成金
26. 高度安全機械等導入支援補助金 27. エイジフレンドリー補助金 28. 個人ばく露測定定着促進補助金
29. 中小企業退職金共済制度に係る新規加入等掛金助成

※ IT導入補助金、ものづくり補助金、事業再構築補助金等の経済産業省・中小企業庁管轄の補助金は対象外です

該当する助成金について、適用可能性の高い順に最大10件まで、以下の形式で見やすく整理して回答してください：

助成金診断結果

【高適用可能性】

1. [助成金名]
- 支給額: [具体的な金額・上限額]
- 適用要件: [詳細な条件]
- 申請準備: [必要な準備事項]

2. [助成金名]
- 支給額: [具体的な金額・上限額]
- 適用要件: [詳細な条件]
- 申請準備: [必要な準備事項]

【中程度適用可能性】

3. [助成金名]
- 支給額: [具体的な金額・上限額]
- 適用要件: [詳細な条件]

【検討価値あり】

[助成金名]
[理由を含めて説明]

総合アドバイス:
[全体的な申請戦略や優先順位のアドバイス]

---
【重要】
このサービスは厚生労働省管轄の助成金専門です。IT導入補助金・ものづくり補助金・事業再構築補助金等の補助金については一切回答しません。

【ご利用について】
この診断は情報提供を目的としています。正式な申請手続きについては社会保険労務士等の有資格者にご相談ください。

【次のステップ】
診断結果を保存して、詳細な相談に進むことをお勧めします。

この形式で、助成金ごとに明確に区切って、読みやすく整理して回答してください。

【回答形式の重要事項】
- 各助成金の間には必ず空行を入れること
- 項目ごとに改行して整理すること  
- 長い文章は適切に改行すること
- 読みやすさを最優先にすること

必ず以下の例のような形式で回答してください：

1. 業務改善助成金

- 支給額: 30円コース（上限100万円）、60円コース（上限150万円）等
- 適用要件: 最低賃金30円以上引上げ、設備投資等
- 申請準備: 賃金引上げ計画書、設備投資見積書

2. キャリアアップ助成金

- 支給額: 正社員化57万円/人
- 適用要件: 有期雇用から正規雇用への転換

このように各助成金を完全に分離して記載してください。
"""
        
        # Claude AIに問い合わせ
        raw_response = get_claude_service().chat(prompt, "")
        
        # 強制的に改行を整理
        response = _format_diagnosis_response(raw_response)
        
        # レスポンスを構造化
        applicable_grants = [{
            'name': 'AI診断結果',
            'description': response,
            'amount': '上記診断結果をご確認ください',
            'eligibility': '詳細な適用要件は診断結果に記載',
            'specialist': '該当する専門エージェント',
            'probability': 'AI判定済み'
        }]
        
        return jsonify({
            'status': 'success',
            'applicable_grants': applicable_grants
        })
                
    except Exception as e:
        logger.error(f"Error in joseikin diagnosis: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

# ===== 認証・ユーザー管理関連のAPIエンドポイント =====

@app.route('/api/auth/user', methods=['GET'])
@require_auth
def get_user():
    """現在のユーザー情報と使用状況を取得"""
    try:
        current_user = get_current_user()
        usage_stats = get_usage_stats()
        
        return jsonify({
            'user': current_user,
            'usage_stats': usage_stats,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Error getting user info: {str(e)}")
        return jsonify({'error': 'ユーザー情報の取得に失敗しました'}), 500

@app.route('/api/auth/register', methods=['POST'])
def register():
    """新規ユーザー登録（Firebase認証後）"""
    try:
        data = request.json
        uid = data.get('uid')
        email = data.get('email')
        display_name = data.get('display_name', '')
        
        if not uid or not email:
            return jsonify({'error': 'UIDとメールアドレスが必要です'}), 400
        
        logger.info(f"Registering new user: {email} (uid: {uid})")
        
        # AUTH_ENABLEDがFalseの場合はダミーのレスポンスを返す
        if not AUTH_ENABLED:
            logger.warning("Auth is disabled, returning dummy response")
            return jsonify({
                'user': {'uid': uid, 'email': email},
                'status': 'success'
            })
        
        try:
            # Stripe顧客を作成
            stripe_customer_id = get_stripe_service().create_customer(
                email=email,
                name=display_name,
                metadata={'firebase_uid': uid}
            )
            
            # ユーザーを作成
            result = get_auth_service().create_user_with_stripe({
                'uid': uid,
                'email': email,
                'display_name': display_name
            }, stripe_customer_id)
            
            if result['success']:
                logger.info(f"User registered successfully: {email}")
                return jsonify({
                    'user': result['user'],
                    'status': 'success'
                })
            else:
                logger.error(f"User registration failed: {result['error']}")
                return jsonify({
                    'error': result['error']
                }), 500
                
        except Exception as inner_e:
            logger.error(f"Error creating user with Stripe: {str(inner_e)}")
            # Stripeエラーの場合でも、ユーザー作成は試みる
            try:
                from models.user import User
                user_service = User(firebase_service)
                user_id = user_service.create_user({
                    'uid': uid,
                    'email': email,
                    'display_name': display_name
                })
                user = user_service.get_user_by_id(user_id)
                logger.info(f"User created without Stripe: {email}")
                return jsonify({
                    'user': user,
                    'status': 'success'
                })
            except Exception as fallback_e:
                logger.error(f"Fallback user creation failed: {str(fallback_e)}")
                return jsonify({'error': str(fallback_e)}), 500
            
    except Exception as e:
        logger.error(f"Error in user registration: {str(e)}")
        return jsonify({'error': 'ユーザー登録に失敗しました'}), 500

# ===== Stripe決済関連のAPIエンドポイント =====

@app.route('/api/payment/basic-plan', methods=['POST'])
@require_auth
def create_basic_plan_checkout():
    """基本プラン（月額3,000円）の決済セッションを作成"""
    try:
        current_user = get_current_user()
        
        # Stripe顧客IDがない場合は自動作成
        stripe_customer_id = current_user.get('stripe_customer_id')
        if not stripe_customer_id:
            try:
                stripe_customer_id = get_stripe_service().create_customer(
                    email=current_user['email'],
                    name=current_user.get('display_name', ''),
                    metadata={'firebase_uid': current_user['uid']}
                )
                # ユーザーデータベースにStripe顧客IDを保存
                get_auth_service().update_stripe_customer_id(current_user['id'], stripe_customer_id)
                logger.info(f"Created Stripe customer: {stripe_customer_id}")
            except Exception as e:
                logger.error(f"Failed to create Stripe customer: {str(e)}")
                return jsonify({'error': f'Stripe顧客作成エラー: {str(e)}'}), 500
        
        data = request.json
        success_url = data.get('success_url', 'https://your-domain.com/success')
        cancel_url = data.get('cancel_url', 'https://your-domain.com/cancel')
        
        checkout_session = get_stripe_service().create_basic_plan_checkout(
            customer_id=stripe_customer_id,
            user_id=current_user['id'],
            success_url=success_url,
            cancel_url=cancel_url
        )
        
        return jsonify({
            'checkout_url': checkout_session['url'],
            'session_id': checkout_session['id'],
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Error creating basic plan checkout: {str(e)}")
        return jsonify({'error': '決済セッションの作成に失敗しました'}), 500

@app.route('/api/payment/additional-pack', methods=['POST'])
@require_auth
def create_additional_pack_checkout():
    """追加パック（2,000円）の決済セッションを作成"""
    try:
        current_user = get_current_user()
        
        # Stripe顧客IDがない場合は自動作成
        stripe_customer_id = current_user.get('stripe_customer_id')
        if not stripe_customer_id:
            try:
                stripe_customer_id = get_stripe_service().create_customer(
                    email=current_user['email'],
                    name=current_user.get('display_name', ''),
                    metadata={'firebase_uid': current_user['uid']}
                )
                # ユーザーデータベースにStripe顧客IDを保存
                get_auth_service().update_stripe_customer_id(current_user['id'], stripe_customer_id)
                logger.info(f"Created Stripe customer: {stripe_customer_id}")
            except Exception as e:
                logger.error(f"Failed to create Stripe customer: {str(e)}")
                return jsonify({'error': f'Stripe顧客作成エラー: {str(e)}'}), 500
        
        data = request.json
        success_url = data.get('success_url', 'https://your-domain.com/success')
        cancel_url = data.get('cancel_url', 'https://your-domain.com/cancel')
        
        checkout_session = get_stripe_service().create_additional_pack_checkout(
            customer_id=stripe_customer_id,
            user_id=current_user['id'],
            success_url=success_url,
            cancel_url=cancel_url
        )
        
        return jsonify({
            'checkout_url': checkout_session['url'],
            'session_id': checkout_session['id'],
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Error creating additional pack checkout: {str(e)}")
        return jsonify({'error': '決済セッションの作成に失敗しました'}), 500

@app.route('/api/stripe/webhook', methods=['POST'])
def stripe_webhook():
    """Stripe webhookを処理"""
    try:
        payload = request.get_data(as_text=True)
        signature = request.headers.get('Stripe-Signature')
        
        if not get_stripe_service().verify_webhook_signature(payload, signature):
            return jsonify({'error': 'Invalid signature'}), 400
        
        import json
        event = json.loads(payload)
        
        # webhookイベントを処理
        result = get_stripe_service().handle_webhook_event(event)
        
        # 決済完了やサブスクリプション変更に応じてデータベースを更新
        if result['status'] == 'success':
            if result['action'] == 'checkout_completed':
                user_id = result.get('user_id')
                plan_type = result.get('plan_type')
                
                if plan_type == 'basic':
                    # 基本プランにアップグレード
                    session_id = result.get('session_id')
                    get_subscription_service().upgrade_to_basic_plan(user_id, session_id)
                elif plan_type == 'additional_pack':
                    # 追加パックを追加
                    payment_id = result.get('session_id')
                    get_subscription_service().add_additional_pack(user_id, payment_id)
        
        return jsonify({'received': True})
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({'error': 'Webhook処理エラー'}), 500

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)