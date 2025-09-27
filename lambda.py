import json
import boto3
import datetime
import base64
import traceback

# AWS Clients
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

# Fixed values from your environment
BUCKET_NAME = "faster-upload-file"
TABLE_NAME  = "FileMetadata"
TOPIC_ARN   = "arn:aws:sns:ap-south-1:533267287744:FileUploadTopic"

def lambda_handler(event, context):
    try:
        print("EVENT:", json.dumps(event)[:1000])  # log first 1000 chars

        # 1) Get filename from query string
        qs = event.get('queryStringParameters') or {}
        filename = qs.get('filename')
        if not filename:
            raise ValueError("Missing query parameter: filename. Use ?filename=file.text")

        # 2) Get file body
        if event.get('isBase64Encoded'):
            body_bytes = base64.b64decode(event.get('body') or "")
        else:
            body = event.get('body') or ""
            if isinstance(body, str):
                body_bytes = body.encode('utf-8')
            else:
                body_bytes = str(body).encode('utf-8')

        # 3) Upload to S3
        s3.put_object(Bucket=BUCKET_NAME, Key=filename, Body=body_bytes)
        print(f"Uploaded to S3: s3://{BUCKET_NAME}/{filename} (size={len(body_bytes)})")

        # 4) Save metadata to DynamoDB
        table = dynamodb.Table(TABLE_NAME)
        item = {
            'filename': filename,
            'filesize': len(body_bytes),
            'upload_time': datetime.datetime.utcnow().isoformat()
        }
        table.put_item(Item=item)
        print("DynamoDB put_item:", item)

        # 5) Publish SNS notification
        sns.publish(
            TopicArn=TOPIC_ARN,
            Subject="New File Upload Notification",
            Message=f"File '{filename}' uploaded to bucket '{BUCKET_NAME}'. Size={len(body_bytes)} bytes."
        )
        print("SNS published")

        # 6) Return success
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "File uploaded successfully ✅",
                "file_url": f"https://{BUCKET_NAME}.s3.amazonaws.com/{filename}"
            }),
            "headers": {"Content-Type": "application/json"}
        }

    except Exception as e:
        # full traceback in CloudWatch logs
        tb = traceback.format_exc()
        print("ERROR TRACEBACK:\n", tb)

        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e),
                "hint": "Check CloudWatch logs for full traceback"
            }),
            "headers": {"Content-Type": "application/json"}
        }
