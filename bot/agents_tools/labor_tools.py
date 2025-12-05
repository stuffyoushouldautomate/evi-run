"""
Labor Research Tools - Credential-based tools for labor union research
"""

from agents import function_tool, RunContextWrapper
from database.repositories.credential import CredentialRepository
from bot.api_connectors.osha import OSHAConnector


@function_tool
async def search_osha_violations(
    ctx: RunContextWrapper,
    company_name: str,
    state: str
) -> str:
    """
    Search OSHA violations for a company in NJ or NY.
    Requires user to have configured OSHA API credentials via /add_credential.
    
    Args:
        company_name: Name of the company to search (e.g., "ABC Construction")
        state: State code - must be either "NJ" or "NY"
    
    Returns:
        Formatted OSHA violation history and details for the company
    """
    
    # Validate state
    if state.upper() not in ['NJ', 'NY']:
        return "❌ Error: This tool only works for New Jersey (NJ) and New York (NY). Please specify NJ or NY."
    
    # Get database session from context
    from database.models import async_session
    
    async with async_session() as session:
        cred_repo = CredentialRepository(session)
        
        # Get user's OSHA API credential
        credential_data = await cred_repo.get_credential_decrypted(
            user_id=ctx.context[1],
            service_name='osha_api'
        )
        
        if not credential_data:
            return (
                "❌ OSHA API credential not configured.\n\n"
                "To access OSHA data, you need to:\n"
                "1. Get a free API key from https://www.osha.gov/developers\n"
                "2. Add it using: /add_credential\n"
                "3. Select 'OSHA API' and enter your key\n\n"
                "Then you can search OSHA violations for any company in NJ/NY!"
            )
        
        # Create connector with user's API key
        connector = OSHAConnector(api_key=credential_data.get('api_key'))
        
        try:
            # Generate formatted report
            report = await connector.format_company_report(
                company_name=company_name,
                state=state.upper(),
                years=5
            )
            
            # Update last_used timestamp
            await cred_repo.update_last_used(ctx.context[1], 'osha_api')
            
            return report
            
        except Exception as e:
            return f"❌ Error searching OSHA database: {str(e)}\n\nPlease verify your API key is valid using /test_credential"


@function_tool
async def get_osha_company_summary(
    ctx: RunContextWrapper,
    company_name: str,
    state: str
) -> str:
    """
    Get a quick summary of OSHA violations for a company.
    Requires OSHA API credentials.
    
    Args:
        company_name: Name of the company
        state: State code (NJ or NY)
    
    Returns:
        Brief summary of OSHA violations
    """
    
    if state.upper() not in ['NJ', 'NY']:
        return "❌ Error: Only NJ and NY are supported."
    
    from database.models import async_session
    
    async with async_session() as session:
        cred_repo = CredentialRepository(session)
        credential_data = await cred_repo.get_credential_decrypted(
            user_id=ctx.context[1],
            service_name='osha_api'
        )
        
        if not credential_data:
            return "❌ OSHA API credential not configured. Use /add_credential to add one."
        
        connector = OSHAConnector(api_key=credential_data.get('api_key'))
        
        try:
            data = await connector.get_company_history(
                company_name=company_name,
                state=state.upper(),
                years=5
            )
            
            summary = data['summary']
            
            result = f"📊 **OSHA Summary: {company_name} ({state.upper()})**\n\n"
            result += f"• Inspections (5 years): {summary['total_inspections']}\n"
            result += f"• Total Violations: {summary['total_violations']}\n"
            result += f"• Total Penalties: ${summary['total_penalties']:,.2f}\n"
            
            if summary['total_inspections'] > 0:
                result += f"• Avg Penalty/Inspection: ${summary['average_penalty_per_inspection']:,.2f}\n"
            
            if data['recent_inspections']:
                latest = data['recent_inspections'][0]
                result += f"\n🕒 Most Recent: {latest.get('open_date', 'N/A')}\n"
                result += f"   {latest.get('nr_violations', 0)} violations, "
                result += f"${float(latest.get('total_current_penalty', 0) or 0):,.2f} penalty"
            
            await cred_repo.update_last_used(ctx.context[1], 'osha_api')
            
            return result
            
        except Exception as e:
            return f"❌ Error: {str(e)}"


