import jwt
import hashlib
import datetime

class JWTManager:
    """
    Manages JWT (JSON Web Token) operations, including creation and verification. 
    The class uses a provided secret key for token encoding and decoding.
    """
    def __init__(self, secret_key):
        self.secret_key = secret_key

    def create_jwt(self, app_name, expiry_days):
        """
        Creates a JWT with a specified application name and expiry period.
        """
        payload = {
            'app_name': app_name,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=expiry_days)
        }
        return jwt.encode(payload, self.secret_key, algorithm='HS256')

    def verify_jwt(self, token, db_operations, app_name):
        """
        Verifies a JWT against a provided token and application name.
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            if payload.get('app_name') == app_name:
                result = db_operations.get_item({'appName': app_name})
                if 'tokenHash' in result['Item']:
                    token_hash = result['Item']['tokenHash']
                    return hashlib.sha256(token.encode()).hexdigest() == token_hash
            return False
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return False
