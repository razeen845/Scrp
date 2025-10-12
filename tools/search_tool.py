"""
Search Tool - DuckDuckGo integration for OpenAI Agents SDK
"""

import asyncio
from typing import Dict, Any, List
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urlencode, urlparse, parse_qs, unquote
import re
from fuzzywuzzy import fuzz
from utils.logger import setup_logger

logger = setup_logger(__name__)

class SearchTool:
    def __init__(self):
        self.base_url = "https://duckduckgo.com"
        self.session = None
        
    async def initialize(self):
        """Initialize Search Tool for OpenAI Agents SDK"""
        logger.info("Initializing Search Tool for OpenAI Agents SDK")
        logger.info("Search Tool initialized")
        
    async def _get_session(self):
        """Get aiohttp session with proper headers"""
        if not self.session:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            connector = aiohttp.TCPConnector(limit=10)
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                headers=headers, 
                connector=connector,
                timeout=timeout
            )
        return self.session
        
    async def search_company_website(self, company_name: str) -> Dict[str, Any]:
        """Search for company's official website"""
        logger.info(f"Searching for company website: {company_name}")
        
        try:
            search_queries = [
                # f"{company_name} official website",
                # f"{company_name} company homepage", 
                # f"{company_name} corporate site",
                f"{company_name}",
                company_name
            ]
            
            best_result = None
            best_confidence = 0
            
            for query in search_queries:
                results = await self._perform_search(query, max_results=5)
                
                if not results:
                    continue
                    
                for result in results:
                    confidence = self._calculate_company_confidence(result, company_name)
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_result = result
                        
                if best_confidence > 70:
                    break
                    
            if best_result and best_confidence > 25:
                confidence_level = self._confidence_level(best_confidence)
                
                logger.info(f"Found company website: {best_result['url']} (confidence: {confidence_level})")

                parsed_url = urlparse(best_result["url"])
                root_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                
                return {
                    "success": True,
                    "company_name": company_name,
                    "url": best_result["url"],
                    "title": best_result["title"],
                    "description": best_result["description"],
                    "confidence": confidence_level,
                    "confidence_score": best_confidence,
                    "status": "company_website_found"
                }
            else:
                return {
                    "success": False,
                    "error": f"No suitable website found for {company_name}",
                    "company_name": company_name,
                    "best_score": best_confidence,
                    "status": "company_website_not_found"
                }
                
        except Exception as e:
            logger.error(f"Company website search failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "company_name": company_name,
                "status": "search_failed"
            }
            
    async def search_general(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        """Perform general web search"""
        logger.info(f"Performing general search: {query}")
        
        try:
            results = await self._perform_search(query, max_results)
            
            return {
                "success": True,
                "query": query,
                "results": results,
                "total_results": len(results),
                "status": "search_completed"
            }
            
        except Exception as e:
            logger.error(f"General search failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "query": query,
                "status": "search_failed"
            }
            
    async def _perform_search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Perform DuckDuckGo search"""
        try:
            session = await self._get_session()
            
            search_url = f"{self.base_url}/html/"
            params = {
                'q': query,
                'kl': 'us-en',
                'safe': 'moderate',
                's': '0'
            }
            
            url = f"{search_url}?{urlencode(params)}"
            
            async with session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    results = self._parse_search_results(html, max_results)
                    quality_results = self._filter_quality_results(results)
                    
                    logger.info(f"Found {len(quality_results)} quality search results for: {query}")
                    return quality_results
                else:
                    logger.error(f"Search request failed with status: {response.status}")
                    return []
                    
        except asyncio.TimeoutError:
            logger.error(f"Search timeout for query: {query}")
            return []
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {str(e)}")
            return []
            
    def _parse_search_results(self, html: str, max_results: int) -> List[Dict[str, Any]]:
        """Parse DuckDuckGo search results"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            results = []
            
            result_containers = self._find_result_containers(soup)
                
            if not result_containers:
                logger.warning("No result containers found")
                return []
                
            for container in result_containers[:max_results*2]:
                try:
                    result = self._parse_single_result(container)
                    if result and self._is_valid_result(result):
                        results.append(result)
                        
                        if len(results) >= max_results:
                            break
                            
                except Exception as e:
                    logger.debug(f"Failed to parse individual result: {str(e)}")
                    continue
                    
            logger.info(f"Successfully parsed {len(results)} search results")
            return results
            
        except Exception as e:
            logger.error(f"Failed to parse search results: {str(e)}")
            return []
            
    def _find_result_containers(self, soup):
        """Find result containers using multiple strategies"""
        result_selectors = [
            'div.result',
            'div[class*="result"]',
            'article',
            '.result__body',
            '.web-result',
            'div[data-testid="result"]',
            '.result'
        ]
        
        result_containers = []
        for selector in result_selectors:
            containers = soup.select(selector)
            if containers and len(containers) > 2:
                result_containers = containers
                logger.debug(f"Found {len(containers)} containers with selector: {selector}")
                break
                
        return result_containers
        
    def _parse_single_result(self, container):
        """Parse a single search result container"""
        title_elem = self._find_title_element(container)
        if not title_elem:
            return None
            
        title = title_elem.get_text(strip=True)
        url = title_elem.get('href')
        
        if not title or not url:
            return None
            
        url = self._clean_redirect_url(url)
        
        if not url:
            return None
            
        description = self._extract_description(container)
        
        return {
            'title': title,
            'url': url,
            'description': description[:300] if description else ""
        }
        
    def _find_title_element(self, container):
        """Find title element using multiple strategies"""
        title_selectors = [
            'a[class*="result"]',
            'h3 a',
            'h2 a', 
            'a[href]',
            '.result__a',
            '[data-testid="result-title-a"]'
        ]
        
        for selector in title_selectors:
            elem = container.select_one(selector)
            if elem and elem.get('href'):
                return elem
                
        return None
        
    def _extract_description(self, container):
        """Extract description from result container"""
        desc_selectors = [
            '.result__snippet',
            '[class*="snippet"]',
            '.result-snippet',
            'span[class*="snippet"]',
            'div[class*="snippet"]',
            'p'
        ]
        
        for selector in desc_selectors:
            elem = container.select_one(selector)
            if elem:
                desc = elem.get_text(strip=True)
                if desc and len(desc) > 10:
                    return desc
                    
        return ""
        
    def _clean_redirect_url(self, url):
        """Clean DuckDuckGo redirect URLs"""
        if not url:
            return None
            
        if url.startswith('/l/?'):
            try:
                parsed = urlparse(url)
                query_params = parse_qs(parsed.query)
                if 'uddg' in query_params:
                    return unquote(query_params['uddg'][0])
            except Exception as e:
                logger.debug(f"Failed to clean redirect URL: {str(e)}")
                return None
                
        if url.startswith(('http://', 'https://')):
            return url
            
        return None
        
    def _is_valid_result(self, result):
        """Validate search result quality"""
        if not result or not result.get('url') or not result.get('title'):
            return False
            
        url = result['url']
        title = result['title']
        
        skip_domains = ['duckduckgo.com', 'google.com', 'bing.com', 'yahoo.com']
        if any(domain in url.lower() for domain in skip_domains):
            return False
            
        if len(title) < 5 or len(title) > 200:
            return False
            
        if not url.startswith(('http://', 'https://')):
            return False
            
        return True
        
    def _filter_quality_results(self, results):
        """Filter results for quality and relevance"""
        quality_results = []
        
        for result in results:
            if self._is_quality_result(result):
                quality_results.append(result)
                
        return quality_results
        
    def _is_quality_result(self, result):
        """Check if result meets quality standards"""
        url = result.get('url', '').lower()
        title = result.get('title', '').lower()
        description = result.get('description', '').lower()
        
        low_quality_indicators = [
            'blogspot', 'wordpress.com', 'tumblr', 'reddit.com/r/',
            'quora.com', 'answers.com', 'ask.com'
        ]
        
        for indicator in low_quality_indicators:
            if indicator in url:
                return False
                
        total_content = len(title + description)
        if total_content < 20:
            return False
            
        return True
        
    def _calculate_company_confidence(self, result: Dict[str, Any], company_name: str) -> float:
        """Calculate confidence score for company website match"""
        try:
            company_words = company_name.lower().replace(',', ' ').replace('.', ' ').split()
            company_words = [word for word in company_words if len(word) > 2]
            
            url = result['url'].lower()
            title = result['title'].lower()
            description = result['description'].lower()
            
            domain = urlparse(url).netloc.replace('www.', '')
            
            score = 0
            
            # Domain matching
            for word in company_words:
                if word in domain:
                    score += 35
                    
            # Perfect domain match bonus
            company_clean = ''.join(company_words)
            domain_clean = domain.replace('.com', '').replace('.org', '').replace('.net', '').replace('-', '').replace('_', '')
            
            if fuzz.ratio(company_clean, domain_clean) > 85:
                score += 40
            elif fuzz.ratio(company_clean, domain_clean) > 70:
                score += 25
                
            # Title matching
            title_score = 0
            for word in company_words:
                if word in title:
                    title_score += 20
                else:
                    best_word_match = max([fuzz.ratio(word, title_word) for title_word in title.split()] + [0])
                    if best_word_match > 80:
                        title_score += 15
                        
            score += min(title_score, 40)
                    
            # Description matching
            desc_score = 0
            for word in company_words:
                if word in description:
                    desc_score += 8
            score += min(desc_score, 20)
                    
            # Official indicators bonus
            official_indicators = ['official', 'corporate', 'company', 'homepage', 'home', 'main']
            for indicator in official_indicators:
                if indicator in title or indicator in description:
                    score += 15
                    break
                    
            # TLD bonus
            if any(tld in domain for tld in ['.com', '.org', '.net']):
                score += 10
                
            # Penalties for non-company sites
            penalty_sites = [
                'linkedin', 'facebook', 'twitter', 'instagram', 'youtube', 
                'wikipedia', 'crunchbase', 'glassdoor', 'indeed', 'bloomberg',
                'news', 'blog', 'forum'
            ]
            
            penalty_applied = False
            for penalty in penalty_sites:
                if penalty in url or penalty in title.lower():
                    score -= 30
                    penalty_applied = True
                    break
                    
            # Job sites penalty
            job_indicators = ['jobs', 'careers', 'hiring', 'employment']
            if not penalty_applied:
                for indicator in job_indicators:
                    if indicator in url and not domain.startswith(company_clean):
                        score -= 15
                        break
                
            return max(0, score)
            
        except Exception as e:
            logger.error(f"Error calculating confidence: {str(e)}")
            return 0
            
    def _confidence_level(self, score: float) -> str:
        """Convert numeric confidence to level"""
        if score >= 80:
            return "high"
        elif score >= 50:
            return "medium"
        elif score >= 25:
            return "low"
        else:
            return "very_low"
            
    async def cleanup(self):
        """Cleanup search tool resources"""
        logger.info("Cleaning up Search Tool resources")
        
        if self.session:
            await self.session.close()
            self.session = None
            
        logger.info("Search Tool cleanup completed")