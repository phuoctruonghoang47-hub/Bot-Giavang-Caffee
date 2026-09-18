"""Bot Telegram cập nhật giá vàng, cà phê và tin tức liên quan.

Cách dùng:
    python bot.py prices     # gửi bản tin giá
    python bot.py news       # quét tin mới + cảnh báo biến động vàng
    python bot.py prices --dry-run   # in ra màn hình, không gửi Telegram

Biến môi trường: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (có thể đặt trong file .env).
"""
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from itertools import zip_longest
from pathlib import Path

import config

ROOT = Path(__file__).parent
STATE_FILE = ROOT / "state" / "state.json"
VN_TZ = timezone(timedelta(hours=7))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
GRAMS_PER_OZ = 31.1034768
GRAMS_PER_LUONG = 37.5

sys.stdout.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------- tiện ích

def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def http_get(url, data=None, timeout=25):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # thử lại khi lỗi mạng tạm thời
            last = e
            time.sleep(2 * (attempt + 1))
    raise last


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def now_vn():
    return datetime.now(VN_TZ)


def fmt_trieu(vnd):
    """147600000 -> '147,6'"""
    s = f"{vnd / 1e6:,.2f}".rstrip("0").rstrip(".")
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_int(n):
    return f"{n:,.0f}".replace(",", ".")


def arrow(delta):
    if delta > 0:
        return "🟢▲"
    if delta < 0:
        return "🔴▼"
    return "⚪"


def diff_text(cur, prev, unit_fn=fmt_trieu, suffix=""):
    if prev is None or prev == cur:
        return ""
    d = cur - prev
    sign = "+" if d > 0 else "-"
    return f" {arrow(d)} {sign}{unit_fn(abs(d))}{suffix}"


# ---------------------------------------------------------------- Telegram

def send_telegram(text, dry_run=False):
    if dry_run:
        print(text)
        print("-" * 60)
        return
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        sys.exit("Thiếu TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID")
    # Telegram giới hạn 4096 ký tự/tin -> chia theo dòng
    chunks, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > 4000:
            chunks.append(cur)
            cur = ""
        cur += line + "\n"
    if cur.strip():
        chunks.append(cur)
    for chunk in chunks:
        payload = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode()
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            urllib.request.urlopen(urllib.request.Request(url, data=payload), timeout=25).read()
        except urllib.error.HTTPError as e:
            sys.exit(f"Telegram lỗi {e.code}: {e.read().decode('utf-8', 'replace')}")
        time.sleep(1)


# ---------------------------------------------------------------- nguồn giá

def world_gold():
    """Giá vàng thế giới (USD/oz) + thay đổi so với phiên trước, từ Yahoo Finance (GC=F)."""
    try:
        data = json.loads(http_get("https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1d&range=5d"))
        meta = data["chart"]["result"][0]["meta"]
        return {"price": meta["regularMarketPrice"], "prev_close": meta.get("chartPreviousClose")}
    except Exception:
        data = json.loads(http_get("https://api.gold-api.com/price/XAU"))
        return {"price": data["price"], "prev_close": None}


def usd_vnd():
    try:
        data = json.loads(http_get("https://query1.finance.yahoo.com/v8/finance/chart/VND=X?interval=1d&range=5d"))
        return data["chart"]["result"][0]["meta"]["regularMarketPrice"]
    except Exception:
        return None


def sjc_prices():
    data = json.loads(http_get(
        "https://sjc.com.vn/GoldPrice/Services/PriceService.ashx",
        data=b"method=GetCurrentGoldPricesByBranch&BranchId=1",
    ))
    rows = {d["TypeName"]: (d["BuyValue"], d["SellValue"]) for d in data["data"]}
    out = {}
    for name, key in [("Vàng miếng SJC", "Vàng SJC 1L, 10L, 1KG"),
                      ("Vàng nhẫn SJC 99,99", "Vàng nhẫn SJC 99,99% 1 chỉ, 2 chỉ, 5 chỉ")]:
        if key in rows:
            out[name] = rows[key]
    return out, data.get("latestDate", "")


def pnj_prices():
    data = json.loads(http_get("https://edge-api.pnj.io/ecom-frontend/v1/get-gold-price?zone=00"))
    out = {}
    for d in data["data"]:
        # PNJ trả về nghìn đồng/chỉ -> đổi ra đồng/lượng
        if d["masp"] == "SJC":
            out["Vàng miếng SJC"] = (d["giamua"] * 10_000, d["giaban"] * 10_000)
        elif d["masp"] == "N24K":
            out["Nhẫn trơn PNJ 999.9"] = (d["giamua"] * 10_000, d["giaban"] * 10_000)
    return out, data.get("updateDate", "")


