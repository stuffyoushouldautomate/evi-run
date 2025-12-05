"""
FSM States for Credential Management
"""

from aiogram.fsm.state import State, StatesGroup


class CredentialStates(StatesGroup):
    """States for credential management flow"""
    
    # Adding credential flow
    waiting_for_service = State()
    waiting_for_credential_data = State()
    confirming_add = State()
    
    # Removing credential flow
    waiting_for_removal_service = State()
    confirming_removal = State()
    
    # Testing credential flow
    waiting_for_test_service = State()
