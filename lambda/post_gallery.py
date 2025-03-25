import os
import json
import uuid
from datetime import datetime
import boto3
import jwt
import time
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
  Firebaseトークンを検証する関数
  """
  try:
    # # 実際のFirebaseプロジェクトIDを環境変数から取得
    # project_id = os.environ.get('FIREBASE_PROJECT_ID')
    # if not project_id:
    #   raise Exception("FIREBASE_PROJECT_ID environment variable is missing")

    # 公開鍵を取得して署名を検証
    jwks_url = f'https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com'
    jwks_client = jwt.PyJWKClient(jwks_url)
    signing_key = jwks_client.get_signing_key_from_jwt(token)

    # トークンの検証
    decoded = jwt.decode(
      token,
      signing_key.key,
      algorithms=["RS256"],
      # audience=project_id,
      # issuer=f'https://securetoken.google.com/{project_id}'
    )

    # トークンの有効期限確認
    exp = decoded.get('exp', 0)
    if exp < time.time():
      raise Exception("Token expired")

    return decoded
  except Exception as e:
    raise Exception(f"Token validation failed: {str(e)}")
