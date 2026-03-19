import asyncio
from datetime import datetime
from typing import Dict, List
from twilio.rest import Client
from config import config

class VerificationEngine:
    def __init__(self):
        self.client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
        self.from_number = config.TWILIO_PHONE_NUMBER
    
    async def verify_businesses(self, businesses: List[Dict]) -> List[Dict]:
        tasks = [self.verify_single(biz) for biz in businesses]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        verified = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                businesses[i]['verification'] = {'status': 'ERROR', 'error': str(result)}
                verified.append(businesses[i])
            else:
                verified.append(result)
        
        return verified
    
    async def verify_single(self, business: Dict) -> Dict:
        phone = business.get('phone')
        if not phone:
            business['verification'] = {'status': 'FAILED', 'error': 'No phone'}
            return business
        
        # SIMULATION MODE - Remove this when ready to make real calls
        await asyncio.sleep(2)
        business['verification'] = {
            'status': 'SUCCESS',
            'duration': 5,
            'answered_by': 'human',
            'timestamp': datetime.utcnow()
        }
        return business
        
        # REAL TWILIO CALL - Uncomment when ready:
        """
        try:
            call = self.client.calls.create(
                to=phone,
                from_=self.from_number,
                url=f"{config.WEBHOOK_URL}/twilio/status",
                timeout=config.VERIFY_TIMEOUT
            )
            
            status = await self._wait_for_call(call.sid)
            business['verification'] = status
            return business
            
        except Exception as e:
            business['verification'] = {'status': 'ERROR', 'error': str(e)}
            return business
        """
    
    async def _wait_for_call(self, call_sid: str, timeout: int = 20) -> Dict:
        return {'status': 'SUCCESS', 'duration': 0, 'answered_by': 'unknown'}

verification_engine = VerificationEngine()