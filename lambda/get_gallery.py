import os
import json
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('GALLERY_TABLE_NAME')
table = dynamodb.Table(TABLE_NAME)

def handler(event, context):
  try:
    # クエリパラメータ "tag" を取得
    params = event.get('queryStringParameters')
    if params is None or 'tag' not in params:
      return {
        "statusCode": 400,
        "body": json.dumps({"error": "クエリパラメータ 'tag' がありません"})
      }
    tag_value = params.get('tag')

    # DynamoDB の Query で該当のパーティションキーを検索
    response = table.query(
      KeyConditionExpression=Key('tag').eq(tag_value)
    )

    items = response.get('Items', [])

    # 必要に応じて uid-created_at など不要な属性を除去できますが、ここではそのまま返します
    return {
      "statusCode": 200,
      "body": json.dumps({"items": items})
    }
  except Exception as e:
    return {
      "statusCode": 500,
      "body": json.dumps({"error": str(e)})
    }
