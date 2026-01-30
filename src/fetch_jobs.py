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
    Fetch job postings from Jobindex. Tries multiple search endpoints and selectors to be robust
    against minor layout changes on Jobindex.

    Behavior:
    - If `search_term` is the default "IT drift", we will also search for
      "IT operations" and "systemadministrator" to broaden results.
    - Returns up to `limit` unique jobs.
    - On network/parsing errors or no results, logs a clear message and returns an empty list
      so the caller can fall back to sample jobs.

    Returns:
        List of job dictionaries with keys: job_title, company, location, short_description, url
    """

    # If default term, expand to the required search terms
    queries = [search_term]
    if search_term.strip().lower() == "it drift":
        queries = ["IT drift", "IT operations", "systemadministrator"]

    headers = {
        "User-Agent": "JobHunter/1.0 (+https://github.com)"
    }

    jobs: List[Dict] = []
    seen_urls = set()

    for q in queries:
        if len(jobs) >= limit:
            break

        # Try a couple of likely Jobindex search endpoints
        endpoints = [
            ("https://www.jobindex.dk/jobsoegning", {"q": q}),
            ("https://www.jobindex.dk/jobs", {"query": q}),
        ]

        queried = False
        for url, params in endpoints:
            try:
                resp = requests.get(url, params=params, timeout=10, headers=headers)
                resp.raise_for_status()
                queried = True

                soup = BeautifulSoup(resp.content, 'html.parser')

                # Try several selectors (these may change if Jobindex updates HTML)
                # Commented where each selector is used to extract elements.
                selectors = [
                    # Common article/listing patterns
                    'article.job-result',     # article elements with job-result
                    'article.job-item',       # article with job-item
                    'div.job-listing',        # div with job-listing
                    'li.job',                 # list items with job
                    'div.job',                # generic div.job
                ]

                job_elements = []
                for sel in selectors:
                    found = soup.select(sel)
                    if found:
                        job_elements = found
                        break

                # If still nothing, try to find anchors that look like job links and use their parents
                if not job_elements:
                    anchors = soup.select('a[href*="/job/"]')
                    job_elements = [a.parent for a in anchors if a and a.parent]

                for elem in job_elements:
                    if len(jobs) >= limit:
                        break
                    try:
                        # Title: prefer anchor with job link
                        a = elem.select_one('a[href*="/job/"]') or elem.find('a')
                        if not a:
                            continue
                        href = a.get('href', '').strip()
                        if not href:
                            continue
                        url_abs = href if href.startswith('http') else 'https://www.jobindex.dk' + href

                        if url_abs in seen_urls:
                            continue

                        title = a.get_text(strip=True)

                        # Company selector(s): .company, .job-company, span.company
                        company_elem = elem.select_one('.company, .job-company, span.company, .company-name')
                        company = company_elem.get_text(strip=True) if company_elem else ""

                        # Location selector(s): .location, .job-location, span.location
                        loc_elem = elem.select_one('.location, .job-location, span.location')
                        location = loc_elem.get_text(strip=True) if loc_elem else ""

                        # Short description: .job-summary, .description, .teaser
                        desc_elem = elem.select_one('.job-summary, .description, .teaser, .job__excerpt')
                        short_desc = desc_elem.get_text(strip=True)[:300] if desc_elem else ""

                        job = {
                            "job_title": title or "Unknown",
                            "company": company or "Unknown",
                            "location": location or "Unknown",
                            "short_description": short_desc,
                            "url": url_abs
                        }

                        jobs.append(job)
                        seen_urls.add(url_abs)

                    except Exception as e:
                        # Skip malformed entries but keep the scrape running
                        print(f"Warning: could not parse a job element: {e}", file=sys.stderr)
                        continue

                # If we found some results on this endpoint, no need to try the next endpoint for the same query
                if job_elements:
                    break

            except requests.exceptions.RequestException as e:
                # Network-level error for this endpoint, try next endpoint or next query
                print(f"Error fetching Jobindex for query '{q}' from '{url}': {e}", file=sys.stderr)
                continue
            except Exception as e:
                # Any other parsing error shouldn't crash the program
                print(f"Error parsing Jobindex results for query '{q}': {e}", file=sys.stderr)
                continue

        if not queried:
            print(f"Warning: No successful request performed for query '{q}'", file=sys.stderr)

    if not jobs:
        # Clear, human-friendly message and empty return so the caller will use sample jobs as fallback
        print("Could not fetch or parse Jobindex results; using sample jobs as fallback", file=sys.stderr)
        return []

    # Limit to the requested amount and return
    return jobs[:limit]


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
