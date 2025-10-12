"""
Analyzer Agent - HTML analysis and decision making using OpenAI Agents SDK
"""

import asyncio
from typing import Dict, Any, List

from agents import Agent, function_tool
from tools.html_scraping_tool import HTMLScrapingTool
from tools.job_matching_tool import JobMatchingTool
from utils.logger import setup_logger
from bs4 import BeautifulSoup
import re

logger = setup_logger(__name__)

# Define tools as functions for Analyzer Agent
@function_tool
def analyze_html_structure_tool(html_content: str, analysis_type: str = "general") -> str:
    """Analyze HTML structure to understand page layout and content"""
    return f"Analyzing HTML structure for {analysis_type}"

@function_tool
def validate_job_listings_page_tool(html_content: str) -> str:
    """Validate if current page contains actual job listings"""
    return f"Validating job listings page content"

@function_tool
def find_careers_links_tool(html_content: str, base_url: str) -> str:
    """Find careers/jobs page links from company homepage"""
    return f"Finding careers links from {base_url}"

@function_tool
def extract_job_links_tool(html_content: str, job_title: str) -> str:
    """Extract job posting links from careers/listings pages"""
    return f"Extracting job links for {job_title}"

@function_tool
def match_jobs_fuzzy_tool(job_links: str, job_title: str, location: str = None) -> str:
    """Find best job matches using fuzzy matching"""
    return f"Matching jobs for {job_title} in {location or 'any location'}"

@function_tool
def extract_structured_job_data_tool(html_content: str, job_context: str = None) -> str:
    """Extract structured job information from job posting HTML"""
    return f"Extracting job data from posting"

@function_tool
def determine_page_strategy_tool(html_content: str, current_goal: str, context: str = None) -> str:
    """Determine the next action needed for job scraping workflow"""
    return f"Determining strategy for {current_goal}"

@function_tool
def extract_jobs_with_llm_tool(html_content: str, job_title: str) -> str:
    """Use LLM to intelligently extract job listings from HTML"""
    return f"Using LLM to analyze page for '{job_title}' positions"

# @function_tool
async def find_all_job_matches(self, job_links: List[Dict], job_params: Dict[str, Any]) -> Dict[str, Any]:
    """Find ALL job matches above threshold - calls JobMatchingTool"""
    return await self.job_matching_tool.find_all_job_matches(job_links, job_params)

# @function_tool
async def extract_enhanced_job_data(self, html_content: str, job_params: Dict[str, Any]) -> Dict[str, Any]:
    """Extract enhanced job data - calls JobMatchingTool"""
    return await self.job_matching_tool.extract_enhanced_job_data(html_content, job_params)

