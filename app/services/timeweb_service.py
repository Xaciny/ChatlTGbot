import logging
import aiohttp
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class TimewebService:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.timeweb.cloud/api/v1"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_token}"
        }
    
    async def get_balance(self) -> Optional[Dict[str, Any]]:
        if not self.api_token:
            logger.error("TIMEWEB_API_TOKEN не настроен")
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/account/finances",
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        finances = data.get('finances', {})
                        
                        return {
                            'balance': float(finances.get('balance', 0)),
                            'currency': finances.get('currency', 'RUB'),
                            'hourly_cost': float(finances.get('hourly_cost', 0)),
                            'monthly_cost': float(finances.get('monthly_cost', 0)),
                            'raw_data': finances
                        }
                    else:
                        logger.error(f"Ошибка API Timeweb: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Ошибка при запросе к API Timeweb: {e}")
            return None
    
    async def get_account_status(self) -> Optional[Dict[str, Any]]:
        if not self.api_token:
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/account/status",
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('status', {})
                    return None
        except Exception as e:
            logger.error(f"Ошибка при получении статуса аккаунта: {e}")
            return None
    
    def calculate_days_remaining(self, balance: float, daily_cost: float) -> int:
        if daily_cost <= 0:
            return 999
        return int(balance / daily_cost)