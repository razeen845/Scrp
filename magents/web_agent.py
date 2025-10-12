"""
Web Agent - Handles web navigation and scraping with iframe support fully integrated
"""

import asyncio
from typing import Dict, Any
from urllib.parse import urljoin

from agents import Agent, function_tool
from tools.web_navigation_tool import WebNavigationTool
from tools.html_scraping_tool import HTMLScrapingTool
from tools.search_tool import SearchTool
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Define tools as functions for Web Agent
@function_tool
def navigate_to_url_tool(url: str) -> str:
    """Navigate to a specific URL"""
    return f"Navigating to: {url}"

@function_tool
def scrape_page_content_tool(include_links: bool = True, clean_text: bool = False) -> str:
    """Scrape HTML content from current page"""
    return f"Scraping page content (links: {include_links}, clean: {clean_text})"

@function_tool
def search_company_website_tool(company_name: str) -> str:
    """Search for a company's official website using search engines"""
    return f"Searching for company: {company_name}"

@function_tool
def interact_with_element_tool(action: str, selector: str, value: str = None) -> str:
    """Interact with page elements (click, fill forms, submit)"""
    return f"Interacting: {action} on {selector} with {value}"

@function_tool
def find_page_elements_tool(selectors: str) -> str:
    """Find specific elements on the page using CSS selectors"""
    return f"Finding elements: {selectors}"

@function_tool
def handle_page_search_tool(job_title: str) -> str:
    """Handle search functionality on current page"""
    return f"Searching page for: {job_title}"

@function_tool
def check_page_iframes_tool() -> str:
    """Check for iframes on current page"""
    return "Checking for iframes"

