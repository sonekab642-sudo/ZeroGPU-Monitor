import os
import time
import random
import sqlite3
import datetime
import threading
from flask import Flask, request, redirect, url_for, render_template_string
from huggingface_hub import HfApi

app = Flask(__name__)
DB_FILE = "accounts.db"

# =====================================================================
# ⚙️ আপনার ৩২টি অ্যাকাউন্টের সম্পূর্ণ তালিকা
# (প্রতিটি অ্যাকাউন্টের আসল API Key hf_xxxxxxxx এর জায়গায় বসিয়ে দিন)
# =====================================================================
ACCOUNTS_LIST = [
    {"username": "pagle-kukur-8", "api_key": "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"},
    {"username": "pagle-kukur-9", "api_key": "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"},
    {"username": "pagle-kukur-10", "api_key": "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"},
    {"username": "pagle-kukur-11", "api_key": "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"},
    {"username": "pagle-kukur-12", "api_key": "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"},
    {"username": "pagle-kukur-13", "api_key": "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"},
    {"username": "pagle-kukur-14", "api_key": "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"},
    {"username": "pagle-kukur-15", "api_key": "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"},
    {"username": "pagle-kukur-16", "api_key": "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"},
    {"username": "pagle-kukur-17", "api_key": "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"},
    {"username": "pagle-kukur-18", "api_key": "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"},
    {"username": "pagle-kukur-19", "api_key": "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"},
    {"username": "pagle-kukur-20", "api_key": "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"},
    {"username": "pagle-kukur-21", "api_key": "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"},]
 
