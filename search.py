import httpx
import re
import asyncio
from typing import List, Dict, Optional
from config import config

class GooglePlacesSearch:
    def __init__(self):
        self.api_key = config.GOOGLE_PLACES_API_KEY
        self.base_url = "https://maps.googleapis.com/maps/api/place"
    
    async def search(self, query: str, location: str = "Lagos, Nigeria") -> List[Dict]:
        # Check if API key is configured
        if not self.api_key or self.api_key == "your_google_places_api_key_here":
            print("Warning: No Google Places API key configured")
            return self._get_mock_results(query, location)
        
        try:
            url = f"{self.base_url}/textsearch/json"
            params = {
                "query": f"{query} in {location}",
                "key": self.api_key,
                "region": "ng"
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                data = response.json()
                
                if data.get("status") != "OK":
                    print(f"API Error: {data.get('status')}")
                    return self._get_mock_results(query, location)
                
                results = []
                for place in data.get("results", [])[:3]:
                    details = await self.get_place_details(place.get("place_id"))
                    
                    if details and details.get("phone_number"):
                        results.append({
                            "place_id": place.get("place_id"),
                            "name": place.get("name"),
                            "phone": self._clean_phone(details.get("phone_number")),
                            "address": place.get("formatted_address", ""),
                        })
                
                return results if results else self._get_mock_results(query, location)
                
        except httpx.ConnectError as e:
            print(f"Network error (ConnectError): {e}")
            return self._get_mock_results(query, location)
        except httpx.TimeoutException as e:
            print(f"Network error (Timeout): {e}")
            return self._get_mock_results(query, location)
        except Exception as e:
            print(f"Search error: {e}")
            return self._get_mock_results(query, location)
    
    async def get_place_details(self, place_id: str) -> Optional[Dict]:
        try:
            url = f"{self.base_url}/details/json"
            params = {
                "place_id": place_id,
                "fields": "name,formatted_phone_number,formatted_address",
                "key": self.api_key
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                data = response.json()
                
                if data.get("status") == "OK":
                    result = data.get("result", {})
                    return {
                        "phone_number": result.get("formatted_phone_number"),
                        "address": result.get("formatted_address")
                    }
                return None
                
        except Exception as e:
            print(f"Details error: {e}")
            return None
    
    def _clean_phone(self, phone: str) -> str:
        if not phone:
            return ""
        
        digits = re.sub(r'\D', '', phone)
        
        if digits.startswith('234'):
            return '+' + digits
        elif digits.startswith('0'):
            return '+234' + digits[1:]
        
        return phone
    
    def _get_mock_results(self, query: str, location: str) -> List[Dict]:
        """
        Return mock results when API fails or for testing
        """
        print(f"Using mock results for: {query} in {location}")
        
        # Mock data for testing
        mock_data = {
            'plumber': [
                {"name": "Quick Fix Plumbing", "phone": "+2348123456789", "address": "Lekki Phase 1"},
                {"name": "Pipe Masters", "phone": "+2348098765432", "address": "Lekki"},
            ],
            'electrician': [
                {"name": "PowerPro Electric", "phone": "+2347012345678", "address": "Yaba"},
                {"name": "Spark Solutions", "phone": "+2348023456789", "address": "Ikeja"},
            ],
            'ac repair': [
                {"name": "Cool Air Services", "phone": "+2349034567890", "address": "Victoria Island"},
                {"name": "AC Masters", "phone": "+2347045678901", "address": "Ikoyi"},
            ],
            'generator': [
                {"name": "GenPro Repairs", "phone": "+2348056789012", "address": "Surulere"},
                {"name": "PowerGen Solutions", "phone": "+2349067890123", "address": "Ikeja"},
            ]
        }
        
        # Find matching category
        query_lower = query.lower()
        for category, results in mock_data.items():
            if category in query_lower:
                # Add place_id for consistency
                for i, r in enumerate(results):
                    r['place_id'] = f"mock_{category}_{i}"
                return results
        
        # Default fallback
        return [
            {"name": "Test Business 1", "phone": "+2348012345678", "address": location, "place_id": "mock_1"},
            {"name": "Test Business 2", "phone": "+2348023456789", "address": location, "place_id": "mock_2"},
        ]

search_service = GooglePlacesSearch()