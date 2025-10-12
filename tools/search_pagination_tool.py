"""
Search and Pagination Tool - Handles search forms and pagination separately
Can be used by any scraper without modifying core logic
"""

import asyncio
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
from openai import AsyncOpenAI
from utils.logger import setup_logger

logger = setup_logger(__name__)

class SearchAndPaginationTool:
    """
    Standalone tool for handling search forms and pagination
    Can be used before/after scraping to enhance results
    """
    
    def __init__(self, web_navigator):
        self.web_navigator = web_navigator
        self.client = AsyncOpenAI()
        self.max_pages = 5
        
    async def detect_and_use_search(self, job_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect search inputs on current page and use them
        Returns: {"success": bool, "search_used": bool, "error": str}
        """
        logger.info("🔍 SearchTool: Detecting search inputs...")
        
        try:
            page = self.web_navigator.page
            html_content = await self.web_navigator.get_page_html()
            
            # Analyze page for search inputs
            search_info = await self._analyze_search_inputs(html_content)
            
            if not search_info["has_search"]:
                logger.info("❌ No search inputs detected")
                return {"success": True, "search_used": False, "message": "No search found"}
            
            logger.info(f"✅ Found {len(search_info['inputs'])} search input(s)")
            
            # Try to use the search
            search_result = await self._execute_search(
                page, 
                search_info['inputs'], 
                job_params['job_title'],
                job_params.get('location')
            )
            
            if search_result["success"]:
                logger.info("✅ Search executed successfully")
                await asyncio.sleep(5)  # Wait for results
                return {"success": True, "search_used": True}
            else:
                logger.warning(f"⚠️ Search failed: {search_result.get('error')}")
                return {"success": True, "search_used": False, "error": search_result.get('error')}
                
        except Exception as e:
            logger.error(f"Search detection failed: {str(e)}")
            return {"success": False, "search_used": False, "error": str(e)}
    
    async def _analyze_search_inputs(self, html_content: str) -> Dict[str, Any]:
        """Analyze HTML to find search inputs"""
        
        soup = BeautifulSoup(html_content, 'html.parser')
        search_keywords = ['search', 'keyword', 'query', 'job', 'title', 'position']
        location_keywords = ['location', 'city', 'place', 'where']
        
        search_inputs = []
        location_inputs = []
        
        # Scan all input fields
        for input_elem in soup.find_all('input'):
            input_type = input_elem.get('type', 'text')
            input_id = input_elem.get('id', '')
            input_name = input_elem.get('name', '')
            input_placeholder = input_elem.get('placeholder', '')
            input_class = ' '.join(input_elem.get('class', []))
            
            all_text = f"{input_id} {input_name} {input_placeholder} {input_class}".lower()
            
            # Check for search input
            if input_type in ['text', 'search']:
                is_search = any(kw in all_text for kw in search_keywords)
                is_location = any(kw in all_text for kw in location_keywords)
                
                input_info = {
                    "id": input_id,
                    "name": input_name,
                    "type": input_type,
                    "placeholder": input_placeholder,
                    "selectors": []
                }
                
                # Build selectors
                if input_id:
                    input_info["selectors"].append(f"#{input_id}")
                if input_name:
                    input_info["selectors"].append(f'input[name="{input_name}"]')
                if input_class:
                    first_class = input_elem.get('class', [])[0] if input_elem.get('class') else None
                    if first_class:
                        input_info["selectors"].append(f'input.{first_class}')
                
                if is_search and not is_location:
                    search_inputs.append(input_info)
                elif is_location:
                    location_inputs.append(input_info)
        
        return {
            "has_search": len(search_inputs) > 0,
            "inputs": search_inputs,
            "location_inputs": location_inputs
        }
    
    async def _execute_search(self, page, search_inputs: List[Dict], job_title: str, location: Optional[str] = None) -> Dict[str, Any]:
        """Execute search using detected inputs"""
        
        # Try to fill search input
        search_filled = False
        for search_input in search_inputs:
            for selector in search_input["selectors"]:
                try:
                    logger.info(f"  Trying selector: {selector}")
                    element = await page.wait_for_selector(selector, timeout=2000)
                    if element and await element.is_visible() and await element.is_enabled():
                        await page.fill(selector, job_title)
                        logger.info(f"  ✅ Filled search: {selector}")
                        search_filled = True
                        break
                except Exception as e:
                    logger.debug(f"  ❌ Selector failed: {str(e)[:50]}")
                    continue
            
            if search_filled:
                break
        
        if not search_filled:
            # Try generic fallback selectors
            fallback_selectors = [
    # --- Common by input type ---
                                'input[type="search"]',
                                'input[type="text"][aria-label*="search" i]',
                                'input[type="text"][role="searchbox" i]',
                                'input[type="text"][placeholder*="search" i]',
                                'input[type="text"][placeholder*="keyword" i]',
                                'input[type="text"][placeholder*="job" i]',
                                'input[type="text"][placeholder*="position" i]',
                                'input[type="text"][placeholder*="title" i]',

                                # --- Common by name attribute ---
                                'input[name*="search" i]',
                                'input[name*="keyword" i]',
                                'input[name*="q" i]',
                                'input[name*="query" i]',
                                'input[name*="job" i]',
                                'input[name*="position" i]',
                                'input[name*="title" i]',
                                'input[name*="role" i]',

                                # --- Common by id attribute ---
                                'input[id*="search" i]',
                                'input[id*="keyword" i]',
                                'input[id*="q" i]',
                                'input[id*="query" i]',
                                'input[id*="job" i]',
                                'input[id*="title" i]',
                                'input[id^="typehead" i]',
                                'input[id^="global-search" i]',
                                'input[id^="careers-search" i]',

                                # --- Common by class name ---
                                'input[class*="search" i]',
                                'input[class*="keyword" i]',
                                'input[class*="job" i]',
                                'input[class*="query" i]',
                                'input[class*="title" i]',
                                'input[class*="position" i]',
                                'input[class*="phw-s-a11y-search-box" i]',  # NTT Data pattern
                                'input[class*="phw-s-keywords" i]',         # NTT Data keyword box
                                'input[class*="global-search" i]',
                                'input[class*="search-field" i]',
                                'input[class*="search-box" i]',
                                'input[class*="input-search" i]',
                                'input[class*="search-input" i]',
                                'input[class*="job-search" i]',
                                'input[class*="careers-search" i]',

                                # --- Generic fallbacks ---
                                'input[aria-label*="search" i]',
                                'input[title*="search" i]',
                                'input[role="combobox"][aria-autocomplete="list"]',
                                'input[aria-labelledby*="search" i]',
                                'input[aria-describedby*="search" i]',
                                'input[placeholder][class*="input" i]',
                                'input:not([type="hidden"]):not([disabled])',

                                # --- Company-specific patterns (known platforms) ---
                                'input[id*="jobsearch" i]',        # Workday / Taleo
                                'input[id*="keysearch" i]',        # SuccessFactors
                                'input[id*="keywordsearch" i]',    # SuccessFactors alt
                                'input[name*="keywordsearch" i]',  # SuccessFactors alt
                                'input[id*="gh-search" i]',        # Greenhouse
                                'input[name*="lever-search" i]',   # Lever
                                'input[class*="ais-SearchBox-input" i]',  # Algolia-based career pages
                            ]
            
            for selector in fallback_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=2000)
                    if element and await element.is_visible():
                        await page.fill(selector, job_title)
                        logger.info(f"  ✅ Filled with fallback: {selector}")
                        search_filled = True
                        break
                except:
                    continue
        
        if not search_filled:
            return {"success": False, "error": "Could not fill search input"}
        
        await asyncio.sleep(1)
        
        # Try to submit
        submit_clicked = False
        
        # Try common submit buttons
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Search")',
            'button:has-text("Find")',
            'button:has-text("Go")',
            'button[aria-label*="search" i]',
            '.search-button',
            'button[class*="search"]',
        ]
        
        for selector in submit_selectors:
            try:
                await page.click(selector, timeout=1000)
                logger.info(f"✅ Clicked submit: {selector}")
                submit_clicked = True
                break
            except:
                continue
        
        # If no button found, press Enter
        if not submit_clicked:
            logger.info("⌨️ Pressing Enter")
            # Try to press Enter on the last filled input
            for search_input in search_inputs:
                for selector in search_input["selectors"]:
                    try:
                        await page.press(selector, "Enter")
                        logger.info(f"✅ Pressed Enter on: {selector}")
                        submit_clicked = True
                        break
                    except:
                        continue
                if submit_clicked:
                    break
        
        if not submit_clicked:
            return {"success": False, "error": "Could not submit search"}
        
        return {"success": True}
    
    async def handle_pagination(self, extractor_func, *args, **kwargs) -> Dict[str, Any]:
        """
        Handle pagination and collect results from multiple pages
        
        Args:
            extractor_func: Function to extract data from each page (should return List[Dict])
            *args, **kwargs: Arguments to pass to extractor_func
            
        Returns:
            {"success": bool, "all_results": List[Dict], "pages_scraped": int}
        """
        logger.info("📄 PaginationTool: Starting pagination handling...")
        
        all_results = []
        page_count = 0
        page = self.web_navigator.page
        
        try:
            while page_count < self.max_pages:
                page_count += 1
                logger.info(f"📄 Processing page {page_count}/{self.max_pages}")
                
                # Extract from current page
                try:
                    page_results = await extractor_func(*args, **kwargs)
                    
                    if page_results:
                        # Deduplicate by URL
                        existing_urls = {item.get('url') for item in all_results if item.get('url')}
                        new_results = [item for item in page_results if item.get('url') not in existing_urls]
                        all_results.extend(new_results)
                        logger.info(f"✅ Added {len(new_results)} new results from page {page_count}")
                    else:
                        logger.warning(f"⚠️ No results on page {page_count}")
                        
                except Exception as e:
                    logger.error(f"Extraction failed on page {page_count}: {str(e)}")
                
                # Try to find and click next button
                next_found = await self._click_next_page(page)
                
                if not next_found:
                    logger.info("📍 No more pages found")
                    break
                
                # Wait for next page to load
                await asyncio.sleep(3)
            
            logger.info(f"🎉 Pagination complete: {len(all_results)} total results from {page_count} pages")
            
            return {
                "success": True,
                "all_results": all_results,
                "pages_scraped": page_count
            }
            
        except Exception as e:
            logger.error(f"Pagination handling failed: {str(e)}")
            return {
                "success": len(all_results) > 0,
                "all_results": all_results,
                "pages_scraped": page_count,
                "error": str(e)
            }
    
    async def _click_next_page(self, page) -> bool:
        """Try to find and click the next page button"""
        
        logger.info("🔍 Looking for next page button...")
        
        next_selectors = [
            # Text-based
            'a:has-text("Next")',
            'button:has-text("Next")',
            'a:has-text("›")',
            'button:has-text("›")',
            'a:has-text(">")',
            
            # Aria labels
            'a[aria-label="Next"]',
            'button[aria-label="Next"]',
            'a[aria-label*="next" i]',
            'button[aria-label*="next" i]',
            
            # Common classes
            'a.next',
            'button.next',
            'a[class*="next" i]',
            'button[class*="next" i]',
            '.pagination a:last-child',
            
            # Workday specific
            '[data-automation-id="nextButton"]',
            
            # Rel attribute
            'a[rel="next"]',
            'button[rel="next"]',
        ]
        
        for selector in next_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=2000)
                
                if element:
                    # Check if visible and not disabled
                    is_visible = await element.is_visible()
                    is_enabled = await element.is_enabled()
                    
                    # Check for disabled class
                    class_attr = await element.get_attribute('class') or ''
                    is_disabled_class = 'disabled' in class_attr.lower()
                    
                    if is_visible and is_enabled and not is_disabled_class:
                        logger.info(f"✅ Clicking next: {selector}")
                        await element.click()
                        return True
                    else:
                        logger.debug(f"Next button found but disabled: {selector}")
                        
            except Exception as e:
                logger.debug(f"Selector failed: {selector}")
                continue
        
        logger.info("❌ No next page button found")
        return False
    
    async def detect_pagination_info(self) -> Dict[str, Any]:
        """
        Detect if current page has pagination
        Returns info about pagination controls
        """
        try:
            html_content = await self.web_navigator.get_page_html()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            has_pagination = False
            pagination_type = None
            
            # Check for pagination indicators
            pagination_indicators = [
                ('next', 'Next button'),
                ('previous', 'Previous button'),
                ('pagination', 'Pagination container'),
                ('page-', 'Page numbers'),
            ]
            
            text_content = soup.get_text().lower()
            
            for indicator, desc in pagination_indicators:
                if indicator in text_content or soup.find(class_=re.compile(indicator, re.I)):
                    has_pagination = True
                    pagination_type = desc
                    break
            
            # Check for "showing X of Y" pattern
            import re
            showing_pattern = re.search(r'showing\s+\d+\s*-?\s*\d+\s+of\s+(\d+)', text_content, re.I)
            total_items = None
            if showing_pattern:
                total_items = int(showing_pattern.group(1))
                has_pagination = True
            
            return {
                "has_pagination": has_pagination,
                "pagination_type": pagination_type,
                "total_items": total_items
            }
            
        except Exception as e:
            logger.error(f"Pagination detection failed: {str(e)}")
            return {"has_pagination": False, "error": str(e)}