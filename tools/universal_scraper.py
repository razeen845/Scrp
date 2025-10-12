"""
Universal Job Scraper - Works with ANY ATS system and website structure
Adaptive, self-learning approach using LLM intelligence
"""

import asyncio
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import re
from openai import AsyncOpenAI
from utils.logger import setup_logger

logger = setup_logger(__name__)

class UniversalJobScraper:
    """
    Universal scraper that adapts to ANY website structure
    Uses LLM to understand page structure instead of hardcoded selectors
    """
    
    def __init__(self, web_navigator, scraping_tool):
        self.web_navigator = web_navigator
        self.scraping_tool = scraping_tool
        self.client = AsyncOpenAI()
        self.learning_cache = {}  # Cache successful patterns
        
    async def scrape_any_careers_page(self, job_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Universal method that works on ANY careers page structure
        """
        logger.info("🌐 Starting Universal Scraping Mode")
        
        # Step 2: Analyze page structure with LLM
        page_analysis = await self._analyze_page_structure_llm(job_params)
        
        if not page_analysis["success"]:
            return page_analysis
        
        # Step 3: Execute LLM's recommended strategy
        extraction_result = await self._execute_extraction_strategy(
            page_analysis["strategy"],
            job_params
        )
        
        # Add strategy info to result
        if extraction_result.get("success"):
            extraction_result["strategy"] = page_analysis["strategy"]
        
        return extraction_result
    
    async def _analyze_page_structure_llm(self, job_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM to understand the page structure and decide extraction strategy
        This is the KEY to making it work everywhere
        """
        logger.info("🧠 Using LLM to analyze page structure")
        
        try:
            html_content = await self.web_navigator.get_page_html()
            current_url = self.web_navigator.current_url
            
            # Clean and prepare HTML for LLM
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove noise
            for tag in soup(['script', 'style', 'meta', 'link', 'noscript']):
                tag.decompose()
            
            # Get page structure
            page_structure = self._extract_page_structure(soup)
            
            # Create comprehensive analysis prompt
            prompt = f"""You are a web scraping expert analyzing a careers/jobs page.

TARGET: Find job listings for "{job_params['job_title']}" {f"in {job_params.get('location')}" if job_params.get('location') else ""}

CURRENT URL: {current_url}

PAGE STRUCTURE ANALYSIS:
- Total iframes: {page_structure['iframe_count']}
- Forms: {page_structure['form_count']}
- Total links: {page_structure['link_count']}
- Search inputs: {page_structure['search_input_count']}
- Dynamic indicators: {page_structure['dynamic_indicators']}

IFRAME DETAILS:
{json.dumps(page_structure['iframes'][:5], indent=2)}

FORMS DETAILS:
{json.dumps(page_structure['forms'][:3], indent=2)}

KEY LINKS (top 20):
{json.dumps(page_structure['key_links'][:20], indent=2)}

PAGE TEXT PREVIEW (first 1500 chars):
{page_structure['text_preview']}

VISIBLE HEADINGS:
{json.dumps(page_structure['headings'][:10], indent=2)}

---

ANALYZE THIS PAGE AND DETERMINE THE BEST STRATEGY TO EXTRACT JOB LISTINGS.

Consider:
1. Are there iframes? If yes, which one likely contains job listings?
2. Is there a search form? Should we use it?
3. Is there any button or link that likely leads to job listings?
4. Are job listings visible on this page already?
5. Do we need to navigate to another page first?
6. Is this an ATS system (Workday, Greenhouse, Lever, etc.)? Which one?
7. Does content load dynamically (need scrolling)?
8. **Pagination**: Are there pagination controls (Next, Page 2, 3, etc.)? If current page shows some jobs but has pagination, we may need to navigate to page 2 or click "Next"
9. **Hidden Jobs**: If you see pagination or "Load More" buttons, there are likely more jobs on other pages
10. If job listing is visible you should click on the job title linl of each relevant job to get the full job description.
PAGINATION PRIORITY:
- If you see job listings on current page BUT also see pagination (page 2, 3, next button, etc.), set needs_pagination=true
- If page says "Showing 1-10 of 50 jobs", there are more jobs on other pages
- Look for: "Next", "›", "Page 2", "Load More", numbered page links

Return JSON with this EXACT structure:
{{
  "strategy": "iframe_navigation" | "use_search_form" | "extract_current_page" | "navigate_to_link" | "scroll_and_extract",
  "ats_system": "workday" | "greenhouse" | "lever" | "icims" | "taleo" | "smartrecruiters" | "custom" | null,
  "confidence": 0-100,
  "reasoning": "detailed explanation of why you chose this strategy",
  "execution_plan": {{
    "iframe_index": 0 or null,
    "iframe_src": "url" or null,
    "search_input_selector": "css selector" or null,
    "target_link_url": "url" or null,
    "needs_scrolling": true/false,
    "scroll_amount": number or null
  }},
  "fallback_strategy": "what to try if primary fails"
}}

BE SPECIFIC. Provide actual CSS selectors and URLs."""

            # Call GPT-4 for intelligent analysis
            response = await self.client.chat.completions.create(
                model="gpt-5-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=1,
                response_format={"type": "json_object"}
            )
            
            analysis = json.loads(response.choices[0].message.content)
            
            logger.info(f"📊 LLM Strategy: {analysis['strategy']}")
            logger.info(f"🎯 Confidence: {analysis.get('confidence', 0)}%")
            logger.info(f"💭 Reasoning: {analysis.get('reasoning', 'N/A')}")
            
            # Cache successful patterns for this domain
            domain = urlparse(current_url).netloc
            self.learning_cache[domain] = {
                "strategy": analysis,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            return {
                "success": True,
                "strategy": analysis,
                "page_structure": page_structure
            }
            
        except Exception as e:
            logger.error(f"LLM analysis failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "strategy": {"strategy": "extract_current_page"}  # Fallback
            }
    
    def _extract_page_structure(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract comprehensive page structure for LLM analysis"""
        
        structure = {
            "iframe_count": 0,
            "iframes": [],
            "form_count": 0,
            "forms": [],
            "link_count": 0,
            "key_links": [],
            "search_input_count": 0,
            "dynamic_indicators": [],
            "text_preview": "",
            "headings": []
        }
        
        # Analyze iframes
        for iframe in soup.find_all('iframe'):
            structure["iframe_count"] += 1
            structure["iframes"].append({
                "src": iframe.get('src'),
                "id": iframe.get('id'),
                "name": iframe.get('name'),
                "title": iframe.get('title'),
                "class": iframe.get('class', [])
            })
        
        # Analyze forms
        for form in soup.find_all('form'):
            form_data = {
                "action": form.get('action'),
                "method": form.get('method'),
                "inputs": []
            }
            
            for input_elem in form.find_all('input'):
                input_type = input_elem.get('type', 'text')
                if input_type in ['text', 'search']:
                    structure["search_input_count"] += 1
                    form_data["inputs"].append({
                        "type": input_type,
                        "name": input_elem.get('name'),
                        "id": input_elem.get('id'),
                        "placeholder": input_elem.get('placeholder')
                    })
            
            if form_data["inputs"]:
                structure["forms"].append(form_data)
                structure["form_count"] += 1
        
        # Analyze links
        job_keywords = ['job', 'career', 'position', 'opening', 'vacancy', 'apply', 'opportunity']
        
        for link in soup.find_all('a', href=True):
            text = link.get_text(strip=True)
            href = link['href']
            
            if len(text) < 3 or len(text) > 200:
                continue
            
            structure["link_count"] += 1
            
            # Prioritize job-related links
            relevance = sum(1 for keyword in job_keywords if keyword in text.lower() or keyword in href.lower())
            
            if relevance > 0 or structure["link_count"] <= 50:
                structure["key_links"].append({
                    "text": text,
                    "href": href,
                    "relevance": relevance
                })
        
        # Sort links by relevance
        structure["key_links"].sort(key=lambda x: x["relevance"], reverse=True)
        
        # Check for dynamic loading indicators
        dynamic_classes = ['infinite-scroll', 'lazy-load', 'load-more', 'pagination']
        for class_name in dynamic_classes:
            if soup.find(class_=re.compile(class_name, re.I)):
                structure["dynamic_indicators"].append(class_name)
        
        # Get text preview
        structure["text_preview"] = soup.get_text()[:1500]
        
        # Get headings
        for heading in soup.find_all(['h1', 'h2', 'h3']):
            text = heading.get_text(strip=True)
            if text:
                structure["headings"].append({
                    "level": heading.name,
                    "text": text
                })
        
        return structure
    
    async def _execute_extraction_strategy(self, strategy: Dict[str, Any], job_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the LLM-recommended extraction strategy
        """
        logger.info(f"⚙️ Executing strategy: {strategy['strategy']}")
        
        strategy_type = strategy["strategy"]
        execution_plan = strategy.get("execution_plan", {})
        
        try:
            if strategy_type == "iframe_navigation":
                return await self._execute_iframe_strategy(execution_plan, job_params)
            
            elif strategy_type == "use_search_form":
                return await self._execute_search_strategy(execution_plan, job_params)
            
            elif strategy_type == "extract_current_page":
                return await self._execute_direct_extraction(execution_plan, job_params)
            
            elif strategy_type == "navigate_to_link":
                return await self._execute_navigation_strategy(execution_plan, job_params)
            
            elif strategy_type == "scroll_and_extract":
                return await self._execute_scroll_strategy(execution_plan, job_params)
            
            else:
                # Fallback to direct extraction
                return await self._execute_direct_extraction(execution_plan, job_params)
                
        except Exception as e:
            logger.error(f"Strategy execution failed: {str(e)}")
            
            # Try fallback strategy
            fallback = strategy.get("fallback_strategy")
            if fallback and fallback != strategy_type:
                logger.info(f"🔄 Trying fallback: {fallback}")
                return await self._execute_direct_extraction(execution_plan, job_params)
            
            return {"success": False, "error": str(e)}
    
    async def _execute_iframe_strategy(self, plan: Dict, job_params: Dict) -> Dict[str, Any]:
        """Execute iframe navigation strategy"""
        logger.info("🖼️ Executing iframe strategy")
        
        try:
            iframe_src = plan.get("iframe_src")
            iframe_index = plan.get("iframe_index", 0)
            
            if iframe_src:
                # Navigate to iframe URL
                if not iframe_src.startswith('http'):
                    iframe_src = urljoin(self.web_navigator.current_url, iframe_src)
                
                logger.info(f"Navigating to iframe: {iframe_src}")
                await self.web_navigator.navigate_to_url(iframe_src)
                await asyncio.sleep(3)
            else:
                # Access frame directly via Playwright
                page = self.web_navigator.page
                frames = page.frames
                
                if iframe_index < len(frames):
                    logger.info(f"Accessing frame {iframe_index} directly")
                    # Frame content will be scraped in next step
            
            # Now extract job listings from iframe content
            return await self._execute_direct_extraction(plan, job_params)
            
        except Exception as e:
            logger.error(f"Iframe strategy failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _execute_search_strategy(self, plan: Dict, job_params: Dict) -> Dict[str, Any]:
        """Execute search form strategy"""
        logger.info("🔍 Executing search strategy")
        
        try:
            search_selector = plan.get("search_input_selector")
            
            if not search_selector:
                return {"success": False, "error": "No search selector provided"}
            
            # Fill search input
            fill_result = await self.web_navigator.interact_with_element(
                "fill",
                search_selector,
                job_params["job_title"]
            )
            
            if not fill_result.get("success"):
                return fill_result
            
            # Submit form
            submit_selector = plan.get("submit_button_selector")
            if submit_selector:
                await self.web_navigator.interact_with_element("click", submit_selector)
            else:
                await self.web_navigator.interact_with_element("submit", search_selector)
            
            await asyncio.sleep(3)
            
            # Extract results
            return await self._execute_direct_extraction(plan, job_params)
            
        except Exception as e:
            logger.error(f"Search strategy failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _execute_direct_extraction(self, plan: Dict, job_params: Dict) -> Dict[str, Any]:
        """Extract job listings from current page using LLM"""
        logger.info("📄 Executing direct extraction")
        
        try:
            # Wait for dynamic content to load
            page = self.web_navigator.page
            
            # Wait a bit for JavaScript to execute
            await asyncio.sleep(3)
            
            # Try to detect and wait for job listings to appear
            logger.info("⏳ Waiting for job listings to load...")
            try:
                # Common selectors for job listings
                job_selectors = [
                    '[data-automation-id="jobTitle"]',  # Workday
                    'li[class*="job"]',
                    'div[class*="job"]',
                    'a[href*="/job/"]',
                    '[role="listitem"]',
                    'article',
                    '.job-card',
                    '.job-listing'
                ]
                
                # Try waiting for any of these selectors
                for selector in job_selectors:
                    try:
                        await page.wait_for_selector(selector, timeout=5000)
                        logger.info(f"✅ Found elements with selector: {selector}")
                        break
                    except:
                        continue
                
                # Additional wait after elements appear
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.warning(f"Could not detect job listings selector: {str(e)}")
            
            # Scroll to trigger lazy loading
            logger.info("📜 Scrolling to load more content...")
            try:
                for i in range(3):
                    await page.evaluate("window.scrollBy(0, 1000)")
                    await asyncio.sleep(1)
            except:
                pass
            
            html_content = await self.web_navigator.get_page_html()
            
            # Check if HTML has substantial content
            if len(html_content) < 1000:
                logger.warning(f"⚠️ Very little HTML content ({len(html_content)} chars)")
            
            # Use LLM to extract job listings intelligently
            job_listings = await self._llm_extract_jobs(html_content, job_params, plan)
            
            return {
                "success": True,
                "job_listings": job_listings,
                "total_found": len(job_listings)
            }
            
        except Exception as e:
            logger.error(f"Direct extraction failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _execute_navigation_strategy(self, plan: Dict, job_params: Dict) -> Dict[str, Any]:
        """Navigate to target link then extract"""
        logger.info("🔗 Executing navigation strategy")
        
        try:
            target_url = plan.get("target_link_url")
            
            if not target_url:
                return {"success": False, "error": "No target URL"}
            
            if not target_url.startswith('http'):
                target_url = urljoin(self.web_navigator.current_url, target_url)
            
            await self.web_navigator.navigate_to_url(target_url)
            await asyncio.sleep(3)
            
            return await self._execute_direct_extraction(plan, job_params)
            
        except Exception as e:
            logger.error(f"Navigation strategy failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _execute_scroll_strategy(self, plan: Dict, job_params: Dict) -> Dict[str, Any]:
        """Scroll to load content then extract"""
        logger.info("📜 Executing scroll strategy")
        
        try:
            page = self.web_navigator.page
            scroll_amount = plan.get("scroll_amount", 5)
            
            previous_height = await page.evaluate("document.body.scrollHeight")
            
            for i in range(scroll_amount):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
                
                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height == previous_height:
                    break
                previous_height = new_height
                
                logger.info(f"Scrolled {i+1}/{scroll_amount}")
            
            return await self._execute_direct_extraction(plan, job_params)
            
        except Exception as e:
            logger.error(f"Scroll strategy failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _llm_extract_jobs(self, html_content: str, job_params: Dict, plan: Dict) -> List[Dict]:
        """Use LLM to intelligently extract job listings"""
        logger.info("🤖 Using LLM to extract jobs")
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Log HTML size before cleaning
            logger.info(f"📏 Original HTML size: {len(html_content)} chars")
            
            # Remove noise
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()
            
            # Get text content with more context
            text_content = soup.get_text(separator='\n', strip=True)[:20000]  # Increased limit
            logger.info(f"📄 Text content size: {len(text_content)} chars")
            
            # Log a preview of what we're actually seeing
            logger.info(f"📝 Content preview:\n{text_content[:500]}\n...")
            
            # Get all links with more detail
            all_links = []
            for link in soup.find_all('a', href=True):
                text = link.get_text(strip=True)
                if text and len(text) > 2:
                    all_links.append({
                        "text": text,
                        "href": link['href']
                    })
            
            logger.info(f"🔗 Found {len(all_links)} total links")
            
            # If very few links, might be a loading issue
            if len(all_links) < 5:
                logger.warning("⚠️ Very few links found - page might not be fully loaded")
            
            links_json = json.dumps(all_links[:100], indent=2)  # Top 100 links
            
            prompt = f"""You are analyzing a job search results page for: "{job_params['job_title']}"

PAGE TEXT CONTENT (first 20,000 chars):
{text_content}

ALL CLICKABLE LINKS ({len(all_links)} total, showing first 100):
{links_json}

TASK: Extract ALL job listings that match or are related to "{job_params['job_title']}"

Look for:
- Job titles in the text
- Links that look like job postings
- Position names, role titles
- Any employment opportunities

Return a JSON object with a "jobs" key containing an array.
Each job MUST have both "title" and "url" fields.

{{
  "jobs": [
    {{
      "title": "exact job title as it appears",
      "url": "full URL or relative path to job posting (REQUIRED - use # if not found)",
      "location": "location if found, otherwise empty string",
      "description": "brief description if available, otherwise empty string",
      "relevance_score": 50
    }}
  ],
  "debug_info": "explain what you see on the page and why you found X jobs (or no jobs)"
}}

IMPORTANT: 
- ALWAYS include "title" and "url" for each job
- If this looks like a job search results page but jobs aren't visible, mention it in debug_info
- If you see loading indicators or "No results" messages, mention that in debug_info
- Be thorough - check all the links for job-related content
- If no jobs found, return {{"jobs": [], "debug_info": "explanation of what's on the page"}}"""

            response = await self.client.chat.completions.create(
                model="gpt-5-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=1,
                response_format={"type": "json_object"}
            )
            
            response_content = response.choices[0].message.content
            logger.info(f"📥 LLM Response preview: {response_content[:500]}")
            
            result = json.loads(response_content)
            logger.info(f"📊 Parsed result keys: {list(result.keys())}")
            
            # Log debug info from LLM
            if 'debug_info' in result:
                logger.info(f"🔍 LLM Debug Info: {result['debug_info']}")
            
            # Handle various response formats
            jobs = []
            if isinstance(result, list):
                jobs = result
                logger.info(f"Result is a list with {len(jobs)} items")
            elif isinstance(result, dict):
                # Try common key names
                for key in ['jobs', 'job_listings', 'listings', 'results', 'data']:
                    if key in result:
                        jobs = result[key]
                        logger.info(f"Found jobs under key '{key}': {len(jobs)} items")
                        break
                
                # If still empty, check if the dict itself is a job
                if not jobs and 'title' in result:
                    jobs = [result]
                    logger.info("Treating entire result as single job")
                elif not jobs:
                    logger.warning(f"Could not find jobs in result. Available keys: {list(result.keys())}")
            
            logger.info(f"🔍 Found {len(jobs)} potential jobs before validation")
            
            # Convert relative URLs to absolute and validate
            cleaned_jobs = []
            current_url = self.web_navigator.current_url
            
            for idx, job in enumerate(jobs):
                if not isinstance(job, dict):
                    logger.warning(f"Job {idx}: Skipping non-dict entry (type: {type(job)})")
                    continue
                
                # Log what we received
                logger.debug(f"Job {idx}: {job}")
                
                # More lenient validation - try to fix missing fields
                if 'title' not in job:
                    logger.warning(f"Job {idx}: Missing 'title' field. Keys: {list(job.keys())}")
                    # Try common variations
                    for key in ['job_title', 'position', 'role', 'name']:
                        if key in job:
                            job['title'] = job[key]
                            logger.info(f"Job {idx}: Used '{key}' as title")
                            break
                    else:
                        logger.warning(f"Job {idx}: Skipping - no title found")
                        continue
                
                if 'url' not in job:
                    logger.warning(f"Job {idx}: Missing 'url' field. Keys: {list(job.keys())}")
                    # Try common variations
                    for key in ['link', 'href', 'job_url', 'apply_url']:
                        if key in job:
                            job['url'] = job[key]
                            logger.info(f"Job {idx}: Used '{key}' as url")
                            break
                    else:
                        # Use current URL as fallback
                        job['url'] = current_url
                        logger.warning(f"Job {idx}: Using current URL as fallback")
                
                # Convert relative URLs to absolute
                url = job.get("url", "")
                if url and url != "#" and not url.startswith("http"):
                    job["url"] = urljoin(current_url, url)
                    logger.debug(f"Job {idx}: Converted relative URL to {job['url']}")
                
                # Ensure other fields exist with defaults
                job.setdefault('location', '')
                job.setdefault('description', '')
                job.setdefault('relevance_score', 50)
                
                cleaned_jobs.append(job)
                logger.info(f"Job {idx}: ✅ '{job['title']}'")
            
            logger.info(f"✅ Extracted {len(cleaned_jobs)} valid jobs")
            return cleaned_jobs
            
        except json.JSONDecodeError as e:
            logger.error(f"LLM returned invalid JSON: {str(e)}")
            if 'response' in locals():
                logger.error(f"Response content: {response.choices[0].message.content[:1000]}")
            return []
        except Exception as e:
            logger.error(f"LLM extraction failed: {str(e)}", exc_info=True)
            return []