@function_tool
async def check_available_labor_tools(ctx: RunContextWrapper) -> str:
    """
    Check which labor research tools are available based on user's configured credentials.
    
    Returns:
        List of available tools and instructions for enabling more
    """
    
    from database.models import async_session
    
    async with async_session() as session:
        cred_repo = CredentialRepository(session)
        services = await cred_repo.get_services_with_credentials(ctx.context[1])
        
        result = "🔧 **Available Labor Research Tools**\n\n"
        
        if not services:
            result += "❌ No credentials configured yet.\n\n"
            result += "Add credentials with /add_credential to unlock:\n"
            result += "• OSHA violation searches\n"
            result += "• DOL employee benefits data\n"
            result += "• Federal court records (PACER)\n"
            result += "• Political contribution data (FEC)\n"
            result += "• Corporate structure data (OpenCorporates)\n"
            return result
        
        result += "✅ **Active Tools:**\n\n"
        
        if 'osha_api' in services:
            result += "• **OSHA Violations**\n"
            result += "  - search_osha_violations(company, state)\n"
            result += "  - get_osha_company_summary(company, state)\n\n"
        
        if 'dol_efast' in services:
            result += "• **DOL Employee Benefits**\n"
            result += "  - search_dol_benefits(company)\n\n"
        
        if 'pacer' in services:
            result += "• **Court Records**\n"
            result += "  - search_court_cases(company)\n\n"
        
        if 'fec_api' in services:
            result += "• **Political Contributions**\n"
            result += "  - search_political_contributions(company)\n\n"
        
        if 'opencorporates' in services:
            result += "• **Corporate Structure**\n"
            result += "  - search_corporate_structure(company)\n\n"
        
        # Show what's missing
        all_services = ['osha_api', 'dol_efast', 'pacer', 'fec_api', 'opencorporates']
        missing = [s for s in all_services if s not in services]
        
        if missing:
            result += "\n📋 **Add More Tools:**\n"
            result += "Use /add_credential to enable:\n"
            for service in missing:
                service_names = {
                    'osha_api': 'OSHA API',
                    'dol_efast': 'DOL E-Fast',
                    'pacer': 'PACER (Court Records)',
                    'fec_api': 'FEC API (Political Contributions)',
                    'opencorporates': 'OpenCorporates'
                }
                result += f"• {service_names.get(service, service)}\n"
        
        return result


# Placeholder tools for other services (to be implemented)

@function_tool
async def search_dol_benefits(ctx: RunContextWrapper, company_name: str) -> str:
    """
    Search DOL E-Fast database for employee benefits information.
    Requires DOL E-Fast credentials.
    
    Args:
        company_name: Name of the company
    
    Returns:
        Employee benefits and pension plan information
    """
    return "🚧 DOL E-Fast integration coming soon. This will provide access to 401k, pension, and benefits data."


@function_tool
async def search_court_cases(ctx: RunContextWrapper, company_name: str) -> str:
    """
    Search PACER for federal court cases involving a company.
    Requires PACER credentials.
    
    Args:
        company_name: Name of the company
    
    Returns:
        Federal court case information
    """
    return "🚧 PACER integration coming soon. This will provide access to federal court records and labor disputes."


@function_tool
async def search_political_contributions(ctx: RunContextWrapper, company_name: str) -> str:
    """
    Search FEC database for political contributions by company executives.
    Requires FEC API credentials.
    
    Args:
        company_name: Name of the company
    
    Returns:
        Political contribution data for company executives
    """
    return "🚧 FEC API integration coming soon. This will provide political contribution data for company leadership."


@function_tool
async def search_corporate_structure(ctx: RunContextWrapper, company_name: str) -> str:
    """
    Search OpenCorporates for company structure, officers, and subsidiaries.
    Requires OpenCorporates API credentials.
    
    Args:
        company_name: Name of the company
    
    Returns:
        Corporate structure and officer information
    """
    return "🚧 OpenCorporates integration coming soon. This will provide company structure and officer data."
