# 2025-09-18 専門家相談予約システム設計セッション

## セッション概要
- **日時**: 2025-09-18
- **要求**: 専門家相談（30分14,300円）の支払い・予約フロー構築
- **方針**: 円山動物病院システムの手法を参考にした実装

## 課題分析

### 現在の状況
- 専門家相談システムは決済のみ実装済み
- 決済後の予約管理機能が未実装
- 顧客は決済後に別途予約を取る必要がある

### 要求される機能
1. 決済 → 予約の一連フロー
2. Calendly連携による予約管理
3. 管理者による予約確認機能
4. 自動化されたZoom URL送信（将来実装）

## 設計案検討

### 参考システム: 円山動物病院
**優れた点**:
1. 決済 → 予約の明確な2段階フロー
2. Calendly連携による予約管理
3. Firestoreでの予約情報管理
4. 管理者ダッシュボードでの予約確認

### 提案する3つの実装案

#### 案1: 最小限実装（推奨） 🎯

**フロー**:
```
現在: 専門家相談ページ → 支払い・ご予約に進む → Stripe決済
     ↓
改良: 専門家相談ページ → 支払い・ご予約に進む → Stripe決済 → Calendly予約画面
```

**実装方法**:
```python
# 既存の決済成功ページを拡張
@app.route('/consultation/payment-success')
def consultation_payment_success():
    session_id = request.args.get('session_id')

    # 決済情報を確認
    session = stripe.checkout.Session.retrieve(session_id)

    # 予約情報をFirestoreに保存
    appointment_data = {
        'user_id': current_user['user_id'],
        'user_email': current_user['email'],
        'payment_session_id': session_id,
        'amount': 14300,
        'status': 'payment_completed',
        'booking_status': 'pending',  # 予約待ち
        'created_at': datetime.now()
    }

    save_appointment_data(appointment_data)

    # CalendlyのURLを表示
    return render_template('consultation_payment_success.html',
                         calendly_url="https://calendly.com/your-account/30min",
                         appointment_id=appointment_data['id'])
```

#### 案2: 円山動物病院方式 🏥

**フロー**:
```
1. 決済完了
   ↓
2. 予約情報をFirestoreに保存
   ↓
3. Calendly埋め込み画面表示
   ↓
4. 顧客が日時選択
   ↓
5. Calendly Webhook → 予約確定
   ↓
6. Zoom URL自動送信
```

**実装方法**:
```python
# Calendly Webhook処理
@app.route('/webhook/calendly', methods=['POST'])
def calendly_webhook():
    event = request.json

    if event['event'] == 'invitee.created':
        # 予約確定処理
        invitee_email = event['payload']['email']
        event_start_time = event['payload']['start_time']

        # FirestoreのappointmentをCalendly情報で更新
        update_appointment_with_calendly_data(
            invitee_email,
            event['payload']
        )

        # Zoom URL送信
        send_zoom_url_email(invitee_email, event_start_time)

    return jsonify({'status': 'success'})
```

#### 案3: シンプル統合版 ⚡

**フロー**:
```
1. 専門家相談ページ
   ↓
2. 「支払い・ご予約に進む」
   ↓
3. Stripe決済
   ↓
4. 決済成功ページにCalendly埋め込み表示
   ↓
5. その場で予約完了
```

**UI設計**:
```html
<!-- 決済成功ページに追加 -->
<div class="payment-success-container">
    <h2>✅ 決済完了</h2>
    <p>お疲れ様でした！続いて面談日時をご選択ください。</p>

    <!-- Calendly埋め込み -->
    <div class="calendly-inline-widget"
         data-url="https://calendly.com/your-account/30min"
         style="min-width:320px;height:700px;">
    </div>

    <script src="https://assets.calendly.com/assets/external/widget.js"></script>
</div>
```

## 既存システムへの影響分析

### ✅ 既存機能への影響ゼロの理由

1. **完全に独立した新機能追加**
```python
# 既存（変更なし）
@app.route('/api/payment/consultation', methods=['POST'])  # 既存の決済API
@app.route('/consultation/payment-success')  # 既存の成功ページ

# 新規追加（既存と分離）
@app.route('/webhook/calendly', methods=['POST'])  # 新規Webhook
@app.route('/admin/appointments')  # 新規管理画面
```

2. **既存のStripe決済フローは完全保持**
```
# 現在の動作（変更なし）
1. 専門家相談ページ
2. 「支払い・ご予約に進む」ボタン
3. Stripe決済（/api/payment/consultation）
4. 決済成功ページ表示

# 新規追加（既存フローの後に追加）
5. + Calendly予約画面表示  # 👈 新機能のみ追加
6. + 予約情報をFirestoreに保存  # 👈 新機能のみ追加
```

3. **データベース構造も安全**
```
// 既存のFirestoreコレクション（変更なし）
users/        // ユーザー情報
subscriptions/  // サブスク情報
payments/     // 決済情報

// 新規追加のみ
appointments/  // 👈 新しいコレクション
```

## 推奨実装順序 📋

### Phase 1: 基本予約機能
1. 決済成功ページにCalendly埋め込み（案3）
2. 予約情報のFirestore保存
3. 管理者予約確認画面

### Phase 2: 高度な機能
1. Calendly Webhook連携（案2）
2. 自動Zoom URL送信
3. 予約キャンセル機能

### Phase 3: 管理機能強化
1. 管理者用予約管理ダッシュボード
2. 追加請求システム連携
3. 予約統計・レポート

## 結論

**推奨**: 案3（シンプル統合版）から始めて、段階的に案2の機能を追加する方法
- 既存システムを壊さず、確実に動作
- 円山動物病院方式でも既存実装への影響は100%ゼロ
- 将来的な拡張性も確保

**安全性**: どの案でも既存システムは完全に保護される
1. 既存APIを一切変更しない
2. 新しいエンドポイントのみ追加
3. 既存テンプレートに新セクション追加のみ
4. 新機能エラー時も既存機能は動作
5. 段階的実装可能