class WebAgent(Agent):
    def __init__(self, web_nav_tool: WebNavigationTool, scraping_tool: HTMLScrapingTool, search_tool: SearchTool):
        super().__init__(
            name="WebNavigationAgent",
            instructions="""
            You are a web navigation and scraping specialist agent.
            
            Your responsibilities:
            1. Navigate to websites and handle page loading
            2. Search for company websites using search engines
            3. Scrape HTML content from web pages
            4. Interact with web page elements (forms, buttons, search bars)
            5. Handle dynamic content, iframes, and complex page structures
            6. Perform searches within websites using their search functionality
            
            Always ensure pages are fully loaded before scraping content.
            Handle errors gracefully and provide detailed feedback about navigation results.
            """,
            model="gpt-5-nano",
            tools=[
                navigate_to_url_tool,
                scrape_page_content_tool,
                search_company_website_tool,
                interact_with_element_tool,
                find_page_elements_tool,
                handle_page_search_tool,
                check_page_iframes_tool
            ]
        )
        
        # Store tool references
        self.web_nav_tool = web_nav_tool
        self.scraping_tool = scraping_tool
        self.search_tool = search_tool
        
        # Initialize iframe handler
        self.iframe_handler = None
        
    async def initialize(self):
        """Initialize the Web Agent with tools"""
        logger.info("Initializing Web Agent with OpenAI Agents SDK")
        
        # Set up scraping tool with navigator reference
        self.scraping_tool.set_web_navigator(self.web_nav_tool)
        
        # Initialize iframe handler
        from tools.iframe_handler import IframeHandler
        self.iframe_handler = IframeHandler(self.web_nav_tool, self.scraping_tool)
        
        logger.info("Web Agent initialized with all tools registered")
        
    async def search_company(self, company_name: str) -> Dict[str, Any]:
        """Search for company website and navigate to it"""
        logger.info(f"Web Agent searching for company: {company_name}")
        
        try:
            # Use search tool to find company website
            search_result = await self.search_tool.search_company_website(company_name)
            
            if search_result.get("success"):
                # Navigate to the found website
                nav_result = await self.web_nav_tool.navigate_to_url(search_result["url"])
                
                if nav_result.get("success"):
                    return {
                        "success": True,
                        "url": search_result["url"],
                        "title": nav_result.get("title", ""),
                        "confidence": search_result.get("confidence", "medium"),
                        "message": f"Successfully found and navigated to {company_name} website"
                    }
                    
            raise Exception(f"Could not find or navigate to website for {company_name}")
            
        except Exception as e:
            logger.error(f"Company search failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def navigate_to_url(self, url: str) -> Dict[str, Any]:
        """Navigate to specific URL"""
        logger.info(f"Web Agent navigating to: {url}")
        
        try:
            result = await self.web_nav_tool.navigate_to_url(url)
            
            if result.get("success"):
                # Wait for page to stabilize
                await asyncio.sleep(2)
                
            return result
            
        except Exception as e:
            logger.error(f"Navigation failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def scrape_current_page(self) -> Dict[str, Any]:
        """Scrape HTML content from current page"""
        logger.info("Web Agent scraping current page")
        
        try:
            result = await self.scraping_tool.scrape_page(
                include_links=True, 
                clean_text=False
            )
            
            logger.info(f"Scraped page content: {result.get('html_length', 0)} characters")
            return result
            
        except Exception as e:
            logger.error(f"Page scraping failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def scrape_with_iframe_detection(self, job_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhanced scraping that automatically detects and handles iframes
        """
        logger.info("Starting enhanced scraping with iframe detection")
        
        try:
            # First, check if current page has iframes
            iframe_result = await self.iframe_handler.detect_and_handle_iframes(job_params)
            
            if iframe_result.get("success") and iframe_result.get("job_listings"):
                logger.info(f"Found {len(iframe_result['job_listings'])} jobs via iframe handling")
                return {
                    "success": True,
                    "job_links": iframe_result["job_listings"],
                    "source": "iframe",
                    "iframes_processed": iframe_result.get("iframes_processed", 0)
                }
            
            # If no iframes or no jobs in iframes, try main page
            logger.info("No jobs in iframes, trying main page extraction")
            
            # Handle dynamic loading first
            await self.iframe_handler.handle_dynamic_loading()
            
            # Extract from main page
            page_content = await self.scrape_current_page()
            
            job_listings_result = await self.scraping_tool.extract_job_listings_with_llm(
                job_params["job_title"]
            )
            
            return {
                "success": True,
                "job_links": job_listings_result.get("job_listings", []),
                "source": "main_page",
                "extraction_method": "llm_analysis"
            }
            
        except Exception as e:
            logger.error(f"Enhanced scraping failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def search_jobs_on_page(self, job_title: str) -> Dict[str, Any]:
        """Use GPT to find and use search functionality"""
        from openai import AsyncOpenAI
        
        try:
            # Get page HTML
            page_content = await self.scraping_tool.scrape_page()
            html_content = page_content["html_content"]
            
            client = AsyncOpenAI()
            
            prompt = f"""Analyze this HTML and find the best way to search for jobs: "{job_title}"

Find search inputs and return JSON:
{{"search_found": true/false, "input_selector": "the exact css selector for input", "submit_method": "click_button|press_enter", "submit_selector": "selector for submit button if needed", "reasoning": "explanation"}}

HTML content: {html_content[:200000]}
"""
            
            response = await client.chat.completions.create(
                model="gpt-5-nano",
                messages=[{"role": "user", "content": prompt}],
                temperature=1
            )
            
            import json
            search_info = json.loads(response.choices[0].message.content)
            logger.info(f"Search info: {search_info}")
            
            if search_info.get("search_found"):
                # Use GPT-provided selector
                selector = search_info["input_selector"]
                fill_result = await self.web_nav_tool.interact_with_element("fill", selector, job_title)
                
                if fill_result.get("success"):
                    if search_info["submit_method"] == "click_button":
                        submit_result = await self.web_nav_tool.interact_with_element("click", search_info["submit_selector"])
                    else:
                        submit_result = await self.web_nav_tool.interact_with_element("submit", selector)
                        
                    await asyncio.sleep(3)
                    return {"success": True, "current_url": self.web_nav_tool.current_url}
            
            return {"success": False, "error": "GPT couldn't find search functionality"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def handle_iframe_content(self) -> Dict[str, Any]:
        """Handle content inside iframes"""
        logger.info("Web Agent handling iframe content")
        
        try:
            iframe_result = await self.scraping_tool.check_for_iframes()
            
            if iframe_result.get("has_iframes"):
                iframes = iframe_result["iframes"]
                
                # Try to interact with the first meaningful iframe
                for iframe in iframes:
                    if iframe.get("src"):
                        # Navigate to iframe source if it's a full URL
                        if iframe["src"].startswith(("http://", "https://")):
                            nav_result = await self.web_nav_tool.navigate_to_url(iframe["src"])
                            if nav_result.get("success"):
                                return nav_result
                                
            return {"success": False, "error": "No actionable iframes found"}
            
        except Exception as e:
            logger.error(f"Iframe handling failed: {str(e)}")
            return {"success": False, "error": str(e)}
        
    async def cleanup(self):
        """Cleanup Web Agent resources"""
        logger.info("Cleaning up Web Agent resources")
        # Cleanup handled by tools