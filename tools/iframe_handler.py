"""
Enhanced Iframe and Dynamic Content Handler
Handles iframes, shadow DOMs, and dynamic loading scenarios
"""

import asyncio
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from utils.logger import setup_logger

logger = setup_logger(__name__)

class IframeHandler:
    def __init__(self, web_navigator, scraping_tool):
        self.web_navigator = web_navigator
        self.scraping_tool = scraping_tool
        self.iframe_cache = {}
        
    async def detect_and_handle_iframes(self, job_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive iframe detection and handling
        Returns job listings found in iframes or main page
        """
        logger.info("Starting comprehensive iframe detection")
        
        try:
            # Step 1: Check for iframes in current page
            iframe_info = await self._detect_iframes()
            
            if not iframe_info["has_iframes"]:
                logger.info("No iframes detected, proceeding with main page")
                return {"success": True, "source": "main_page", "iframes_found": 0}
            
            logger.info(f"Found {len(iframe_info['iframes'])} iframes")
            
            # Step 2: Try to extract content from each iframe
            job_results = []
            
            for idx, iframe_data in enumerate(iframe_info["iframes"]):
                logger.info(f"Processing iframe {idx + 1}/{len(iframe_info['iframes'])}")
                
                iframe_result = await self._process_single_iframe(
                    iframe_data, 
                    idx, 
                    job_params
                )
                
                if iframe_result.get("success") and iframe_result.get("job_listings"):
                    job_results.extend(iframe_result["job_listings"])
            
            return {
                "success": True,
                "source": "iframes",
                "iframes_processed": len(iframe_info["iframes"]),
                "job_listings": job_results,
                "total_jobs": len(job_results)
            }
            
        except Exception as e:
            logger.error(f"Iframe handling failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _detect_iframes(self) -> Dict[str, Any]:
        """Detect all iframes on current page with detailed info"""
        try:
            html_content = await self.web_navigator.get_page_html()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            iframes = []
            
            for iframe in soup.find_all('iframe'):
                iframe_info = {
                    'src': iframe.get('src'),
                    'id': iframe.get('id'),
                    'name': iframe.get('name'),
                    'class': iframe.get('class', []),
                    'title': iframe.get('title'),
                    'width': iframe.get('width'),
                    'height': iframe.get('height'),
                    'data_src': iframe.get('data-src'),  # Lazy loaded iframes
                    'sandbox': iframe.get('sandbox'),
                    'loading': iframe.get('loading')
                }
                
                # Check if iframe is likely to contain job listings
                iframe_info['relevance_score'] = self._calculate_iframe_relevance(iframe_info)
                iframes.append(iframe_info)
            
            # Sort by relevance
            iframes.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            return {
                "has_iframes": len(iframes) > 0,
                "iframes": iframes,
                "total_count": len(iframes)
            }
            
        except Exception as e:
            logger.error(f"Iframe detection failed: {str(e)}")
            return {"has_iframes": False, "iframes": [], "error": str(e)}
    
    def _calculate_iframe_relevance(self, iframe_info: Dict) -> int:
        """Calculate how likely an iframe contains job listings"""
        score = 0
        
        # Check src URL
        src = (iframe_info.get('src') or '').lower()
        if any(keyword in src for keyword in ['job', 'career', 'position', 'apply', 'workday', 'greenhouse', 'lever']):
            score += 50
        
        # Check id and name
        id_name = f"{iframe_info.get('id', '')} {iframe_info.get('name', '')}".lower()
        if any(keyword in id_name for keyword in ['job', 'career', 'position', 'listing']):
            score += 30
        
        # Check class
        classes = ' '.join(iframe_info.get('class', [])).lower()
        if any(keyword in classes for keyword in ['job', 'career', 'position']):
            score += 20
        
        # Check title
        title = (iframe_info.get('title') or '').lower()
        if any(keyword in title for keyword in ['job', 'career', 'position']):
            score += 25
        
        # Bonus for known ATS systems
        ats_systems = ['workday', 'greenhouse', 'lever', 'icims', 'taleo', 'smartrecruiters', 'jobvite']
        if any(ats in src for ats in ats_systems):
            score += 60
        
        return score
    
    async def _process_single_iframe(self, iframe_data: Dict, iframe_index: int, job_params: Dict) -> Dict[str, Any]:
        """Process a single iframe to extract job listings"""
        logger.info(f"Processing iframe (relevance: {iframe_data['relevance_score']})")
        
        try:
            src = iframe_data.get('src') or iframe_data.get('data_src')
            
            if not src:
                logger.warning("Iframe has no src, attempting to access via Playwright frame")
                return await self._access_iframe_via_playwright(iframe_index, job_params)
            
            # Convert relative URL to absolute
            if src.startswith('/'):
                current_url = self.web_navigator.current_url
                src = urljoin(current_url, src)
            
            if not src.startswith(('http://', 'https://')):
                logger.warning(f"Invalid iframe src: {src}")
                return {"success": False, "error": "Invalid src"}
            
            # Navigate to iframe URL in main page
            logger.info(f"Navigating to iframe URL: {src}")
            nav_result = await self.web_navigator.navigate_to_url(src)
            
            if not nav_result.get("success"):
                return {"success": False, "error": "Failed to navigate to iframe"}
            
            # Wait for content to load
            await asyncio.sleep(3)
            
            # Extract job listings from iframe content
            page_content = await self.scraping_tool.scrape_page()
            
            # Use LLM to extract jobs
            job_listings_result = await self.scraping_tool.extract_job_listings_with_llm(
                job_params["job_title"]
            )
            
            return {
                "success": True,
                "job_listings": job_listings_result.get("job_listings", []),
                "source_url": src
            }
            
        except Exception as e:
            logger.error(f"Failed to process iframe: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _access_iframe_via_playwright(self, iframe_index: int, job_params: Dict) -> Dict[str, Any]:
        """Access iframe content directly via Playwright frames"""
        try:
            page = self.web_navigator.page
            frames = page.frames
            
            if iframe_index >= len(frames):
                return {"success": False, "error": "Iframe index out of range"}
            
            target_frame = frames[iframe_index]
            
            # Wait for frame to load
            await asyncio.sleep(2)
            
            # Get frame content
            frame_content = await target_frame.content()
            
            # Parse frame content for job listings
            soup = BeautifulSoup(frame_content, 'html.parser')
            
            # Look for job-related elements
            job_links = []
            for link in soup.find_all('a', href=True):
                text = link.get_text(strip=True)
                if any(keyword in text.lower() for keyword in ['apply', 'view', 'position', 'job']):
                    href = link['href']
                    if not href.startswith('http'):
                        href = urljoin(target_frame.url, href)
                    
                    job_links.append({
                        'url': href,
                        'title': text,
                        'source': 'iframe_frame_access'
                    })
            
            return {
                "success": True,
                "job_listings": job_links,
                "extraction_method": "playwright_frame"
            }
            
        except Exception as e:
            logger.error(f"Playwright frame access failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def handle_dynamic_loading(self, max_scrolls: int = 5) -> Dict[str, Any]:
        """Handle infinite scroll and lazy-loaded content"""
        logger.info("Handling dynamic content loading")
        
        try:
            page = self.web_navigator.page
            previous_height = await page.evaluate("document.body.scrollHeight")
            
            scroll_count = 0
            no_change_count = 0
            
            while scroll_count < max_scrolls and no_change_count < 2:
                # Scroll to bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
                
                # Check if new content loaded
                new_height = await page.evaluate("document.body.scrollHeight")
                
                if new_height == previous_height:
                    no_change_count += 1
                else:
                    no_change_count = 0
                
                previous_height = new_height
                scroll_count += 1
                
                logger.info(f"Scroll {scroll_count}/{max_scrolls}, height: {new_height}")
            
            return {
                "success": True,
                "scrolls_performed": scroll_count,
                "final_height": previous_height
            }
            
        except Exception as e:
            logger.error(f"Dynamic loading handling failed: {str(e)}")
            return {"success": False, "error": str(e)}