"""
run.py

Main orchestrator for the JobHunter AI job agent.
Fetches jobs, evaluates them using MCP prompt, and outputs JSON results.
"""

import json
import os
import sys
import hashlib
from typing import Dict, Any

from openai import OpenAI

# The OpenAI API key is expected via the OPENAI_API_KEY environment variable
# (for example from a .env file mounted by docker-compose)

# Import the job fetcher
from fetch_jobs import fetch_jobindex_jobs, get_sample_jobs


def evaluate_job_with_mcp(job: Dict[str, str]) -> Dict[str, Any]:
    """
    Evaluate a job using the evaluate_job.mcp prompt via OpenAI MCP.
    
    Args:
        job: Dictionary with job_title, company, location, and url
        
    Returns:
        Dictionary with evaluation results: relevant, score, category, reason
    """
    
    # Prepare the job description from the job data
    job_description = f"{job.get('short_description', '')}"
    
    # Create the prompt for MCP
    # Since we're using MCP client, we'll format a request
    prompt = f"""
Evaluate this job posting:

job_title: {job.get('job_title', '')}
company: {job.get('company', '')}
location: {job.get('location', '')}
job_description: {job_description}
"""
    
    try:
        # Call OpenAI API with the MCP system prompt
        # Read the MCP prompt
        mcp_path = "/app/evaluate_job.mcp"
        if not os.path.exists(mcp_path):
            mcp_path = "evaluate_job.mcp"
        
        with open(mcp_path, 'r', encoding='utf-8') as f:
            mcp_system_prompt = f.read()
        
        # Fetch OpenAI credentials from environment
        # Support for project-based API keys (sk-proj-...)
        api_key = os.getenv("OPENAI_API_KEY")
        project_id = os.getenv("OPENAI_PROJECT_ID")
        
        if not api_key or not project_id:
            raise RuntimeError("OPENAI_API_KEY or OPENAI_PROJECT_ID not set")
        
        # Initialize OpenAI client with project-based API key
        # The project parameter ensures API calls use the correct project context
        client = OpenAI(
            api_key=api_key,
            project=project_id
        )
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": mcp_system_prompt
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        # Parse the response
        response_text = response.choices[0].message.content.strip()
        
        # Try to extract JSON from the response
        try:
            # Find JSON in the response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                evaluation = json.loads(json_str)
            else:
                # Fallback: create minimal evaluation
                evaluation = {
                    "relevant": False,
                    "score": 0.0,
                    "category": "Other",
                    "reason": "Could not parse evaluation"
                }
        except json.JSONDecodeError:
            # Fallback: create minimal evaluation
            evaluation = {
                "relevant": False,
                "score": 0.0,
                "category": "Other",
                "reason": "Invalid JSON in response"
            }
        
        return evaluation
    
    except Exception as e:
        # 429 håndteres særskilt så vi logger en klar besked, returnerer en eksplicit "quota exceeded" evaluation
        # og fortsætter til næste job i køen uden at afslutte hele processen.
        err_str = str(e).lower()
        err_code = None
        # Nogle OpenAI-klientfejl eksponerer status/kode på forskellige attributter
        for attr in ("status", "status_code", "http_status", "code"):
            if hasattr(e, attr):
                try:
                    val = getattr(e, attr)
                    if isinstance(val, int) and val == 429:
                        err_code = 429
                        break
                    if isinstance(val, str) and val.isdigit() and int(val) == 429:
                        err_code = 429
                        break
                except Exception:
                    pass

        if "429" in err_str or "insufficient_quota" in err_str or err_code == 429:
            # Menneskelig venlig logbesked for quota-problemer
            print("OpenAI quota exceeded – check billing for project", file=sys.stderr)
            # Returnér klart signal i evaluation så downstream kan skelne denne fejl
            return {
                "relevant": False,
                "score": 0.0,
                "category": "Other",
                "reason": "OpenAI quota exceeded"
            }

        # Fallback: behold eksisterende generiske fejl-output for andre fejl
        print(f"Error evaluating job: {e}", file=sys.stderr)
        # Return neutral evaluation on error
        return {
            "relevant": False,
            "score": 0.0,
            "category": "Other",
            "reason": f"Evaluation error: {str(e)}"
        }


