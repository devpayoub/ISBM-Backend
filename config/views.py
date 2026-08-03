import os

from django.conf import settings
from django.http import HttpResponse


def _last_commit_info() -> str:
    """Render sets RENDER_GIT_COMMIT for deployed instances (no .git checked
    out there); fall back to reading .git/HEAD directly for local dev — the
    git CLI isn't installed in the app container, so this parses the ref by
    hand instead of shelling out (handles both loose and packed refs)."""
    commit = os.environ.get("RENDER_GIT_COMMIT")
    if commit:
        return commit[:7]
    try:
        git_dir = settings.BASE_DIR / ".git"
        head = (git_dir / "HEAD").read_text().strip()
        if not head.startswith("ref:"):
            return head[:7]
        ref_name = head.split(" ", 1)[1].strip()
        ref_path = git_dir / ref_name
        if ref_path.exists():
            return ref_path.read_text().strip()[:7]
        packed = git_dir / "packed-refs"
        if packed.exists():
            for line in packed.read_text().splitlines():
                if line.endswith(ref_name):
                    return line.split()[0][:7]
    except Exception:
        pass
    return "unknown"


def status_view(request):
    commit = _last_commit_info()
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>ISBM Backend — Status</title>
<style>
  body {{ margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
          font-family:-apple-system,"Segoe UI",Arial,sans-serif; background:#0f172a; color:#e2e8f0; }}
  .card {{ text-align:center; }}
  h1 {{ font-size:28px; margin:0 0 14px; display:flex; align-items:center; justify-content:center; gap:10px; }}
  .dot {{ width:14px; height:14px; border-radius:50%; background:#22c55e;
          box-shadow:0 0 12px rgba(34,197,94,.7); }}
  .commit {{ font-family:ui-monospace,Menlo,Consolas,monospace; font-size:13px; color:#94a3b8; }}
</style>
</head>
<body>
  <div class="card">
    <h1><span class="dot"></span>Running</h1>
    <div class="commit">{commit}</div>
  </div>
</body>
</html>"""
    return HttpResponse(html)
