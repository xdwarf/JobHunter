"""
fetch_jobs.py

Simple web scraper for Jobindex IT drift job postings.
Returns a list of job dictionaries with title, company, location, short_description, and url.
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict


def fetch_jobindex_jobs(search_term: str = "IT drift", limit: int = 10) -> List[Dict]:
    """
    Fetch job postings from Jobindex for a given search term.
    
    Args:
        search_term: What to search for (default: "IT drift")
        limit: Maximum number of jobs to return (default: 10)
        
    Returns:
        List of job dictionaries with keys: job_title, company, location, short_description, url
    """
    
    # Build Jobindex search URL
    base_url = "https://www.jobindex.dk/jobs"
    params = {"query": search_term}
    
    jobs = []
    
    try:
        # Fetch the search results page
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find job listing containers
        # Jobindex typically uses job item elements - adjust selector as needed
        job_elements = soup.find_all('article', class_='job-item')
        
        if not job_elements:
            # Fallback: try alternative selector
            job_elements = soup.find_all('div', class_='job-posting')
        
        for job_elem in job_elements[:limit]:
            try:
                # Extract job details
                title_elem = job_elem.find('a', class_='job-headline')
                company_elem = job_elem.find('span', class_='company')
                location_elem = job_elem.find('span', class_='location')
                desc_elem = job_elem.find('div', class_='job-summary')
                
                # Create job dict if we have at least title and company
                if title_elem and company_elem:
                    job = {
                        "job_title": title_elem.get_text(strip=True) if title_elem else "Unknown",
                        "company": company_elem.get_text(strip=True) if company_elem else "Unknown",
                        "location": location_elem.get_text(strip=True) if location_elem else "Unknown",
                        "short_description": desc_elem.get_text(strip=True)[:200] if desc_elem else "",
                        "url": title_elem.get('href', '') if title_elem else ""
                    }
                    
                    # Make sure URL is absolute
                    if job["url"] and not job["url"].startswith("http"):
                        job["url"] = "https://www.jobindex.dk" + job["url"]
                    
                    jobs.append(job)
            except Exception as e:
                # Skip malformed job entries
                print(f"Warning: Could not parse job entry: {e}")
                continue
        
        return jobs
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Jobindex: {e}")
        return []


def get_sample_jobs() -> List[Dict]:
    """
    Fallback: return sample job data if scraping fails.
    This ensures the pipeline can run even if Jobindex is unreachable.
    """
    return [
        {
            "job_title": "IT Drift Specialist",
            "company": "Tech Company A",
            "location": "København",
            "short_description": "Vi søger en erfaren IT drift specialist til at varetage systems administration og overvågning af vores infrastruktur.",
            "url": "https://www.jobindex.dk/jobs/1"
        },
        {
            "job_title": "Systems Administrator",
            "company": "Enterprise Corp",
            "location": "Aarhus",
            "short_description": "Du vil få ansvar for daglig drift og vedligeholdelse af serverpark samt support til brugere.",
            "url": "https://www.jobindex.dk/jobs/2"
        },
        {
            "job_title": "Help Desk Support",
            "company": "Service Center",
            "location": "Odense",
            "short_description": "Vi har brug for supportmedarbejder til at håndtere bruger-henvendelser via telefon og mail.",
            "url": "https://www.jobindex.dk/jobs/3"
        },
        {
            "job_title": "Cloud Infrastructure Engineer",
            "company": "Digital Solutions",
            "location": "København",
            "short_description": "Søger erfaren engineer til setup og drift af AWS/Azure infrastructure samt CI/CD pipelines.",
            "url": "https://www.jobindex.dk/jobs/4"
        },
        {
            "job_title": "Junior Programmør",
            "company": "StartUp Inc",
            "location": "Frederiksberg",
            "short_description": "Vi søger junior udvikler til Python og JavaScript udvikling af vores webapplikation.",
            "url": "https://www.jobindex.dk/jobs/5"
        }
    ]


if __name__ == "__main__":
    # Test the scraper
    jobs = fetch_jobindex_jobs()
    if not jobs:
        print("Using sample jobs (scraping failed)")
        jobs = get_sample_jobs()
    
    print(f"Found {len(jobs)} jobs")
    for job in jobs:
        print(f"- {job['job_title']} @ {job['company']}")
