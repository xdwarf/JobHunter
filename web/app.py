from flask import Flask, render_template_string
import json
import os

app = Flask(__name__)

# Simple HTML template for job listing
TEMPLATE = """
<!doctype html>
<html lang="da">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>JobHunter - Jobs</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 40px; background:#f7f9fb; }
      .container { max-width: 900px; margin: 0 auto; }
      .job { background: #fff; border-radius: 6px; padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
      .meta { font-size: 0.9em; color: #444; }
      .title { font-size: 1.1em; font-weight: bold; margin-bottom: 6px; }
      .score { float: right; font-weight: bold; }
      .reason { margin-top: 8px; color: #222; }
      .relevant { color: green; font-weight: bold; }
      .not-relevant { color: #c0392b; font-weight: bold; }
      header { margin-bottom: 24px; }
    </style>
  </head>
  <body>
    <div class="container">
      <header>
        <h1>JobHunter — Gemte job</h1>
        <p>Liste over gemte job fra <code>data/jobs.json</code>. Sorteret: relevante først, højeste score øverst.</p>
      </header>

      {% for job in jobs %}
      <div class="job">
        <div>
          <a class="title" href="{{ job.url }}" target="_blank">{{ job.job_title or '–' }}</a>
          <!-- Avoid using Jinja string-formatting (|format or %) here as it can raise TypeError during rendering.
               If you need rounding/formatting, prepare a display string in Python before rendering the template. -->
          <span class="score">Score: {{ job.evaluation.score or "" }}</span>
        </div>
        <div class="meta">{{ job.company or '–' }} — {{ job.location or '–' }} &nbsp;|&nbsp; <span class="{{ 'relevant' if job.evaluation.relevant else 'not-relevant' }}">{{ 'Relevant' if job.evaluation.relevant else 'Ikke relevant' }}</span></div>
        <div class="reason">{{ job.evaluation.reason or "" }}</div>
      </div>
      {% endfor %}

    </div>
  </body>
</html>
"""


def load_jobs():
    data_path = os.path.join(os.getcwd(), 'data', 'jobs.json')
    try:
        if not os.path.exists(data_path):
            return []
        with open(data_path, 'r', encoding='utf-8') as f:
            jobs = json.load(f) or []
            return jobs
    except Exception as e:
        # Fail safe: don't crash the web server if file is invalid
        print(f"Error loading jobs for web UI: {e}")
        return []


@app.route('/')
def index():
    jobs = load_jobs()

    # Normalize and sort: relevant first, then by score descending
    def sort_key(j):
        eval_ = j.get('evaluation', {})
        relevant = bool(eval_.get('relevant'))
        score = float(eval_.get('score') or 0.0)
        # Sorting reversed later, so we return tuple
        return (relevant, score)

    jobs_sorted = sorted(jobs, key=sort_key, reverse=True)

    # Convert keys to attributes-like for template simplicity
    class J:
        def __init__(self, d):
            self.__dict__.update(d)
            # ensure evaluation is an object with attributes
            ev = d.get('evaluation', {})
            class E: pass
            e = E()
            e.__dict__.update(ev)
            self.evaluation = e

    jobs_wrapped = [J(j) for j in jobs_sorted]

    return render_template_string(TEMPLATE, jobs=jobs_wrapped)


if __name__ == '__main__':
    # Run on 0.0.0.0:5500 as requested
    app.run(host='0.0.0.0', port=5500)
