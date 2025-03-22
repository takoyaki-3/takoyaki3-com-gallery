import os
import json
import uuid
from datetime import datetime
import boto3

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('GALLERY_TABLE_NAME')
table = dynamodb.Table(TABLE_NAME)

def handler(event, context):
  try:
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
      # ユニークなID生成
      unique_id = str(uuid.uuid4())
      now = datetime.now()
      ms = int(now.microsecond / 1000)
      created_at = now.strftime("%Y%m%d-%H%M%S") + f".{ms:03d}"
      sort_key = f"{unique_id}-{created_at}"

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
