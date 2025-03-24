import os
import tempfile
import subprocess
import boto3
import zipfile

s3 = boto3.client('s3')

def handler(event, context):
  """
  カスタムリソースから呼ばれて、指定された "<module>==<version>" パッケージを
  pip install し、モジュール名==バージョン.zip というファイル名で S3 にアップロードする。
  """
  # カスタムリソースのイベント
  request_type = event.get('RequestType')
  props = event.get('ResourceProperties', {})

  # 取りたいパラメータ: "PackageName" (例: "requests==2.31.0"), "OutputBucket" など
  package_name_and_version = props.get('PackageName')  # "requests==2.31.0" の想定
  output_bucket = props.get('OutputBucket')
  # Delete イベントなら何もしないで成功返す
  if request_type == 'Delete':
    return cfn_response('SUCCESS', "Delete request")

  if not package_name_and_version or not output_bucket:
    return cfn_response('FAILED', f"PackageName or OutputBucket not specified")

  # ZIP 名を作る ("requests==2.31.0.zip" のように)
  zip_filename = f"{package_name_and_version}.zip"

  # /tmp に作業ディレクトリを作る
  with tempfile.TemporaryDirectory() as tmpdir:
    python_dir = os.path.join(tmpdir, 'python')
    os.mkdir(python_dir)

    # pip install
    cmd = [
      'pip', 'install',
      package_name_and_version,
      '-t', python_dir,
      '--no-cache-dir'
    ]
    try:
      subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
      return cfn_response('FAILED', f"pip install failed: {str(e)}")

    # ZIP 化
    zip_path = os.path.join(tmpdir, zip_filename)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
      for root, dirs, files in os.walk(tmpdir):
        for file in files:
          file_path = os.path.join(root, file)
          # ZIP 内でのパスを決める (python/ 以下に入れる)
          arcname = os.path.relpath(file_path, tmpdir)
          zf.write(file_path, arcname)

    # S3 にアップロード
    # 同名ファイルがすでに存在すると上書きになるため、必要に応じて時間などを付与してもOK
    try:
      s3.upload_file(zip_path, output_bucket, zip_filename)
    except Exception as e:
      return cfn_response('FAILED', f"S3 upload failed: {str(e)}")

  # 成果物のキーを応答
  data = {
    "OutputKey": zip_filename
  }
  return cfn_response('SUCCESS', "Build success", data)


def cfn_response(status, reason, data=None):
  """
  カスタムリソース (CFN) に返す形式のレスポンス。
  ただし実際には、CDK の Provider 経由の場合はこの戻り値がそのまま
  CloudFormation に返るわけではなく、内部で JSON シリアライズされる。
  """
  response = {
    'Status': status,
    'Reason': reason,
  }
  if data:
    response['Data'] = data
  return response