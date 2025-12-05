"""
OSHA API Connector - Access OSHA workplace inspection and violation data
"""

import aiohttp
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta


class OSHAConnector:
    """
    Connector for OSHA (Occupational Safety and Health Administration) API
    
    API Documentation: https://www.osha.gov/developers
    """
    
    BASE_URL = "https://data.osha.gov/api/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OSHA connector
        
        Args:
            api_key: OSHA API key (optional, but recommended for higher rate limits)
        """
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    async def search_inspections(
        self,
        establishment_name: Optional[str] = None,
        state: Optional[str] = None,
        city: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Search OSHA inspections
        
        Args:
            establishment_name: Company/establishment name
            state: Two-letter state code (e.g., 'NJ', 'NY')
            city: City name
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            limit: Maximum number of results (default 100)
        
        Returns:
            Dictionary containing inspection results
        """
        params = {"size": limit}
        
        if establishment_name:
            params["establishment_name"] = establishment_name
        if state:
            params["state"] = state.upper()
        if city:
            params["city"] = city
        if start_date:
            params["inspection_start_date"] = start_date
        if end_date:
            params["inspection_end_date"] = end_date
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/inspections",
                headers=self.headers,
                params=params
            ) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    raise Exception("OSHA API authentication failed. Check your API key.")
                elif response.status == 429:
                    raise Exception("OSHA API rate limit exceeded. Try again later.")
                else:
                    raise Exception(f"OSHA API error: HTTP {response.status}")
    
    async def get_violations(
        self,
        activity_nr: str
    ) -> Dict[str, Any]:
        """
        Get violations for a specific inspection
        
        Args:
            activity_nr: Inspection activity number
        
        Returns:
            Dictionary containing violation details
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/inspections/{activity_nr}/violations",
                headers=self.headers
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"OSHA API error: HTTP {response.status}")
    
    async def get_company_history(
        self,
        company_name: str,
        state: Optional[str] = None,
        years: int = 5
    ) -> Dict[str, Any]:
        """
        Get complete OSHA inspection history for a company
        
        Args:
            company_name: Name of the company
            state: State code (e.g., 'NJ', 'NY')
            years: Number of years of history to retrieve (default 5)
        
        Returns:
            Structured dictionary with company OSHA history
        """
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years * 365)
        
        # Search inspections
        results = await self.search_inspections(
            establishment_name=company_name,
            state=state,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            limit=500
        )
        
        # Process results
        inspections = results.get("data", [])
        
        # Calculate statistics
        total_inspections = len(inspections)
        total_violations = sum(
            insp.get("nr_violations", 0) for insp in inspections
        )
        total_penalties = sum(
            float(insp.get("total_current_penalty", 0) or 0) for insp in inspections
        )
        
        # Group by year
        by_year = {}
        for insp in inspections:
            open_date = insp.get("open_date", "")
            if open_date:
                year = open_date[:4]
                if year not in by_year:
                    by_year[year] = {
                        "inspections": 0,
                        "violations": 0,
                        "penalties": 0.0
                    }
                by_year[year]["inspections"] += 1
                by_year[year]["violations"] += insp.get("nr_violations", 0)
                by_year[year]["penalties"] += float(insp.get("total_current_penalty", 0) or 0)
        
        # Get violation types
        violation_types = {}
        for insp in inspections:
            if insp.get("nr_violations", 0) > 0:
                # Would need to fetch individual violations for detailed breakdown
                # For now, just track inspection types
                insp_type = insp.get("inspection_type", "Unknown")
                violation_types[insp_type] = violation_types.get(insp_type, 0) + 1
        
        return {
            "company": company_name,
            "state": state,
            "period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            "summary": {
                "total_inspections": total_inspections,
                "total_violations": total_violations,
                "total_penalties": round(total_penalties, 2),
                "average_penalty_per_inspection": round(
                    total_penalties / total_inspections if total_inspections > 0 else 0,
                    2
                )
            },
            "by_year": by_year,
            "violation_types": violation_types,
            "recent_inspections": inspections[:10],  # Most recent 10
            "raw_data": inspections
        }
    
    async def format_company_report(
        self,
        company_name: str,
        state: Optional[str] = None,
        years: int = 5
    ) -> str:
        """
        Generate a formatted text report of company OSHA history
        
        Args:
            company_name: Name of the company
            state: State code (e.g., 'NJ', 'NY')
            years: Number of years of history (default 5)
        
        Returns:
            Formatted text report
        """
        try:
            data = await self.get_company_history(company_name, state, years)
            
            report = f"🏗️ **OSHA Inspection History: {company_name}**\n"
            if state:
                report += f"📍 State: {state}\n"
            report += f"📅 Period: {data['period']}\n\n"
            
            summary = data['summary']
            report += "**Summary:**\n"
            report += f"• Total Inspections: {summary['total_inspections']}\n"
            report += f"• Total Violations: {summary['total_violations']}\n"
            report += f"• Total Penalties: ${summary['total_penalties']:,.2f}\n"
            report += f"• Average Penalty: ${summary['average_penalty_per_inspection']:,.2f}\n\n"
            
            if data['by_year']:
                report += "**By Year:**\n"
                for year in sorted(data['by_year'].keys(), reverse=True):
                    year_data = data['by_year'][year]
                    report += f"• {year}: {year_data['inspections']} inspections, "
                    report += f"{year_data['violations']} violations, "
                    report += f"${year_data['penalties']:,.2f} penalties\n"
                report += "\n"
            
            if data['recent_inspections']:
                report += "**Recent Inspections (Top 5):**\n"
                for insp in data['recent_inspections'][:5]:
                    report += f"• {insp.get('open_date', 'N/A')}: "
                    report += f"{insp.get('inspection_type', 'Unknown')} - "
                    report += f"{insp.get('nr_violations', 0)} violations, "
                    report += f"${float(insp.get('total_current_penalty', 0) or 0):,.2f} penalty\n"
            
            report += f"\n📊 Source: OSHA API (data.osha.gov)"
            
            return report
            
        except Exception as e:
            return f"❌ Error generating OSHA report: {str(e)}"
    
    async def test_connection(self) -> bool:
        """
        Test if the API connection and credentials work
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Make a simple test query
            await self.search_inspections(state="NJ", limit=1)
            return True
        except Exception:
            return False
