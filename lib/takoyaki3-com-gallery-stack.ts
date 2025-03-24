import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as path from 'path';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as logs from 'aws-cdk-lib/aws-logs';

const prefix = 'takoyaki3-com-gallery';

export class Takoyaki3ComGalleryStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // レイヤーパッケージ保存用のバケット作成
    const layerBucket = new s3.Bucket(this, 'LayerBucket', {
      bucketName: `${prefix}-layer-bucket-${this.stackName}`.toLowerCase(),
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // レイヤー作成用 Lambda の定義
    const buildLayerLambda = new lambda.Function(this, 'BuildLayerLambda', {
      functionName: `${prefix}-build-layer-${this.stackName}`,
      runtime: lambda.Runtime.PYTHON_3_10,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../build-layer-lambda')),
      architecture: lambda.Architecture.ARM_64,
      timeout: cdk.Duration.minutes(5),
      memorySize: 1024,
    });

    // Lambda にバケットへの読み書き権限を付与
    layerBucket.grantWrite(buildLayerLambda);
    layerBucket.grantRead(buildLayerLambda);

    // カスタムリソースプロバイダー作成（ログ保持も設定）
    const buildLayerProvider = new cr.Provider(this, 'BuildLayerProvider', {
      onEventHandler: buildLayerLambda,
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // カスタムリソースを利用して Python レイヤーを作成する関数
    const createPythonLayer = (id: string, description: string, packageName: string): lambda.LayerVersion => {
      const buildResource = new cdk.CustomResource(this, `Build${id}Resource`, {
        serviceToken: buildLayerProvider.serviceToken,
        resourceType: 'Custom::BuildSingleLayer',
        properties: {
          PackageName: packageName,
          OutputBucket: layerBucket.bucketName,
        },
      });

      // カスタムリソースのレスポンスから S3 キー (OutputKey) を取得
      const builtZipKey = buildResource.getAttString('OutputKey');
      console.log(`Layer ${id} S3 Key: ${builtZipKey}`);

      // S3 上の ZIP ファイルからレイヤーを作成
      return new lambda.LayerVersion(this, id, {
        code: lambda.Code.fromBucket(layerBucket, builtZipKey),
        compatibleRuntimes: [lambda.Runtime.PYTHON_3_10],
        description: description,
      });
    };

    // 必要なレイヤーの作成
    const requestsLayer = createPythonLayer(
      'RequestsLayer',
      'Layer containing the requests library',
      'requests==2.32.3'
    );

    const pilLayer = createPythonLayer(
      'PilLayer',
      'Layer containing the Pillow library',
      'Pillow==10.2.0'
    );

    // DynamoDB テーブルの作成
    const galleryTable = new dynamodb.Table(this, 'GalleryTable', {
      tableName: `${prefix}-table`,
      partitionKey: { name: 'tag', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'uid-created_at', type: dynamodb.AttributeType.STRING },
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
    });

    // POST 用 Lambda 関数
    const postGalleryHandler = new lambda.Function(this, 'PostGalleryHandler', {
      runtime: lambda.Runtime.PYTHON_3_10,
      handler: 'post_gallery.handler',
      functionName: `${prefix}-post-gallery`,
      code: lambda.Code.fromAsset('lambda'),
      environment: {
        GALLERY_TABLE_NAME: galleryTable.tableName,
      },
      architecture: lambda.Architecture.ARM_64,
      layers: [requestsLayer, pilLayer],
    });

    // GET 用 Lambda 関数
    const getGalleryHandler = new lambda.Function(this, 'GetGalleryHandler', {
      runtime: lambda.Runtime.PYTHON_3_10,
      handler: 'get_gallery.handler',
      functionName: `${prefix}-get-gallery`,
      code: lambda.Code.fromAsset('lambda'),
      environment: {
        GALLERY_TABLE_NAME: galleryTable.tableName,
      },
      architecture: lambda.Architecture.ARM_64,
    });

    // 必要な権限の付与
    galleryTable.grantWriteData(postGalleryHandler);
    galleryTable.grantReadData(getGalleryHandler);

    // API Gateway の設定
    const api = new apigateway.RestApi(this, 'GalleryApi', {
      restApiName: 'Gallery Service',
      description: 'This service serves gallery.',
    });

    const postGalleryIntegration = new apigateway.LambdaIntegration(postGalleryHandler);
    const getGalleryIntegration = new apigateway.LambdaIntegration(getGalleryHandler);

    const gallery = api.root.addResource('gallery');
    gallery.addMethod('POST', postGalleryIntegration);
    gallery.addMethod('GET', getGalleryIntegration);
  }
}
