import json
import boto3
import os
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

# # Initialize the DynamoDB client
# # dynamodb = boto3.resource('dynamodb')
# # table = dynamodb.Table(os.environ['TABLE_NAME'])

# dynamodb_client = boto3.resource(
#     'dynamodb',
#     endpoint_url="http://host.docker.internal:8000",
#     region_name='us-west-2',  # Example region, you can set this to any valid AWS region
#     aws_access_key_id='fakeMyKeyId',  # Dummy credentials for local testing
#     aws_secret_access_key='fakeSecretAccessKey'
# )
# table = dynamodb_client.Table(os.environ['TABLE_NAME'])

# Check if the code is running locally
is_local = os.environ.get('IS_LOCAL', '') == 'true'

if is_local:
    # Connect to DynamoDB Local
    dynamodb_client = boto3.resource(
        'dynamodb',
        endpoint_url="http://host.docker.internal:8000",
        region_name='us-west-2',
        aws_access_key_id='fakeMyKeyId',
        aws_secret_access_key='fakeSecretAccessKey'
    )
else:
    # Connect to DynamoDB in AWS
    dynamodb_client = boto3.resource('dynamodb')

# Access the table
table_name = os.environ['TABLE_NAME']
table = dynamodb_client.Table(table_name)

def test_dynamodb_connection():
    try:
        # Try to get an item that does not necessarily exist
        response = table.get_item(Key={'appName': 'TestConnectionApp'})
        print("Connection Test Succeeded:", response)
        return True
    except Exception as e:
        print("Failed to connect to DynamoDB:", str(e))
        return False
    
def lambda_handler(event, context):
    # return response(os.environ['TABLE_NAME'], 200)
    
    # Test DynamoDB connection
    if not test_dynamodb_connection():
        return response('Failed to connect to DynamoDB', 500)
    
    try:
        operation = event['httpMethod']
        path = event['resource']
        params = event.get('queryStringParameters', {})
        
        if path == "/create-app" and operation == "POST":
            app_name = params.get('app_name')
            return create_app(app_name)
        elif path == "/{app_name}/version" and operation == "GET":
            app_name = event['pathParameters']['app_name']
            return get_version(app_name)
        elif path == "/{app_name}/bump" and operation == "POST":
            app_name = event['pathParameters']['app_name']
            version_type = params.get('type')
            return bump_version(app_name, version_type)
        elif path == "/{app_name}/set" and operation == "POST":
            app_name = event['pathParameters']['app_name']
            new_version = params.get('new_version')
            return set_version(app_name, new_version)
        else:
            return response('Invalid request', 400)
    except Exception as e:
        return response(str(e), 500)

def create_app(app_name):
    if not app_name:
        return response('Missing app_name', 400)
    
    try:
        result = table.get_item(Key={'appName': app_name})
        if 'Item' in result:
            return response('App already exists', 409)
        
        table.put_item(Item={'appName': app_name, 'version': '0.1.0'})
        return response('App created with version 0.1.0', 201)
    except ClientError as e:
        return response(e.response['Error']['Message'], 500)

def get_version(app_name):
    try:
        result = table.get_item(Key={'appName': app_name})
        if 'Item' not in result:
            return response('App not found', 404)
        return response({'version': result['Item']['version']}, 200)
    except ClientError as e:
        return response(e.response['Error']['Message'], 500)

def bump_version(app_name, version_type):
   if not version_type or version_type not in ['major', 'minor', 'patch']:
       return response('Invalid or missing version type', 400)

   try:
       result = table.get_item(Key={'appName': app_name})
       if 'Item' not in result:
           initial_versions = {
               'major': '1.0.0',
               'minor': '0.1.0',
               'patch': '0.0.1'
           }
           initial_version = initial_versions[version_type]
           table.put_item(Item={'appName': app_name, 'version': initial_version})
           return response(f"App created with version {initial_version}", 201)
       else:
           current_version = result['Item']['version']
           major, minor, patch = [int(part) for part in current_version.split('.')]

           if version_type == 'major':
               new_version = f"{major + 1}.0.0"
           elif version_type == 'minor':
               new_version = f"{major}.{minor + 1}.0"
           else:  # version_type is 'patch'
               new_version = f"{major}.{minor}.{patch + 1}"

           table.update_item(
               Key={'appName': app_name},
               UpdateExpression='SET version = :v',
               ExpressionAttributeValues={':v': new_version}
           )
           return response({'new_version': new_version}, 200)
   except ClientError as e:
       return response(e.response['Error']['Message'], 500)



def set_version(app_name, new_version):
    if not new_version:
        return response('Missing new_version', 400)

    try:
        table.update_item(
            Key={'appName': app_name},
            UpdateExpression='SET version = :v',
            ExpressionAttributeValues={':v': new_version}
        )
        return response({'new_version': new_version}, 200)
    except ClientError as e:
        return response(e.response['Error']['Message'], 500)

def response(message, status_code):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'  # CORS configuration if necessary
        },
        'body': json.dumps(message) if isinstance(message, dict) else message
    }


