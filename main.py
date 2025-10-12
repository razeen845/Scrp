#!/usr/bin/env python3
"""
Job Scraper Main Script - With Universal Scraper Support Fully Integrated
"""

import asyncio
import json
import sys
import io
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

from agents import Agent
from magents.lead_agent import LeadAgent
from utils.logger import setup_logger

# Load environment variables
load_dotenv()

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

logger = setup_logger(__name__)

class JobScraperSystem:
    def __init__(self):
        self.lead_agent = None
        self.output_file = "output.json"
        self.enable_universal_mode = True  # Set to True to use universal scraper
        
    async def initialize(self):
        """Initialize the lead agent using OpenAI Agents SDK"""
        logger.info("Initializing Job Scraper System with OpenAI Agents SDK")
        
        self.lead_agent = LeadAgent()
        await self.lead_agent.initialize()
        
        logger.info("Job Scraper System initialized successfully")
        
    def get_user_input(self):
        """Get required inputs from user"""
        print("\n" + "="*60)
        print("Job Scraper - Universal Mode")
        print("="*60)
        print("Please provide the following information:\n")
        
        # Get job title (mandatory)
        job_title = input("Job Title (mandatory): ").strip()
        while not job_title:
            print("❌ Job title is required!")
            job_title = input("Job Title (mandatory): ").strip()
            
        # Get company name or domain (at least one is mandatory)
        company_name = input("Company Name (optional if domain provided): ").strip()
        company_domain = input("Company Domain (optional if name provided): ").strip()
        
        while not company_name and not company_domain:
            print("❌ Either company name or company domain is required!")
            company_name = input("Company Name: ").strip()
            if not company_name:
                company_domain = input("Company Domain: ").strip()
                
        # Get location (optional)
        location = input("Location (optional): ").strip()
        
        job_params = {
            "job_title": job_title,
            "company_name": company_name if company_name else None,
            "company_domain": company_domain if company_domain else None,
            "location": location if location else None
        }
        
        # Display confirmation
        print("\n" + "-"*60)
        print("📋 Search Parameters:")
        print(f"  Job Title: {job_params['job_title']}")
        if job_params['company_name']:
            print(f"  Company: {job_params['company_name']}")
        if job_params['company_domain']:
            print(f"  Domain: {job_params['company_domain']}")
        if job_params['location']:
            print(f"  Location: {job_params['location']}")
        print("-"*60 + "\n")
        
        return job_params
        
    async def scrape_job(self, job_params):
        """Main scraping workflow using OpenAI Agents SDK"""
        logger.info(f"Starting job scrape for: {job_params}")
        
        print("🚀 Starting job scraping...")
        print("⏳ This may take 30-90 seconds depending on the website...\n")
        
        try:
            # Process job request using the lead agent
            result = await self.lead_agent.process_job_request(job_params)
            
            # Enhance result with metadata
            result["scrape_metadata"] = {
                "timestamp": datetime.now().isoformat(),
                "scraper_version": "universal_v1.0",
                "mode": "universal" if self.enable_universal_mode else "standard"
            }
            
            # Clean up the output (remove noise)
            result = self._clean_output(result)
            
            # Save result to JSON
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Job scraping completed. Results saved to {self.output_file}")
            
            # Print summary
            self._print_summary(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error during job scraping: {str(e)}")
            
            error_result = {
                "success": False,
                "error": str(e),
                "error_type": self._classify_error(str(e)),
                "job_params": job_params,
                "scrape_metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "scraper_version": "universal_v1.0",
                    "mode": "universal" if self.enable_universal_mode else "standard"
                }
            }
            
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(error_result, f, indent=2, ensure_ascii=False)
            
            self._print_error(error_result)
            
            raise
    
    def _clean_output(self, result: dict) -> dict:
        """Clean up output by removing noise and fixing issues"""
        
        if result.get("success") and result.get("all_job_data"):
            for job in result["all_job_data"]:
                # Fix null job_url issue
                if not job.get("job_url") and result.get("workflow_steps", {}).get("job_listings_url"):
                    job["job_url"] = result["workflow_steps"]["job_listings_url"]
                
                # Clean location details
                if job.get("location_details"):
                    location_details = job["location_details"]
                    # Remove cookie settings noise
                    if location_details.get("city_state") and "COOKIE" in str(location_details["city_state"]).upper():
                        location_details["city_state"] = None
                
                # Clean summary field (remove duplicates and noise)
                if job.get("summary") and isinstance(job["summary"], list):
                    job["summary"] = [s for s in job["summary"] if len(s) > 20 and "COOKIE" not in s.upper()]
                    # Remove excessive newlines
                    job["summary"] = [s.replace('\n\n\n', '\n').strip() for s in job["summary"]]
                
                # Remove empty arrays
                for key in ["key_responsibilities", "required_qualifications", 
                           "preferred_qualifications", "technical_skills", "soft_skills",
                           "benefits_compensation", "company_culture"]:
                    if key in job and not job[key]:
                        del job[key]
        
        return result
    
    def _classify_error(self, error_str: str) -> str:
        """Classify error type for better handling"""
        error_lower = error_str.lower()
        
        if "cloudflare" in error_lower:
            return "bot_protection"
        elif "timeout" in error_lower:
            return "timeout"
        elif "navigation" in error_lower:
            return "navigation_failed"
        elif "no job" in error_lower:
            return "no_jobs_found"
        else:
            return "unknown"
    
    def _print_summary(self, result: dict):
        """Print a nice summary of results"""
        print("\n" + "="*60)
        
        if result.get("success"):
            print("✅ SCRAPING SUCCESSFUL")
            print("="*60)
            
            jobs_found = result.get("jobs_found", 0)
            print(f"\n📊 Summary:")
            print(f"  • Total Jobs Found: {jobs_found}")
            
            if result.get("workflow_steps"):
                steps = result["workflow_steps"]
                print(f"\n🔗 URLs:")
                print(f"  • Company: {steps.get('company_url')}")
                print(f"  • Careers Page: {steps.get('careers_url')}")
                
                if steps.get("strategy_used"):
                    print(f"\n🎯 Strategy Used: {steps['strategy_used']}")
                if steps.get("ats_system"):
                    print(f"  • ATS System: {steps['ats_system']}")
            
            if jobs_found > 0:
                print(f"\n💼 Jobs Scraped:")
                for i, job in enumerate(result.get("all_job_data", []), 1):
                    print(f"\n  {i}. {job.get('title', 'Unknown')}")
                    print(f"     Location: {job.get('location', 'N/A')}")
                    print(f"     Match Score: {job.get('match_score', 0)}/100")
                    print(f"     URL: {job.get('job_url', 'N/A')}")
                    
                    if job.get('employment_type'):
                        print(f"     Type: {job['employment_type']}")
                    if job.get('remote_option'):
                        print(f"     Remote: {job['remote_option']}")
            
        else:
            print("❌ SCRAPING FAILED")
            print("="*60)
            print(f"\n⚠️  Error: {result.get('error', 'Unknown error')}")
            
            if result.get('error_type'):
                error_type = result['error_type']
                print(f"\n📋 Error Type: {error_type}")
                
                # Provide helpful suggestions
                if error_type == "bot_protection":
                    print("\n💡 Suggestion:")
                    print("   This website uses bot protection (Cloudflare).")
                    print("   Try applying directly on their website.")
                
                elif error_type == "timeout":
                    print("\n💡 Suggestion:")
                    print("   The website is slow to respond.")
                    print("   Try again later or check your internet connection.")
                
                elif error_type == "no_jobs_found":
                    print("\n💡 Suggestion:")
                    print("   - Try a more generic job title")
                    print("   - Check if the company has an active careers page")
                    print("   - Verify the company domain is correct")
        
        print("\n" + "="*60)
        print(f"📄 Full results saved to: {self.output_file}")
        print("="*60 + "\n")
    
    def _print_error(self, error_result: dict):
        """Print error in a user-friendly way"""
        self._print_summary(error_result)
            
    async def cleanup(self):
        """Cleanup resources"""
        if self.lead_agent:
            await self.lead_agent.cleanup()

