<?php
/**
 * さくらサーバー用メール送信スクリプト（改善版）
 */

// エラー表示（デバッグ用）
error_reporting(E_ALL);
ini_set('display_errors', 1);

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
$API_KEY = 'jyoseikin_rescue_2024_secure_key_xyz789';

// APIキーチェック
$headers = getallheaders();
if (!isset($headers['X-API-Key']) || $headers['X-API-Key'] !== $API_KEY) {
    http_response_code(401);
    echo json_encode(['error' => 'Unauthorized']);
    exit;
}

// 日本語対応を最初に設定
mb_language('Japanese');
mb_internal_encoding('UTF-8');

// POSTデータを取得
$raw_input = file_get_contents('php://input');
$input = json_decode($raw_input, true);

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

// 送信者設定
$from = 'rescue@jyoseikin.jp';
$from_name = '助成金レスキュー';

// メールヘッダー作成（シンプル版）
$from_header = mb_encode_mimeheader($from_name, 'UTF-8', 'B') . " <$from>";
$headers = "From: $from_header\r\n";
$headers .= "Reply-To: $from\r\n";
$headers .= "Content-Type: text/plain; charset=UTF-8\r\n";
$headers .= "Content-Transfer-Encoding: 8bit\r\n";
$headers .= "X-Mailer: PHP/" . phpversion();

// デバッグ情報
$debug_info = [
    'body_length' => mb_strlen($body),
    'body_preview' => mb_substr($body, 0, 100),
    'encoding' => mb_detect_encoding($body)
];

// メール送信
try {
    // メール本文を確実にUTF-8に変換
    $body_utf8 = mb_convert_encoding($body, 'UTF-8', 'auto');

    // mb_send_mailで送信
    $result = mb_send_mail($to, $subject, $body_utf8, $headers);

    if ($result) {
        echo json_encode([
            'success' => true,
            'message' => 'Email sent successfully',
            'to' => $to,
            'debug' => $debug_info
        ], JSON_UNESCAPED_UNICODE);
    } else {
        // メール送信失敗ログを記録（不正検知用）
        $client_ip = $_SERVER['HTTP_X_FORWARDED_FOR'] ?? $_SERVER['HTTP_X_REAL_IP'] ?? $_SERVER['REMOTE_ADDR'] ?? 'unknown';
        $log_entry = json_encode([
            'timestamp' => date('Y-m-d H:i:s'),
            'email' => $to,
            'ip' => $client_ip,
            'reason' => 'send_failure',
            'user_agent' => $_SERVER['HTTP_USER_AGENT'] ?? 'unknown'
        ], JSON_UNESCAPED_UNICODE) . "\n";

        // ログファイルに記録（エラーでも既存処理に影響させない）
        try {
            file_put_contents(__DIR__ . '/logs/failed_emails.log', $log_entry, FILE_APPEND | LOCK_EX);
        } catch (Exception $log_error) {
            // ログ記録失敗しても既存処理には影響させない
            error_log("Failed to write email failure log: " . $log_error->getMessage());
        }

        http_response_code(500);
        echo json_encode([
            'success' => false,
            'error' => 'Failed to send email',
            'debug' => $debug_info
        ], JSON_UNESCAPED_UNICODE);
    }
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode([
        'success' => false,
        'error' => 'Exception: ' . $e->getMessage(),
        'debug' => $debug_info
    ], JSON_UNESCAPED_UNICODE);
}
?>