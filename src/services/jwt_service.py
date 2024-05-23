import jwt
import hashlib
import datetime
import boto3
from botocore.exceptions import ClientError
import logging
import json

class JWTManager:
    """
    Manages JWT (JSON Web Token) operations, including creation and verification. 
    The class uses a provided secret key for token encoding and decoding.
    """
    def __init__(self, secret_name=None, secrets_client=None):
        self.client = secrets_client or boto3.client('secretsmanager')
        
        if secret_name:
            self.secret_key = self._get_secret_from_secrets_manager(secret_name)
        else:
            raise ValueError("secret_name must be provided")

    def _get_secret_from_secrets_manager(self, secret_name):
        """
        Fetches the secret key from AWS Secrets Manager.
        """
        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            secret = json.loads(response['SecretString'])
            return secret['JWT_SECRET']  # Adjust field name as per your secret structure
        except ClientError as e:
            logging.error(f"Unable to retrieve secret {secret_name}: {str(e)}")
            raise e

    def create_jwt(self, app_name, expiry_days):
        """
        Creates a JWT with a specified application name and expiry period.
        """
        expiry_date = datetime.datetime.utcnow() + datetime.timedelta(days=expiry_days)
        payload = {'app_name': app_name, 'exp': expiry_date}
        token = jwt.encode(payload, self.secret_key, algorithm='HS256')
        return token

    def verify_jwt(self, token, db_operations, app_name):
        """
        Verifies a JWT against a provided token and application name.
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            if payload.get('app_name') == app_name:
                result = db_operations.get_item({'appName': app_name})
                if 'tokenHash' in result['Item']:
                    token_hash = hashlib.sha256(token.encode()).hexdigest()
                    return token_hash == result['Item']['tokenHash']
            return False
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as e:
            logging.error(f"Token verification failed: {str(e)}")
            return False
