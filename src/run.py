"""
run.py

Main orchestrator for the JobHunter AI job agent.
Fetches jobs, evaluates them using MCP prompt, and outputs JSON results.
"""

import json
import os
import sys
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
        # Ensure API key is present in environment (fail fast)
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY not set in environment; set it via .env or environment variables")

        # Read the MCP prompt
        mcp_path = "/app/evaluate_job.mcp"
        if not os.path.exists(mcp_path):
            mcp_path = "evaluate_job.mcp"
        
        with open(mcp_path, 'r', encoding='utf-8') as f:
            mcp_system_prompt = f.read()
        
        # Initialize OpenAI client. The client will read the API key from
        # the OPENAI_API_KEY environment variable (no manual api_key setting).
        # Proxies parameter removed; rely on standard http(s)_proxy env vars if needed.
        client = OpenAI()
        
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
    
    # Evaluate each job
    for i, job in enumerate(jobs, 1):
        print(f"Evaluating job {i}/{len(jobs)}: {job.get('job_title', 'Unknown')}", file=sys.stderr)
        
        # Get evaluation from MCP
        evaluation = evaluate_job_with_mcp(job)
        
        # Create output object
        output = create_output_object(job, evaluation)
        
        # Print JSON result to stdout (one per line)
        print(json.dumps(output, ensure_ascii=False))
    
    print(f"\nProcessed {len(jobs)} jobs", file=sys.stderr)


if __name__ == "__main__":
    main()
