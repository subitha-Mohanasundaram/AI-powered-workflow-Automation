import urllib.request

try:
    r = urllib.request.urlopen('http://127.0.0.1:8000/dashboard', timeout=5)
    body = r.read().decode()
    checks = [
        ('Glassmorphism bg',    'rgba(255,255,255,.03)' in body),
        ('Sticky header',       'position:sticky' in body),
        ('Animated bg',         'bgShift' in body),
        ('AI status pill',      'aiStatusPill' in body),
        ('Countdown timer',     'countdown' in body),
        ('Toast system',        'toastContainer' in body),
        ('Shimmer button',      'run-btn' in body),
        ('Typing placeholder',  'animatePlaceholder' in body),
        ('Progress bar',        'progressWrap' in body),
        ('Tab switching',       'switchTab' in body),
        ('JSON highlight',      'highlightJson' in body),
        ('Auto refresh',        'startCountdown' in body),
        ('Weather render',      'open-meteo' in body),
        ('News render',         'gnews' in body),
        ('GitHub render',       'github' in body),
        ('Currency render',     'open.er-api.com' in body),
        ('LeetCode render',     'leetcode_report' in body),
        ('Fade-up animation',   'fadeUp' in body),
    ]
    all_ok = all(v for _, v in checks)
    print("=== Dashboard UI Checks ===")
    for name, ok in checks:
        status = "OK  " if ok else "MISS"
        print(f"  {status} | {name}")
    print()
    print(f"Page size : {len(body):,} chars")
    print(f"Result    : {'ALL CHECKS PASSED' if all_ok else 'SOME CHECKS FAILED'}")
except Exception as e:
    print("ERROR:", e)
