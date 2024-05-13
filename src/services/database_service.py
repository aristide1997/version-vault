import boto3
import os

class DynamoDBOperations:
    def __init__(self, client=None):
        if client:
            self.client = client
        else:
            is_local = os.environ.get('IS_LOCAL', '') == 'true'
            if is_local:
                self.client = boto3.resource(
                    'dynamodb',
                    endpoint_url="http://host.docker.internal:8000",
                    region_name='us-west-2',
                    aws_access_key_id='fakeMyKeyId',
                    aws_secret_access_key='fakeSecretAccessKey'
                )
            else:
                self.client = boto3.resource('dynamodb')
        
        self.table = self.client.Table(os.environ['TABLE_NAME'])

    def get_item(self, key):
        try:
            return self.table.get_item(Key=key)
        except Exception as e:
            raise Exception(f"Error getting item: {str(e)}")

    def put_item(self, item):
        try:
            self.table.put_item(Item=item)
        except Exception as e:
            raise Exception(f"Error putting item: {str(e)}")

    def update_item(self, key, expression, values):
        try:
            self.table.update_item(Key=key, UpdateExpression=expression, ExpressionAttributeValues=values)
        except Exception as e:
            raise Exception(f"Error updating item: {str(e)}")