async def main():
    """Main function"""
    scraper_system = JobScraperSystem()
    
    try:
        # Initialize the system
        await scraper_system.initialize()
        
        # Get user input
        job_params = scraper_system.get_user_input()
        
        # Perform scraping
        result = await scraper_system.scrape_job(job_params)
        
        # Exit with appropriate code
        sys.exit(0 if result.get("success") else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Scraping interrupted by user")
        logger.info("Scraping interrupted by user")
        sys.exit(130)
        
    except Exception as e:
        print(f"\n❌ Unexpected Error: {str(e)}")
        logger.error(f"Main execution error: {str(e)}")
        sys.exit(1)
        
    finally:
        await scraper_system.cleanup()

async def test_mode():
    """Test mode with predefined parameters"""
    scraper_system = JobScraperSystem()
    
    # Test cases
    test_cases = [
        {
            "job_title": "sap fi berater",
            "company_name": "standard kessel baumgarte",
            "company_domain": None,
            "location": None
        }
    ]
    
    try:
        await scraper_system.initialize()
        
        for i, test_params in enumerate(test_cases, 1):
            print(f"\n{'='*60}")
            print(f"TEST CASE {i}/{len(test_cases)}")
            print(f"{'='*60}\n")
            
            result = await scraper_system.scrape_job(test_params)
            
            # Save test results separately
            test_output = f"test_output_{i}.json"
            with open(test_output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            print(f"\nTest {i} results saved to: {test_output}")
            
            await asyncio.sleep(5)  # Rate limiting between tests
        
    finally:
        await scraper_system.cleanup()

if __name__ == "__main__":
    # Check if test mode is enabled
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        asyncio.run(test_mode())
    else:
        try:
            asyncio.run(main())
        except RuntimeError as e:
            # Ignore "Event loop is closed" noise on Windows shutdown
            if "Event loop is closed" not in str(e):
                raise