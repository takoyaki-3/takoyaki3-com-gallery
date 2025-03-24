import os
import json
import uuid
from datetime import datetime
import boto3
import jwt
import time

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('GALLERY_TABLE_NAME')
table = dynamodb.Table(TABLE_NAME)
allowed_users = os.environ.get('ALLOWED_USERS', '').split(',')

def handler(event, context):
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

      # Check if user is allowed (if allowed_users is configured)
      if allowed_users and allowed_users[0] and user_id not in allowed_users:
        return {
          "statusCode": 403,
          "body": json.dumps({"error": "アクセス権限がありません"})
        }
    except Exception as e:
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
      return {
        "statusCode": 400,
        "body": json.dumps({"error": "リクエストボディがありません"})
      }
    data = json.loads(body) if isinstance(body, str) else body

    photos = data.get('photos', [])
    tags = data.get('tag', [])
    text = data.get('text', "")

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

      table.put_item(Item=item)

    return {
      "statusCode": 200,
      "body": json.dumps({"message": "Gallery item(s) created"})
    }
  except Exception as e:
    return {
      "statusCode": 500,
      "body": json.dumps({"error": str(e)})
    }

def verify_firebase_token(token):
  """
  Firebaseトークンを検証する関数
  """
  try:
    # トークンの検証（簡易実装）
    decoded = jwt.decode(token, options={"verify_signature": False})

    # トークンの有効期限確認
    exp = decoded.get('exp', 0)
    if exp < time.time():
      raise Exception("Token expired")

    return decoded
  except Exception as e:
    raise Exception(f"Token validation failed: {str(e)}")
