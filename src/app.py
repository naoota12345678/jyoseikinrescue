from flask import Flask, render_template, request, jsonify, session
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
    """助成金診断ページ"""
    return render_template('joseikin_diagnosis.html')

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
        
        # Claude APIに質問を送信
        response = get_claude_service().get_grant_consultation(company_info, question)
        
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

@app.route('/api/joseikin-diagnosis', methods=['POST'])
def joseikin_diagnosis():
    try:
        data = request.json
        diagnosis_data = data.get('diagnosis_data', {})
        
        # Claude AIを使用して包括的な助成金診断
        prompt = f"""
あなたは令和7年度雇用・労働分野の助成金の専門家です。以下の企業情報を基に、該当する可能性のある助成金をすべて判定してください。

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

以下の29カテゴリーから該当するものを判定し、具体的な支給額と適用条件を含めて回答してください：

1. 雇用調整助成金 2. 産業雇用安定助成金 3. 早期再就職支援等助成金 4. 特定求職者雇用開発助成金
5. トライアル雇用助成金 6. 地域雇用開発助成金 7. 人材確保等支援助成金 8. 通年雇用助成金
9. 65歳超雇用推進助成金 10. キャリアアップ助成金 11. 両立支援等助成金 12. 人材開発支援助成金
13. 障害者作業施設設置等助成金 14. 障害者福祉施設設置等助成金 15. 障害者介助等助成金
16. 職場適応援助者助成金 17. 重度障害者等通勤対策助成金 18. 重度障害者多数雇用事業所施設設置等助成金
19. 障害者雇用相談援助助成金 20. 障害者能力開発助成金 21. 職場適応訓練費 22. 業務改善助成金
23. 働き方改革推進支援助成金 24. 受動喫煙防止対策助成金 25. 団体経由産業保健活動推進助成金
26. 高度安全機械等導入支援補助金 27. エイジフレンドリー補助金 28. 個人ばく露測定定着促進補助金
29. 中小企業退職金共済制度に係る新規加入等掛金助成

該当する助成金について、適用可能性の高い順に最大10件まで、以下の情報を含めて具体的に回答してください：
- 助成金名（正確なコース名を含む）
- 支給額（具体的な金額）
- 適用要件（詳細な条件）
- 申請に必要な準備
- 専門エージェント名

可能性が低くても検討すべき助成金があれば、その理由も含めて言及してください。
"""
        
        # Claude AIに問い合わせ
        response = get_claude_service().chat(prompt, "")
        
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
        
        if not current_user.get('stripe_customer_id'):
            return jsonify({'error': 'Stripe顧客IDが設定されていません'}), 400
        
        data = request.json
        success_url = data.get('success_url', 'https://your-domain.com/success')
        cancel_url = data.get('cancel_url', 'https://your-domain.com/cancel')
        
        checkout_session = get_stripe_service().create_basic_plan_checkout(
            customer_id=current_user['stripe_customer_id'],
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
        
        if not current_user.get('stripe_customer_id'):
            return jsonify({'error': 'Stripe顧客IDが設定されていません'}), 400
        
        data = request.json
        success_url = data.get('success_url', 'https://your-domain.com/success')
        cancel_url = data.get('cancel_url', 'https://your-domain.com/cancel')
        
        checkout_session = get_stripe_service().create_additional_pack_checkout(
            customer_id=current_user['stripe_customer_id'],
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