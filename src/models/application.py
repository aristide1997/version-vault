from services import DynamoDBOperations, JWTManager
from utilities import ResponseHandler, ErrorMessages

class Application:
    def __init__(self, app_name, db_operations=None):
        self.app_name = app_name
        self.db_operations = db_operations or DynamoDBOperations()
        self.response_handler = ResponseHandler()
        self.load_app()

    def load_app(self):
        """Load application details from the database."""
        result = self.db_operations.get_item({'appName': self.app_name})
        if 'Item' in result:
            self.version = result['Item']['version']
            self.secure = result['Item'].get('secure', False)
            self.token_hash = result['Item'].get('tokenHash', None)
            self.token_expiry_days = result['Item'].get('tokenExpiryDays', None)
        else:
            raise ValueError(ErrorMessages.APP_NOT_FOUND)
            # return self.response_handler.response(ErrorMessages.APP_NOT_FOUND, 404)

    def get_version(self):
        """Retrieves the current version of the application."""
        return self.response_handler.response({'version': self.version}, 200)

    def bump_version(self, version_type):
        valid_types = ['major', 'minor', 'patch']
        if version_type not in valid_types:
            return self.response_handler.response(ErrorMessages.INVALID_VERSION_TYPE, 400)
        
        major, minor, patch = map(int, self.version.split('.'))
        if version_type == 'major':
            self.version = f"{major + 1}.0.0"
        elif version_type == 'minor':
            self.version = f"{major}.{minor + 1}.0"
        else:  # patch
            self.version = f"{major}.{minor}.{patch + 1}"

        self.db_operations.update_item(
            {'appName': self.app_name},
            'SET version = :v',
            {':v': self.version}
        )
        return self.response_handler.response({'new_version': self.version}, 200)

    def set_version(self, new_version):
        if not new_version:
            return self.response_handler.response(ErrorMessages.INVALID_VERSION_TYPE, 400)

        self.version = new_version
        self.db_operations.update_item(
            {'appName': self.app_name},
            'SET version = :v',
            {':v': new_version}
        )
        return self.response_handler.response({'new_version': new_version}, 200)

    def is_secure(self):
        """Checks if the app has enhanced security."""
        return self.secure