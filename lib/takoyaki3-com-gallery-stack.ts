import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as lambda from 'aws-cdk-lib/aws-lambda';

const prefix = 'takoyaki3-com-gallery';

export class Takoyaki3ComGalleryStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const galleryTable = new dynamodb.Table(this, 'GalleryTable', {
      tableName: `${prefix}-table`,
      partitionKey: { name: 'tag', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'uid-created_at', type: dynamodb.AttributeType.STRING },
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
    });

    const postGalleryHandler = new lambda.Function(this, 'PostGalleryHandler', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'post_gallery.handler',
      functionName: `${prefix}-post-gallery`,
      code: lambda.Code.fromAsset('lambda'),
      environment: {
        GALLERY_TABLE_NAME: galleryTable.tableName,
      },
      architecture: lambda.Architecture.ARM_64,
    });
    const getGalleryHandler = new lambda.Function(this, 'GetGalleryHandler', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'get_gallery.handler',
      functionName: `${prefix}-get-gallery`,
      code: lambda.Code.fromAsset('lambda'),
      environment: {
        GALLERY_TABLE_NAME: galleryTable.tableName,
      },
      architecture: lambda.Architecture.ARM_64,
    });

    galleryTable.grantWriteData(postGalleryHandler);
    galleryTable.grantReadData(getGalleryHandler);

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
