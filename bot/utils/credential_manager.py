"""
Credential Manager - Secure encryption and decryption of user credentials
"""

import os
import json
from typing import Dict, Optional
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()


class CredentialManager:
    """Manages encryption and decryption of user credentials"""
    
    def __init__(self):
        """Initialize with encryption key from environment"""
        key = os.getenv('CREDENTIAL_ENCRYPTION_KEY')
        
        if not key:
            raise ValueError(
                "CREDENTIAL_ENCRYPTION_KEY not found in environment. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        
        self.cipher = Fernet(key.encode())
    
    def encrypt_credential(self, credential_data: Dict) -> str:
        """
        Encrypt credential dictionary to string
        
        Args:
            credential_data: Dictionary containing credential information
                Examples:
                - {"api_key": "sk_1234567890"}
                - {"username": "user@example.com", "password": "secret123"}
                - {"token": "bearer_token_xyz", "refresh_token": "refresh_xyz"}
        
        Returns:
            Encrypted string safe for database storage
        """
        json_data = json.dumps(credential_data)
        encrypted = self.cipher.encrypt(json_data.encode())
        return encrypted.decode()
    
    def decrypt_credential(self, encrypted_data: str) -> Dict:
        """
        Decrypt credential string to dictionary
        
        Args:
            encrypted_data: Encrypted credential string from database
        
        Returns:
            Dictionary containing decrypted credential information
        
        Raises:
            ValueError: If decryption fails (invalid key or corrupted data)
        """
        try:
            decrypted = self.cipher.decrypt(encrypted_data.encode())
            return json.loads(decrypted.decode())
        except Exception as e:
            raise ValueError(f"Failed to decrypt credential: {str(e)}")
    
    def validate_credential_format(self, service_name: str, credential_data: Dict) -> bool:
        """
        Validate that credential data matches expected format for service
        
        Args:
            service_name: Name of the service (e.g., 'osha_api', 'dol_efast')
            credential_data: Dictionary to validate
        
        Returns:
            True if valid, False otherwise
        """
        # Define expected formats for each service
        formats = {
            'osha_api': ['api_key'],
            'dol_efast': ['username', 'password'],
            'pacer': ['username', 'password'],
            'fec_api': ['api_key'],
            'opencorporates': ['api_key'],
            'newsapi': ['api_key'],
            'propublica': ['api_key'],
            'sam_gov': ['api_key'],
        }
        
        expected_keys = formats.get(service_name)
        if not expected_keys:
            # Unknown service, accept any format
            return True
        
        # Check if all expected keys are present
        return all(key in credential_data for key in expected_keys)


# Singleton instance
_credential_manager: Optional[CredentialManager] = None


def get_credential_manager() -> CredentialManager:
    """Get or create singleton CredentialManager instance"""
    global _credential_manager
    if _credential_manager is None:
        _credential_manager = CredentialManager()
    return _credential_manager
