"""Notify Bark when the check-in workflow fails, without logging credentials."""
import json
import os
import urllib.parse
import urllib.request


def main():
    endpoint = os.environ.get("BARK_URL", "").strip().rstrip("/")
    if not endpoint:
        print("Bark notification endpoint is not configured.")
        return 1
    run_url = os.environ.get("CHECKIN_RUN_URL", "")
    title = "GLaDOS 签到失败"
    body = "自动签到任务失败，请检查登录状态或任务日志。" + ("\n" + run_url if run_url else "")
    url = endpoint + "/" + urllib.parse.quote(title, safe="") + "/" + urllib.parse.quote(body, safe="")
    url += "?" + urllib.parse.urlencode({"group": "GLaDOS签到", "ttl": 600})
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            result = json.load(response)
        if result.get("code") != 200:
            print("Bark rejected the notification.")
            return 1
    except Exception:
        print("Bark notification request failed.")
        return 1
    print("Bark failure notification accepted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