class AnalyzerAgent(Agent):
    def __init__(self, scraping_tool: HTMLScrapingTool, job_matching_tool: JobMatchingTool):
        super().__init__(
            name="HTMLAnalyzerAgent",
            instructions="""
            You are an HTML analysis and job matching specialist agent.
            
            Your responsibilities:
            1. Analyze HTML content to understand page structure and purpose
            2. Find careers/jobs page links from company homepages
            3. Extract job posting links from careers/listings pages
            4. Determine the best navigation strategy for different page types
            5. Use fuzzy matching to find the best job matches
            6. Extract structured job data from job posting pages
            
            Always provide detailed reasoning for your analysis and decisions.
            Use fuzzy matching scores to rank job matches by relevance.
            """,
            model="gpt-5-nano",
            tools=[
                analyze_html_structure_tool,
                find_careers_links_tool,
                validate_job_listings_page_tool,
                extract_jobs_with_llm_tool,
                match_jobs_fuzzy_tool,
                extract_structured_job_data_tool,
                determine_page_strategy_tool
            ]
        )
        
        # Store tool references
        self.scraping_tool = scraping_tool
        self.job_matching_tool = job_matching_tool
        
    async def initialize(self):
        """Initialize the Analyzer Agent with tools"""
        logger.info("Initializing Analyzer Agent with OpenAI Agents SDK")
        logger.info("Analyzer Agent initialized with all tools registered")
        
    async def find_careers_link(self, html_content: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Find careers page link from homepage HTML"""
        logger.info("Analyzer Agent finding careers link")
        
        try:
            base_url = context.get("base_url", "")
            
            # Use job matching tool to find best careers link
            careers_result = await self.job_matching_tool.find_careers_link(
                html_content, 
                base_url
            )
            
            if careers_result.get("success"):
                logger.info(f"Found careers link: {careers_result['careers_url']}")
                return careers_result
            else:
                return {
                    "success": False,
                    "error": "No suitable careers link found",
                    "fallback_url": f"{base_url}/careers"
                }
                
        except Exception as e:
            logger.error(f"Careers link finding failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def extract_job_links(self, html_content: str, job_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract job links using LLM analysis instead of selectors"""
        logger.info("Analyzer Agent extracting job links with LLM")
        
        try:
            # Use LLM-powered extraction instead of selectors
            job_listings_result = await self.scraping_tool.extract_job_listings_with_llm(
                job_params["job_title"]
            )
            
            if job_listings_result.get("success") and job_listings_result.get("job_listings"):
                job_links = job_listings_result["job_listings"]
                logger.info(f"LLM found {len(job_links)} job listings")
                
                return {
                    "success": True,
                    "job_links": job_links,
                    "total_found": len(job_links),
                    "extraction_method": "llm_analysis"
                }
            else:
                return {
                    "success": False,
                    "error": "LLM could not identify job listings",
                    "job_links": []
                }
                
        except Exception as e:
            logger.error(f"LLM job links extraction failed: {str(e)}")
            return {"success": False, "error": str(e)}
        
    # ligma
    async def decide_careers_page_action(self, html_content: str, job_title: str) -> Dict[str, Any]:
        """Let LLM analyze careers page and decide best action"""
        logger.info(f"LLM deciding action for careers page (looking for: {job_title})")
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove noise
            for element in soup(["script", "style", "nav", "footer"]):
                element.decompose()
                
            # Extract key page elements
            page_text = soup.get_text().lower()  # Limit for analysis
            
            # Find search elements
            search_inputs = []
            for form in soup.find_all('form'):
                for input_elem in form.find_all('input'):
                    if input_elem.get('type') in ['text', 'search']:
                        search_inputs.append({
                            'placeholder': input_elem.get('placeholder', ''),
                            'name': input_elem.get('name', ''),
                            'id': input_elem.get('id', '')
                        })
            
            # Find all links with their context
            links = []
            for link in soup.find_all('a', href=True):
                text = link.get_text(strip=True)
                href = link['href']
                
                # Skip useless links
                if any(skip in href.lower() for skip in ['datenschutz', 'privacy', 'cookie', 'impressum', 'mailto:', 'tel:']):
                    continue
                if any(skip in text.lower() for skip in ['datenschutz', 'privacy', 'cookie', 'impressum']):
                    continue
                if len(text) < 3:  # Skip very short link texts
                    continue
                    
                links.append({
                    'text': text,
                    'href': href,
                    'context': str(link.parent)[:100] if link.parent else ''
                })
            
            logger.info(f"Found {len(links)} links on careers page:")
            with open("links.txt", "w", encoding="utf-8") as f:
                for link in links:
                    f.write(f"{link['text']} -> {link['href']}\n")
            
            # Create analysis prompt
            analysis_data = {
                'job_title': job_title,
                'page_preview': page_text[:500],
                'search_inputs': search_inputs,
                'links': links,
                'has_search': len(search_inputs) > 0
            }
            
            # Use heuristic analysis (replace with actual LLM call later)
            decision = await self._analyze_careers_page_heuristic(analysis_data)
            
            return decision
            
        except Exception as e:
            logger.error(f"Careers page analysis failed: {str(e)}")
            return {
            "success": False,
                "action": "search_links",
                "reasoning": "Analysis failed, defaulting to link search"
            }
        
    async def find_all_job_matches(self, job_links: List[Dict], job_params: Dict[str, Any]) -> Dict[str, Any]:
        """Find ALL job matches above threshold - calls JobMatchingTool"""
        return await self.job_matching_tool.find_all_job_matches(job_links, job_params)
    
    async def extract_enhanced_job_data(self, html_content: str, job_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract enhanced job data - calls JobMatchingTool"""
        return await self.job_matching_tool.extract_enhanced_job_data(html_content, job_params)


    async def _analyze_careers_page_heuristic(self, data):
        """Use GPT to analyze careers page and decide action"""
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI()
        
        job_title = data['job_title']
        page_preview = data['page_preview']
        links = data['links']
        search_inputs = data['search_inputs']
        
        links_text = "\n".join([f"- '{link['text']}' -> {link['href']}" for link in links[:20]])
        search_text = "\n".join([f"- {inp.get('placeholder', inp.get('name', 'search input'))}" for inp in search_inputs]) if search_inputs else "No search inputs"
        logger.info(f"\n{search_text}\n")
        prompt = f"""Analyze this careers page and determine the best action to find job listings for: "{job_title}"

        Page content preview: {page_preview[:3000]}

        Available links on page:
        {links_text}

        Available search inputs:
        {search_text}

        Choose the BEST action:
        1. "navigate_to_link" - if you see a link to view all jobs/positions
        2. "use_search" - if there's search functionality 
        3. "extract_jobs_current_page" - if this page shows job listings
        4. "search_links" - fallback option

        Return JSON only:
        {{"action": "action_name", "target_url": "url_if_navigate", "search_selector": "selector_if_search", "reasoning": "explanation"}}"""
        
        try:
            response = await client.chat.completions.create(
                model="gpt-5-nano",
                messages=[{"role": "user", "content": prompt}],
                temperature=1
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            logger.error(f"GPT analysis failed: {str(e)}")
            return {"action": "search_links", "reasoning": "GPT analysis failed"}
            
    async def find_best_job_match(self, job_links: List[Dict], job_params: Dict[str, Any]) -> Dict[str, Any]:
        """Find best job match using fuzzy matching"""
        logger.info(f"Analyzer Agent finding best match from {len(job_links)} job links")
        
        try:
            job_title = job_params["job_title"]
            location = job_params.get("location")
            
            # Use job matching tool for fuzzy matching
            match_result = await self.job_matching_tool.find_best_match(
                job_links, 
                job_title, 
                location
            )
            
            if match_result.get("success"):
                best_match = match_result["best_match"]
                logger.info(f"Best match: '{best_match['title']}' (score: {best_match['match_score']})")
                return best_match
            else:
                raise Exception("No suitable job matches found")
                
        except Exception as e:
            logger.error(f"Job matching failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def extract_job_data(self, html_content: str, job_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured job data from job posting HTML"""
        logger.info("Analyzer Agent extracting structured job data")
        
        try:
            # Use job matching tool to extract structured data
            extraction_result = await self.job_matching_tool.extract_job_data(
                html_content, 
                job_params
            )
            
            if extraction_result.get("success"):
                logger.info("Job data extracted successfully")
                return extraction_result
            else:
                return {
                    "success": False,
                    "error": "Failed to extract job data",
                    "job_data": {}
                }
                
        except Exception as e:
            logger.error(f"Job data extraction failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def analyze_page_structure(self, html_content: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze page structure and determine next action"""
        logger.info("Analyzer Agent analyzing page structure")
        
        try:
            goal = context.get("goal", "unknown")
            job_params = context.get("job_params", {})
            
            # Analyze page using scraping tool
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Check for various page elements
            has_search_forms = bool(soup.find('form')) and bool(soup.find('input', {'type': ['search', 'text']}))
            has_job_links = len(await self._find_job_related_links(soup)) > 0
            has_iframes = bool(soup.find('iframe'))
            
            # Determine next action based on analysis
            if goal == "find_job_listings":
                if has_job_links:
                    next_action = "extract_job_links"
                    confidence = "high"
                    reasoning = f"Found job-related links on the page"
                elif has_search_forms:
                    next_action = "use_search"
                    confidence = "medium"
                    reasoning = "Page has search functionality, try searching for jobs"
                elif has_iframes:
                    next_action = "check_iframes"
                    confidence = "medium"
                    reasoning = "Page contains iframes that may have job listings"
                else:
                    next_action = "navigate_to_listings"
                    confidence = "low"
                    reasoning = "No clear job listings found, may need to navigate elsewhere"
            else:
                next_action = "analyze"
                confidence = "medium"
                reasoning = "General page analysis needed"
                
            return {
                "success": True,
                "next_action": next_action,
                "confidence": confidence,
                "reasoning": reasoning,
                "page_analysis": {
                    "has_search_forms": has_search_forms,
                    "has_job_links": has_job_links,
                    "has_iframes": has_iframes
                }
            }
            
        except Exception as e:
            logger.error(f"Page structure analysis failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def _find_job_related_links(self, soup) -> List[Dict]:
        """Helper method to find job-related links"""
        job_keywords = ['job', 'career', 'position', 'role', 'opening', 'vacancy', 'apply']
        job_links = []
        
        for link in soup.find_all('a', href=True):
            text = link.get_text(strip=True).lower()
            href = link['href'].lower()
            
            if any(keyword in text or keyword in href for keyword in job_keywords):
                job_links.append({
                    'url': link['href'],
                    'title': link.get_text(strip=True)
                })
                
        return job_links
    async def extract_job_links_universal(self, html_content: str, job_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Universal job link extraction that works on ANY website
        Replace your existing extract_job_links method
        """
        logger.info("🌐 Using Universal Extraction Mode")
        
        try:
            # Import universal scraper
            from tools.universal_scraper import UniversalJobScraper
            
            # Initialize universal scraper
            universal_scraper = UniversalJobScraper(
                self.scraping_tool.web_navigator,
                self.scraping_tool
            )
            
            # Let it handle everything
            result = await universal_scraper.scrape_any_careers_page(job_params)
            
            if result.get("success") and result.get("job_listings"):
                return {
                    "success": True,
                    "job_links": result["job_listings"],
                    "total_found": len(result["job_listings"]),
                    "extraction_method": "universal_llm",
                    "strategy_used": result.get("strategy_used")
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "No jobs found"),
                    "job_links": []
                }
                
        except Exception as e:
            logger.error(f"Universal extraction failed: {str(e)}")
            return {"success": False, "error": str(e)}
    async def is_job_listings_page(self, html_content: str) -> Dict[str, Any]:
        """Let LLM determine if current page actually contains job listings"""
        logger.info("LLM validating if page contains job listings")
        
        try:
            # Clean HTML and extract meaningful text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script, style, nav, footer
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()
                
            # Get text content (limit to avoid token limits)
            page_text = soup.get_text()[:5000]  # First 5000 chars
            
            # Also get some HTML structure info
            job_indicators = {
                "apply_buttons": len(soup.find_all(text=re.compile(r'apply|application', re.I))),
                "job_titles_count": len(soup.find_all(['h1', 'h2', 'h3', 'h4'])),
                "form_count": len(soup.find_all('form')),
                "link_count": len(soup.find_all('a'))
            }
            
            # Use job matching tool to analyze with LLM-like logic
            # For now, use heuristics until we have proper LLM integration
            
            # Strong indicators of job listings page
            strong_indicators = [
                'apply now', 'view job', 'job opening', 'position available',
                'requirements:', 'responsibilities:', 'qualifications:',
                'salary:', 'location:', 'posted:', 'deadline:'
            ]
            
            weak_indicators = [
                'career', 'job', 'work', 'opportunity', 'hiring',
                'benefits', 'culture', 'why join', 'about us'
            ]
            
            strong_count = sum(1 for indicator in strong_indicators if indicator in page_text.lower())
            weak_count = sum(1 for indicator in weak_indicators if indicator in page_text.lower())
            
            # Decision logic
            if strong_count >= 3:
                contains_listings = True
                confidence = "high"
                reasoning = f"Found {strong_count} strong job listing indicators"
            elif strong_count >= 1 and job_indicators["apply_buttons"] > 0:
                contains_listings = True
                confidence = "medium" 
                reasoning = f"Found {strong_count} strong indicators and {job_indicators['apply_buttons']} apply buttons"
            elif weak_count > 5 and strong_count == 0:
                contains_listings = False
                confidence = "medium"
                reasoning = f"Only weak indicators ({weak_count}), no strong job listing signals"
            else:
                contains_listings = weak_count > 2
                confidence = "low"
                reasoning = f"Unclear - {strong_count} strong, {weak_count} weak indicators"
                
            return {
                "success": True,
                "contains_job_listings": contains_listings,
                "confidence": confidence,
                "reasoning": reasoning,
                "indicators": job_indicators,
                "strong_signals": strong_count,
                "weak_signals": weak_count
            }
            
        except Exception as e:
            logger.error(f"Job listings validation failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "contains_job_listings": False,
                "reasoning": "Validation failed, assuming no listings"
            }
        
    async def cleanup(self):
        """Cleanup Analyzer Agent resources"""
        logger.info("Cleaning up Analyzer Agent resources")
        # Cleanup handled by tools
    