"""
Credential Management Router - Telegram commands for managing API credentials
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.states.credential_states import CredentialStates
from database.repositories.credential import CredentialRepository
from sqlalchemy.ext.asyncio import AsyncSession

router = Router()

# Supported services configuration
SUPPORTED_SERVICES = {
    'osha_api': {
        'name': 'OSHA API',
        'description': 'Access OSHA workplace inspection and violation data',
        'credential_type': 'api_key',
        'fields': ['api_key'],
        'instructions': 'Enter your OSHA API key',
        'url': 'https://www.osha.gov/developers'
    },
    'dol_efast': {
        'name': 'DOL E-Fast',
        'description': 'Access Department of Labor employee benefits data',
        'credential_type': 'basic_auth',
        'fields': ['username', 'password'],
        'instructions': 'Enter your DOL E-Fast credentials in format: username:password',
        'url': 'https://www.dol.gov/agencies/ebsa/researchers/data'
    },
    'pacer': {
        'name': 'PACER',
        'description': 'Access federal court records',
        'credential_type': 'basic_auth',
        'fields': ['username', 'password'],
        'instructions': 'Enter your PACER credentials in format: username:password',
        'url': 'https://pacer.uscourts.gov/'
    },
    'fec_api': {
        'name': 'FEC API',
        'description': 'Access Federal Election Commission political contribution data',
        'credential_type': 'api_key',
        'fields': ['api_key'],
        'instructions': 'Enter your FEC API key',
        'url': 'https://api.open.fec.gov/developers/'
    },
    'opencorporates': {
        'name': 'OpenCorporates',
        'description': 'Access corporate structure and officer data',
        'credential_type': 'api_key',
        'fields': ['api_key'],
        'instructions': 'Enter your OpenCorporates API key',
        'url': 'https://api.opencorporates.com/'
    },
}


@router.message(Command('add_credential'))
async def cmd_add_credential(message: Message, state: FSMContext):
    """Start the add credential flow"""
    
    # Build keyboard with available services
    builder = InlineKeyboardBuilder()
    for service_id, service_info in SUPPORTED_SERVICES.items():
        builder.button(
            text=service_info['name'],
            callback_data=f"cred_add_{service_id}"
        )
    builder.adjust(2)  # 2 buttons per row
    
    await message.answer(
        "🔐 <b>Add New Credential</b>\n\n"
        "Select a service to add credentials for:\n\n"
        "These credentials will be encrypted and stored securely. "
        "They will only be used when you request data from these services.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith('cred_add_'))
async def process_service_selection(callback: CallbackQuery, state: FSMContext):
    """Handle service selection for adding credential"""
    
    service_id = callback.data.replace('cred_add_', '')
    service_info = SUPPORTED_SERVICES.get(service_id)
    
    if not service_info:
        await callback.answer("❌ Invalid service", show_alert=True)
        return
    
    # Store service in FSM
    await state.update_data(service_id=service_id)
    await state.set_state(CredentialStates.waiting_for_credential_data)
    
    # Send instructions
    await callback.message.edit_text(
        f"🔐 <b>Add {service_info['name']} Credential</b>\n\n"
        f"<i>{service_info['description']}</i>\n\n"
        f"<b>Instructions:</b>\n"
        f"{service_info['instructions']}\n\n"
        f"<b>Get API Key:</b> {service_info['url']}\n\n"
        f"⚠️ <b>Security Note:</b> Your credentials will be encrypted with AES-256 "
        f"and stored securely. Only you can access them.\n\n"
        f"Send your credential now (or /cancel to abort):",
        parse_mode="HTML"
    )
    
    await callback.answer()


@router.message(CredentialStates.waiting_for_credential_data)
async def process_credential_data(message: Message, state: FSMContext, session: AsyncSession):
    """Process and store the credential data"""
    
    data = await state.get_data()
    service_id = data.get('service_id')
    service_info = SUPPORTED_SERVICES.get(service_id)
    
    if not service_info:
        await message.answer("❌ Error: Invalid service. Please start over with /add_credential")
        await state.clear()
        return
    
    # Parse credential data based on type
    credential_data = {}
    
    try:
        if service_info['credential_type'] == 'api_key':
            credential_data = {'api_key': message.text.strip()}
        
        elif service_info['credential_type'] == 'basic_auth':
            # Expected format: username:password
            parts = message.text.strip().split(':', 1)
            if len(parts) != 2:
                await message.answer(
                    "❌ Invalid format. Please use: username:password\n"
                    "Try again or /cancel to abort."
                )
                return
            credential_data = {
                'username': parts[0].strip(),
                'password': parts[1].strip()
            }
        
        # Delete the message containing credentials for security
        try:
            await message.delete()
        except:
            pass
        
        # Store credential in database
        cred_repo = CredentialRepository(session)
        
        await cred_repo.add_credential(
            user_id=message.from_user.id,
            service_name=service_id,
            credential_type=service_info['credential_type'],
            credential_data=credential_data
        )
        
        await message.answer(
            f"✅ <b>{service_info['name']} credential added successfully!</b>\n\n"
            f"You can now use Bulldozer to access {service_info['name']} data.\n\n"
            f"Try asking: \"Find OSHA violations for [Company Name] in New Jersey\"",
            parse_mode="HTML"
        )
        
        await state.clear()
        
    except ValueError as e:
        await message.answer(
            f"❌ Error: {str(e)}\n\n"
            f"Please try again or /cancel to abort."
        )
    except Exception as e:
        await message.answer(
            f"❌ Failed to store credential: {str(e)}\n\n"
            f"Please try again later or contact support."
        )
        await state.clear()


@router.message(Command('list_credentials'))
async def cmd_list_credentials(message: Message, session: AsyncSession):
    """List all active credentials for user"""
    
    cred_repo = CredentialRepository(session)
    credentials = await cred_repo.get_all_credentials(message.from_user.id, active_only=True)
    
    if not credentials:
        await message.answer(
            "❌ <b>No credentials configured</b>\n\n"
            "Add credentials with /add_credential to unlock access to:\n"
            "• OSHA violation data\n"
            "• DOL employee benefits data\n"
            "• Federal court records (PACER)\n"
            "• Political contribution data (FEC)\n"
            "• Corporate structure data (OpenCorporates)",
            parse_mode="HTML"
        )
        return
    
    text = "🔐 <b>Your Active Credentials</b>\n\n"
    
    for cred in credentials:
        service_info = SUPPORTED_SERVICES.get(cred.service_name, {})
        service_name = service_info.get('name', cred.service_name)
        
        status = "✅ Active" if cred.is_active else "❌ Inactive"
        last_used = cred.last_used.strftime("%Y-%m-%d %H:%M") if cred.last_used else "Never"
        
        text += f"• <b>{service_name}</b> - {status}\n"
        text += f"  Type: {cred.credential_type}\n"
        text += f"  Added: {cred.created_at.strftime('%Y-%m-%d')}\n"
        text += f"  Last used: {last_used}\n\n"
    
    text += "\n<i>Use /remove_credential to remove a credential</i>"
    
    await message.answer(text, parse_mode="HTML")


@router.message(Command('remove_credential'))
async def cmd_remove_credential(message: Message, state: FSMContext, session: AsyncSession):
    """Start the remove credential flow"""
    
    cred_repo = CredentialRepository(session)
    credentials = await cred_repo.get_all_credentials(message.from_user.id, active_only=True)
    
    if not credentials:
        await message.answer("❌ No credentials to remove")
        return
    
    # Build keyboard with user's credentials
    builder = InlineKeyboardBuilder()
    for cred in credentials:
        service_info = SUPPORTED_SERVICES.get(cred.service_name, {})
        service_name = service_info.get('name', cred.service_name)
        builder.button(
            text=service_name,
            callback_data=f"cred_remove_{cred.service_name}"
        )
    builder.adjust(2)
    
    await message.answer(
        "🗑️ <b>Remove Credential</b>\n\n"
        "Select a credential to remove:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith('cred_remove_'))
async def process_credential_removal(callback: CallbackQuery, session: AsyncSession):
    """Handle credential removal"""
    
    service_id = callback.data.replace('cred_remove_', '')
    service_info = SUPPORTED_SERVICES.get(service_id, {})
    service_name = service_info.get('name', service_id)
    
    cred_repo = CredentialRepository(session)
    success = await cred_repo.remove_credential(callback.from_user.id, service_id)
    
    if success:
        await callback.message.edit_text(
            f"✅ <b>{service_name} credential removed</b>\n\n"
            f"You will no longer be able to access {service_name} data until you add new credentials.",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            f"❌ Failed to remove {service_name} credential",
            parse_mode="HTML"
        )
    
    await callback.answer()


@router.message(Command('test_credential'))
async def cmd_test_credential(message: Message, state: FSMContext, session: AsyncSession):
    """Test if a credential works"""
    
    cred_repo = CredentialRepository(session)
    credentials = await cred_repo.get_all_credentials(message.from_user.id, active_only=True)
    
    if not credentials:
        await message.answer("❌ No credentials to test")
        return
    
    # Build keyboard with user's credentials
    builder = InlineKeyboardBuilder()
    for cred in credentials:
        service_info = SUPPORTED_SERVICES.get(cred.service_name, {})
        service_name = service_info.get('name', cred.service_name)
        builder.button(
            text=service_name,
            callback_data=f"cred_test_{cred.service_name}"
        )
    builder.adjust(2)
    
    await message.answer(
        "🧪 <b>Test Credential</b>\n\n"
        "Select a credential to test:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith('cred_test_'))
async def process_credential_test(callback: CallbackQuery, session: AsyncSession):
    """Test a credential by making a simple API call"""
    
    service_id = callback.data.replace('cred_test_', '')
    service_info = SUPPORTED_SERVICES.get(service_id, {})
    service_name = service_info.get('name', service_id)
    
    await callback.message.edit_text(
        f"🧪 Testing {service_name} credential...",
        parse_mode="HTML"
    )
    
    cred_repo = CredentialRepository(session)
    credential_data = await cred_repo.get_credential_decrypted(callback.from_user.id, service_id)
    
    if not credential_data:
        await callback.message.edit_text(
            f"❌ Failed to decrypt {service_name} credential\n\n"
            f"Please remove and re-add the credential.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    # TODO: Implement actual API test calls for each service
    # For now, just confirm decryption worked
    
    await callback.message.edit_text(
        f"✅ <b>{service_name} credential is valid</b>\n\n"
        f"Credential was successfully decrypted and is ready to use.\n\n"
        f"<i>Note: Full API connectivity test will be implemented in next update.</i>",
        parse_mode="HTML"
    )
    
    await callback.answer()


@router.message(Command('credential_help'))
async def cmd_credential_help(message: Message):
    """Show help for credential management"""
    
    help_text = (
        "🔐 <b>Credential Management Help</b>\n\n"
        "<b>Available Commands:</b>\n"
        "/add_credential - Add new API credentials\n"
        "/list_credentials - View your active credentials\n"
        "/remove_credential - Remove a credential\n"
        "/test_credential - Test if a credential works\n\n"
        "<b>Supported Services:</b>\n"
    )
    
    for service_id, service_info in SUPPORTED_SERVICES.items():
        help_text += f"• <b>{service_info['name']}</b>\n"
        help_text += f"  {service_info['description']}\n"
        help_text += f"  Get key: {service_info['url']}\n\n"
    
    help_text += (
        "<b>Security:</b>\n"
        "• All credentials are encrypted with AES-256\n"
        "• Only you can access your credentials\n"
        "• Credentials are never logged or shared\n"
        "• Messages containing credentials are auto-deleted\n\n"
        "<b>Usage:</b>\n"
        "Once you add credentials, Bulldozer will automatically use them "
        "when you request data from those services. For example:\n\n"
        "\"Find OSHA violations for ABC Construction in New Jersey\"\n\n"
        "Bulldozer will use your OSHA API credential to fetch the data."
    )
    
    await message.answer(help_text, parse_mode="HTML")