def coffee_tay_nguyen():
    """Giá cà phê nhân trung bình Tây Nguyên (đ/kg) và thay đổi so với hôm trước."""
    try:
        page = http_get("https://giacaphe.com/gia-ca-phe-noi-dia/")
        m = re.search(r'name="description" content="([^"]+)"', page)
        desc = html.unescape(m.group(1)) if m else ""
        m = re.search(r"trung bình\s+([\d.,]+)\s*vnđ/kg\s*(tăng|giảm)?\s*([-+]?[\d.,]+)?", desc, re.I)
        if m:
            price = int(re.sub(r"[.,]", "", m.group(1)))
            change = int(re.sub(r"[-+.,]", "", m.group(3))) if m.group(3) else 0
            if (m.group(2) or "").lower() == "giảm":
                change = -change
            return {"price": price, "change": change, "source": "giacaphe.com",
                    "url": "https://giacaphe.com/gia-ca-phe-noi-dia/"}
    except Exception:
        pass
    page = http_get("https://webgia.com/gia-hang-hoa/ca-phe/")
    text = re.sub(r"<[^>]+>", " ", page)
    m = re.search(r"Giá cà phê trung bình:\s*([\d.,]+)\s*vnđ/kg", text, re.I)
    if not m:
        raise RuntimeError("Không đọc được giá cà phê")
    return {"price": int(re.sub(r"[.,]", "", m.group(1))), "change": None, "source": "webgia.com",
            "url": "https://webgia.com/gia-hang-hoa/ca-phe/"}


# ---------------------------------------------------------------- bản tin giá

def build_price_report(state):
    prev = state.get("last_prices", {})
    cur = {}
    lines = [f"📊 <b>BẢN TIN GIÁ VÀNG & CÀ PHÊ</b>\n🕐 {now_vn():%H:%M %d/%m/%Y}\n"]
    errors = []

    # Vàng thế giới
    try:
        g = world_gold()
        cur["world_gold"] = g["price"]
        line = f"🌍 <b>Vàng thế giới:</b> ${g['price']:,.1f}/oz"
        if g["prev_close"]:
            d = g["price"] - g["prev_close"]
            line += f" {arrow(d)} {d:+,.1f} ({d / g['prev_close'] * 100:+.2f}%)"
        lines.append(line)
        rate = usd_vnd()
        if rate:
            quy_doi = g["price"] * rate * GRAMS_PER_LUONG / GRAMS_PER_OZ
            cur["world_gold_vnd"] = quy_doi
            lines.append(f"   ↳ Quy đổi ≈ {fmt_trieu(quy_doi)} tr/lượng (USD/VND {fmt_int(rate)})")
    except Exception as e:
        errors.append(f"vàng thế giới: {e}")

    # Vàng trong nước
    # Web SJC hay chặn máy chủ nước ngoài (GitHub) -> khi đó lấy giá miếng SJC từ bảng giá PNJ
    domestic = {}
    for fn, label in [(sjc_prices, "SJC"), (pnj_prices, "PNJ")]:
        try:
            rows, _ = fn()
            for name, val in rows.items():
                domestic.setdefault(name, val)
        except Exception as e:
            errors.append(f"{label}: {e}")
    if domestic:
        lines.append("\n🇻🇳 <b>Vàng trong nước</b> (triệu đ/lượng, mua – bán)")
        for name, (buy, sell) in domestic.items():
            p = prev.get("domestic", {}).get(name)
            chg = diff_text(sell, p[1] if p else None)
            lines.append(f"• {name}: {fmt_trieu(buy)} – <b>{fmt_trieu(sell)}</b>{chg}")
        cur["domestic"] = domestic
        sjc = domestic.get("Vàng miếng SJC")
        if sjc and cur.get("world_gold_vnd"):
            lines.append(f"   ↳ SJC cao hơn thế giới ≈ {fmt_trieu(sjc[1] - cur['world_gold_vnd'])} tr/lượng")

    # Cà phê
    try:
        c = coffee_tay_nguyen()
        cur["coffee"] = c["price"]
        line = f"\n☕ <b>Cà phê nhân Tây Nguyên:</b> <b>{fmt_int(c['price'])}</b> đ/kg"
        if c["change"] is not None:
            line += f" {arrow(c['change'])} {c['change']:+,}đ".replace(",", ".") if c["change"] else " ⚪ không đổi"
        lines.append(line)
        lines.append(f'   ↳ Giá trung bình Đắk Lắk, Lâm Đồng, Gia Lai, Đắk Nông · <a href="{c["url"]}">Xem theo tỉnh</a>')
    except Exception as e:
        errors.append(f"cà phê: {e}")

    lines.append("\n<i>Nguồn: Yahoo Finance (COMEX), SJC, PNJ, giacaphe.com</i>")
    if errors:
        print("Lỗi nguồn:", *errors, sep="\n  ", file=sys.stderr)
    state["last_prices"] = {**prev, **cur}
    return "\n".join(lines)


# ---------------------------------------------------------------- tin tức

