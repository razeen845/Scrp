"""
Job Matching Tool - Fuzzy matching and data extraction for OpenAI Agents SDK
"""

import asyncio
from typing import Dict, Any, List
from fuzzywuzzy import fuzz
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
from utils.logger import setup_logger
import json

logger = setup_logger(__name__)

class JobMatchingTool:
    def __init__(self):
        pass
        
    async def initialize(self):
        """Initialize Job Matching Tool for OpenAI Agents SDK"""
        logger.info("Initializing Job Matching Tool for OpenAI Agents SDK")
        logger.info("Job Matching Tool initialized")
        
    async def find_careers_link(self, html_content: str, base_url: str) -> Dict[str, Any]:
        """Find careers page link from HTML - OpenAI Agents SDK compatible"""
        logger.info("Finding careers page link")
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            links = []
            
            # Extract all links
            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.get_text(strip=True).lower()
                
                # Convert relative URLs to absolute
                if href.startswith('/') or not href.startswith(('http://', 'https://')):
                    href = urljoin(base_url, href)
                    
                links.append({
                    'url': href,
                    'text': text,
                    'href_original': link['href']
                })
            
            # Write all links to links.json file
            try:
                links_data = {
                    "base_url": base_url,
                    "total_links": len(links),
                    "timestamp": asyncio.get_event_loop().time(),
                    "links": links
                }
                
                with open("links.json", "w", encoding="utf-8") as f:
                    json.dump(links_data, f, indent=2, ensure_ascii=False)
                    
                logger.info(f"Wrote {len(links)} links to links.json")
                
            except Exception as file_error:
                logger.error(f"Failed to write links to file: {str(file_error)}")
            
            # Find best careers link using fuzzy matching
            careers_keywords = ['career', 'job', 'hiring', 'opportunity', 'employment', 'join', 'work', 'talent', 'careers', 'karriere']
            
            best_match = None
            best_score = 0
            
            for link in links:
                text = link['text']
                url = link['url'].lower()
                
                score = 0
                
                # Direct keyword matching
                for keyword in careers_keywords:
                    if keyword in text:
                        score += 30
                    if keyword in url:
                        score += 25
                        
                # Fuzzy matching for variations
                for keyword in careers_keywords:
                    text_similarity = fuzz.partial_ratio(keyword, text)
                    url_similarity = fuzz.partial_ratio(keyword, url)
                    
                    if text_similarity > 80:
                        score += 20
                    if url_similarity > 80:
                        score += 15
                
                # Bonus for official indicators
                official_words = ['official', 'corporate', 'company']
                if any(word in text or word in url for word in official_words):
                    score += 10
                    
                # Penalty for non-careers content
                penalty_words = ['news', 'blog', 'contact', 'about', 'investor']
                if any(word in text or word in url for word in penalty_words):
                    score -= 15
                
                # Add score to link for debugging
                link['score'] = score
                
                if score > best_score:
                    best_score = score
                    best_match = link
                    
            if best_match and best_score > 20:
                confidence = "high" if best_score > 60 else "medium" if best_score > 35 else "low"
                
                return {
                    "success": True,
                    "careers_url": best_match['url'],
                    "confidence": confidence,
                    "score": best_score,
                    "reasoning": f"Best match found with score {best_score}",
                    "status": "careers_link_found"
                }
            else:
                # Fallback to common careers path
                fallback_url = urljoin(base_url, "/careers")
                return {
                    "success": True,
                    "careers_url": fallback_url,
                    "confidence": "low",
                    "score": 0,
                    "reasoning": "No clear careers link found, using fallback /careers",
                    "status": "fallback_careers_url"
                }
                
        except Exception as e:
            logger.error(f"Careers link finding failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "status": "careers_link_failed"
            }
            
    async def find_best_match(self, job_links: List[Dict], job_title: str, location: str = None) -> Dict[str, Any]:
        """Find best job match using fuzzy matching - OpenAI Agents SDK compatible"""
        logger.info(f"Finding best job match for '{job_title}' from {len(job_links)} links")
        
        try:
            if not job_links:
                return {
                    "success": False,
                    "error": "No job links provided for matching",
                    "status": "no_links_provided"
                }
                
            matches = []
            job_title_lower = job_title.lower()
            location_lower = location.lower() if location else ""
            
            for link in job_links:
                title = link.get('title', '').lower()
                url = link.get('url', '').lower()
                
                # Calculate similarity scores
                title_similarity = fuzz.token_sort_ratio(job_title_lower, title)
                partial_similarity = fuzz.partial_ratio(job_title_lower, title)
                url_similarity = fuzz.partial_ratio(job_title_lower, url)
                
                # Base score from title matching
                base_score = max(title_similarity, partial_similarity * 0.8)
                
                # URL bonus
                url_bonus = url_similarity * 0.3
                
                # Location bonus
                location_bonus = 0
                if location_lower and location_lower in title:
                    location_bonus = 20
                elif location_lower and location_lower in url:
                    location_bonus = 10
                    
                # Keyword matching bonus
                job_keywords = job_title_lower.split()
                keyword_bonus = 0
                for keyword in job_keywords:
                    if len(keyword) > 2:  # Skip short words
                        if keyword in title:
                            keyword_bonus += 15
                        elif fuzz.partial_ratio(keyword, title) > 85:
                            keyword_bonus += 10
                            
                # Calculate total score
                total_score = base_score + url_bonus + location_bonus + keyword_bonus
                
                matches.append({
                    **link,
                    'match_score': total_score,
                    'title_similarity': title_similarity,
                    'partial_similarity': partial_similarity,
                    'url_similarity': url_similarity,
                    'location_bonus': location_bonus,
                    'keyword_bonus': keyword_bonus
                })
                
            # Sort by match score
            matches.sort(key=lambda x: x['match_score'], reverse=True)
            
            if matches:
                best_match = matches[0]
                confidence = self._get_match_confidence(best_match['match_score'])
                
                return {
                    "success": True,
                    "best_match": best_match,
                    "all_matches": matches[:10],  # Top 10 matches
                    "match_confidence": confidence,
                    "status": "best_match_found"
                }
            else:
                return {
                    "success": False,
                    "error": "No job matches found",
                    "status": "no_matches_found"
                }
                
        except Exception as e:
            logger.error(f"Job matching failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "status": "job_matching_failed"
            }
            
    def _get_match_confidence(self, score: float) -> str:
        """Convert match score to confidence level"""
        if score >= 80:
            return "high"
        elif score >= 60:
            return "medium"
        elif score >= 40:
            return "low"
        else:
            return "very_low"
            
    async def extract_job_data(self, html_content: str, job_params: Dict[str, Any]) -> Dict[str, Any]:
        """Use GPT to extract job data from posting"""
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
            
        text_content = soup.get_text()[:10000]  # Limit tokens
        
        prompt = f"""Extract job information from this job posting:

    Job posting content:
    {text_content}

    Extract and return JSON:
    {{"title": "job title", "company": "company name", "location": "location", "employment_type": "full-time/part-time/etc", "salary_range": "salary if mentioned", "requirements": ["list of requirements"], "responsibilities": ["list of responsibilities"], "description": "job summary", "benefits": ["benefits listed"], "experience_level": "entry/mid/senior", "remote_option": "remote/hybrid/onsite", "department": "department/team"}}

    Be thorough and accurate. Set fields to null if not found."""
        
        try:
            response = await client.chat.completions.create(
                model="gpt-5-nano",
                messages=[{"role": "user", "content": prompt}],
                temperature=1
            )
            
            import json
            job_data = json.loads(response.choices[0].message.content)
            
            return {
                "success": True,
                "job_data": job_data,
                "extraction_method": "gpt_powered"
            }
            
        except Exception as e:
            logger.error(f"GPT job data extraction failed: {str(e)}")
            return {"success": False, "error": str(e)}
            
    async def _extract_job_title(self, soup, expected_title: str) -> str:
        """Extract job title from soup"""
        # Try common title selectors
        title_selectors = ['h1', '.job-title', '.position-title', '[class*="title"]', 'title']
        
        for selector in title_selectors:
            elements = soup.select(selector)
            for element in elements:
                title_text = element.get_text(strip=True)
                if title_text and len(title_text) > 5:
                    # Check if it's similar to expected title
                    if expected_title and fuzz.partial_ratio(expected_title.lower(), title_text.lower()) > 60:
                        return title_text
                    # Or if it contains job-related keywords
                    if any(word in title_text.lower() for word in ['engineer', 'developer', 'manager', 'analyst', 'consultant', 'specialist']):
                        return title_text
                        
        return expected_title  # Fallback to expected title
        
    async def _extract_location(self, text: str) -> str:
        """Extract location from text using patterns"""
        location_patterns = [
            r'Location:?\s*([^,\n]+(?:,\s*[^,\n]+)*)',
            r'Based in:?\s*([^,\n]+)',
            r'Office:?\s*([^,\n]+)',
            r'City:?\s*([^,\n]+)',
            r'\b([A-Z][a-z]+,\s*[A-Z]{2})\b',  # City, State format
            r'\b([A-Z][a-z]+\s+[A-Z][a-z]+,\s*[A-Z]{2})\b'  # City Name, State
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                if len(location) > 2 and len(location) < 50:
                    return location
                    
        return None
        
    async def _extract_employment_type(self, text: str) -> str:
        """Extract employment type from text"""
        employment_types = {
            'full-time': ['full-time', 'full time', 'fulltime', 'permanent'],
            'part-time': ['part-time', 'part time', 'parttime'],
            'contract': ['contract', 'contractor', 'freelance', 'temporary'],
            'internship': ['intern', 'internship', 'trainee'],
            'temporary': ['temp', 'temporary', 'seasonal']
        }
        
        text_lower = text.lower()
        
        for emp_type, keywords in employment_types.items():
            if any(keyword in text_lower for keyword in keywords):
                return emp_type.title()
                
        return None
        
    async def _extract_salary(self, text: str) -> str:
        """Extract salary information from text"""
        salary_patterns = [
            r'\$[\d,]+-\$?[\d,]+',
            r'£[\d,]+-£?[\d,]+',
            r'€[\d,]+-€?[\d,]+',
            r'\$[\d,]+(?:\.\d{2})?\s*-\s*\$?[\d,]+(?:\.\d{2})?',
            r'Salary:?\s*([^\n]+)',
            r'Pay:?\s*([^\n]+)',
            r'Compensation:?\s*([^\n]+)'
        ]
        
        for pattern in salary_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                salary = match.group().strip()
                if '$' in salary or '£' in salary or '€' in salary or any(word in salary.lower() for word in ['salary', 'pay', 'compensation']):
                    return salary
                    
        return None
        
    async def _extract_remote_option(self, text: str) -> str:
        """Extract remote work option from text"""
        remote_indicators = {
            'remote': ['remote', 'work from home', 'wfh', 'telecommute'],
            'hybrid': ['hybrid', 'flexible', 'mixed'],
            'onsite': ['on-site', 'onsite', 'office-based', 'in-office']
        }
        
        text_lower = text.lower()
        
        for option, keywords in remote_indicators.items():
            if any(keyword in text_lower for keyword in keywords):
                return option.title()
                
        return None
        
    async def _extract_experience_level(self, text: str) -> str:
        """Extract experience level from text"""
        experience_levels = {
            'entry': ['entry', 'junior', 'graduate', 'trainee', '0-2 years'],
            'mid': ['mid', 'intermediate', '2-5 years', '3-7 years'],
            'senior': ['senior', 'lead', 'principal', '5+ years', '7+ years'],
            'executive': ['director', 'vp', 'executive', 'head of', 'chief']
        }
        
        text_lower = text.lower()
        
        for level, keywords in experience_levels.items():
            if any(keyword in text_lower for keyword in keywords):
                return level.title()
                
        return None
        
    async def _extract_requirements(self, text: str) -> List[str]:
        """Extract requirements from text"""
        requirements = []
        
        # Look for requirements sections
        req_patterns = [
            r'Requirements?:?\s*([^:]+(?:\n[^:]+)*)',
            r'Qualifications?:?\s*([^:]+(?:\n[^:]+)*)',
            r'Skills?:?\s*([^:]+(?:\n[^:]+)*)'
        ]
        
        for pattern in req_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                req_text = match.group(1)
                # Split by bullet points or new lines
                req_items = re.split(r'[•\*\-\n]', req_text)
                for item in req_items:
                    item = item.strip()
                    if len(item) > 10 and len(item) < 200:
                        requirements.append(item)
                break
                
        return requirements[:10]  # Limit to 10 requirements
        
    async def _extract_responsibilities(self, text: str) -> List[str]:
        """Extract responsibilities from text"""
        responsibilities = []
        
        # Look for responsibilities sections
        resp_patterns = [
            r'Responsibilities:?\s*([^:]+(?:\n[^:]+)*)',
            r'Duties:?\s*([^:]+(?:\n[^:]+)*)',
            r'You will:?\s*([^:]+(?:\n[^:]+)*)'
        ]
        
        for pattern in resp_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                resp_text = match.group(1)
                # Split by bullet points or new lines
                resp_items = re.split(r'[•\*\-\n]', resp_text)
                for item in resp_items:
                    item = item.strip()
                    if len(item) > 10 and len(item) < 200:
                        responsibilities.append(item)
                break
                
        return responsibilities[:10]  # Limit to 10 responsibilities
        
    async def _extract_benefits(self, text: str) -> List[str]:
        """Extract benefits from text"""
        benefits = []
        
        # Look for benefits sections
        benefit_patterns = [
            r'Benefits:?\s*([^:]+(?:\n[^:]+)*)',
            r'Perks:?\s*([^:]+(?:\n[^:]+)*)',
            r'We offer:?\s*([^:]+(?:\n[^:]+)*)'
        ]
        
        for pattern in benefit_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                benefit_text = match.group(1)
                # Split by bullet points or new lines
                benefit_items = re.split(r'[•\*\-\n]', benefit_text)
                for item in benefit_items:
                    item = item.strip()
                    if len(item) > 5 and len(item) < 100:
                        benefits.append(item)
                break
                
        return benefits[:10]  # Limit to 10 benefits
    
    async def find_all_job_matches(self, job_links: List[Dict], job_params: Dict[str, Any]) -> Dict[str, Any]:
        """Find ALL job matches above a threshold, not just the best one"""
        logger.info(f"Finding all job matches for '{job_params['job_title']}' from {len(job_links)} links")
        
        try:
            job_title = job_params.get("job_title", "") or ""
            location = job_params.get("location") or ""

            if not job_title:
                return {"success": False, "error": "No job title provided"}

            job_title = job_title.lower()
            location = location.lower()
            
            all_matches = []
            threshold_score = 80  # Minimum score to consider a match
            
            for link in job_links:
                title = link.get('title') 
                url = link.get('url', '')
                
                # Skip links with None or empty titles
                if not title:
                    continue
                
                title_lower = title.lower()  # Now safe to call .lower()
                url_lower = url.lower() if url else ''
                
                # Calculate similarity scores (same logic as before)
                title_similarity = fuzz.token_sort_ratio(job_title, title)
                partial_similarity = fuzz.partial_ratio(job_title, title)
                url_similarity = fuzz.partial_ratio(job_title, url)
                
                base_score = max(title_similarity, partial_similarity * 0.8)
                url_bonus = url_similarity * 0.3
                
                location_bonus = 0
                if location and location in title:
                    location_bonus = 20
                elif location and location in url:
                    location_bonus = 10
                    
                job_keywords = job_title.split()
                keyword_bonus = 0
                for keyword in job_keywords:
                    if len(keyword) > 2 and keyword in title:
                        keyword_bonus += 15
                        
                total_score = base_score + url_bonus + location_bonus + keyword_bonus
                
                # Only include if above threshold
                if total_score >= threshold_score:
                    all_matches.append({
                        **link,
                        'match_score': total_score,
                        'title_similarity': title_similarity,
                        'partial_similarity': partial_similarity
                    })
            
            # Sort by score
            all_matches.sort(key=lambda x: x['match_score'], reverse=True)
            
            logger.info(f"Found {len(all_matches)} job matches above threshold ({threshold_score})")
            
            return {
                "success": True,
                "matches": all_matches,
                "total_matches": len(all_matches),
                "threshold_used": threshold_score
            }
            
        except Exception as e:
            logger.error(f"Job matching failed: {str(e)}")
            return {"success": False, "error": str(e)}
    

    async def extract_enhanced_job_data(self, html_content: str, job_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and intelligently parse job data with LLM analysis"""
        logger.info("Extracting enhanced job data with LLM analysis")
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove noise
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
                
            text_content = soup.get_text()
            
            # Basic extraction (existing logic)
            basic_job_data = await self.extract_job_data(html_content, job_params)
            
            if not basic_job_data.get("success"):
                return basic_job_data
                
            job_data = basic_job_data["job_data"]
            
            # Enhanced location extraction
            enhanced_location = await self._extract_enhanced_location(text_content, job_data.get("location"))
            job_data["location_details"] = enhanced_location
            
            # LLM-powered description breakdown
            description_breakdown = await self._breakdown_job_description(text_content)
            job_data.update(description_breakdown)
            
            # Extract additional metadata
            metadata = await self._extract_job_metadata(text_content)
            job_data["metadata"] = metadata
            
            return {
                "success": True,
                "job_data": job_data,
                "extraction_type": "enhanced"
            }
            
        except Exception as e:
            logger.error(f"Enhanced job data extraction failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _extract_enhanced_location(self, text: str, basic_location: str) -> Dict[str, Any]:
        """Extract detailed location information"""
        location_patterns = {
            'full_address': r'(\d+[^,\n]*,\s*[^,\n]+,\s*[A-Z]{2}\s*\d{5})',
            'city_state': r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([A-Z]{2})\b',
            'country': r'\b(United States|USA|UK|United Kingdom|Germany|France|Canada|Australia)\b',
            'remote_hybrid': r'\b(remote|hybrid|work from home|telecommute|flexible)\b',
            'on_site': r'\b(on-?site|office|in-person)\b'
        }
        
        location_info = {"basic_location": basic_location}
        
        for key, pattern in location_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                location_info[key] = matches[0] if isinstance(matches[0], str) else matches[0][0]
        
        return location_info

    async def _breakdown_job_description(self, text: str) -> Dict[str, Any]:
        """Use LLM-like logic to break down job description into parts"""
        
        # Find section markers
        sections = {
            'summary': [],
            'key_responsibilities': [],
            'required_qualifications': [],
            'preferred_qualifications': [],
            'technical_skills': [],
            'soft_skills': [],
            'benefits_compensation': [],
            'company_culture': []
        }
        
        # Split text into sentences
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if len(s.strip()) > 10]
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            
            # Classify sentence based on content
            if any(word in sentence_lower for word in ['responsible for', 'will be', 'you will', 'duties include']):
                sections['key_responsibilities'].append(sentence)
            elif any(word in sentence_lower for word in ['required:', 'must have', 'minimum', 'essential']):
                sections['required_qualifications'].append(sentence)
            elif any(word in sentence_lower for word in ['preferred', 'nice to have', 'bonus', 'plus']):
                sections['preferred_qualifications'].append(sentence)
            elif any(word in sentence_lower for word in ['python', 'java', 'sql', 'aws', 'docker', 'kubernetes', 'react', 'node']):
                sections['technical_skills'].append(sentence)
            elif any(word in sentence_lower for word in ['communication', 'teamwork', 'leadership', 'problem solving']):
                sections['soft_skills'].append(sentence)
            elif any(word in sentence_lower for word in ['salary', 'benefits', 'health', 'vacation', 'pto', '401k']):
                sections['benefits_compensation'].append(sentence)
            elif any(word in sentence_lower for word in ['culture', 'mission', 'values', 'team environment']):
                sections['company_culture'].append(sentence)
            elif len(sections['summary']) < 3:  # First few sentences as summary
                sections['summary'].append(sentence)
        
        # Clean up sections
        for key in sections:
            sections[key] = sections[key][:5]  # Limit to 5 items per section
            
        return sections

    async def _extract_job_metadata(self, text: str) -> Dict[str, Any]:
        """Extract additional job metadata"""
        metadata = {}
        
        # Extract job ID/reference
        job_id_patterns = [
            r'Job ID:?\s*([A-Z0-9-]+)',
            r'Reference:?\s*([A-Z0-9-]+)',
            r'Req\.?\s*#?([A-Z0-9-]+)'
        ]
        
        for pattern in job_id_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata['job_id'] = match.group(1)
                break
        
        # Extract application deadline
        deadline_patterns = [
            r'Apply by:?\s*([A-Za-z]+ \d{1,2},? \d{4})',
            r'Deadline:?\s*([A-Za-z]+ \d{1,2},? \d{4})',
            r'Closes:?\s*([A-Za-z]+ \d{1,2},? \d{4})'
        ]
        
        for pattern in deadline_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata['application_deadline'] = match.group(1)
                break
        
        # Extract team/department info
        team_patterns = [
            r'Team:?\s*([^.\n]+)',
            r'Department:?\s*([^.\n]+)',
            r'Division:?\s*([^.\n]+)'
        ]
        
        for pattern in team_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata['team_department'] = match.group(1).strip()
                break
        
        return metadata

    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up Job Matching Tool resources")
        # No specific cleanup needed