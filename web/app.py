from flask import Flask, render_template_string, request, redirect, url_for
import json
import os
import subprocess
import sys

app = Flask(__name__)

# Simple HTML template for job listing with basic navigation and a button to trigger the agent
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
      .nav { margin-bottom: 16px; }
      .nav a { margin-right: 12px; text-decoration: none; color: #2c3e50; font-weight: bold; }
      .job { background: #fff; border-radius: 6px; padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
      .meta { font-size: 0.9em; color: #444; }
      .title { font-size: 1.1em; font-weight: bold; margin-bottom: 6px; }
      .score { float: right; font-weight: bold; }
      .reason { margin-top: 8px; color: #222; }
      .relevant { color: green; font-weight: bold; }
      .not-relevant { color: #c0392b; font-weight: bold; }
      header { margin-bottom: 12px; }
      .actions { margin-bottom: 18px; }
      .btn { display: inline-block; padding: 8px 12px; background:#2c7; color:#fff; border-radius:4px; text-decoration:none; }
    </style>
  </head>
  <body>
    <div class="container">
      <div class="nav"><a href="/">Dashboard</a><a href="/settings">Indstillinger</a></div>
      <header>
        <h1>JobHunter — Gemte job</h1>
        <p>Liste over gemte job fra <code>data/jobs.json</code>. Sorteret: relevante først, højeste score øverst.</p>
      </header>

      <div class="actions">
        <form action="/update" method="post" style="display:inline;">
          <button class="btn" type="submit">Kør job-agent nu</button>
        </form>
      </div>

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


# Settings helpers: load/save settings to data/settings.json with safe defaults
DEFAULT_SETTINGS = {
    "search_terms": ["it drift", "systemadministrator", "it operations"],
    "include_titles": ["IT-drift", "IT Operations", "Systemadministrator", "IT-ansvarlig"],
    "exclude_titles": ["1st line", "Helpdesk", "Junior", "Trainee", "Developer"],
    "max_jobs": 10
}


def load_settings():
    path = os.path.join(os.getcwd(), 'data', 'settings.json')
    try:
        if not os.path.exists(path):
            # Create file with defaults
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_SETTINGS, f, ensure_ascii=False, indent=2)
            return DEFAULT_SETTINGS.copy()

        with open(path, 'r', encoding='utf-8') as f:
            s = json.load(f) or DEFAULT_SETTINGS.copy()
            # Validate minimal structure
            if not isinstance(s.get('search_terms'), list):
                s['search_terms'] = DEFAULT_SETTINGS['search_terms']
            if not isinstance(s.get('max_jobs'), int):
                s['max_jobs'] = DEFAULT_SETTINGS['max_jobs']
            return s
    except Exception as e:
        print(f"Error loading settings: {e}")
        return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    path = os.path.join(os.getcwd(), 'data', 'settings.json')
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False


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


# Settings page: view and edit settings
SETTINGS_TEMPLATE = """
<!doctype html>
<html lang="da">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>JobHunter - Indstillinger</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 40px; background:#f7f9fb; }
      .container { max-width: 800px; margin: 0 auto; }
      textarea, input { width: 100%; padding: 8px; border-radius:4px; border:1px solid #ddd; box-sizing: border-box; }
      label { font-weight: bold; display:block; margin-top: 12px; }
      .nav { margin-bottom: 16px; }
      .msg { background: #e8f5e9; color: #2e7d32; padding: 8px 12px; border-radius: 4px; }
      .btn { display: inline-block; padding: 8px 12px; background:#2c7; color:#fff; border-radius:4px; text-decoration:none; border: none; }
    </style>
  </head>
  <body>
    <div class="container">
      <div class="nav"><a href="/">Dashboard</a><a href="/settings">Indstillinger</a></div>

      <h1>Indstillinger</h1>
      {% if saved %}
        <div class="msg">Indstillinger gemt</div>
      {% endif %}

      <form method="post" action="/settings">
        <label for="search_terms">Search terms (én per linje)</label>
        <textarea id="search_terms" name="search_terms" rows="6">{{ search_terms }}</textarea>

        <label for="include_titles">Include titles (én per linje)</label>
        <textarea id="include_titles" name="include_titles" rows="4">{{ include_titles }}</textarea>

        <label for="exclude_titles">Exclude titles (én per linje)</label>
        <textarea id="exclude_titles" name="exclude_titles" rows="4">{{ exclude_titles }}</textarea>

        <label for="max_jobs">Max jobs</label>
        <input type="number" id="max_jobs" name="max_jobs" value="{{ max_jobs }}" />

        <p style="margin-top:12px;"><button class="btn" type="submit">Gem indstillinger</button></p>
      </form>
    </div>
  </body>
</html>
"""


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        # Read form values and persist
        search = request.form.get('search_terms', '')
        include = request.form.get('include_titles', '')
        exclude = request.form.get('exclude_titles', '')
        max_jobs = request.form.get('max_jobs', '')

        settings = {}
        settings['search_terms'] = [s.strip() for s in search.splitlines() if s.strip()]
        settings['include_titles'] = [s.strip() for s in include.splitlines() if s.strip()]
        settings['exclude_titles'] = [s.strip() for s in exclude.splitlines() if s.strip()]
        try:
            settings['max_jobs'] = int(max_jobs)
        except Exception:
            settings['max_jobs'] = DEFAULT_SETTINGS['max_jobs']

        save_success = save_settings(settings)
        return redirect(url_for('settings', saved=1))

    # GET: load and render
    s = load_settings()
    # Prepare textarea contents (one per line)
    search_terms = "\n".join(s.get('search_terms', []))
    include_titles = "\n".join(s.get('include_titles', []))
    exclude_titles = "\n".join(s.get('exclude_titles', []))
    max_jobs = s.get('max_jobs', DEFAULT_SETTINGS['max_jobs'])

    saved = request.args.get('saved') == '1' or request.args.get('saved') == 'True' or False

    return render_template_string(SETTINGS_TEMPLATE, search_terms=search_terms, include_titles=include_titles, exclude_titles=exclude_titles, max_jobs=max_jobs, saved=saved)


@app.route('/update', methods=['POST'])
def update():
    # Trigger the job agent via subprocess when the user requests an update
    try:
        print('Update triggered by web UI', file=sys.stderr)
        # Run agent; do not raise on non-zero exit to avoid crashing the web server
        subprocess.run(["python", "src/run.py"], check=False)
    except Exception as e:
        print(f"Error running update: {e}", file=sys.stderr)

    return redirect(url_for('index'))


if __name__ == '__main__':
    # Run on 0.0.0.0:5500 as requested
    app.run(host='0.0.0.0', port=5500)