def google_news(query, lang):
    q = f"{query} when:1d"
    if lang == "vi":
        params = {"q": q, "hl": "vi", "gl": "VN", "ceid": "VN:vi"}
    else:
        params = {"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    xml = http_get("https://news.google.com/rss/search?" + urllib.parse.urlencode(params))
    items = []
    for it in ET.fromstring(xml).iter("item"):
        title = it.findtext("title", "")
        source = it.findtext("source", "")
        if source and title.endswith(" - " + source):
            title = title[: -len(source) - 3]
        try:
            pub = parsedate_to_datetime(it.findtext("pubDate"))
        except Exception:
            continue
        items.append({"title": html.unescape(title).strip(), "link": it.findtext("link", ""),
                      "source": source, "pub": pub})
    return items


DAILY_PRICE_RE = re.compile(r"^(giá (vàng|cà phê|nông sản)|tt cà phê)[^:]*(hôm nay|ngày|\d+/\d+)", re.I)


def news_key(title, label, pub):
    """Khoá chống trùng. Các bài 'Giá ... hôm nay' báo nào cũng đăng -> chỉ giữ 1 bài/ngày/chủ đề."""
    if DAILY_PRICE_RE.search(title):
        return f"daily:{label}:{pub.astimezone(VN_TZ):%Y-%m-%d}"
    return re.sub(r"\W+", " ", title.lower()).strip()[:90]


def collect_news(seen):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.NEWS_MAX_AGE_HOURS)
    found = {}
    for label, query, lang in config.NEWS_QUERIES:
        try:
            items = google_news(query, lang)
        except Exception as e:
            print(f"Lỗi Google News ({label}): {e}", file=sys.stderr)
            continue
        for it in items:
            t = it["title"].lower()
            src = it["source"].lower()
            key = news_key(it["title"], label, it["pub"])
            if (it["pub"] < cutoff or key in seen or key in found
                    or not any(s in src for s in config.TRUSTED_SOURCES)
                    or not any(re.search(rf"\b{re.escape(k)}\b", t) for k in config.REQUIRED_KEYWORDS[label])
                    or any(k in t for k in config.EXCLUDE_KEYWORDS)):
                continue
            found[key] = {**it, "label": label}
        time.sleep(1)
    return sorted(found.items(), key=lambda kv: kv[1]["pub"], reverse=True)


def build_news_report(state):
    seen = state.get("seen", {})
    items = collect_news(seen)
    first_run = not seen
    stamp = int(time.time())
    for key, _ in items:
        seen[key] = stamp
    # Giữ lịch sử 3 ngày cho gọn file
    state["seen"] = {k: v for k, v in seen.items() if stamp - v < 3 * 86400}

    # Xen kẽ vàng / cà phê để một chủ đề không lấn át chủ đề kia
    groups = {}
    for kv in items:
        groups.setdefault(kv[1]["label"], []).append(kv)
    mixed = [kv for rnd in zip_longest(*groups.values()) for kv in rnd if kv]
    to_send = mixed[: 6 if first_run else config.NEWS_MAX_PER_RUN]
    if not to_send:
        return None
    lines = [f"📰 <b>TIN MỚI – VÀNG & CÀ PHÊ</b> · {now_vn():%H:%M %d/%m}\n"]
    for _, it in to_send:
        t = it["pub"].astimezone(VN_TZ)
        lines.append(f'{it["label"]} <a href="{html.escape(it["link"])}">{html.escape(it["title"])}</a>\n'
                     f'   <i>{html.escape(it["source"])} · {t:%H:%M %d/%m}</i>\n')
    return "\n".join(lines)


def build_gold_alert(state):
    """Cảnh báo khi vàng thế giới biến động mạnh giữa các lần quét."""
    try:
        price = world_gold()["price"]
    except Exception:
        return None
    ref = state.get("alert_ref_gold")
    if ref is None:
        state["alert_ref_gold"] = price
        return None
    pct = (price - ref) / ref * 100
    if abs(pct) < config.GOLD_ALERT_PCT:
        return None
    state["alert_ref_gold"] = price
    return (f"⚡ <b>CẢNH BÁO: Vàng thế giới {'TĂNG' if pct > 0 else 'GIẢM'} MẠNH</b>\n"
            f"{arrow(pct)} ${ref:,.1f} → <b>${price:,.1f}</b>/oz ({pct:+.2f}%)\n"
            f"🕐 {now_vn():%H:%M %d/%m/%Y}")


# ---------------------------------------------------------------- main

def main():
    load_env()
    args = sys.argv[1:]
    dry = "--dry-run" in args
    cmd = next((a for a in args if not a.startswith("--")), "")
    state = load_state()
    if cmd == "prices":
        send_telegram(build_price_report(state), dry)
    elif cmd == "news":
        alert = build_gold_alert(state)
        if alert:
            send_telegram(alert, dry)
        report = build_news_report(state)
        if report:
            send_telegram(report, dry)
        else:
            print("Không có tin mới.")
    elif cmd == "test":
        send_telegram("✅ Bot đã kết nối thành công với kênh!", dry)
        return
    else:
        sys.exit(__doc__)
    if not dry:
        save_state(state)


if __name__ == "__main__":
    main()
