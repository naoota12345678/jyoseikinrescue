from flask import Flask, render_template, request, jsonify, session, send_from_directory, redirect
from flask_cors import CORS
import os
import sys
import time
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
    logger.error(f"Authentication modules failed to load: {str(e)}")
    logger.error(f"Error type: {type(e).__name__}")
    import traceback
    logger.error(f"Full traceback: {traceback.format_exc()}")
    AUTH_ENABLED = False
    # ダミーのデコレータを提供
    def require_auth(f):
        return f
    def check_usage_limit(f):
        return f
    def get_current_user():
        return {'user_id': 'guest', 'id': 'guest', 'email': 'guest@example.com'}
    def get_usage_stats():
        return {'current_usage': 0, 'limit': 1000, 'reset_date': None}

app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# CORS設定
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Static files route
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('../static', filename)

# Google Search Console verification
@app.route('/googlec5d4388883141aa9.html')
def google_verification():
    return send_from_directory('../static', 'googlec5d4388883141aa9.html')

@app.route('/debug/test-auth', methods=['POST'])
def debug_test_auth():
    """認証処理のテスト用エンドポイント"""
    try:
        auth_header = request.headers.get('Authorization')
        
        debug_info = {
            'has_auth_header': bool(auth_header),
            'header_format_correct': auth_header and auth_header.startswith('Bearer ') if auth_header else False,
        }
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            debug_info['token_length'] = len(token)
            debug_info['token_first_10'] = token[:10] + '...'
            
            # Firebase検証をテスト
            try:
                from firebase_config import firebase_service
                decoded = firebase_service.verify_token(token)
                debug_info['firebase_verify_success'] = decoded is not None
                if decoded:
                    debug_info['decoded_uid'] = decoded.get('uid')
            except Exception as e:
                debug_info['firebase_verify_error'] = str(e)
        
        return jsonify(debug_info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug/full-auth-test', methods=['POST'])
@require_auth
def debug_full_auth_test():
    """フル認証処理のテスト"""
    try:
        current_user = get_current_user()
        return jsonify({
            'success': True,
            'user_found': current_user is not None,
            'user_id': current_user.get('user_id') if current_user else None,
            'user_keys': list(current_user.keys()) if current_user else []
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/debug/auth-status')
def debug_auth_status():
    """認証状態のデバッグ情報"""
    import sys
    import os
    
    debug_info = {
        'AUTH_ENABLED': AUTH_ENABLED,
        'python_version': sys.version,
        'environment_vars': {
            'SECRET_KEY': 'SET' if os.getenv('SECRET_KEY') else 'NOT_SET',
            'CLAUDE_API_KEY': 'SET' if os.getenv('CLAUDE_API_KEY') else 'NOT_SET',
            'FIREBASE_PROJECT_ID': 'SET' if os.getenv('FIREBASE_PROJECT_ID') else 'NOT_SET',
            'FIREBASE_PRIVATE_KEY': 'SET' if os.getenv('FIREBASE_PRIVATE_KEY') else 'NOT_SET',
            'FIREBASE_CLIENT_EMAIL': 'SET' if os.getenv('FIREBASE_CLIENT_EMAIL') else 'NOT_SET'
        }
    }
    
    try:
        current_user_info = get_current_user()
        debug_info['current_user'] = current_user_info
    except Exception as e:
        debug_info['current_user_error'] = str(e)
    
    # Firebase初期化状態も確認
    try:
        from firebase_config import firebase_service
        debug_info['firebase_initialized'] = hasattr(firebase_service, 'db') and firebase_service.db is not None
    except Exception as e:
        debug_info['firebase_init_error'] = str(e)
    
    return jsonify(debug_info)

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

@app.route('/diagnosis_simple')
def diagnosis_simple():
    """シンプルな助成金診断ページ（自動でフォーム表示）"""
    return render_template('joseikin_diagnosis_simple.html')

@app.route('/dashboard')
def dashboard():
    """統合ダッシュボード（エージェント選択画面）"""
    # 認証はクライアント側のFirebaseで行う

    # 管理者ログイン状態確認
    is_admin = False
    if ADMIN_AUTH_ENABLED:
        is_admin = is_admin_user()

    return render_template('dashboard.html', is_admin=is_admin)

@app.route('/pricing')
def pricing():
    """料金プラン選択ページ"""
    return render_template('pricing.html')

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
        result = get_subscription_service().use_question(current_user.get('user_id') or current_user['id'])
        
        if not result['success']:
            logger.error(f"Failed to record question usage: {result.get('error')}")
        
        # 最新の使用状況を取得
        updated_usage = get_subscription_service().get_usage_stats(current_user.get('user_id') or current_user['id'])
        
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

# 削除済み: _load_joseikin_knowledge() 関数は不正確なハードコードデータを使用していたため削除

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
        
        # データの前処理と解釈
        # 業種を日本語に変換
        industry_map = {
            'construction': '建設業',
            'manufacturing': '製造業',
            'service': 'サービス業',
            'it': 'IT・通信業',
            'retail': '小売業・飲食業',
            'other': 'その他'
        }
        industry = diagnosis_data.get('industry', '')
        industry_ja = industry_map.get(industry, industry) if industry else 'なし'
        
        # 従業員数を解釈
        total_employees = diagnosis_data.get('totalEmployees', 'なし')
        is_small_business = False
        if total_employees != 'なし' and str(total_employees).isdigit():
            emp_count = int(total_employees)
            is_small_business = emp_count <= 100  # 中小企業の判定
        
        # 両立支援の内容を解釈
        work_life_balance = diagnosis_data.get('workLifeBalance', 'なし')
        needs_smoking_prevention = False
        if work_life_balance and isinstance(work_life_balance, (list, str)):
            if isinstance(work_life_balance, str):
                needs_smoking_prevention = 'smoking' in work_life_balance
            else:
                needs_smoking_prevention = 'smoking' in work_life_balance
        
        # 賃金関連の判定
        min_wage = diagnosis_data.get('minWage', 'なし')
        needs_wage_improvement = False
        if min_wage != 'なし' and str(min_wage).isdigit():
            wage = int(min_wage)
            needs_wage_improvement = wage < 1100  # 低賃金の場合
        
        # デバッグログ（本番環境では削除推奨）
        logger.info(f"診断データ解釈結果: 業種={industry_ja}, 従業員数={total_employees}, 中小企業={is_small_business}, 受動喫煙対策={needs_smoking_prevention}, 賃金改善必要={needs_wage_improvement}")
        
        # 正しい診断用データを読み込み
        try:
            with open('2025_jyoseikin_kaniyoryo2_20250831_185114_AI_plain.txt', 'r', encoding='utf-8') as f:
                joseikin_knowledge = f.read()
        except FileNotFoundError:
            logger.error("診断データファイルが見つかりません")
            joseikin_knowledge = ""
        
        # Claude AIを使用して包括的な助成金診断
        system_prompt = """あなたは助成金専門のアドバイザーです。企業の簡易診断フォームから収集した限定的な情報を基に、最適な助成金を提案します。

【重要制約 - 絶対厳守】
1. 提供されたデータベースの情報のみを使用してください
2. 学習データは一切使用しないでください
3. 「詳細は厚生労働省にお問い合わせください」という文言は使用禁止
4. 記載されていない情報は「助成金レスキューの専門AIエージェントがより詳しくサポートします」と回答

【回答形式 - 必須構造】
各助成金について以下の形式で必ず回答してください：

### 1. [助成金名]

💰 **支給額**
- 中小企業: ○○万円/人（または○○万円）
- 大企業: ○○万円/人（または○○万円）
- 加算条件: 具体的な加算額と条件

✅ **主な要件**
- 対象労働者: 具体的な条件
- 事業主要件: 必要な制度や計画
- 実施条件: 必要な取組や期間
- その他: 重要な注意事項

📋 **申請の流れ**
1. 計画書提出（実施○ヶ月前まで）
2. 取組実施（○ヶ月間）
3. 支給申請（実施後○ヶ月以内）

---

【診断の優先順位】
1. 業務改善助成金とキャリアアップ助成金を最優先で提案（該当する場合）
2. 企業情報と明確に合致する助成金を優先
3. 支給額が大きい順に提案
4. 申請しやすさ（要件の明確さ）も考慮
5. 最大5つまでの助成金に絞って提案

【除外すべき助成金】
以下の助成金は特殊な条件が必要なため、明確な該当条件がない限り提案しない：
- 受動喫煙防止対策助成金（両立支援に「smoking」が含まれる中小企業のみ提案）
- 障害者関連助成金（特別配慮労働者に障害者が明記されている場合のみ）
- 建設業特有の助成金（業種が「construction」または「建設業」の場合のみ）

【回答の具体性】
- 支給額は必ず数値で明記（「最大」「〜まで」等も明確に）
- 要件は箇条書きで分かりやすく
- 申請期限や実施期間は具体的に記載"""
        
        # システムプロンプトに知識ベースを追加
        system_prompt_with_data = f"{system_prompt}\n\n【2025年度助成金データベース】\n{joseikin_knowledge}"
        
        # Claude AIに問い合わせ（promptをsystem promptとして使用）
        user_question = f"""
以下の企業情報を基に、該当する助成金を診断してください。
各助成金について、💰支給額、✅主な要件、📋申請の流れの3点を必ず明記してください。

【企業情報】
業種: {industry_ja}
従業員数: {total_employees}人
企業規模: {'中小企業' if is_small_business else '大企業' if total_employees != 'なし' else '不明'}
雇用保険被保険者数: {diagnosis_data.get('insuredEmployees', 'なし')}
有期契約労働者数: {diagnosis_data.get('temporaryEmployees', 'なし')}
短時間労働者数: {diagnosis_data.get('partTimeEmployees', 'なし')}
年齢構成: {diagnosis_data.get('ageGroups', 'なし')}
特別配慮労働者: {diagnosis_data.get('specialNeeds', 'なし')}
経営状況: {diagnosis_data.get('businessSituation', 'なし')}
事業場内最低賃金: {min_wage}円/時{'（改善が必要）' if needs_wage_improvement else ''}
賃金・処遇改善: {diagnosis_data.get('wageImprovement', 'なし')}
投資・改善予定: {diagnosis_data.get('investments', 'なし')}
両立支援: {work_life_balance}{'（受動喫煙防止対策を含む）' if needs_smoking_prevention else ''}

【重要】
- 業務改善助成金とキャリアアップ助成金を優先的に検討し、該当する場合は必ず上位に提案してください
- この企業の状況から判断して、最も可能性が高い助成金を最大5つまで提案してください
- 各助成金の支給額は必ず具体的な金額で示してください
- 要件は企業情報と照らし合わせて、該当/非該当の判断材料を明確に示してください

【判定の注意点】
- 「なし」と記載された項目は、その条件に該当しないと判断してください
- 例：特別配慮労働者が「なし」→ 障害者関連助成金は提案しない
- 例：投資・改善予定が「なし」→ 設備投資が必要な助成金は慎重に判断
- 例：両立支援が「なし」または「smoking」を含まない → 受動喫煙防止対策助成金は提案しない
- 提供された情報から確実に該当すると判断できる助成金のみを提案してください
- 受動喫煙防止対策助成金は中小企業が対象で、飲食店は助成率2/3、その他業種は1/2、上限100万円です
"""
        raw_response = get_claude_service().chat_diagnosis_haiku(user_question, system_prompt_with_data)
        
        # 強制的に改行を整理
        response = _format_diagnosis_response(raw_response)
        
        # 厚生労働省への問い合わせ文言を強制的に削除
        import re
        response = re.sub(r'詳細は厚生労働省.*?ください[。\n]?', '', response)
        response = re.sub(r'厚生労働省.*?お問い合わせ.*?[。\n]?', '', response)
        response = re.sub(r'労働局.*?お問い合わせ.*?[。\n]?', '', response)
        response = re.sub(r'ハローワーク.*?お問い合わせ.*?[。\n]?', '', response)
        response = re.sub(r'詳しくは.*?ご確認ください[。\n]?', '詳しくは助成金レスキューの専門AIエージェントがサポートします。', response)
        # 不完全な文章を削除
        response = re.sub(r'詳細な手続きや申請方法については、最寄りの[。\n]?', '', response)
        response = re.sub(r'詳細な.*?については、最寄りの[。\n]?', '', response)
        
        # レスポンスを構造化
        applicable_grants = [{
            'name': 'AI診断結果',
            'description': response
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
        
        # 使用状況を直接取得
        usage_stats = None
        if current_user:
            usage_stats = get_subscription_service().get_usage_stats(current_user.get('user_id') or current_user['id'])
        
        return jsonify({
            'user': current_user,
            'usage_stats': usage_stats,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Error getting user info: {str(e)}")
        return jsonify({'error': 'ユーザー情報の取得に失敗しました'}), 500

@app.route('/api/debug/create-subscription', methods=['POST'])
@require_auth 
def debug_create_subscription():
    """デバッグ用: 現在のユーザーにサブスクリプションを作成"""
    try:
        current_user = get_current_user()
        user_id = current_user.get('user_id') or current_user['id']
        
        # UserServiceのcreate_initial_subscriptionを使用
        get_user_service().create_initial_subscription(user_id)
        
        # 作成後に確認
        usage_stats = get_subscription_service().get_usage_stats(user_id)
        
        return jsonify({
            'status': 'success',
            'message': 'サブスクリプション作成完了',
            'usage_stats': usage_stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

        # 不正検知: 使い捨てメール・無効ドメイン検知
        email_domain = email.split('@')[1].lower() if '@' in email else ''

        # 使い捨てメールドメイン
        disposable_domains = [
            '10minutemail.com', 'temp-mail.org', 'guerrillamail.com',
            'mailinator.com', 'throwaway.email', 'getnada.com',
            'maildrop.cc', 'tempmail.ninja', 'yopmail.com'
        ]

        # タイポドメイン（よくある誤字）
        typo_domains = [
            'gmali.com', 'yahooo.com', 'hotmial.com', 'gmai.com',
            'yaho.com', 'hotmai.com', 'gmial.com', 'outlok.com'
        ]

        if email_domain in disposable_domains + typo_domains:
            logger.warning(f"Blocked registration with invalid domain: {email_domain} (uid: {uid})")
            return jsonify({
                'error': 'このメールアドレスは使用できません。正しいメールアドレスを入力してください。',
                'code': 'INVALID_EMAIL_DOMAIN'
            }), 400
        
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

                # ウェルカムメール送信（エラーが発生してもサービス継続）
                try:
                    from email_service import get_email_service
                    email_service = get_email_service()
                    email_service.send_welcome_email(email, display_name)
                    logger.info(f"Welcome email sent to: {email}")
                except Exception as email_error:
                    logger.error(f"Welcome email failed (service continues): {str(email_error)}")
                    # エラーが発生してもユーザー登録は成功として処理を続行

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

                # ウェルカムメールは既に上で送信済みなのでここでは送信しない

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
                    metadata={'firebase_uid': current_user['user_id']}
                )
                # ユーザーデータベースにStripe顧客IDを保存
                get_auth_service().update_stripe_customer_id(current_user.get('user_id') or current_user['id'], stripe_customer_id)
                logger.info(f"Created Stripe customer: {stripe_customer_id}")
            except Exception as e:
                logger.error(f"Failed to create Stripe customer: {str(e)}")
                return jsonify({'error': f'Stripe顧客作成エラー: {str(e)}'}), 500
        
        data = request.json
        success_url = data.get('success_url', 'https://your-domain.com/success')
        cancel_url = data.get('cancel_url', 'https://your-domain.com/cancel')
        
        checkout_session = get_stripe_service().create_basic_plan_checkout(
            customer_id=stripe_customer_id,
            user_id=current_user.get('user_id') or current_user['id'],
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
                    metadata={'firebase_uid': current_user['user_id']}
                )
                # ユーザーデータベースにStripe顧客IDを保存
                get_auth_service().update_stripe_customer_id(current_user.get('user_id') or current_user['id'], stripe_customer_id)
                logger.info(f"Created Stripe customer: {stripe_customer_id}")
            except Exception as e:
                logger.error(f"Failed to create Stripe customer: {str(e)}")
                return jsonify({'error': f'Stripe顧客作成エラー: {str(e)}'}), 500
        
        data = request.json
        success_url = data.get('success_url', 'https://your-domain.com/success')
        cancel_url = data.get('cancel_url', 'https://your-domain.com/cancel')
        
        checkout_session = get_stripe_service().create_additional_pack_checkout(
            customer_id=stripe_customer_id,
            user_id=current_user.get('user_id') or current_user['id'],
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

# ===== 新料金プラン決済エンドポイント =====

@app.route('/api/payment/light-plan', methods=['POST'])
@require_auth
def create_light_plan_checkout():
    """ライトプラン（1,480円/月）の決済セッションを作成"""
    return _create_subscription_checkout('light')

@app.route('/api/payment/regular-plan', methods=['POST'])
@require_auth 
def create_regular_plan_checkout():
    """レギュラープラン（3,300円/月）の決済セッションを作成"""
    return _create_subscription_checkout('regular')

@app.route('/api/payment/heavy-plan', methods=['POST'])
@require_auth
def create_heavy_plan_checkout():
    """ヘビープラン（5,500円/月）の決済セッションを作成"""
    return _create_subscription_checkout('heavy')

def _create_subscription_checkout(plan_type: str):
    """サブスクリプション決済セッション作成の共通処理"""
    try:
        current_user = get_current_user()
        
        # Stripe顧客IDがない場合は自動作成
        stripe_customer_id = current_user.get('stripe_customer_id')
        if not stripe_customer_id:
            try:
                stripe_customer_id = get_stripe_service().create_customer(
                    email=current_user['email'],
                    name=current_user.get('display_name', ''),
                    metadata={'firebase_uid': current_user['user_id']}
                )
                get_auth_service().update_stripe_customer_id(current_user.get('user_id') or current_user['id'], stripe_customer_id)
                logger.info(f"Created Stripe customer for {plan_type} plan: {stripe_customer_id}")
            except Exception as e:
                logger.error(f"Failed to create Stripe customer: {str(e)}")
                return jsonify({'error': f'Stripe顧客作成エラー: {str(e)}'}), 500
        
        data = request.json
        base_success_url = data.get('success_url', 'https://your-domain.com/success')
        cancel_url = data.get('cancel_url', 'https://your-domain.com/cancel')
        
        # success_urlにsession_idパラメータを追加
        separator = '&' if '?' in base_success_url else '?'
        success_url = f"{base_success_url}{separator}session_id={{CHECKOUT_SESSION_ID}}"
        
        # プランごとに適切なcheckout methodを呼び出し
        stripe_service = get_stripe_service()
        if plan_type == 'light':
            checkout_session = stripe_service.create_light_plan_checkout(
                customer_id=stripe_customer_id,
                user_id=current_user.get('user_id') or current_user['id'],
                success_url=success_url,
                cancel_url=cancel_url
            )
        elif plan_type == 'regular':
            checkout_session = stripe_service.create_regular_plan_checkout(
                customer_id=stripe_customer_id,
                user_id=current_user.get('user_id') or current_user['id'],
                success_url=success_url,
                cancel_url=cancel_url
            )
        elif plan_type == 'heavy':
            checkout_session = stripe_service.create_heavy_plan_checkout(
                customer_id=stripe_customer_id,
                user_id=current_user.get('user_id') or current_user['id'],
                success_url=success_url,
                cancel_url=cancel_url
            )
        else:
            return jsonify({'error': 'Invalid plan type'}), 400
        
        return jsonify({
            'checkout_url': checkout_session['url'],
            'session_id': checkout_session['id'],
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Error creating {plan_type} plan checkout: {str(e)}")
        return jsonify({'error': '決済セッションの作成に失敗しました'}), 500

# ===== 追加パック決済エンドポイント =====

@app.route('/api/payment/pack-20', methods=['POST'])
@require_auth
def create_pack_20_checkout():
    """20回追加パック（1,480円）の決済セッションを作成"""
    return _create_pack_checkout('pack_20', 20)

@app.route('/api/payment/pack-40', methods=['POST'])
@require_auth
def create_pack_40_checkout():
    """40回追加パック（2,680円）の決済セッションを作成"""
    return _create_pack_checkout('pack_40', 40)

@app.route('/api/payment/pack-90', methods=['POST'])
@require_auth
def create_pack_90_checkout():
    """90回追加パック（5,500円）の決済セッションを作成"""
    return _create_pack_checkout('pack_90', 90)

# 新しいURL形式でのエンドポイント（pricing.htmlから呼び出される）
@app.route('/api/payment/additional-pack-20', methods=['POST'])
@require_auth
def create_additional_pack_20_checkout():
    """20回追加パック（1,480円）の決済セッションを作成"""
    return _create_pack_checkout('pack_20', 20)

@app.route('/api/payment/additional-pack-40', methods=['POST'])
@require_auth
def create_additional_pack_40_checkout():
    """40回追加パック（2,680円）の決済セッションを作成"""
    return _create_pack_checkout('pack_40', 40)

@app.route('/api/payment/additional-pack-90', methods=['POST'])
@require_auth
def create_additional_pack_90_checkout():
    """90回追加パック（5,500円）の決済セッションを作成"""
    return _create_pack_checkout('pack_90', 90)

# ===== 専門家相談決済エンドポイント =====

@app.route('/api/payment/consultation', methods=['POST'])
@require_auth
def create_consultation_payment():
    """専門家相談の決済セッションを作成"""
    try:
        current_user = get_current_user()
        data = request.json

        # リクエストデータの検証
        plan_type = data.get('plan_type')
        consultation_category = data.get('consultation_category')

        if not plan_type or not consultation_category:
            return jsonify({'error': 'プランタイプと相談カテゴリは必須です'}), 400

        if plan_type not in ['basic', 'standard', 'premium']:
            return jsonify({'error': '無効なプランタイプです'}), 400

        if consultation_category not in ['business_improvement', 'career_up', 'human_development', 'comprehensive']:
            return jsonify({'error': '無効な相談カテゴリです'}), 400

        # Stripe顧客IDがない場合は自動作成
        stripe_customer_id = current_user.get('stripe_customer_id')
        if not stripe_customer_id:
            try:
                stripe_customer_id = get_stripe_service().create_customer(
                    email=current_user['email'],
                    name=current_user.get('display_name', ''),
                    metadata={'firebase_uid': current_user['user_id']}
                )
                get_auth_service().update_stripe_customer_id(current_user.get('user_id') or current_user['id'], stripe_customer_id)
                logger.info(f"Created Stripe customer for consultation: {stripe_customer_id}")
            except Exception as e:
                logger.error(f"Failed to create Stripe customer: {str(e)}")
                return jsonify({'error': f'Stripe顧客作成エラー: {str(e)}'}), 500

        # URL設定
        base_url = request.host_url.rstrip('/')
        success_url = f"{base_url}/consultation/payment-success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base_url}/dashboard?payment=cancelled"

        # カスタムURLが指定されている場合は使用
        if data.get('success_url'):
            success_url = data.get('success_url')
        if data.get('cancel_url'):
            cancel_url = data.get('cancel_url')

        # ユーザー情報を準備
        user_info = {
            'user_id': current_user.get('user_id') or current_user['id'],
            'email': current_user.get('email', ''),
            'displayName': current_user.get('display_name', ''),
        }

        # Stripe決済セッションを作成
        stripe_service = get_stripe_service()
        session_result = stripe_service.create_consultation_payment(
            customer_id=stripe_customer_id,
            plan_type=plan_type,
            consultation_category=consultation_category,
            user_info=user_info,
            success_url=success_url,
            cancel_url=cancel_url
        )

        logger.info(f"Consultation payment session created: {session_result['id']} for user {current_user['user_id']}")

        return jsonify({
            'success': True,
            'session_id': session_result['id'],
            'payment_url': session_result['url'],
            'amount': session_result['amount'],
            'plan_name': session_result['plan_name'],
            'category_name': session_result['category_name']
        })

    except Exception as e:
        logger.error(f"Error creating consultation payment: {str(e)}")
        return jsonify({'error': '決済セッションの作成に失敗しました'}), 500

@app.route('/consultation/payment-success')
def consultation_payment_success():
    """専門家相談決済成功ページ"""
    session_id = request.args.get('session_id')
    if not session_id:
        return redirect('/dashboard?error=no_session_id')

    return render_template('consultation_payment_success.html', session_id=session_id)

def _create_pack_checkout(pack_type: str, questions_count: int):
    """追加パック決済セッション作成の共通処理"""
    try:
        current_user = get_current_user()
        
        # Stripe顧客IDがない場合は自動作成
        stripe_customer_id = current_user.get('stripe_customer_id')
        if not stripe_customer_id:
            try:
                stripe_customer_id = get_stripe_service().create_customer(
                    email=current_user['email'],
                    name=current_user.get('display_name', ''),
                    metadata={'firebase_uid': current_user['user_id']}
                )
                get_auth_service().update_stripe_customer_id(current_user.get('user_id') or current_user['id'], stripe_customer_id)
                logger.info(f"Created Stripe customer for {pack_type}: {stripe_customer_id}")
            except Exception as e:
                logger.error(f"Failed to create Stripe customer: {str(e)}")
                return jsonify({'error': f'Stripe顧客作成エラー: {str(e)}'}), 500
        
        data = request.json
        base_success_url = data.get('success_url', 'https://your-domain.com/success')
        cancel_url = data.get('cancel_url', 'https://your-domain.com/cancel')
        
        # success_urlにsession_idパラメータを追加
        separator = '&' if '?' in base_success_url else '?'
        success_url = f"{base_success_url}{separator}session_id={{CHECKOUT_SESSION_ID}}"
        
        # パックごとに適切なcheckout methodを呼び出し
        stripe_service = get_stripe_service()
        if pack_type == 'pack_20':
            checkout_session = stripe_service.create_pack_20_checkout(
                customer_id=stripe_customer_id,
                user_id=current_user.get('user_id') or current_user['id'],
                success_url=success_url,
                cancel_url=cancel_url
            )
        elif pack_type == 'pack_40':
            checkout_session = stripe_service.create_pack_40_checkout(
                customer_id=stripe_customer_id,
                user_id=current_user.get('user_id') or current_user['id'],
                success_url=success_url,
                cancel_url=cancel_url
            )
        elif pack_type == 'pack_90':
            checkout_session = stripe_service.create_pack_90_checkout(
                customer_id=stripe_customer_id,
                user_id=current_user.get('user_id') or current_user['id'],
                success_url=success_url,
                cancel_url=cancel_url
            )
        else:
            return jsonify({'error': 'Invalid pack type'}), 400
        
        return jsonify({
            'checkout_url': checkout_session['url'],
            'session_id': checkout_session['id'],
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Error creating {pack_type} checkout: {str(e)}")
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
                session_id = result.get('session_id')
                
                # サブスクリプションプラン
                if plan_type in ['light', 'regular', 'heavy', 'basic']:
                    get_subscription_service().upgrade_to_subscription_plan(user_id, plan_type, session_id)
                
                # 追加パック（session_idをstripe_payment_idとして使用）
                elif plan_type == 'pack_20':
                    get_subscription_service().add_pack_20(user_id, session_id)
                elif plan_type == 'pack_40':
                    get_subscription_service().add_pack_40(user_id, session_id)
                elif plan_type == 'pack_90':
                    get_subscription_service().add_pack_90(user_id, session_id)
                elif plan_type == 'additional_pack':
                    # 既存コードとの互換性のため
                    get_subscription_service().add_additional_pack(user_id, session_id)

            elif result['action'] == 'expert_consultation_paid':
                # 専門家相談決済完了処理
                consultation_id = result.get('consultation_id')
                payment_intent_id = result.get('payment_intent_id')

                if EXPERT_CONSULTATION_ENABLED and consultation_id:
                    expert_consultation_service.update_consultation_payment(
                        consultation_id, payment_intent_id
                    )
                    logger.info(f"Expert consultation payment completed: {consultation_id}")
        
        return jsonify({'received': True})
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({'error': 'Webhook処理エラー'}), 500

@app.route('/api/force-plan-update', methods=['POST'])
@require_auth
def force_plan_update():
    """Webhook失敗時の代替手段として手動でプラン更新を実行"""
    try:
        current_user = get_current_user()
        data = request.json
        
        user_id = current_user.get('user_id') or current_user['id']
        plan_type = data.get('plan_type')
        session_id = data.get('session_id', 'manual_update')
        
        logger.info(f"Manual plan update requested - User: {user_id}, Plan: {plan_type}, Session: {session_id}")
        
        if not plan_type:
            return jsonify({'error': 'プランタイプが必要です'}), 400
            
        subscription_service = get_subscription_service()
        
        # サブスクリプションプラン
        if plan_type in ['light', 'regular', 'heavy', 'basic']:
            # Session IDから実際のSubscription IDを取得を試行
            if session_id != 'manual_update':
                from .stripe_service import StripeService
                stripe_service = StripeService()
                actual_subscription_id = stripe_service.get_subscription_from_session(session_id)
                
                if actual_subscription_id:
                    stripe_sub_id = actual_subscription_id
                    logger.info(f"Using actual Stripe subscription ID: {stripe_sub_id}")
                else:
                    # Session IDから取得できない場合は仮IDを生成
                    import uuid
                    stripe_sub_id = f"session_{uuid.uuid4().hex[:8]}"
                    logger.warning(f"Could not get subscription ID from session, using temporary ID: {stripe_sub_id}")
            else:
                # 完全な手動更新の場合
                import uuid
                stripe_sub_id = f"manual_{uuid.uuid4().hex[:8]}"
                logger.info(f"Manual update using temporary ID: {stripe_sub_id}")
            
            success = subscription_service.upgrade_to_subscription_plan(user_id, plan_type, stripe_sub_id)
            if success:
                logger.info(f"Manual subscription plan update successful: {user_id} -> {plan_type}")
                return jsonify({
                    'status': 'success',
                    'message': f'{plan_type}プランにアップグレードしました',
                    'plan_type': plan_type
                })
            else:
                logger.error(f"Manual subscription plan update failed: {user_id} -> {plan_type}")
                return jsonify({'error': 'プランアップグレードに失敗しました'}), 500
        
        # 追加パック（stripe_payment_idには手動更新IDを使用）
        elif plan_type == 'pack_20':
            success = subscription_service.add_pack_20(user_id, session_id)
        elif plan_type == 'pack_40':
            success = subscription_service.add_pack_40(user_id, session_id)
        elif plan_type == 'pack_90':
            success = subscription_service.add_pack_90(user_id, session_id)
        elif plan_type == 'additional_pack':
            success = subscription_service.add_additional_pack(user_id, session_id)
        else:
            return jsonify({'error': '無効なプランタイプです'}), 400
            
        if success:
            logger.info(f"Manual pack update successful: {user_id} -> {plan_type}")
            
            # 最新の使用状況を取得
            updated_usage = subscription_service.get_usage_stats(user_id)
            
            return jsonify({
                'status': 'success',
                'message': f'{plan_type}を追加しました',
                'plan_type': plan_type,
                'usage_stats': updated_usage
            })
        else:
            logger.error(f"Manual pack update failed: {user_id} -> {plan_type}")
            return jsonify({'error': 'パック追加に失敗しました'}), 500
            
    except Exception as e:
        logger.error(f"Error in manual plan update: {str(e)}")
        return jsonify({'error': '手動プラン更新エラー'}), 500

@app.route('/api/get-subscription-from-session', methods=['POST'])
@require_auth
def get_subscription_from_session():
    """Stripe SessionからSubscription IDを取得して更新"""
    try:
        current_user = get_current_user()
        data = request.json
        
        user_id = current_user.get('user_id') or current_user['id']
        session_id = data.get('session_id')
        plan_type = data.get('plan_type')
        
        if not session_id:
            return jsonify({'error': 'session_idが必要です'}), 400
            
        # Stripeセッションから詳細を取得
        stripe_service = get_stripe_service()
        import stripe
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        
        try:
            # セッション詳細を取得
            session = stripe.checkout.Session.retrieve(session_id)
            subscription_id = session.subscription
            
            if not subscription_id:
                return jsonify({'error': 'セッションにSubscription IDが見つかりません'}), 400
                
            logger.info(f"Retrieved subscription ID from session: {subscription_id}")
            
            # サブスクリプションプランの場合のみ処理
            if plan_type in ['light', 'regular', 'heavy', 'basic']:
                subscription_service = get_subscription_service()
                success = subscription_service.upgrade_to_subscription_plan(user_id, plan_type, subscription_id)
                
                if success:
                    # 最新の使用状況を取得
                    updated_usage = subscription_service.get_usage_stats(user_id)
                    
                    return jsonify({
                        'status': 'success',
                        'message': f'{plan_type}プランに正常にアップグレードしました',
                        'subscription_id': subscription_id,
                        'usage_stats': updated_usage
                    })
                else:
                    return jsonify({'error': 'プランアップグレードに失敗しました'}), 500
            else:
                return jsonify({'error': '無効なプランタイプです'}), 400
                
        except stripe.error.StripeError as e:
            logger.error(f"Stripe API error: {str(e)}")
            return jsonify({'error': 'Stripe APIエラー'}), 500
        
    except Exception as e:
        logger.error(f"Error getting subscription from session: {str(e)}")
        return jsonify({'error': 'セッション処理エラー'}), 500

# ===== 助成金メモ・スケジュール管理API =====

@app.route('/subsidy-memo')
def subsidy_memo_page():
    """助成金メモ・スケジュール管理ページ（認証はクライアント側で実行）"""
    return render_template('subsidy_memo.html')

@app.route('/api/subsidies', methods=['GET'])
@require_auth
def get_subsidies():
    """ユーザーの助成金メモ一覧を取得"""
    try:
        current_user = get_current_user()
        uid = current_user.get('user_id', 'Unknown')
        user_id = current_user.get('id', 'Unknown')
        logger.info(f"API GET: current_user keys: {list(current_user.keys())}")
        logger.info(f"API GET: Firebase UID: {uid}")
        logger.info(f"API GET: Database User ID: {user_id}")
        logger.info(f"API GET: Email: {current_user.get('email', 'Unknown')}")
        
        from subsidy_service import SubsidyService
        
        service = SubsidyService(firebase_service.get_db())
        # まずFirebase UIDで試し、見つからない場合はDatabase User IDでも試す
        subsidies = service.get_user_subsidies(current_user['user_id'])
        if not subsidies and current_user.get('id'):
            logger.info(f"No subsidies found with Firebase UID, trying database user ID: {current_user['id']}")
            subsidies = service.get_user_subsidies(current_user['id'])
        
        logger.info(f"API GET: Found {len(subsidies)} subsidies for user")
        
        result = [s.to_dict() for s in subsidies]
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error fetching subsidies in API: {str(e)}")
        logger.error(f"Current user: {current_user if 'current_user' in locals() else 'Not available'}")
        return jsonify({'error': '助成金メモの取得に失敗しました'}), 500

@app.route('/api/subsidies', methods=['POST'])
@require_auth
def create_subsidy():
    """新規助成金メモを作成"""
    try:
        current_user = get_current_user()
        data = request.json
        uid = current_user.get('user_id', 'Unknown')
        user_id = current_user.get('id', 'Unknown')
        
        logger.info(f"API POST: current_user keys: {list(current_user.keys())}")
        logger.info(f"API POST: Firebase UID: {uid}")
        logger.info(f"API POST: Database User ID: {user_id}")
        logger.info(f"API POST: Email: {current_user.get('email', 'Unknown')}")
        logger.info(f"API POST: Received data keys: {list(data.keys()) if data else 'None'}")
        
        from subsidy_service import SubsidyService
        service = SubsidyService(firebase_service.get_db())
        
        # Firebase UIDを優先的に使用（取得時と一貫性を保つため）
        user_id_for_save = current_user['user_id']
        memo = service.create_subsidy_memo(user_id_for_save, data)
        
        logger.info(f"API: Successfully created memo with ID: {memo.id}")
        
        return jsonify(memo.to_dict()), 201
        
    except Exception as e:
        logger.error(f"Error creating subsidy in API: {str(e)}")
        logger.error(f"Request data: {request.json if request.json else 'No JSON data'}")
        logger.error(f"Current user: {current_user if 'current_user' in locals() else 'Not available'}")
        return jsonify({'error': '助成金メモの作成に失敗しました'}), 500

@app.route('/api/subsidies/<subsidy_id>', methods=['PUT'])
@require_auth
def update_subsidy(subsidy_id):
    """助成金メモを更新"""
    try:
        current_user = get_current_user()
        data = request.json
        
        from subsidy_service import SubsidyService
        service = SubsidyService(firebase_service.get_db())
        
        success = service.update_subsidy_memo(current_user['user_id'], subsidy_id, data)
        
        if success:
            return jsonify({'status': 'success'})
        else:
            return jsonify({'error': '更新に失敗しました'}), 400
            
    except Exception as e:
        logger.error(f"Error updating subsidy: {str(e)}")
        return jsonify({'error': '助成金メモの更新に失敗しました'}), 500

@app.route('/api/subsidies/<subsidy_id>/memo', methods=['POST'])
@require_auth
def add_chat_history(subsidy_id):
    """チャット履歴・メモを追加"""
    try:
        current_user = get_current_user()
        data = request.json
        content = data.get('content', '')
        
        if not content:
            return jsonify({'error': 'メモ内容が必要です'}), 400
        
        from subsidy_service import SubsidyService
        service = SubsidyService(firebase_service.get_db())
        
        success = service.add_chat_history(current_user['user_id'], subsidy_id, content)
        
        if success:
            return jsonify({'status': 'success'})
        else:
            return jsonify({'error': 'メモの追加に失敗しました'}), 400
            
    except Exception as e:
        logger.error(f"Error adding chat history: {str(e)}")
        return jsonify({'error': 'メモの追加に失敗しました'}), 500

@app.route('/api/subsidies/<subsidy_id>', methods=['DELETE'])
@require_auth
def delete_subsidy(subsidy_id):
    """助成金メモを削除"""
    try:
        current_user = get_current_user()
        
        from subsidy_service import SubsidyService
        service = SubsidyService(firebase_service.get_db())
        
        success = service.delete_subsidy_memo(current_user['user_id'], subsidy_id)
        
        if success:
            return jsonify({'status': 'success'})
        else:
            return jsonify({'error': '削除に失敗しました'}), 400
            
    except Exception as e:
        logger.error(f"Error deleting subsidy: {str(e)}")
        return jsonify({'error': '助成金メモの削除に失敗しました'}), 500

@app.route('/api/subsidies/deadlines', methods=['GET'])
@require_auth
def get_deadlines():
    """期限が近い助成金を取得"""
    try:
        current_user = get_current_user()
        days = request.args.get('days', 30, type=int)
        
        from subsidy_service import SubsidyService
        service = SubsidyService(firebase_service.get_db())
        
        # Firebase UIDを使用（他のAPIと一貫性を保つため）
        deadlines = service.get_upcoming_deadlines(current_user['user_id'], days)
        
        return jsonify(deadlines)
        
    except Exception as e:
        logger.error(f"Error fetching deadlines: {str(e)}")
        return jsonify({'error': '期限情報の取得に失敗しました'}), 500

@app.route('/api/diagnosis/save-temp', methods=['POST'])
def save_temp_diagnosis():
    """無料診断結果を一時保存"""
    try:
        data = request.json
        
        from subsidy_service import SubsidyService
        service = SubsidyService(firebase_service.get_db())
        
        session_id = service.save_temp_diagnosis(data)
        
        return jsonify({'session_id': session_id})
        
    except Exception as e:
        logger.error(f"Error saving temp diagnosis: {str(e)}")
        return jsonify({'error': '診断結果の保存に失敗しました'}), 500

# ===== AIエージェント関連API =====

@app.route('/api/agent/chat', methods=['POST'])
@require_auth
@check_usage_limit
def agent_chat():
    """AIエージェントとのチャット"""
    try:
        current_user = get_current_user()
        data = request.json
        
        agent_id = data.get('agent_id')
        message = data.get('message')
        conversation_history = data.get('conversation_history', [])
        
        if not agent_id or not message:
            return jsonify({'error': 'エージェントIDとメッセージが必要です'}), 400
        
        # エージェント情報を取得（既存のものを使用）
        agent_info = {
            'hanntei': {
                'name': '助成金判定エージェント',
                'system_prompt': '助成金判定エージェントとして、企業に最適な助成金を対話形式で判定・提案します。'
            },
            'gyoumukaizen': {
                'name': '業務改善助成金専門AIエージェント',
                'system_prompt': '業務改善助成金の専門エージェントとして、最新の情報を基に正確なアドバイスを提供してください。'
            },
            'career-up_seishain': {
                'name': 'キャリアアップ助成金専門エージェント（正社員化コース）',
                'system_prompt': 'キャリアアップ助成金の専門エージェントとして、最新の情報を基に正確なアドバイスを提供してください。'
            },
            'career-up_chingin': {
                'name': 'キャリアアップ助成金専門エージェント（賃金規定等改定コース）',
                'system_prompt': 'キャリアアップ助成金の専門エージェントとして、最新の情報を基に正確なアドバイスを提供してください。'
            },
            'career-up_shogaisha': {
                'name': 'キャリアアップ助成金専門エージェント（障害者正社員化コース）',
                'system_prompt': 'キャリアアップ助成金の専門エージェントとして、最新の情報を基に正確なアドバイスを提供してください。'
            },
            'career-up_kyotsu': {
                'name': 'キャリアアップ助成金専門エージェント（賃金規定等共通化コース）',
                'system_prompt': 'キャリアアップ助成金の専門エージェントとして、最新の情報を基に正確なアドバイスを提供してください。'
            },
            'career-up_shoyo': {
                'name': 'キャリアアップ助成金専門エージェント（賞与・退職金制度導入コース）',
                'system_prompt': 'キャリアアップ助成金の専門エージェントとして、最新の情報を基に正確なアドバイスを提供してください。'
            },
            'career-up_shahoken': {
                'name': 'キャリアアップ助成金専門エージェント（社会保険適用時処遇改善コース）',
                'system_prompt': 'キャリアアップ助成金の専門エージェントとして、最新の情報を基に正確なアドバイスを提供してください。'
            },
            'career-up_tanshuku': {
                'name': 'キャリアアップ助成金専門エージェント（短時間労働者労働時間延長支援コース）',
                'system_prompt': 'キャリアアップ助成金の専門エージェントとして、最新の情報を基に正確なアドバイスを提供してください。'
            },
            'jinzai-kaihatsu_jinzai-ikusei_kunren': {
                'name': '人材開発支援助成金専門エージェント（人材育成支援コース・人材育成訓練）',
                'system_prompt': '人材開発支援助成金の専門エージェントとして、最新の情報を基に正確なアドバイスを提供してください。'
            },
            'jinzai-kaihatsu_jinzai-ikusei_nintei': {
                'name': '人材開発支援助成金専門エージェント（人材育成支援コース・認定実習併用職業訓練）',
                'system_prompt': '人材開発支援助成金の専門エージェントとして、最新の情報を基に正確なアドバイスを提供してください。'
            },
            'jinzai-kaihatsu_jinzai-ikusei_yuki': {
                'name': '人材開発支援助成金専門エージェント（人材育成支援コース・有期実習型訓練）',
                'system_prompt': '人材開発支援助成金の専門エージェントとして、最新の情報を基に正確なアドバイスを提供してください。'
            },
            'jinzai-kaihatsu_kyoiku-kyuka': {
                'name': '人材開発支援助成金専門エージェント（教育訓練休暇等付与コース）',
                'system_prompt': '人材開発支援助成金の専門エージェントとして、最新の情報を基に正確なアドバイスを提供してください。'
            },
            'jinzai-kaihatsu_toushi_teigaku': {
                'name': '人材開発支援助成金専門エージェント（人への投資促進コース・定額制訓練）',
                'system_prompt': '人材開発支援助成金の専門エージェントとして、最新の情報を基に正確なアドバイスを提供してください。'
            },
            'jinzai-kaihatsu_toushi_jihatsu': {
                'name': '人材開発支援助成金専門エージェント（人への投資促進コース・自発的職業能力開発訓練）',
                'system_prompt': '人材開発支援助成金の専門エージェントとして、最新の情報を基に正確なアドバイスを提供してください。'
            },
            'jinzai-kaihatsu_toushi_digital': {
                'name': '人材開発支援助成金専門エージェント（人への投資促進コース・高度デジタル人材等訓練）',
                'system_prompt': '人材開発支援助成金の専門エージェントとして、最新の情報を基に正確なアドバイスを提供してください。'
            },
            'jinzai-kaihatsu_toushi_it': {
                'name': '人材開発支援助成金専門エージェント（人への投資促進コース・情報技術分野認定実習併用職業訓練）',
                'system_prompt': '人材開発支援助成金の専門エージェントとして、最新の情報を基に正確なアドバイスを提供してください。'
            },
            'reskilling': {
                'name': '人材開発支援助成金専門エージェント（事業展開等リスキリング支援コース）',
                'system_prompt': '人材開発支援助成金の専門エージェントとして、最新の情報を基に正確なアドバイスを提供してください。'
            },
            '65sai_keizoku': {
                'name': '65歳超雇用推進助成金専門エージェント（65歳超継続雇用促進コース）',
                'system_prompt': '65歳超雇用推進助成金の専門エージェントとして、最新の情報を基に正確なアドバイスを提供してください。'
            }
        }
        
        if agent_id not in agent_info:
            return jsonify({'error': '無効なエージェントIDです'}), 400
        
        # Claude APIを使用してレスポンスを生成（元の方式に戻す）
        claude_service = get_claude_service()
        
        # 会話履歴を含むコンテキストを構築
        context_messages = []
        for msg in conversation_history[-10:]:  # 最新10件まで（トークンコスト削減）
            role = '次の質問例' if msg['sender'] == 'user' else 'assistant'
            context_messages.append(f"{role}: {msg['message']}")
        
        full_prompt = f"""
これまでの会話:
{chr(10).join(context_messages) if context_messages else '新しい会話です'}

ユーザー: {message}
"""
        
        # 元のclaude_serviceを使用（エージェント別のファイルを読み込む）
        response = claude_service.get_agent_response(full_prompt, agent_id)
        
        # デバッグ: レスポンス内容をログ出力（質問ボタン調査用）
        logger.info(f"Raw Claude response preview: {response[:500]}...")
        
        # エラーメッセージかどうかを判定
        is_error_response = (
            "申し訳ございません" in response and 
            ("サーバーが込み合っています" in response or 
             "時間がかかりすぎています" in response or 
             "サーバーが混雑しています" in response or 
             "認証に問題が発生しています" in response or 
             "一時的な問題が発生している" in response)
        )
        
        # 応答から会話履歴の混入を削除（エラーでない場合のみ）
        if not is_error_response:
            # 「ユーザー:」「次の質問例:」以降の部分を削除
            import re
            response = re.sub(r'(ユーザー:|次の質問例:).*$', '', response, flags=re.DOTALL).strip()
            
            # 質問ボタンのHTMLも除去（限定的・安全な対策）
            # 明確にボタンタグのみを削除（他の要素への影響を最小限に）
            response = re.sub(r'<button[^>]*>[^<]*(?:見積|質問|について|ですか)[^<]*</button>', '', response, flags=re.IGNORECASE)
        
        import time
        
        # 統合会話履歴に保存
        conversation_id = data.get('conversation_id')
        try:
            from integrated_conversation_service import IntegratedConversationService
            conv_service = IntegratedConversationService(firebase_service.get_db())
            
            if not conversation_id:
                # 新しい会話を作成
                conversation = conv_service.create_conversation(
                    current_user['user_id'],
                    agent_id,
                    agent_info[agent_id]['name'],
                    message
                )
                conversation_id = conversation['id']
                
                # アシスタントの応答も追加
                conv_service.add_message(conversation_id, current_user['user_id'], response, 'assistant')
            else:
                # 既存の会話にメッセージを追加
                conv_service.add_message(conversation_id, current_user['user_id'], message, 'user')
                conv_service.add_message(conversation_id, current_user['user_id'], response, 'assistant')
        
        except Exception as e:
            logger.error(f"Error saving conversation: {str(e)}")
            # 保存エラーがあっても応答は返す
        
        # エラーでない場合のみ質問使用回数を増加
        if not is_error_response:
            result = get_subscription_service().use_question(current_user.get('user_id') or current_user['id'])
            
            if not result['success']:
                logger.error(f"Failed to record question usage: {result.get('error')}")
        
        # 最新の使用状況を取得
        updated_usage = get_subscription_service().get_usage_stats(current_user.get('user_id') or current_user['id'])
        
        # レスポンスを保存
        response_data = {
            'message': response,
            'agent_name': agent_info[agent_id]['name'],
            'timestamp': int(time.time() * 1000),
            'conversation_id': conversation_id,
            'usage_stats': updated_usage
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"Error in agent chat: {str(e)}\n{error_detail}")
        # デバッグ用に詳細なエラーを返す（本番環境では削除すること）
        return jsonify({'error': f'チャットの処理に失敗しました: {str(e)}'}), 500

# ===== 会話履歴管理API =====

@app.route('/api/conversations', methods=['GET'])
@require_auth
def get_conversations():
    """ユーザーの統合会話一覧を取得"""
    try:
        current_user = get_current_user()
        
        from integrated_conversation_service import IntegratedConversationService
        service = IntegratedConversationService(firebase_service.get_db())
        
        conversations = service.get_conversations(current_user['user_id'])
        
        return jsonify(conversations)
        
    except Exception as e:
        logger.error(f"Error getting conversations: {str(e)}")
        return jsonify({'error': '会話履歴の取得に失敗しました'}), 500

@app.route('/api/conversations', methods=['POST'])
@require_auth
def create_conversation():
    """新しい統合会話を作成"""
    try:
        current_user = get_current_user()
        data = request.json
        
        agent_id = data.get('agent_id')
        agent_name = data.get('agent_name')
        initial_message = data.get('initial_message')
        
        if not agent_id or not agent_name:
            return jsonify({'error': 'エージェントIDとエージェント名が必要です'}), 400
        
        from integrated_conversation_service import IntegratedConversationService
        service = IntegratedConversationService(firebase_service.get_db())
        
        conversation = service.create_conversation(
            current_user['user_id'], 
            agent_id, 
            agent_name,
            initial_message
        )
        
        return jsonify(conversation), 201
        
    except Exception as e:
        logger.error(f"Error creating conversation: {str(e)}")
        return jsonify({'error': '会話の作成に失敗しました'}), 500

@app.route('/api/conversations/<conversation_id>', methods=['GET'])
@require_auth  
def get_conversation(conversation_id):
    """特定の統合会話を取得"""
    try:
        current_user = get_current_user()
        
        from integrated_conversation_service import IntegratedConversationService
        service = IntegratedConversationService(firebase_service.get_db())
        
        conversation = service.get_conversation(conversation_id, current_user['user_id'])
        
        if not conversation:
            return jsonify({'error': '会話が見つかりません'}), 404
        
        return jsonify(conversation)
        
    except Exception as e:
        logger.error(f"Error getting conversation {conversation_id}: {str(e)}")
        return jsonify({'error': '会話の取得に失敗しました'}), 500

@app.route('/api/conversations/<conversation_id>/messages', methods=['POST'])
@require_auth
def add_message_to_conversation(conversation_id):
    """会話にメッセージを追加"""
    try:
        current_user = get_current_user()
        data = request.json
        
        sender = data.get('sender')  # 'user' or 'assistant'
        content = data.get('content')
        
        if not sender or not content:
            return jsonify({'error': '送信者とメッセージ内容が必要です'}), 400
        
        if sender not in ['user', 'assistant']:
            return jsonify({'error': '無効な送信者です'}), 400
        
        from integrated_conversation_service import IntegratedConversationService
        service = IntegratedConversationService(firebase_service.get_db())
        
        success = service.add_message(
            conversation_id, 
            current_user['user_id'], 
            content,
            sender
        )
        
        if success:
            return jsonify({'status': 'success'})
        else:
            return jsonify({'error': 'メッセージの追加に失敗しました'}), 400
        
    except Exception as e:
        logger.error(f"Error adding message to conversation {conversation_id}: {str(e)}")
        return jsonify({'error': 'メッセージの追加に失敗しました'}), 500

@app.route('/api/conversations/<conversation_id>/title', methods=['PUT'])
@require_auth
def update_conversation_title(conversation_id):
    """会話タイトルを更新"""
    try:
        current_user = get_current_user()
        data = request.json
        
        title = data.get('title')
        if not title:
            return jsonify({'error': 'タイトルが必要です'}), 400
        
        from integrated_conversation_service import IntegratedConversationService
        service = IntegratedConversationService(firebase_service.get_db())
        
        success = service.update_conversation_title(
            conversation_id,
            current_user['user_id'], 
            title
        )
        
        if success:
            return jsonify({'status': 'success'})
        else:
            return jsonify({'error': 'タイトルの更新に失敗しました'}), 400
        
    except Exception as e:
        logger.error(f"Error updating conversation title {conversation_id}: {str(e)}")
        return jsonify({'error': 'タイトルの更新に失敗しました'}), 500

@app.route('/api/conversations/<conversation_id>', methods=['DELETE'])
@require_auth
def delete_conversation(conversation_id):
    """会話を削除"""
    try:
        current_user = get_current_user()
        
        from integrated_conversation_service import IntegratedConversationService
        service = IntegratedConversationService(firebase_service.get_db())
        
        success = service.delete_conversation(conversation_id, current_user['user_id'])
        
        if success:
            return jsonify({'status': 'success'})
        else:
            return jsonify({'error': '会話の削除に失敗しました'}), 400
        
    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id}: {str(e)}")
        return jsonify({'error': '会話の削除に失敗しました'}), 500

@app.route('/api/diagnosis/convert/<session_id>', methods=['POST'])
@require_auth
def convert_diagnosis(session_id):
    """一時診断結果を正式なメモに変換"""
    try:
        current_user = get_current_user()
        
        from subsidy_service import SubsidyService
        service = SubsidyService(firebase_service.get_db())
        
        memo = service.convert_temp_to_memo(session_id, current_user['user_id'])
        
        if memo:
            return jsonify(memo.to_dict())
        else:
            return jsonify({'error': '診断結果が見つかりません'}), 404
            
    except Exception as e:
        logger.error(f"Error converting diagnosis: {str(e)}")
        return jsonify({'error': '診断結果の変換に失敗しました'}), 500

@app.route('/api/ai-results', methods=['GET', 'POST'])
@require_auth
def ai_results():
    """AI診断結果の取得・保存"""
    try:
        current_user = get_current_user()
        user_id = current_user['user_id']
        
        from subsidy_service import SubsidyService
        service = SubsidyService(firebase_service.get_db())
        
        if request.method == 'GET':
            # AI診断結果を取得
            results = service.get_ai_results(user_id)
            return jsonify(results)
            
        elif request.method == 'POST':
            # 新しいAI診断結果を保存
            data = request.json
            result_id = service.save_ai_result(user_id, data)
            return jsonify({'id': result_id, 'message': '診断結果を保存しました'})
            
    except Exception as e:
        logger.error(f"Error handling AI results: {str(e)}")
        return jsonify({'error': 'AI診断結果の処理に失敗しました'}), 500

@app.route('/api/forms', methods=['GET'])
def get_application_forms():
    """全助成金の申請書類情報を取得"""
    debug_info = {
        'step': '',
        'json_path': '',
        'file_exists': False,
        'error': None,
        'data_count': 0
    }
    
    try:
        forms_data = []
        
        # まずsubsidy_forms.jsonから直接読み込みを試みる（これがメインの方法）
        import json
        import os
        
        # subsidy_forms.jsonは同じディレクトリにある
        json_path = os.path.join(os.path.dirname(__file__), 'subsidy_forms.json')
        debug_info['json_path'] = json_path
        debug_info['file_exists'] = os.path.exists(json_path)
        debug_info['step'] = 'checking_file'
        
        if json_path and os.path.exists(json_path):
            debug_info['step'] = 'reading_file'
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    subsidies = json.load(f)
                    debug_info['step'] = 'parsing_json'
                    
                for subsidy_id, subsidy_info in subsidies.items():
                    # アクティブなもののみ追加（active=trueまたはactiveフィールドがない場合は含める）
                    if subsidy_info.get('active', True):
                        forms_data.append({
                            'id': subsidy_id,
                            'name': subsidy_info.get('name', ''),
                            'description': subsidy_info.get('description', ''),
                            'main_page': subsidy_info.get('urls', {}).get('main_page', {}),
                            'forms': subsidy_info.get('urls', {}).get('forms', {}),
                            'guides': subsidy_info.get('urls', {}).get('guides', {}),
                            'last_checked': subsidy_info.get('last_checked', '不明'),
                            'notes': subsidy_info.get('notes', '')
                        })
                debug_info['data_count'] = len(forms_data)
                debug_info['step'] = 'completed'
                logger.info(f"Successfully loaded {len(forms_data)} forms from subsidy_forms.json")
            except Exception as json_error:
                debug_info['error'] = str(json_error)
                debug_info['step'] = 'json_error'
                logger.error(f"Error reading subsidy_forms.json: {str(json_error)}")
        else:
            debug_info['step'] = 'file_not_found'
            logger.warning(f"subsidy_forms.json not found at: {json_path}")
            
        # FormsManagerが利用可能な場合は、そちらから追加データを取得
        try:
            from forms_manager import FormsManager
            forms_manager = FormsManager()
            
            # アクティブな助成金の一覧を取得
            active_agents = forms_manager.get_active_agents()
            existing_ids = {form['id'] for form in forms_data}
            
            for agent_id in active_agents:
                if agent_id not in existing_ids:  # 重複を避ける
                    agent_info = forms_manager.get_agent_info(agent_id)
                    if agent_info:
                        forms_data.append({
                            'id': agent_id,
                            'name': agent_info.get('name', ''),
                            'description': agent_info.get('description', ''),
                            'main_page': agent_info.get('urls', {}).get('main_page', {}),
                            'forms': agent_info.get('urls', {}).get('forms', {}),
                            'guides': agent_info.get('urls', {}).get('guides', {}),
                            'last_checked': agent_info.get('last_checked', '不明'),
                            'notes': agent_info.get('notes', '')
                        })
        except ImportError:
            # FormsManagerが利用できない場合は無視（subsidy_forms.jsonのデータのみ使用）
            pass
        
        return jsonify({
            'status': 'success',
            'data': forms_data,
            'count': len(forms_data),
            'debug': debug_info  # デバッグ情報を含める
        })
        
    except Exception as e:
        logger.error(f"Error getting forms data: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'申請書類情報の取得に失敗しました: {str(e)}',
            'data': []
        }), 500

@app.route('/landing')
def landing_page():
    """新しいランディングページ"""
    return render_template('landing_page.html')

@app.route('/landing2')
def landing_page_2():
    """新しいランディングページ v2"""
    return render_template('landing_page.html')

@app.route('/guide')
def guide():
    """活用ガイドページ"""
    return render_template('guide.html')

@app.route('/terms')
def terms():
    """利用規約ページ"""
    return render_template('terms.html')

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

# ===== サブスクリプション管理API =====

@app.route('/api/subscription-status', methods=['GET'])
@require_auth
def get_subscription_status():
    """現在のサブスクリプション状況を取得"""
    try:
        current_user = get_current_user()
        user_id = current_user.get('user_id') or current_user['id']
        
        # サブスクリプションサービスから情報を取得
        subscription_service = get_subscription_service()
        subscription_data = subscription_service.get_subscription_info(user_id)
        
        if subscription_data and subscription_data.get('subscription_id'):
            # Stripeからサブスクリプション詳細を取得
            try:
                import stripe
                stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
                
                # デバッグ: Stripe APIバージョン確認
                logger.info(f"=== DEBUG: Stripe API version: {stripe.api_version}")
                logger.info(f"=== DEBUG: Stripe library version: {stripe.__version__}")
                
                subscription_id = subscription_data['subscription_id']
                
                # 無効なsubscription_idをチェック
                if not subscription_id or subscription_id in ['manual_update', 'none', '']:
                    logger.warning(f"Invalid subscription_id: {subscription_id}")
                    return jsonify({
                        'has_subscription': False,
                        'error': 'サブスクリプションIDが無効です'
                    })
                
                subscription = stripe.Subscription.retrieve(subscription_id)
                
                # デバッグ: subscriptionオブジェクトの詳細を記録
                logger.info(f"=== DEBUG: Subscription object type: {type(subscription)}")
                logger.info(f"=== DEBUG: Subscription object keys: {subscription.keys() if hasattr(subscription, 'keys') else 'No keys method'}")
                logger.info(f"=== DEBUG: Has current_period_end attr: {hasattr(subscription, 'current_period_end')}")
                if hasattr(subscription, 'current_period_end'):
                    logger.info(f"=== DEBUG: current_period_end value: {subscription.current_period_end}")
                    logger.info(f"=== DEBUG: current_period_end type: {type(subscription.current_period_end)}")
                
                # プラン名のマッピング
                plan_names = {
                    'light': 'ライトプラン',
                    'regular': 'レギュラープラン', 
                    'heavy': 'ヘビープラン'
                }
                
                # 次回請求日を計算
                from datetime import datetime
                
                # current_period_endフィールドが存在するかチェック
                if hasattr(subscription, 'current_period_end') and subscription.current_period_end:
                    next_billing_date = datetime.fromtimestamp(subscription.current_period_end).strftime('%Y年%m月%d日')
                    logger.info(f"=== DEBUG: Using current_period_end: {subscription.current_period_end}")
                else:
                    # current_period_endが存在しない場合の代替手段
                    logger.warning("=== DEBUG: current_period_end not found, using alternative method")
                    
                    # billing_cycle_anchorまたはcreatedから計算
                    if hasattr(subscription, 'billing_cycle_anchor') and subscription.billing_cycle_anchor:
                        base_timestamp = subscription.billing_cycle_anchor
                        logger.info(f"=== DEBUG: Using billing_cycle_anchor: {base_timestamp}")
                    else:
                        base_timestamp = subscription.created
                        logger.info(f"=== DEBUG: Using created date: {base_timestamp}")
                    
                    # 30日後を計算（月額サブスクリプションの場合）
                    from datetime import timedelta
                    base_date = datetime.fromtimestamp(base_timestamp)
                    next_billing_date = (base_date + timedelta(days=30)).strftime('%Y年%m月%d日')
                    logger.info(f"=== DEBUG: Calculated next billing date: {next_billing_date}")
                
                return jsonify({
                    'has_subscription': True,
                    'plan_name': plan_names.get(subscription_data.get('plan_type'), subscription_data.get('plan_type', 'プラン')),
                    'next_billing_date': next_billing_date,
                    'status': subscription.status,
                    'cancel_at_period_end': subscription.cancel_at_period_end
                })
                
            except stripe.error.InvalidRequestError as e:
                logger.error(f"Invalid Stripe subscription ID: {str(e)}")
                return jsonify({
                    'has_subscription': False,
                    'error': 'サブスクリプションが見つかりません'
                })
            except Exception as e:
                logger.error(f"Error fetching Stripe subscription: {str(e)}")
                # Stripeエラーでもローカル情報は返す
                return jsonify({
                    'has_subscription': True,
                    'plan_name': subscription_data.get('plan_type', 'プラン'),
                    'next_billing_date': '取得できませんでした',
                    'status': 'unknown'
                })
        else:
            return jsonify({'has_subscription': False})
            
    except Exception as e:
        logger.error(f"Error getting subscription status: {str(e)}")
        return jsonify({'error': 'サブスクリプション情報の取得に失敗しました'}), 500

@app.route('/api/cancel-subscription', methods=['POST'])
@require_auth
def cancel_subscription():
    """サブスクリプションをキャンセル（期間終了時）"""
    try:
        current_user = get_current_user()
        user_id = current_user.get('user_id') or current_user['id']
        
        # サブスクリプション情報を取得
        subscription_service = get_subscription_service()
        subscription_data = subscription_service.get_subscription_info(user_id)
        
        if not subscription_data or not subscription_data.get('subscription_id'):
            return jsonify({'error': 'アクティブなサブスクリプションが見つかりません'}), 400
        
        # Stripeサブスクリプションを期間終了時キャンセルに設定
        try:
            import stripe
            stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
            
            subscription = stripe.Subscription.modify(
                subscription_data['subscription_id'],
                cancel_at_period_end=True
            )
            
            # ローカルデータベースにキャンセル状態を記録
            subscription_service.mark_subscription_cancelled(user_id)
            
            logger.info(f"Subscription cancelled for user {user_id}: {subscription_data['subscription_id']}")
            
            return jsonify({
                'success': True,
                'message': '解約手続きが完了しました。契約期間終了時にサービスが停止されます。',
                'cancel_at_period_end': True
            })
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe cancellation error: {str(e)}")
            return jsonify({'error': f'解約処理でエラーが発生しました: {str(e)}'}), 500
            
    except Exception as e:
        logger.error(f"Error cancelling subscription: {str(e)}")
        return jsonify({'error': '解約処理に失敗しました'}), 500

@app.route('/api/test-email', methods=['POST'])
def test_email():
    """メール送信テスト用エンドポイント"""
    try:
        data = request.json
        test_email = data.get('email', 'rescue@jyoseikin.jp')

        from email_service import get_email_service
        email_service = get_email_service()

        # テストメール送信
        result = email_service.send_test_email(test_email)

        if result:
            return jsonify({
                'success': True,
                'message': f'テストメールが {test_email} に送信されました'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'メール送信に失敗しました'
            }), 500

    except Exception as e:
        logger.error(f"Email test error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# 不正検知関連エンドポイント
@app.route('/admin/fraud-report', methods=['POST'])
def generate_fraud_report():
    """日次不正検知レポート生成（管理者用）"""
    try:
        from fraud_detection import FraudDetectionService

        fraud_service = FraudDetectionService()
        success = fraud_service.generate_daily_report()

        if success:
            return jsonify({
                'success': True,
                'message': 'Daily fraud report sent to Slack'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to send report'
            }), 500

    except Exception as e:
        logger.error(f"Fraud report generation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/admin/emergency-alert', methods=['POST'])
def send_emergency_alert():
    """緊急アラート送信（管理者用）"""
    try:
        from fraud_detection import FraudDetectionService
        data = request.json
        message = data.get('message', '')

        if not message:
            return jsonify({'error': 'Message is required'}), 400

        fraud_service = FraudDetectionService()
        success = fraud_service.send_emergency_alert(message)

        if success:
            return jsonify({
                'success': True,
                'message': 'Emergency alert sent to Slack'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to send alert'
            }), 500

    except Exception as e:
        logger.error(f"Emergency alert error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =============================================================================
# 管理者認証システム
# =============================================================================

try:
    from admin_auth import admin_auth, require_admin, is_admin_user
    ADMIN_AUTH_ENABLED = True
    logger.info("Admin authentication module loaded successfully")
except Exception as e:
    logger.error(f"Admin authentication module failed to load: {str(e)}")
    ADMIN_AUTH_ENABLED = False
    def require_admin(f):
        return f

# 専門家相談システム
try:
    from expert_consultation import expert_consultation_service
    from calendly_service import calendly_service
    EXPERT_CONSULTATION_ENABLED = True
    logger.info("Expert consultation module loaded successfully")
except Exception as e:
    logger.error(f"Expert consultation module failed to load: {str(e)}")
    EXPERT_CONSULTATION_ENABLED = False
    def require_admin(f):
        return f
    def is_admin_user():
        return False

@app.route('/admin/login')
def admin_login_page():
    """管理者ログインページ"""
    if ADMIN_AUTH_ENABLED and admin_auth.is_admin_logged_in():
        return redirect('/dashboard')

    return render_template('admin_login.html')

@app.route('/admin/api/login', methods=['POST'])
def admin_login_api():
    """管理者ログインAPI"""
    if not ADMIN_AUTH_ENABLED:
        return jsonify({
            'success': False,
            'error': '管理者認証システムが無効です'
        }), 500

    try:
        data = request.json
        email = data.get('email', '').strip()
        password = data.get('password', '')

        if not email or not password:
            return jsonify({
                'success': False,
                'error': 'メールアドレスとパスワードを入力してください'
            }), 400

        # 管理者認証
        if admin_auth.authenticate_admin(email, password):
            # セッション作成
            admin_auth.create_admin_session()

            logger.info(f"管理者ログイン成功: {email}")
            return jsonify({
                'success': True,
                'message': 'ログインに成功しました',
                'redirect': '/admin/dashboard'
            })
        else:
            logger.warning(f"管理者ログイン失敗: {email}")
            return jsonify({
                'success': False,
                'error': 'メールアドレスまたはパスワードが正しくありません'
            }), 401

    except Exception as e:
        logger.error(f"管理者ログインAPIエラー: {e}")
        return jsonify({
            'success': False,
            'error': 'システムエラーが発生しました'
        }), 500

@app.route('/admin/api/logout', methods=['POST'])
def admin_logout_api():
    """管理者ログアウトAPI"""
    if not ADMIN_AUTH_ENABLED:
        return jsonify({'success': False, 'error': '管理者認証システムが無効です'}), 500

    try:
        admin_auth.destroy_admin_session()
        logger.info("管理者ログアウト完了")
        return jsonify({
            'success': True,
            'message': 'ログアウトしました',
            'redirect': '/admin/login'
        })

    except Exception as e:
        logger.error(f"管理者ログアウトAPIエラー: {e}")
        return jsonify({
            'success': False,
            'error': 'システムエラーが発生しました'
        }), 500

@app.route('/admin/api/change-password', methods=['POST'])
@require_admin
def admin_change_password_api():
    """管理者パスワード変更API"""
    if not ADMIN_AUTH_ENABLED:
        return jsonify({'success': False, 'error': '管理者認証システムが無効です'}), 500

    try:
        data = request.json
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')
        confirm_password = data.get('confirm_password', '')

        if not current_password or not new_password or not confirm_password:
            return jsonify({
                'success': False,
                'error': '全てのフィールドを入力してください'
            }), 400

        if new_password != confirm_password:
            return jsonify({
                'success': False,
                'error': '新しいパスワードが一致しません'
            }), 400

        # パスワード変更
        success, message = admin_auth.change_admin_password(current_password, new_password)

        if success:
            logger.info("管理者パスワード変更成功")
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        logger.error(f"管理者パスワード変更APIエラー: {e}")
        return jsonify({
            'success': False,
            'error': 'システムエラーが発生しました'
        }), 500

@app.route('/admin/api/init', methods=['POST'])
def admin_init_api():
    """管理者アカウント初期化API（診断用）"""
    if not ADMIN_AUTH_ENABLED:
        return jsonify({'success': False, 'error': '管理者認証システムが無効です'}), 500

    try:
        success = admin_auth.initialize_admin()
        return jsonify({
            'success': success,
            'message': '管理者アカウント初期化が完了しました' if success else '初期化に失敗しました'
        })
    except Exception as e:
        logger.error(f"管理者初期化APIエラー: {e}")
        return jsonify({
            'success': False,
            'error': f'システムエラー: {str(e)}'
        }), 500

@app.route('/admin/test')
@require_admin
def admin_test():
    """管理者権限テスト"""
    return jsonify({
        'success': True,
        'message': '管理者権限が正常に動作しています',
        'timestamp': time.time()
    })

@app.route('/admin/dashboard')
@require_admin
def admin_dashboard():
    """管理者ダッシュボード"""
    return render_template('admin_dashboard.html')

# =============================================================================
# 専門家相談システム
# =============================================================================

@app.route('/expert-consultation')
def expert_consultation():
    """専門家相談予約ページ"""
    # 認証はクライアント側のFirebaseで行う（ダッシュボードと同じ方式）
    if not EXPERT_CONSULTATION_ENABLED:
        return jsonify({'error': '専門家相談システムが利用できません'}), 500

    return render_template('expert_consultation.html')

@app.route('/api/user')
@require_auth
def get_user_info():
    """ユーザー情報取得API"""
    try:
        current_user = get_current_user()
        user_id = current_user.get('user_id') or current_user.get('id')

        # Firestoreからユーザーデータを取得
        db = firebase_service.get_db()
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if user_doc.exists:
            user_data = user_doc.to_dict()
            return jsonify({
                'id': user_id,
                'email': current_user.get('email', ''),
                'name': user_data.get('name', '') or current_user.get('display_name', '') or current_user.get('name', ''),
                'subscription': user_data.get('subscription', {}),
                'subscription_plan': user_data.get('subscription_plan', 'free')
            })
        else:
            # Firestoreにユーザーデータが存在しない場合
            return jsonify({
                'id': user_id,
                'email': current_user.get('email', ''),
                'name': current_user.get('display_name', '') or current_user.get('name', ''),
                'subscription': {},
                'subscription_plan': 'free'
            })
    except Exception as e:
        logger.error(f"ユーザー情報取得エラー: {e}")
        return jsonify({'error': 'ユーザー情報の取得に失敗しました'}), 500

@app.route('/api/expert-consultation/eligibility')
@require_auth
def expert_consultation_eligibility():
    """専門家相談の利用資格確認API"""
    if not EXPERT_CONSULTATION_ENABLED:
        return jsonify({'error': '専門家相談システムが利用できません'}), 500

    try:
        current_user = get_current_user()
        user_id = current_user.get('user_id') or current_user['id']

        can_book, message = expert_consultation_service.can_user_book_consultation(user_id)

        return jsonify({
            'eligible': can_book,
            'message': message,
            'upgrade_required': not can_book and '有料プラン' in message
        })

    except Exception as e:
        logger.error(f"相談資格確認エラー: {e}")
        return jsonify({
            'eligible': False,
            'message': 'システムエラーが発生しました'
        }), 500

@app.route('/api/expert-consultation/create', methods=['POST'])
@require_auth
def create_expert_consultation():
    """専門家相談リクエスト作成API"""
    if not EXPERT_CONSULTATION_ENABLED:
        return jsonify({'error': '専門家相談システムが利用できません'}), 500

    try:
        current_user = get_current_user()
        user_id = current_user.get('user_id') or current_user['id']

        # 利用資格チェック
        can_book, eligibility_message = expert_consultation_service.can_user_book_consultation(user_id)
        if not can_book:
            return jsonify({
                'success': False,
                'error': eligibility_message
            }), 403

        data = request.json
        user_name = data.get('userName', '').strip()
        user_email = data.get('userEmail', '').strip()
        consultation_notes = data.get('consultationNotes', '').strip()

        if not user_name:
            return jsonify({
                'success': False,
                'error': 'お名前を入力してください'
            }), 400

        # メールアドレスが空の場合は、現在のユーザー情報から取得
        if not user_email:
            user_email = current_user.get('email', '')

        # 相談リクエストを作成
        consultation_id = expert_consultation_service.create_consultation_request(
            user_id=user_id,
            user_email=user_email,
            user_name=user_name,
            notes=consultation_notes
        )

        if not consultation_id:
            return jsonify({
                'success': False,
                'error': '相談リクエストの作成に失敗しました'
            }), 500

        # Stripe決済セッション作成
        stripe_service = get_stripe_service()

        # 正しいURL固定（request.url_rootは間違ったURLを返す可能性があるため）
        base_url = 'https://jyoseikinrescue-453016168690.asia-northeast1.run.app'
        success_url = f'{base_url}/expert-consultation/success/{consultation_id}'
        cancel_url = f'{base_url}/expert-consultation'

        checkout_session = stripe_service.create_expert_consultation_checkout(
            consultation_id=consultation_id,
            user_id=user_id,
            user_name=user_name,
            user_email=user_email,
            success_url=success_url,
            cancel_url=cancel_url
        )

        return jsonify({
            'success': True,
            'checkout_url': checkout_session['url'],
            'consultation_id': consultation_id
        })

    except Exception as e:
        logger.error(f"専門家相談作成エラー: {e}")
        return jsonify({
            'success': False,
            'error': 'システムエラーが発生しました'
        }), 500

@app.route('/expert-consultation/booking/<consultation_id>')
def expert_consultation_booking(consultation_id):
    """専門家相談の日時選択ページ（Google Calendar版）"""
    if not EXPERT_CONSULTATION_ENABLED:
        return render_template('error.html',
                             error_message='専門家相談システムが利用できません'), 500

    try:
        current_user = get_current_user()
        user_id = current_user.get('user_id') or current_user['id']

        # 相談情報を取得
        consultation = expert_consultation_service.get_consultation(consultation_id)
        if not consultation:
            return render_template('error.html',
                                 error_message='相談情報が見つかりません'), 404

        # 本人確認
        if consultation['user_id'] != user_id:
            return render_template('error.html',
                                 error_message='アクセス権限がありません'), 403

        # 決済完了チェック
        if consultation['status'] != 'paid':
            return render_template('error.html',
                                 error_message='決済が完了していません'), 400

        return render_template('consultation_booking.html',
                             consultation_id=consultation_id,
                             user_name=consultation['user_name'],
                             user_email=consultation['user_email'])

    except Exception as e:
        logger.error(f"相談予約ページエラー: {e}")
        return render_template('error.html',
                             error_message='システムエラーが発生しました'), 500

@app.route('/expert-consultation/success/<consultation_id>')
def expert_consultation_success(consultation_id):
    """専門家相談決済完了ページ"""
    # 認証はクライアント側のFirebaseで行う（ダッシュボードと同じ方式）
    if not EXPERT_CONSULTATION_ENABLED:
        return jsonify({'error': '専門家相談システムが利用できません'}), 500

    # consultation_idを渡してクライアント側で処理
    return render_template('consultation_success.html',
                         consultation_id=consultation_id)

@app.route('/api/expert-consultation/success/<consultation_id>')
@require_auth
def expert_consultation_success_api(consultation_id):
    """専門家相談決済完了ページのデータを取得するAPI"""
    if not EXPERT_CONSULTATION_ENABLED:
        return jsonify({'error': '専門家相談システムが利用できません'}), 500

    try:
        current_user = get_current_user()
        user_id = current_user.get('user_id') or current_user['id']

        # 相談情報を取得
        consultation = expert_consultation_service.get_consultation(consultation_id)
        if not consultation:
            return jsonify({'error': '相談情報が見つかりません'}), 404

        # 本人確認
        if consultation['user_id'] != user_id:
            return jsonify({'error': 'アクセス権限がありません'}), 403

        # Calendlyウィジェット生成
        calendly_widget = calendly_service.get_embedded_widget_html(
            consultation_id=consultation_id,
            user_email=consultation['user_email'],
            user_name=consultation['user_name']
        )

        # 決済日時をフォーマット
        payment_date = "決済処理中"
        if consultation.get('payment_completed_at'):
            from datetime import datetime
            payment_date = datetime.fromtimestamp(
                consultation['payment_completed_at']
            ).strftime('%Y年%m月%d日 %H:%M')

        return jsonify({
            'success': True,
            'consultation_id': consultation_id,
            'user_name': consultation['user_name'],
            'user_email': consultation['user_email'],
            'payment_date': payment_date,
            'calendly_widget': calendly_widget,
            'status': consultation.get('status', 'pending')
        })

    except Exception as e:
        logger.error(f"相談決済完了APIエラー: {e}")
        return jsonify({'error': 'システムエラーが発生しました'}), 500

@app.route('/expert-consultation/status/<consultation_id>')
@require_auth
def expert_consultation_status(consultation_id):
    """専門家相談ステータス確認ページ"""
    if not EXPERT_CONSULTATION_ENABLED:
        return jsonify({'error': '専門家相談システムが利用できません'}), 500

    try:
        current_user = get_current_user()
        user_id = current_user.get('user_id') or current_user['id']

        # 相談情報を取得
        consultation = expert_consultation_service.get_consultation(consultation_id)
        if not consultation:
            return render_template('error.html',
                                 error_message='相談情報が見つかりません'), 404

        # 本人確認
        if consultation['user_id'] != user_id:
            return render_template('error.html',
                                 error_message='アクセス権限がありません'), 403

        return jsonify(consultation)

    except Exception as e:
        logger.error(f"相談ステータス確認エラー: {e}")
        return render_template('error.html',
                             error_message='システムエラーが発生しました'), 500

# =====================================
# Google Calendar API エンドポイント
# =====================================

try:
    from google_calendar_service import google_calendar_service
    GOOGLE_CALENDAR_ENABLED = True
except ImportError:
    GOOGLE_CALENDAR_ENABLED = False
    logger.warning("Google Calendar service not available")

try:
    from consultation_schedule_service import consultation_schedule_service
    SCHEDULE_SERVICE_ENABLED = True
except ImportError:
    SCHEDULE_SERVICE_ENABLED = False
    logger.warning("Schedule service not available")

@app.route('/api/google-calendar/available-dates')
@require_auth
def get_available_dates():
    """利用可能な日付リストを取得"""
    if not GOOGLE_CALENDAR_ENABLED:
        return jsonify({'error': 'Google Calendar service not available'}), 500

    try:
        dates = google_calendar_service.get_available_dates()
        return jsonify({
            'success': True,
            'dates': dates
        })

    except Exception as e:
        logger.error(f"利用可能日取得エラー: {e}")
        return jsonify({'error': '利用可能な日付の取得に失敗しました'}), 500

@app.route('/api/google-calendar/time-slots')
@require_auth
def get_time_slots():
    """指定日の時間枠を取得"""
    if not GOOGLE_CALENDAR_ENABLED:
        return jsonify({'error': 'Google Calendar service not available'}), 500

    try:
        date_str = request.args.get('date')
        if not date_str:
            return jsonify({'error': '日付が必要です'}), 400

        slots = google_calendar_service.generate_time_slots(date_str)
        return jsonify({
            'success': True,
            'slots': slots
        })

    except Exception as e:
        logger.error(f"時間枠取得エラー: {e}")
        return jsonify({'error': '時間枠の取得に失敗しました'}), 500

@app.route('/api/google-calendar/book-consultation', methods=['POST'])
@require_auth
def book_consultation_slot():
    """相談枠を予約"""
    if not GOOGLE_CALENDAR_ENABLED:
        return jsonify({'error': 'Google Calendar service not available'}), 500

    try:
        current_user = get_current_user()
        data = request.json

        consultation_id = data.get('consultation_id')
        date_str = data.get('date')
        time_str = data.get('time')

        if not all([consultation_id, date_str, time_str]):
            return jsonify({'error': 'すべての項目を入力してください'}), 400

        # 相談情報を取得
        if EXPERT_CONSULTATION_ENABLED:
            consultation = expert_consultation_service.get_consultation(consultation_id)
            if not consultation:
                return jsonify({'error': '相談情報が見つかりません'}), 404

            user_name = consultation['user_name']
            user_email = consultation['user_email']
        else:
            # フォールバック
            user_name = current_user.get('name', 'ユーザー')
            user_email = current_user.get('email', 'user@example.com')

        # 予約実行
        result = google_calendar_service.book_consultation_slot(
            consultation_id=consultation_id,
            user_name=user_name,
            user_email=user_email,
            date_str=date_str,
            time_str=time_str
        )

        if result['success']:
            return jsonify({
                'success': True,
                'message': '予約が確定しました',
                'event_data': result['event_data']
            })
        else:
            return jsonify({'error': result['error']}), 400

    except Exception as e:
        logger.error(f"相談予約エラー: {e}")
        return jsonify({'error': '予約処理中にエラーが発生しました'}), 500

@app.route('/expert-consultation/confirmed/<consultation_id>')
@require_auth
def expert_consultation_confirmed(consultation_id):
    """専門家相談予約確定ページ（Google Calendar版）"""
    if not GOOGLE_CALENDAR_ENABLED:
        return render_template('error.html',
                             error_message='Google Calendar システムが利用できません'), 500

    try:
        current_user = get_current_user()
        user_id = current_user.get('user_id') or current_user['id']

        # 相談イベント情報を取得
        event_data = google_calendar_service.get_consultation_event(consultation_id)
        if not event_data:
            return render_template('error.html',
                                 error_message='相談情報が見つかりません'), 404

        return render_template('consultation_success.html',
                             consultation_id=consultation_id,
                             event_data=event_data,
                             user_name=event_data['user_name'],
                             user_email=event_data['user_email'])

    except Exception as e:
        logger.error(f"相談予約確定ページエラー: {e}")
        return render_template('error.html',
                             error_message='システムエラーが発生しました'), 500

# =====================================
# スケジュール管理API（管理者専用）
# =====================================

@app.route('/api/admin/schedule/business-hours', methods=['GET'])
@require_auth  # 実際は管理者認証が必要
def get_business_hours():
    """営業時間設定を取得"""
    if not SCHEDULE_SERVICE_ENABLED:
        return jsonify({'error': 'Schedule service not available'}), 500

    try:
        business_hours = consultation_schedule_service.get_business_hours()
        return jsonify({
            'success': True,
            'business_hours': business_hours
        })

    except Exception as e:
        logger.error(f"営業時間取得エラー: {e}")
        return jsonify({'error': '営業時間の取得に失敗しました'}), 500

@app.route('/api/admin/schedule/business-hours', methods=['POST'])
@require_auth  # 実際は管理者認証が必要
def save_business_hours():
    """営業時間設定を保存"""
    if not SCHEDULE_SERVICE_ENABLED:
        return jsonify({'error': 'Schedule service not available'}), 500

    try:
        data = request.json
        business_hours = data.get('business_hours')

        if not business_hours:
            return jsonify({'error': '営業時間データが必要です'}), 400

        success = consultation_schedule_service.save_business_hours(business_hours)

        if success:
            return jsonify({
                'success': True,
                'message': '営業時間を保存しました'
            })
        else:
            return jsonify({'error': '営業時間の保存に失敗しました'}), 500

    except Exception as e:
        logger.error(f"営業時間保存エラー: {e}")
        return jsonify({'error': '営業時間の保存中にエラーが発生しました'}), 500

@app.route('/api/admin/schedule/blocked-dates', methods=['GET'])
@require_auth  # 実際は管理者認証が必要
def get_blocked_dates():
    """予約不可日を取得"""
    if not SCHEDULE_SERVICE_ENABLED:
        return jsonify({'error': 'Schedule service not available'}), 500

    try:
        blocked_dates = consultation_schedule_service.get_blocked_dates()
        return jsonify({
            'success': True,
            'blocked_dates': blocked_dates
        })

    except Exception as e:
        logger.error(f"予約不可日取得エラー: {e}")
        return jsonify({'error': '予約不可日の取得に失敗しました'}), 500

@app.route('/api/admin/schedule/blocked-dates', methods=['POST'])
@require_auth  # 実際は管理者認証が必要
def add_blocked_date():
    """予約不可日を追加"""
    if not SCHEDULE_SERVICE_ENABLED:
        return jsonify({'error': 'Schedule service not available'}), 500

    try:
        data = request.json
        date_str = data.get('date')
        reason = data.get('reason', '')

        if not date_str:
            return jsonify({'error': '日付が必要です'}), 400

        success, message = consultation_schedule_service.add_blocked_date(date_str, reason)

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({'error': message}), 400

    except Exception as e:
        logger.error(f"予約不可日追加エラー: {e}")
        return jsonify({'error': '予約不可日の追加中にエラーが発生しました'}), 500

@app.route('/api/admin/schedule/blocked-dates', methods=['DELETE'])
@require_auth  # 実際は管理者認証が必要
def remove_blocked_date():
    """予約不可日を削除"""
    if not SCHEDULE_SERVICE_ENABLED:
        return jsonify({'error': 'Schedule service not available'}), 500

    try:
        data = request.json
        date_str = data.get('date')

        if not date_str:
            return jsonify({'error': '日付が必要です'}), 400

        success, message = consultation_schedule_service.remove_blocked_date(date_str)

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({'error': message}), 400

    except Exception as e:
        logger.error(f"予約不可日削除エラー: {e}")
        return jsonify({'error': '予約不可日の削除中にエラーが発生しました'}), 500

@app.route('/api/admin/schedule/blocked-time-slots', methods=['POST'])
@require_auth  # 実際は管理者認証が必要
def add_blocked_time_slot():
    """予約不可時間枠を追加"""
    if not SCHEDULE_SERVICE_ENABLED:
        return jsonify({'error': 'Schedule service not available'}), 500

    try:
        data = request.json
        date_str = data.get('date')
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        reason = data.get('reason', '')

        if not all([date_str, start_time, end_time]):
            return jsonify({'error': '日付、開始時間、終了時間が必要です'}), 400

        success, message = consultation_schedule_service.add_blocked_time_slot(
            date_str, start_time, end_time, reason
        )

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({'error': message}), 400

    except Exception as e:
        logger.error(f"予約不可時間追加エラー: {e}")
        return jsonify({'error': '予約不可時間の追加中にエラーが発生しました'}), 500

@app.route('/api/admin/schedule/blocked-time-slots', methods=['DELETE'])
@require_auth  # 実際は管理者認証が必要
def remove_blocked_time_slot():
    """予約不可時間枠を削除"""
    if not SCHEDULE_SERVICE_ENABLED:
        return jsonify({'error': 'Schedule service not available'}), 500

    try:
        data = request.json
        date_str = data.get('date')
        start_time = data.get('start_time')
        end_time = data.get('end_time')

        if not all([date_str, start_time, end_time]):
            return jsonify({'error': '日付、開始時間、終了時間が必要です'}), 400

        success, message = consultation_schedule_service.remove_blocked_time_slot(
            date_str, start_time, end_time
        )

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({'error': message}), 400

    except Exception as e:
        logger.error(f"予約不可時間削除エラー: {e}")
        return jsonify({'error': '予約不可時間の削除中にエラーが発生しました'}), 500

@app.route('/api/admin/schedule/summary')
@require_auth  # 実際は管理者認証が必要
def get_schedule_summary():
    """スケジュール概要を取得"""
    if not SCHEDULE_SERVICE_ENABLED:
        return jsonify({'error': 'Schedule service not available'}), 500

    try:
        summary = consultation_schedule_service.get_schedule_summary()

        if summary:
            return jsonify({
                'success': True,
                'summary': summary
            })
        else:
            return jsonify({'error': 'スケジュール概要の取得に失敗しました'}), 500

    except Exception as e:
        logger.error(f"スケジュール概要取得エラー: {e}")
        return jsonify({'error': 'スケジュール概要の取得中にエラーが発生しました'}), 500

# 管理者アカウント初期化（アプリ起動時）
if ADMIN_AUTH_ENABLED:
    try:
        admin_auth.initialize_admin()
        logger.info("管理者アカウント初期化完了")
    except Exception as e:
        logger.error(f"管理者アカウント初期化エラー: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)