def create_output_object(job: Dict[str, str], evaluation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create the final output object combining job and evaluation data.
    
    Args:
        job: Job dictionary from fetch_jobs.py
        evaluation: Evaluation dictionary from MCP
        
    Returns:
        Combined output dictionary
    """
    return {
        "job_title": job.get("job_title", ""),
        "company": job.get("company", ""),
        "location": job.get("location", ""),
        "url": job.get("url", ""),
        "evaluation": evaluation
    }


def main():
    """
    Main entry point: fetch jobs, evaluate each one, output JSON.
    """
    print("JobHunter - AI Job Agent", file=sys.stderr)
    print("=" * 50, file=sys.stderr)
    
    # Fetch jobs
    print("Fetching jobs from Jobindex...", file=sys.stderr)
    jobs = fetch_jobindex_jobs(search_term="IT drift", limit=10)
    
    # Fallback to sample data if scraping fails
    if not jobs:
        print("Using sample job data", file=sys.stderr)
        jobs = get_sample_jobs()
    
    print(f"Found {len(jobs)} jobs", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    # Ensure data directory exists and load existing saved jobs
    data_dir = os.path.join(os.getcwd(), 'data')
    os.makedirs(data_dir, exist_ok=True)
    data_path = os.path.join(data_dir, 'jobs.json')

    existing_jobs = []
    existing_by_id = {}
    try:
        if os.path.exists(data_path):
            with open(data_path, 'r', encoding='utf-8') as f:
                existing_jobs = json.load(f) or []
                # Build lookup by id (if entries don't have id, compute it)
                for j in existing_jobs:
                    jid = j.get('id')
                    if not jid:
                        # compute stable id if missing
                        url = (j.get('url') or '').strip()
                        key = url if url else f"{j.get('job_title','')}|{j.get('company','')}|{j.get('location','')}"
                        jid = hashlib.sha256(key.encode('utf-8')).hexdigest()
                        j['id'] = jid
                    existing_by_id[jid] = j
    except Exception as e:
        print(f"Error loading existing jobs: {e}", file=sys.stderr)
        existing_jobs = []
        existing_by_id = {}

    # Evaluate each job; skip duplicates based on stable id (hash of URL or fallback)
    for i, job in enumerate(jobs, 1):
        print(f"Evaluating job {i}/{len(jobs)}: {job.get('job_title', 'Unknown')}", file=sys.stderr)

        # Generate stable ID (prefer URL, fallback to title|company|location)
        url = (job.get('url') or '').strip()
        id_key = url if url else f"{job.get('job_title','')}|{job.get('company','')}|{job.get('location','')}"
        job_id = hashlib.sha256(id_key.encode('utf-8')).hexdigest()

        if job_id in existing_by_id:
            print(f"Duplicate job skipped: {job.get('job_title','Unknown')} ({job.get('company','')})", file=sys.stderr)
            continue

        # New job — evaluate and save
        evaluation = evaluate_job_with_mcp(job)

        # Attach evaluation and id to saved job object
        saved_job = {
            "id": job_id,
            "job_title": job.get("job_title", ""),
            "company": job.get("company", ""),
            "location": job.get("location", ""),
            "url": job.get("url", ""),
            "short_description": job.get("short_description", ""),
            "evaluation": evaluation
        }

        existing_jobs.append(saved_job)
        existing_by_id[job_id] = saved_job
        print(f"New job saved: {saved_job['job_title']} @ {saved_job['company']}", file=sys.stderr)

        # Also print the JSON result for new job to stdout
        print(json.dumps(create_output_object(job, evaluation), ensure_ascii=False))

    # After processing all jobs, write updated jobs list back to disk
    try:
        with open(data_path, 'w', encoding='utf-8') as f:
            json.dump(existing_jobs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving jobs to {data_path}: {e}", file=sys.stderr)

    print(f"\nProcessed {len(jobs)} jobs", file=sys.stderr)
    
    print(f"\nProcessed {len(jobs)} jobs", file=sys.stderr)


if __name__ == "__main__":
    main()
