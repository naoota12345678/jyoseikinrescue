<?php
/**
 * さくらサーバー用メール送信スクリプト
 * このファイルをさくらのレンタルサーバーにアップロードしてください
 * 設置場所例: https://jyoseikin.jp/api/send_mail.php
 */

// エラー表示（本番環境では無効化してください）
// error_reporting(E_ALL);
// ini_set('display_errors', 1);

// CORS設定（Cloud Runからのアクセスを許可）
header('Access-Control-Allow-Origin: https://jyoseikinrescue-453016168690.asia-northeast1.run.app');
header('Access-Control-Allow-Methods: POST');
header('Access-Control-Allow-Headers: Content-Type, X-API-Key');
header('Content-Type: application/json; charset=UTF-8');

// プリフライトリクエスト対応
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    exit(0);
}

// 簡易認証（セキュリティトークン）
$API_KEY = 'jyoseikin_rescue_2024_secure_key_xyz789';  // この値は変更してください

// APIキーチェック
$headers = getallheaders();
if (!isset($headers['X-API-Key']) || $headers['X-API-Key'] !== $API_KEY) {
    http_response_code(401);
    echo json_encode(['error' => 'Unauthorized']);
    exit;
}

// POSTデータを取得
$input = json_decode(file_get_contents('php://input'), true);

if (!$input) {
    http_response_code(400);
    echo json_encode(['error' => 'Invalid JSON']);
    exit;
}

// 必須パラメータチェック
if (!isset($input['to']) || !isset($input['subject']) || !isset($input['body'])) {
    http_response_code(400);
    echo json_encode(['error' => 'Missing required parameters']);
    exit;
}

// メール送信設定
$to = $input['to'];
$subject = $input['subject'];
$body = $input['body'];
$is_html = isset($input['is_html']) ? $input['is_html'] : false;

// 送信者設定
$from = 'rescue@jyoseikin.jp';
$from_name = '助成金レスキュー';

// メールヘッダー設定
$headers = [
    'From' => "$from_name <$from>",
    'Reply-To' => $from,
    'X-Mailer' => 'PHP/' . phpversion()
];

// HTMLメールの場合
if ($is_html) {
    $headers['MIME-Version'] = '1.0';
    $headers['Content-Type'] = 'text/html; charset=UTF-8';
} else {
    $headers['Content-Type'] = 'text/plain; charset=UTF-8';
}

// ヘッダーを文字列に変換
$header_string = '';
foreach ($headers as $key => $value) {
    $header_string .= "$key: $value\r\n";
}

// 日本語対応
mb_language('Japanese');
mb_internal_encoding('UTF-8');

// メール送信
try {
    $result = mb_send_mail($to, $subject, $body, $header_string);

    if ($result) {
        echo json_encode([
            'success' => true,
            'message' => 'Email sent successfully',
            'to' => $to
        ]);
    } else {
        http_response_code(500);
        echo json_encode([
            'success' => false,
            'error' => 'Failed to send email'
        ]);
    }
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode([
        'success' => false,
        'error' => 'Exception: ' . $e->getMessage()
    ]);
}
?>