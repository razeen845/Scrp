"""
Lead Agent - Main orchestrator with Universal Scraper fully integrated
"""

import asyncio
import json
from typing import Dict, Any, List

from agents import Agent, function_tool
from magents.web_agent import WebAgent
from magents.analyzer_agent import AnalyzerAgent
from tools.web_navigation_tool import WebNavigationTool
from tools.html_scraping_tool import HTMLScrapingTool
from tools.search_tool import SearchTool
from tools.job_matching_tool import JobMatchingTool
from utils.logger import setup_logger
from tools.search_pagination_tool import SearchAndPaginationTool  

logger = setup_logger(__name__)

# Define tools as functions for the Lead Agent
@function_tool
def coordinate_company_search(company_name: str) -> str:
    """Search for company website and navigate to it"""
    return f"Searching for company: {company_name}"

@function_tool 
def coordinate_navigation(url: str) -> str:
    """Navigate to specific URL"""
    return f"Navigating to: {url}"

@function_tool
def coordinate_page_analysis(page_type: str, content: str) -> str:
    """Analyze page content for specific purpose"""
    return f"Analyzing {page_type} page content"

class LeadAgent(Agent):
    def __init__(self):
        super().__init__(
            name="JobScrapingLeadAgent",
            instructions="""
            You are the lead agent responsible for orchestrating job scraping operations.
            
            Your responsibilities:
            1. Coordinate with specialized agents to complete job scraping tasks
            2. Manage the workflow: company discovery → careers page → job listings → specific job → data extraction
            3. Handle errors and coordinate retry strategies
            4. Ensure all steps complete successfully before returning results
            
            Available sub-agents:
            - WebAgent: For navigation, scraping, and web interactions
            - AnalyzerAgent: For HTML analysis, job matching, and data extraction
            
            Always maintain context and coordinate the full workflow to completion.
            """,
            model="gpt-5-nano",
            tools=[coordinate_company_search, coordinate_navigation, coordinate_page_analysis]
        )
        
        # Initialize sub-agents
        self.web_agent = None
        self.analyzer_agent = None
        
        # Initialize tools
        self.web_nav_tool = None
        self.scraping_tool = None
        self.search_tool = None
        self.job_matching_tool = None
        self.search_pagination_tool = None
        
        # Cache for job links
        self._cached_job_links = []
        
    async def initialize(self):
        """Initialize all agents and tools using OpenAI Agents SDK"""
        logger.info("Initializing Lead Agent with OpenAI Agents SDK")
        
        # Initialize tools first
        self.web_nav_tool = WebNavigationTool()
        self.scraping_tool = HTMLScrapingTool()
        self.search_tool = SearchTool()
        self.job_matching_tool = JobMatchingTool()
        self.search_pagination_tool = SearchAndPaginationTool(self.web_nav_tool)
        
        await self.web_nav_tool.initialize()
        await self.scraping_tool.initialize()
        await self.search_tool.initialize()
        await self.job_matching_tool.initialize()
        
        # Initialize sub-agents with tools
        self.web_agent = WebAgent(
            web_nav_tool=self.web_nav_tool,
            scraping_tool=self.scraping_tool,
            search_tool=self.search_tool
        )
        
        self.analyzer_agent = AnalyzerAgent(
            scraping_tool=self.scraping_tool,
            job_matching_tool=self.job_matching_tool
        )
        
        await self.web_agent.initialize()
        await self.analyzer_agent.initialize()
        
        logger.info("All agents and tools initialized successfully")
        
    async def process_job_request(self, job_params: Dict[str, Any]) -> Dict[str, Any]:
        """Process job scraping request with universal scraper integration"""
        logger.info(f"🚀 Lead Agent processing job request: {job_params}")
        
        try:
            # Step 1: Determine company URL
            logger.info("Step 1: Determining company URL")
            company_url = await self._get_company_url(job_params)
            
            # Step 2: Find careers page
            logger.info("Step 2: Finding careers page")
            careers_url = await self._find_careers_page(company_url)
            
            # Step 3: Navigate to careers page
            logger.info("Step 3: Navigating to careers page")
            await self.web_agent.navigate_to_url(careers_url)
            await asyncio.sleep(3)

            # Step 3.5: Try to use search if available (NEW)
            logger.info("Step 3.5: Attempting to use search functionality")
            search_result = await self.search_pagination_tool.detect_and_use_search(job_params)

            if search_result.get("search_used"):
                logger.info("✅ Search functionality used successfully")
                await asyncio.sleep(3)  # Wait for search results
            else:
                logger.info("ℹ️ No search functionality found or failed, continuing...")

            # Step 4: Check for pagination
            logger.info("Step 4: Checking for pagination")
            pagination_info = await self.search_pagination_tool.detect_pagination_info()

            # Step 5: Use Universal Scraper (with or without pagination)
            logger.info("Step 5: Using Universal Scraper")
            from tools.universal_scraper import UniversalJobScraper

            universal_scraper = UniversalJobScraper(
                self.web_nav_tool,
                self.scraping_tool
            )

            # If pagination exists, use pagination tool
            if pagination_info.get("has_pagination"):
                logger.info(f"📄 Pagination detected: {pagination_info.get('pagination_type')}")
                
                # Define extraction function for pagination
                async def extract_from_page():
                    result = await universal_scraper.scrape_any_careers_page(job_params)
                    return result.get("job_listings", [])
                
                # Use pagination tool
                scrape_result = await self.search_pagination_tool.handle_pagination(extract_from_page)
                
                job_links = scrape_result.get("all_results", [])
                pages_scraped = scrape_result.get("pages_scraped", 1)
                
                logger.info(f"✅ Scraped {len(job_links)} jobs from {pages_scraped} pages")
            else:
                # Single page scrape
                logger.info("ℹ️ No pagination detected, single page scrape")
                scrape_result = await universal_scraper.scrape_any_careers_page(job_params)
                job_links = scrape_result.get("job_listings", [])
                pages_scraped = 1

            # Continue with rest of the workflow...
            if not scrape_result.get("success"):
                logger.warning(f"Universal scraper failed: {scrape_result.get('error')}")
                # Fallback to traditional method
                scrape_result = await self._fallback_scraping(job_params)
                job_links = scrape_result.get("job_listings", [])

            if not job_links:
                logger.warning("No job listings found")
                return {
                    "success": False,
                    "error": "No job listings found on careers page",
                    "company_url": company_url,
                    "careers_url": careers_url
                }

            logger.info(f"✅ Found {len(job_links)} job listings")

            # Step 6: Match jobs using fuzzy matching
            logger.info("Step 6: Matching jobs with fuzzy matching")
            
           
            
            from tools.universal_scraper import UniversalJobScraper
            
            universal_scraper = UniversalJobScraper(
                self.web_nav_tool,
                self.scraping_tool
            )
            
         
            
            
          
                
            
            # Use universal scraper
            scrape_result = await universal_scraper.scrape_any_careers_page(job_params)
            
            if not scrape_result.get("success"):
                logger.warning(f"Universal scraper failed: {scrape_result.get('error')}")
                # Fallback to traditional method
                scrape_result = await self._fallback_scraping(job_params)
            
            job_links = scrape_result.get("job_listings", [])
            
            if not job_links:
                logger.warning("No job listings found")
                return {
                    "success": False,
                    "error": "No job listings found on careers page",
                    "company_url": company_url,
                    "careers_url": careers_url
                }
            
            logger.info(f"✅ Found {len(job_links)} job listings")
            
            # Step 5: Match jobs using fuzzy matching
            logger.info("Step 5: Matching jobs with fuzzy matching")
            all_matches = await self.analyzer_agent.find_all_job_matches(
                job_links,
                job_params
            )
            
            if not all_matches.get("matches"):
                logger.warning("No matching jobs found")
                return {
                    "success": False,
                    "error": "No jobs matched the search criteria",
                    "total_jobs_found": len(job_links),
                    "company_url": company_url,
                    "careers_url": careers_url
                }
            
            logger.info(f"✅ Found {len(all_matches['matches'])} matching jobs")
            
            # Step 6: Scrape each matching job
            logger.info("Step 6: Scraping individual job postings")
            scraped_jobs = await self._scrape_all_matched_jobs(
                all_matches["matches"],
                job_params
            )
            
            # Compile final results
            result = {
                "success": True,
                "job_params": job_params,
                "workflow_steps": {
                    "company_url": company_url,
                    "careers_url": careers_url,
                    "job_listings_url": self.web_nav_tool.current_url,
                    "strategy_used": scrape_result.get("strategy", {}).get("strategy"),
                    "ats_system": scrape_result.get("strategy", {}).get("ats_system"),
                    "confidence": scrape_result.get("strategy", {}).get("confidence")
                },
                "jobs_found": len(scraped_jobs),
                "all_job_data": scraped_jobs,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            logger.info(f"✅ Job scraping workflow completed successfully: {len(scraped_jobs)} jobs")
            return result
            
        except Exception as e:
            logger.error(f"❌ Lead Agent error: {str(e)}")
            return self._handle_scraping_error(e, job_params)
    

    async def _fallback_scraping(self, job_params: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback to traditional scraping method"""
        logger.info("🔄 Falling back to traditional scraping method")
        
        try:
            page_content = await self.web_agent.scrape_current_page()
            
            job_links_result = await self.analyzer_agent.extract_job_links(
                page_content["html_content"],
                job_params
            )
            
            return {
                "success": job_links_result.get("success", False),
                "job_listings": job_links_result.get("job_links", [])
            }
            
        except Exception as e:
            logger.error(f"Fallback scraping failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def _get_company_url(self, job_params: Dict[str, Any]) -> str:
        """Get company URL using Web Agent"""
        if job_params.get("company_domain"):
            domain = job_params["company_domain"]
            if not domain.startswith(("http://", "https://")):
                domain = f"https://{domain}"
            return domain
        else:
            # Use Web Agent to search for company
            company_name = job_params["company_name"]
            search_result = await self.web_agent.search_company(company_name)
            return search_result["url"]
            
    async def _find_careers_page(self, company_url: str) -> str:
        """Find careers page using Web Agent and Analyzer Agent coordination"""
        # Navigate to company website using Web Agent
        await self.web_agent.navigate_to_url(company_url)
        
        # Get page content using Web Agent
        page_content = await self.web_agent.scrape_current_page()
        
        # Analyze content to find careers link using Analyzer Agent
        careers_analysis = await self.analyzer_agent.find_careers_link(
            page_content["html_content"], 
            {"base_url": company_url}
        )
        
        return careers_analysis["careers_url"]
    
    async def _scrape_all_matched_jobs(self, matches: List[Dict], job_params: Dict) -> List[Dict]:
        """Scrape all matched jobs with bot protection checks"""
        scraped_jobs = []
        visited_urls = set()
        
        # Import universal scraper for protection checks
        from tools.universal_scraper import UniversalJobScraper
        universal_scraper = UniversalJobScraper(self.web_nav_tool, self.scraping_tool)
        
        for i, job_match in enumerate(matches):
            try:
                job_url = job_match["url"]
                
                if job_url in visited_urls:
                    logger.info(f"Already visited {job_url}, skipping")
                    continue
                
                visited_urls.add(job_url)
                logger.info(f"Scraping job {i+1}/{len(matches)}: {job_match['title']}")
                
                # Navigate to job
                nav_result = await self.web_agent.navigate_to_url(job_url)
                
                if not nav_result.get("success"):
                    logger.warning(f"Failed to navigate to {job_url}")
                    continue
                
                await asyncio.sleep(2)
                
               
                
                
                # Extract job data
                job_page_content = await self.web_agent.scrape_current_page()
                
                job_data_result = await self.analyzer_agent.extract_enhanced_job_data(
                    job_page_content["html_content"],
                    job_params
                )
                
                if job_data_result.get("success"):
                    job_data = job_data_result["job_data"]
                    job_data["match_score"] = job_match["match_score"]
                    job_data["job_url"] = job_url
                    job_data["scrape_order"] = i + 1
                    
                    scraped_jobs.append(job_data)
                    logger.info(f"✅ Successfully scraped: {job_data.get('title', 'Unknown')}")
                else:
                    logger.warning(f"Failed to extract data from: {job_match['title']}")
                    
            except Exception as e:
                logger.error(f"Error scraping job {job_match.get('title')}: {str(e)}")
                continue
        
        return scraped_jobs
    
    def _handle_scraping_error(self, error: Exception, job_params: Dict) -> Dict:
        """Enhanced error handling with specific messages"""
        error_str = str(error).lower()
        
        if "cloudflare" in error_str:
            return {
                "success": False,
                "error": "Cloudflare protection detected",
                "error_type": "bot_protection",
                "recommendation": "This website uses Cloudflare protection. Try using a proxy or contact the company directly.",
                "job_params": job_params
            }
        
        elif "recaptcha" in error_str:
            return {
                "success": False,
                "error": "reCAPTCHA detected",
                "error_type": "captcha",
                "recommendation": "This website requires human verification. Manual application recommended.",
                "job_params": job_params
            }
        
        elif "timeout" in error_str:
            return {
                "success": False,
                "error": "Page load timeout",
                "error_type": "timeout",
                "recommendation": "The website is slow or unresponsive. Try again later.",
                "job_params": job_params
            }
        
        elif "navigation" in error_str:
            return {
                "success": False,
                "error": "Navigation failed",
                "error_type": "navigation",
                "recommendation": "Could not navigate to the careers page. Check if the URL is correct.",
                "job_params": job_params
            }
        
        else:
            return {
                "success": False,
                "error": str(error),
                "error_type": "unknown",
                "recommendation": "An unexpected error occurred. Please try again.",
                "job_params": job_params
            }
        
    async def cleanup(self):
        """Cleanup all resources"""
        logger.info("Cleaning up Lead Agent resources")
        
        # Cleanup sub-agents
        if self.web_agent:
            await self.web_agent.cleanup()
            
        if self.analyzer_agent:
            await self.analyzer_agent.cleanup()
            
        # Cleanup tools
        for tool in [self.web_nav_tool, self.scraping_tool, self.search_tool, self.job_matching_tool,self.search_pagination_tool]:
            if tool and hasattr(tool, 'cleanup'):
                await tool.cleanup()
                
        logger.info("Lead Agent cleanup completed")