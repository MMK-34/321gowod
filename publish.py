"""Publish one day's post to Instagram (Instagram API with Instagram Login).

Usage:  python publish.py [YYYY-MM-DD]      (default: today, UTC)
        python publish.py --refresh-token  (extends the 60-day token, prints new expiry)

Env:    IG_TOKEN     long-lived Instagram access token
        PUBLIC_BASE  public URL of the repo root, e.g. https://raw.githubusercontent.com/<user>/<repo>/main
                     (in GitHub Actions it is derived from GITHUB_REPOSITORY)

A day's post lives in posts/<date>/: 1.jpg [2.jpg 3.jpg] + caption.txt.
After publishing, posts/<date>/published.json is written so a day never posts twice.
"""
import json, os, sys, time, datetime, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API = "https://graph.instagram.com/v24.0"


def call(method, path, **params):
    params["access_token"] = os.environ["IG_TOKEN"]
    data = urllib.parse.urlencode(params).encode()
    url = f"{API}/{path}"
    if method == "GET":
        req = urllib.request.Request(f"{url}?{data.decode()}")
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"Instagram API error on {path}: {e.read().decode()}")


def wait_ready(container):
    for _ in range(30):
        status = call("GET", container, fields="status_code")["status_code"]
        if status == "FINISHED":
            return
        if status == "ERROR":
            sys.exit(f"container {container} failed")
        time.sleep(5)
    sys.exit(f"container {container} not ready in time")


def publish(date):
    day = ROOT / "posts" / date
    if not day.exists():
        print(f"no post scheduled for {date}")
        return
    if (day / "published.json").exists():
        print(f"{date} already published")
        return
    base = os.environ.get("PUBLIC_BASE") or \
        f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/main"
    images = sorted(day.glob("*.jpg"))
    caption = (day / "caption.txt").read_text(encoding="utf-8")
    user = call("GET", "me", fields="user_id,username")
    uid = user["user_id"]
    urls = [f"{base}/posts/{date}/{p.name}" for p in images]

    if len(urls) == 1:
        container = call("POST", f"{uid}/media", image_url=urls[0], caption=caption)["id"]
    else:
        children = []
        for u in urls:
            c = call("POST", f"{uid}/media", image_url=u, is_carousel_item="true")["id"]
            wait_ready(c)
            children.append(c)
        container = call("POST", f"{uid}/media", media_type="CAROUSEL",
                         children=",".join(children), caption=caption)["id"]
    wait_ready(container)
    media = call("POST", f"{uid}/media_publish", creation_id=container)["id"]
    (day / "published.json").write_text(json.dumps({
        "media_id": media, "account": user["username"], "images": len(urls),
        "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}, indent=1))
    print(f"published {date} -> media {media} on @{user['username']}")


def refresh():
    q = urllib.parse.urlencode({"grant_type": "ig_refresh_token", "access_token": os.environ["IG_TOKEN"]})
    with urllib.request.urlopen(f"https://graph.instagram.com/refresh_access_token?{q}", timeout=60) as r:
        res = json.loads(r.read())
    days = res["expires_in"] // 86400
    print(f"token refreshed, valid for {days} more days")
    out = os.environ.get("GITHUB_OUTPUT")
    if out and res["access_token"] != os.environ["IG_TOKEN"]:
        print(f"::add-mask::{res['access_token']}")
        with open(out, "a") as f:
            f.write(f"new_token={res['access_token']}\n")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg == "--refresh-token":
        refresh()
    else:
        publish(arg or datetime.datetime.now(datetime.timezone.utc).date().isoformat())
