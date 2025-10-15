"""
Web Navigation Tool - Playwright-based navigation for OpenAI Agents SDK
"""

import asyncio
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright_stealth import stealth_async
from utils.logger import setup_logger

logger = setup_logger(__name__)

class WebNavigationTool:
    def __init__(self, headless: bool = False, slow_mo: int = 100):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.headless = headless
        self.slow_mo = slow_mo
        self.current_url = None
        
    async def initialize(self):
        """Initialize Playwright browser for OpenAI Agents SDK usage"""
        logger.info("Initializing Web Navigation Tool for OpenAI Agents SDK")
        
        try:
            self.playwright = await async_playwright().start()
            
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            
            self.context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            
            self.page = await self.context.new_page()
            self.page.set_default_timeout(30000)
            await self.page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"
            })

            await stealth_async(self.page)
            
            logger.info("Web Navigation Tool initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Web Navigation Tool: {str(e)}")
            raise
            
    async def navigate_to_url(self, url: str) -> Dict[str, Any]:
        """Navigate to specific URL - OpenAI Agents SDK compatible"""
        logger.info(f"Navigating to: {url}")
        
        try:
            # Ensure URL has protocol
            if not url.startswith(('http://', 'https://')):
                url = f"https://{url}"
            
            logger.info(f"[MDEBUG] URL: {url}")
            await self.page.goto(url, wait_until='domcontentloaded', timeout=50000)
            self.current_url = self.page.url
            
            # Wait for page to stabilize
            await asyncio.sleep(2)
            
            page_title = await self.page.title()
            
            result = {
                "success": True,
                "url": self.current_url,
                "title": page_title,
                "status": "navigated_successfully"
            }
            
            logger.info(f"Navigation successful: {self.current_url}")
            return result
            
        except Exception as e:
            logger.error(f"Navigation failed to {url}: {str(e)}")
            return {
                "success": False,
                "url": url,
                "error": str(e),
                "status": "navigation_failed"
            }
            
    async def interact_with_element(self, action: str, selector: str, value: str = None) -> Dict[str, Any]:
        """Interact with page elements - OpenAI Agents SDK compatible"""
        logger.info(f"Performing {action} on element: {selector}")
        
        try:
            if action == "click":
                await self.page.wait_for_selector(selector, timeout=100000)
                await self.page.click(selector)
                await asyncio.sleep(1)
                
            elif action == "fill":
                if not value:
                    return {"success": False, "error": "Value required for fill action"}
                await self.page.wait_for_selector(selector, timeout=50000)
                await self.page.fill(selector, value)
                
            elif action == "submit":
                await self.page.wait_for_selector(selector, timeout=50000)
                
                # Try multiple submit strategies
                submit_successful = await self._try_submit_strategies(selector)
                
                if not submit_successful:
                    await self.page.press(selector, "Enter")
                    
                await asyncio.sleep(3)  # Wait for results
                
            elif action == "scroll":
                scroll_amount = int(value) if value else 3
                for _ in range(scroll_amount):
                    await self.page.keyboard.press("PageDown")
                    await asyncio.sleep(0.5)
                    
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
                
            current_url = self.page.url
            self.current_url = current_url
            
            return {
                "success": True,
                "action": action,
                "selector": selector,
                "current_url": current_url,
                "status": "interaction_completed"
            }
            
        except Exception as e:
            logger.error(f"Element interaction failed: {str(e)}")
            return {
                "success": False,
                "action": action,
                "selector": selector,
                "error": str(e),
                "status": "interaction_failed"
            }
            
    async def _try_submit_strategies(self, selector: str) -> bool:
        """Try multiple submit strategies"""
        submit_selectors = [
            f"{selector} + button[type='submit']",
            f"{selector} ~ button[type='submit']",
            "form button[type='submit']",
            "form input[type='submit']",
            "button:has-text('Search')",
            "button:has-text('Go')",
            "button:has-text('Submit')",
            ".search-button",
            "#search-button"
        ]
        
        for submit_selector in submit_selectors:
            try:
                element = await self.page.query_selector(submit_selector)
                if element:
                    await element.click()
                    return True
            except:
                continue
                
        return False
        
    async def get_current_page_info(self) -> Dict[str, Any]:
        """Get current page information - OpenAI Agents SDK compatible"""
        try:
            return {
                "success": True,
                "url": self.page.url,
                "title": await self.page.title(),
                "ready_state": await self.page.evaluate("document.readyState"),
                "status": "page_info_retrieved"
            }
        except Exception as e:
            logger.error(f"Failed to get page info: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "status": "page_info_failed"
            }
            
    async def wait_for_element(self, selector: str, timeout: int = 50000) -> Dict[str, Any]:
        """Wait for element to appear - OpenAI Agents SDK compatible"""
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return {
                "success": True,
                "selector": selector,
                "status": "element_appeared"
            }
        except Exception as e:
            return {
                "success": False,
                "selector": selector,
                "error": str(e),
                "status": "element_wait_timeout"
            }
            
    async def take_screenshot(self, filename: str = None) -> Dict[str, Any]:
        """Take screenshot - OpenAI Agents SDK compatible"""
        try:
            from pathlib import Path
            import time
            
            if not filename:
                filename = f"screenshot_{int(time.time())}.png"
                
            screenshots_dir = Path("screenshots")
            screenshots_dir.mkdir(exist_ok=True)
            
            screenshot_path = screenshots_dir / filename
            await self.page.screenshot(path=str(screenshot_path))
            
            return {
                "success": True,
                "filename": filename,
                "path": str(screenshot_path),
                "status": "screenshot_saved"
            }
            
        except Exception as e:
            logger.error(f"Screenshot failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "status": "screenshot_failed"
            }
            
    async def go_back(self) -> Dict[str, Any]:
        """Navigate back - OpenAI Agents SDK compatible"""
        try:
            await self.page.go_back()
            await asyncio.sleep(2)
            
            return {
                "success": True,
                "current_url": self.page.url,
                "status": "navigated_back"
            }
            
        except Exception as e:
            logger.error(f"Go back failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "status": "go_back_failed"
            }
            
    async def evaluate_javascript(self, script: str) -> Dict[str, Any]:
        """Evaluate JavaScript on page - OpenAI Agents SDK compatible"""
        try:
            result = await self.page.evaluate(script)
            return {
                "success": True,
                "result": result,
                "status": "javascript_executed"
            }
        except Exception as e:
            logger.error(f"JavaScript evaluation failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "status": "javascript_failed"
            }
            
    async def check_element_exists(self, selector: str) -> Dict[str, Any]:
        """Check if element exists - OpenAI Agents SDK compatible"""
        try:
            element = await self.page.query_selector(selector)
            exists = element is not None
            
            return {
                "success": True,
                "selector": selector,
                "exists": exists,
                "status": "element_check_completed"
            }
            
        except Exception as e:
            logger.error(f"Element existence check failed: {str(e)}")
            return {
                "success": False,
                "selector": selector,
                "error": str(e),
                "status": "element_check_failed"
            }
            
    async def get_page_html(self) -> str:
        """Get raw HTML content"""
        try:
            return await self.page.content()
        except Exception as e:
            logger.error(f"Failed to get page HTML: {str(e)}")
            raise
            
    async def cleanup(self):
        """Close browser and cleanup resources"""
        logger.info("Cleaning up Web Navigation Tool")
        
        try:
            if self.page:
                await self.page.close()
                
            if self.context:
                await self.context.close()
                
            if self.browser:
                await self.browser.close()
                
            if self.playwright:
                await self.playwright.stop()
                
            logger.info("Web Navigation Tool cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during Web Navigation Tool cleanup: {str(e)}")