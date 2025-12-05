"""
Credential Repository - Database operations for user credentials
"""

from typing import List, Optional, Dict
from datetime import datetime
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import UserCredential
from bot.utils.credential_manager import get_credential_manager


class CredentialRepository:
    """Repository for managing user credentials in database"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.cm = get_credential_manager()
    
    async def add_credential(
        self,
        user_id: int,
        service_name: str,
        credential_type: str,
        credential_data: Dict
    ) -> UserCredential:
        """
        Add or update a credential for a user
        
        Args:
            user_id: Telegram user ID
            service_name: Name of the service (e.g., 'osha_api')
            credential_type: Type of credential ('api_key', 'basic_auth', 'oauth')
            credential_data: Dictionary containing credential information
        
        Returns:
            Created or updated UserCredential object
        """
        # Validate credential format
        if not self.cm.validate_credential_format(service_name, credential_data):
            raise ValueError(f"Invalid credential format for service: {service_name}")
        
        # Encrypt credentials
        encrypted = self.cm.encrypt_credential(credential_data)
        
        # Check if credential already exists
        existing = await self.get_credential(user_id, service_name)
        
        if existing:
            # Update existing credential
            stmt = (
                update(UserCredential)
                .where(
                    UserCredential.user_id == user_id,
                    UserCredential.service_name == service_name
                )
                .values(
                    credential_type=credential_type,
                    encrypted_credentials=encrypted,
                    is_active=True,
                    updated_at=datetime.utcnow()
                )
            )
            await self.session.execute(stmt)
            await self.session.commit()
            
            # Fetch updated credential
            return await self.get_credential(user_id, service_name)
        else:
            # Create new credential
            credential = UserCredential(
                user_id=user_id,
                service_name=service_name,
                credential_type=credential_type,
                encrypted_credentials=encrypted,
                is_active=True
            )
            self.session.add(credential)
            await self.session.commit()
            await self.session.refresh(credential)
            return credential
    
    async def get_credential(
        self,
        user_id: int,
        service_name: str
    ) -> Optional[UserCredential]:
        """
        Get a specific credential for a user
        
        Args:
            user_id: Telegram user ID
            service_name: Name of the service
        
        Returns:
            UserCredential object or None if not found
        """
        stmt = select(UserCredential).where(
            UserCredential.user_id == user_id,
            UserCredential.service_name == service_name,
            UserCredential.is_active == True
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_credential_decrypted(
        self,
        user_id: int,
        service_name: str
    ) -> Optional[Dict]:
        """
        Get and decrypt a credential
        
        Args:
            user_id: Telegram user ID
            service_name: Name of the service
        
        Returns:
            Decrypted credential dictionary or None if not found
        """
        credential = await self.get_credential(user_id, service_name)
        if not credential:
            return None
        
        try:
            return self.cm.decrypt_credential(credential.encrypted_credentials)
        except ValueError:
            # Decryption failed, mark credential as inactive
            await self.deactivate_credential(user_id, service_name)
            return None
    
    async def get_all_credentials(
        self,
        user_id: int,
        active_only: bool = True
    ) -> List[UserCredential]:
        """
        Get all credentials for a user
        
        Args:
            user_id: Telegram user ID
            active_only: If True, only return active credentials
        
        Returns:
            List of UserCredential objects
        """
        stmt = select(UserCredential).where(UserCredential.user_id == user_id)
        
        if active_only:
            stmt = stmt.where(UserCredential.is_active == True)
        
        stmt = stmt.order_by(UserCredential.created_at.desc())
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def remove_credential(
        self,
        user_id: int,
        service_name: str
    ) -> bool:
        """
        Remove (delete) a credential
        
        Args:
            user_id: Telegram user ID
            service_name: Name of the service
        
        Returns:
            True if credential was removed, False if not found
        """
        stmt = delete(UserCredential).where(
            UserCredential.user_id == user_id,
            UserCredential.service_name == service_name
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0
    
    async def deactivate_credential(
        self,
        user_id: int,
        service_name: str
    ) -> bool:
        """
        Deactivate a credential without deleting it
        
        Args:
            user_id: Telegram user ID
            service_name: Name of the service
        
        Returns:
            True if credential was deactivated, False if not found
        """
        stmt = (
            update(UserCredential)
            .where(
                UserCredential.user_id == user_id,
                UserCredential.service_name == service_name
            )
            .values(is_active=False, updated_at=datetime.utcnow())
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0
    
    async def update_last_used(
        self,
        user_id: int,
        service_name: str
    ) -> None:
        """
        Update the last_used timestamp for a credential
        
        Args:
            user_id: Telegram user ID
            service_name: Name of the service
        """
        stmt = (
            update(UserCredential)
            .where(
                UserCredential.user_id == user_id,
                UserCredential.service_name == service_name
            )
            .values(last_used=datetime.utcnow())
        )
        await self.session.execute(stmt)
        await self.session.commit()
    
    async def get_services_with_credentials(
        self,
        user_id: int
    ) -> List[str]:
        """
        Get list of service names that user has credentials for
        
        Args:
            user_id: Telegram user ID
        
        Returns:
            List of service names
        """
        credentials = await self.get_all_credentials(user_id, active_only=True)
        return [cred.service_name for cred in credentials]
