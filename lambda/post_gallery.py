import os
import json
from datetime import datetime
import boto3
import firebase_admin
import logging

# ロガーの設定
logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('GALLERY_TABLE_NAME')
table = dynamodb.Table(TABLE_NAME)
allowed_users = os.environ.get('ALLOWED_USERS', '').split(',')

def handler(event, context):
  logger.info('Received event: %s', json.dumps(event))
  try:
    # Verify authentication token
    token = event.get('headers', {}).get('Authorization', '').replace('Bearer ', '')
    if not token:
      return {
        "statusCode": 401,
        "body": json.dumps({"error": "認証トークンがありません"})
      }

    try:
      # Verify Firebase token
      decoded_token = verify_firebase_token(token)
      user_id = decoded_token.get('user_id')
      logger.info('Authenticated user: %s', user_id)

      # Check if user is allowed (if allowed_users is configured)
      if allowed_users and allowed_users[0] and user_id not in allowed_users:
        logger.warning('User %s is not allowed', user_id)
        return {
          "statusCode": 403,
          "body": json.dumps({"error": "アクセス権限がありません"})
        }
    except Exception as e:
      logger.error('Token verification failed: %s', str(e), exc_info=True)
      return {
        "statusCode": 401,
        "body": json.dumps({
          "error": "無効な認証トークンです",
          "details": str(e)
        })
      }

    # リクエストボディの取得（JSONパース）
    body = event.get('body')
    if body is None:
      logger.error('Request body is missing')
      return {
        "statusCode": 400,
        "body": json.dumps({"error": "リクエストボディがありません"})
      }
    try:
      data = json.loads(body) if isinstance(body, str) else body
    except json.JSONDecodeError as e:
      logger.error('Invalid JSON body: %s', str(e), exc_info=True)
      return {
        "statusCode": 400,
        "body": json.dumps({"error": "無効なJSON形式です"})
      }

    photos = data.get('photos', [])
    tags = data.get('tag', [])
    text = data.get('text', "")
    logger.info('Processing request with %d photos and %d tags', len(photos), len(tags))

    # tag 配列が空の場合は空文字列を利用
    if not tags:
      tags = [""]

    # 各 tag ごとにアイテムを作成
    for single_tag in tags:
      now = datetime.now()
      ms = int(now.microsecond / 1000)
      created_at = now.strftime("%Y%m%d-%H%M%S") + f".{ms:03d}"
      sort_key = f"{user_id}-{created_at}"

      item = {
        "tag": single_tag,
        "uid-created_at": sort_key,
        "photos": photos,
        "text": text
      }

      try:
        response = table.put_item(Item=item)
        logger.debug('DynamoDB put_item response: %s', response)
      except Exception as e:
        logger.error('Failed to put item to DynamoDB: %s', str(e), exc_info=True)
        raise

    logger.info('Successfully created gallery items')
    return {
      "statusCode": 200,
      "body": json.dumps({"message": "Gallery item(s) created"})
    }
  except Exception as e:
    logger.error('Unhandled exception: %s', str(e), exc_info=True)
    return {
      "statusCode": 500,
      "body": json.dumps({"error": "内部サーバーエラーが発生しました"})
    }

def verify_firebase_token(token):
  """
  Firebaseトークンを検証する関数 (Firebase Admin SDKを使用)
  """
  try:
    # Firebase Admin SDKの初期化 (初回のみ)
    if not firebase_admin._apps:
      # 環境変数からサービスアカウントキーを取得
      service_account_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON')
      if service_account_json:
        # JSON文字列から認証情報を生成
        cred = firebase_admin.credentials.Certificate(
          json.loads(service_account_json))
      else:
        # Application Default Credentialsを使用
        cred = firebase_admin.credentials.ApplicationDefault()
      firebase_admin.initialize_app(cred)

    # トークンの検証
    decoded_token = auth.verify_id_token(token)
    print(f"Decoded token: {decoded_token}")
    return decoded_token
  except Exception as e:
    raise Exception(f"Token validation failed: {str(e)}")