# =====================================================================
# ডাটাবেজ সেটআপ
# =====================================================================
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                api_key TEXT,
                status TEXT DEFAULT 'Waiting',
                first_checked_at TIMESTAMP,
                last_checked_at TIMESTAMP,
                error_message TEXT
            )
        ''')
        # ACCOUNTS_LIST এর অ্যাকাউন্টগুলো লোড করা
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for acc in ACCOUNTS_LIST:
            user = acc.get("username", "").strip()
            key = acc.get("api_key", "").strip()
            if user and key:
                cursor.execute('''
                    INSERT OR IGNORE INTO accounts 
                    (username, api_key, status, first_checked_at, last_checked_at, error_message)
                    VALUES (?, ?, 'Waiting', ?, ?, 'Queued')
                ''', (user, key, now_str, now_str))
        conn.commit()

init_db()

# =====================================================================
# জিরোজিপিইউ টেস্ট ফাংশন
# =====================================================================
def test_zerogpu(username, api_key):
    try:
        api = HfApi(token=api_key)
        test_repo_id = f"{username}/zgpu-check-test"
        
        # জিরোজিপিইউ স্পেস তৈরি চেষ্টা
        api.create_repo(
            repo_id=test_repo_id,
            repo_type="space",
            space_sdk="gradio",
            space_hardware="zero-a10g",
            exist_ok=False
        )
        # টেস্ট সফল হলে রিপোজিটরি মুছে দেওয়া
        try:
            api.delete_repo(repo_id=test_repo_id, repo_type="space")
        except Exception:
            pass

        return True, "Space Created Successfully!"
    except Exception as e:
        err = str(e)
        if "401" in err or "Invalid" in err:
            return False, "Invalid API Key"
        elif "Hardware not allowed" in err or "zero-a10g" in err:
            return False, "ZeroGPU not granted yet"
        return False, err[:80]

# =====================================================================
# ব্যাকগ্রাউন্ড ওয়ার্কার: প্রতি ২-৫ মিনিট রেন্ডম সময়ে ১টি করে চেক
# =====================================================================
def background_checker_loop():
    time.sleep(10)  # সার্ভার চালু হওয়ার জন্য ১০ সেকেন্ড অপেক্ষা
    print("🚀 ব্যাকগ্রাউন্ড চেকার শুরু হয়েছে!")

    while True:
        try:
            now = datetime.datetime.now()
            now_str = now.strftime("%Y-%m-%d %H:%M:%S")

            with get_db() as conn:
                cursor = conn.cursor()

                # ১. ৬০ দিন (২ মাস) পার হয়ে যাওয়া অ্যাকাউন্টকে 'Death' মার্ক করা
                sixty_days_ago = (now - datetime.timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute('''
                    UPDATE accounts 
                    SET status = 'Death', error_message = 'Failed after 60 days limit'
                    WHERE status = 'Waiting' AND first_checked_at <= ?
                ''', (sixty_days_ago,))
                conn.commit()

                # ২. সবচেয়ে পুরনো চেক হওয়া ১টি 'Waiting' অ্যাকাউন্ট নেওয়া
                cursor.execute('''
                    SELECT id, username, api_key FROM accounts 
                    WHERE status = 'Waiting' 
                    ORDER BY last_checked_at ASC LIMIT 1
                ''')
                target = cursor.fetchone()

                if target:
                    acc_id = target["id"]
                    username = target["username"]
                    api_key = target["api_key"]

                    print(f"[{now_str}] 🔎 চেকিং চলছে: {username} ...")
                    success, msg = test_zerogpu(username, api_key)

                    if success:
                        # একবার Active হলে আর কখনোই চেক হবে না
                        cursor.execute('''
                            UPDATE accounts 
                            SET status = 'Active', last_checked_at = ?, error_message = ?
                            WHERE id = ?
                        ''', (now_str, msg, acc_id))
                        print(f"🎉 [{username}] এখন Active! ZeroGPU স্পেস তৈরি হয়েছে।")
                    else:
                        cursor.execute('''
                            UPDATE accounts 
                            SET last_checked_at = ?, error_message = ?
                            WHERE id = ?
                        ''', (now_str, msg, acc_id))
                        print(f"⏳ [{username}] এখনো Waiting। নোট: {msg}")

                    conn.commit()
                else:
                    print(f"[{now_str}] কোনো Waiting অ্যাকাউন্ট অবশিষ্ট নেই।")

        except Exception as e:
            print(f"চেকার লুপে সমস্যা: {e}")

        # ২ থেকে ৫ মিনিটের মধ্যে রেন্ডম সেকেন্ড বাছাই (১২০ থেকে ৩০০ সেকেন্ড)
        random_delay = random.randint(120, 300)
        minutes = random_delay // 60
        seconds = random_delay % 60
        print(f"⏱️ পরবর্তী অ্যাকাউন্ট চেক হবে {minutes} মিনিট {seconds} সেকেন্ড পর...\n")
        time.sleep(random_delay)

# আলাদা থ্রেডে ব্যাকগ্রাউন্ড চেকার চালু রাখা
checker_thread = threading.Thread(target=background_checker_loop, daemon=True)
checker_thread.start()

# =====================================================================
# ড্যাশবোর্ড UI টেমপ্লেট
# =====================================================================
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZeroGPU Monitor Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; font-family: system-ui, -apple-system, sans-serif; }
        .card-stat { border-radius: 12px; }
        .badge { font-size: 0.88rem; padding: 6px 12px; }
    </style>
</head>
<body>
<div class="container py-4">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h3 class="fw-bold m-0">⚡ Hugging Face ZeroGPU 24/7 Monitor</h3>
        <span class="badge bg-primary">Interval: প্রতি ২ - ৫ মিনিট (Random)</span>
    </div>

    <!-- স্ট্যাটাস কাউন্টার কার্ড -->
    <div class="row g-3 mb-4">
        <div class="col-md-3">
            <div class="card card-stat bg-primary text-white p-3 shadow-sm">
                <h6>মোট অ্যাকাউন্ট</h6>
                <h2 class="m-0 fw-bold">{{ total }}</h2>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card card-stat bg-success text-white p-3 shadow-sm">
                <h6>🟢 Active (সফল)</h6>
                <h2 class="m-0 fw-bold">{{ active_count }}</h2>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card card-stat bg-warning text-dark p-3 shadow-sm">
                <h6>🟡 Waiting (চলমান)</h6>
                <h2 class="m-0 fw-bold">{{ waiting_count }}</h2>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card card-stat bg-danger text-white p-3 shadow-sm">
                <h6>🔴 Death (২ মাস পার)</h6>
                <h2 class="m-0 fw-bold">{{ death_count }}</h2>
            </div>
        </div>
    </div>

    <!-- নতুন অ্যাকাউন্ট যুক্ত করার ফর্ম -->
    <div class="card border-0 shadow-sm mb-4">
        <div class="card-body">
            <h5 class="fw-bold mb-3">➕ আরও অ্যাকাউন্ট যোগ করুন</h5>
            <form action="/add" method="POST" class="row g-2">
                <div class="col-md-5">
                    <input type="text" name="username" class="form-control" placeholder="Hugging Face Username" required>
                </div>
                <div class="col-md-5">
                    <input type="text" name="api_key" class="form-control" placeholder="API Key (hf_...)" required>
                </div>
                <div class="col-md-2">
                    <button type="submit" class="btn btn-primary w-100 fw-bold">Add Account</button>
                </div>
            </form>
        </div>
    </div>

    <!-- টেবিল ড্যাশবোর্ড -->
    <div class="card border-0 shadow-sm">
        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0">
                    <thead class="table-dark">
                        <tr>
                            <th class="ps-3">#</th>
                            <th>ইউজারনেম</th>
                            <th>স্ট্যাটাস</th>
                            <th>শুরুর তারিখ</th>
                            <th>সর্বশেষ চেক</th>
                            <th class="pe-3">স্ট্যাটাস নোট / এরর</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for acc in accounts %}
                        <tr>
                            <td class="ps-3 text-muted">{{ loop.index }}</td>
                            <td class="fw-bold">{{ acc['username'] }}</td>
                            <td>
                                {% if acc['status'] == 'Active' %}
                                    <span class="badge bg-success">🟢 Active</span>
                                {% elif acc['status'] == 'Waiting' %}
                                    <span class="badge bg-warning text-dark">🟡 Waiting</span>
                                {% elif acc['status'] == 'Death' %}
                                    <span class="badge bg-danger">🔴 Death</span>
                                {% endif %}
                            </td>
                            <td><small class="text-secondary">{{ acc['first_checked_at'] }}</small></td>
                            <td><small class="text-secondary">{{ acc['last_checked_at'] }}</small></td>
                            <td class="pe-3"><small class="text-muted">{{ acc['error_message'] }}</small></td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>
</body>
</html>
"""

# =====================================================================
# রাউটার এন্ডপয়েন্ট
# =====================================================================
@app.route('/')
def dashboard():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM accounts ORDER BY status ASC, id DESC")
        accounts = cursor.fetchall()

        total = len(accounts)
        active_count = sum(1 for a in accounts if a['status'] == 'Active')
        waiting_count = sum(1 for a in accounts if a['status'] == 'Waiting')
        death_count = sum(1 for a in accounts if a['status'] == 'Death')

    return render_template_string(
        DASHBOARD_HTML,
        accounts=accounts,
        total=total,
        active_count=active_count,
        waiting_count=waiting_count,
        death_count=death_count
    )

@app.route('/add', methods=['POST'])
def add():
    user = request.form.get('username', '').strip()
    key = request.form.get('api_key', '').strip()
    if user and key:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO accounts 
                (username, api_key, status, first_checked_at, last_checked_at, error_message)
                VALUES (?, ?, 'Waiting', ?, ?, 'Added, Waiting')
            ''', (user, key, now_str, now_str))
            conn.commit()
    return redirect(url_for('dashboard'))

# রেন্ডারকে ২৪/৭ সজাগ রাখতে পিং লিঙ্ক
@app.route('/ping')
def ping():
    return "OK - 24/7 Alive", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
