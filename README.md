# JobHunter - AI Job Evaluation Agent

Proof-of-concept for an AI-powered job screening agent that evaluates IT operations job postings.

## Architecture

- **fetch_jobs.py**: Scrapes Jobindex for IT drift job postings
- **run.py**: Orchestrates the evaluation pipeline using OpenAI API with MCP system prompt
- **evaluate_job.mcp**: System prompt defining evaluation criteria
- **Docker**: Complete containerized setup

## Quick Start

### Prerequisites

- Docker & Docker Compose
- OpenAI API key

### Setup

1. **Set your OpenAI API key**:
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```

   Or create a `.env` file:
   ```bash
   cp .env.example .env
   # Edit .env and add your API key
   ```

2. **Build and run**:
   ```bash
   docker compose up --build
   ```

## Output Format

Each job evaluation is printed as JSON to stdout:

```json
{
  "job_title": "IT Drift Specialist",
  "company": "Tech Company A",
  "location": "København",
  "url": "https://...",
  "evaluation": {
    "relevant": true,
    "score": 0.82,
    "category": "IT-drift",
    "reason": "Ansvar for systemadministration og infrastrukturvedligeholdelse."
  }
}
```

## Evaluation Criteria

Jobs are evaluated based on the criteria in `evaluate_job.mcp`:

**Relevant for** (IT operations profile):
- System administration & infrastructure
- Technical responsibility
- IT-user coordination
- Operational reliability

**Rejected** (not relevant):
- First-line/helpdesk support
- Customer service
- Sales/presales
- Software development
- Junior/trainee roles

## Development

### Local Testing (without Docker)

```bash
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."
python src/run.py
```

### Troubleshooting

- **Jobs not fetching**: Uses sample data as fallback
- **API errors**: Check that `OPENAI_API_KEY` is set
- **Missing evaluate_job.mcp**: Ensure file exists in repo root

## Phase 1 Status

This is a proof-of-concept. Future enhancements could include:
- Database for job history
- Web UI for results
- Multiple job sources
- Advanced filtering
- Result persistence
