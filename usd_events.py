"""Săn tin USD mức tác động Cao: nhắc trước giờ công bố, lấy kết quả thực tế, phân tích tác động lên vàng.

- Lịch + dự báo: ForexFactory (nfs.faireconomy.media)
- Kết quả thực tế: BLS (Nonfarm, thất nghiệp, lương, CPI, PPI), Fed (lãi suất)
- Phản ứng giá vàng: Yahoo Finance GC=F khung 1 phút
- Phân tích: theo quy tắc cố định (không dùng AI)
"""
import html
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

CAL_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
FF_LINK = "https://www.forexfactory.com/calendar"

# Tên tiếng Việt
VI = {
    "Non-Farm Employment Change": "Bảng lương phi nông nghiệp (Nonfarm)",
    "ADP Non-Farm Employment Change": "Việc làm ADP",
    "Unemployment Rate": "Tỷ lệ thất nghiệp",
    "Average Hourly Earnings m/m": "Lương theo giờ (tháng)",
    "Unemployment Claims": "Đơn trợ cấp thất nghiệp",
    "JOLTS Job Openings": "Việc làm JOLTS",
    "CPI m/m": "CPI tháng", "CPI y/y": "CPI năm", "Core CPI m/m": "CPI lõi tháng",
    "Core CPI y/y": "CPI lõi năm",
    "PPI m/m": "PPI tháng", "Core PPI m/m": "PPI lõi tháng",
    "Core PCE Price Index m/m": "PCE lõi tháng", "PCE Price Index m/m": "PCE tháng",
    "Advance GDP q/q": "GDP sơ bộ (quý)", "Prelim GDP q/q": "GDP điều chỉnh (quý)",
    "Retail Sales m/m": "Doanh số bán lẻ", "Core Retail Sales m/m": "Doanh số bán lẻ lõi",
    "ISM Manufacturing PMI": "PMI sản xuất ISM", "ISM Services PMI": "PMI dịch vụ ISM",
    "CB Consumer Confidence": "Niềm tin tiêu dùng CB",
    "Federal Funds Rate": "Lãi suất Fed", "FOMC Statement": "Tuyên bố FOMC",
    "FOMC Economic Projections": "Dự báo kinh tế của Fed",
    "FOMC Press Conference": "Họp báo Chủ tịch Fed",
    "FOMC Meeting Minutes": "Biên bản họp FOMC",
}

# Chiều tác động: +1 = số liệu CAO hơn dự báo -> USD mạnh lên; -1 = ngược lại
INVERSE = {"Unemployment Rate", "Unemployment Claims"}

# Giải thích ngắn theo nhóm tin
WHY = {
    "jobs": "thị trường lao động", "infl": "lạm phát", "growth": "tăng trưởng", "fed": "lãi suất Fed",
}
GROUP = {
    "Non-Farm Employment Change": "jobs", "ADP Non-Farm Employment Change": "jobs",
    "Unemployment Rate": "jobs", "Average Hourly Earnings m/m": "infl",
    "Unemployment Claims": "jobs", "JOLTS Job Openings": "jobs",
    "CPI m/m": "infl", "CPI y/y": "infl", "Core CPI m/m": "infl", "Core CPI y/y": "infl",
    "PPI m/m": "infl", "Core PPI m/m": "infl", "Core PCE Price Index m/m": "infl",
    "PCE Price Index m/m": "infl", "Advance GDP q/q": "growth", "Prelim GDP q/q": "growth",
    "Retail Sales m/m": "growth", "Core Retail Sales m/m": "growth",
    "ISM Manufacturing PMI": "growth", "ISM Services PMI": "growth",
    "CB Consumer Confidence": "growth", "Federal Funds Rate": "fed",
}

# Mức chênh lệch được coi là "lớn" (cùng đơn vị với dự báo)
BIG = {
    "Non-Farm Employment Change": 50, "ADP Non-Farm Employment Change": 40,
    "Unemployment Rate": 0.2, "Average Hourly Earnings m/m": 0.2, "Unemployment Claims": 20,
    "CPI m/m": 0.2, "CPI y/y": 0.2, "Core CPI m/m": 0.2, "Core CPI y/y": 0.2,
    "PPI m/m": 0.3, "Core PPI m/m": 0.3, "Core PCE Price Index m/m": 0.2,
    "Retail Sales m/m": 0.5, "Core Retail Sales m/m": 0.5, "ISM Manufacturing PMI": 2,
    "ISM Services PMI": 2, "Advance GDP q/q": 0.7, "Federal Funds Rate": 0.1,
}

# Kết quả từ BLS: tên tin -> (mã series, cách tính)
BLS = {
    "Non-Farm Employment Change": ("CES0000000001", "diff_k"),
    "Unemployment Rate": ("LNS14000000", "value"),
    "Average Hourly Earnings m/m": ("CES0500000003", "mom"),
    "CPI m/m": ("CUSR0000SA0", "mom"),
    "Core CPI m/m": ("CUSR0000SA0L1E", "mom"),
    "CPI y/y": ("CUUR0000SA0", "yoy"),
    "Core CPI y/y": ("CUUR0000SA0L1E", "yoy"),
    "PPI m/m": ("WPSFD4", "mom"),
    "Core PPI m/m": ("WPSFD49104", "mom"),
}

VN_TZ = timezone(timedelta(hours=7))


def is_speech(title):
    return "Speaks" in title or "Testifies" in title


def vi_name(title):
    if is_speech(title):
        who = title.replace(" Speaks", "").replace(" Testifies", "")
        return f"Phát biểu của {who.replace('Fed Chair', 'Chủ tịch Fed').replace('FOMC Member', 'thành viên FOMC')}"
    return VI.get(title, title)


def parse_num(s):
    """'150K' -> 150.0 ; '0.3%' -> 0.3 ; '-1.2M' -> -1.2 ; '' -> None"""
    if not s:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s.replace(",", ""))
    return float(m.group()) if m else None


def unit_of(s):
    m = re.search(r"[%KMBT]", s or "")
    return m.group() if m else ""


# ---------------------------------------------------------------- lịch

def load_calendar(state, http_get):
    """Lấy lịch tuần (cache 3 giờ trong state để không gọi ForexFactory quá nhiều)."""
    cache = state.get("cal", {})
    if time.time() - cache.get("fetched", 0) > 3 * 3600:
        try:
            data = json.loads(http_get(CAL_URL))
            cache = {"fetched": time.time(),
                     "events": [e for e in data if e.get("country") == "USD" and e.get("impact") == "High"]}
            state["cal"] = cache
        except Exception as e:
            print(f"Lỗi lịch ForexFactory: {e}", file=sys.stderr)
    events = []
    for e in cache.get("events", []):
        try:
            events.append({**e, "t": datetime.fromisoformat(e["date"])})
        except Exception:
            pass
    return sorted(events, key=lambda e: e["t"])


def calendar_lines(state, http_get, hours_ahead=36):
    now = datetime.now(timezone.utc)
    events = [e for e in load_calendar(state, http_get) if now <= e["t"] <= now + timedelta(hours=hours_ahead)]
    if not events:
        return []
    lines = ["\n📅 <b>Lịch tin USD mạnh sắp tới</b> (giờ VN)"]
    for e in events:
        lines.append(f"🔴 {e['t'].astimezone(VN_TZ):%H:%M %d/%m} – {html.escape(vi_name(e['title']))}{fc_text(e)}")
    return lines


def fc_text(e):
    parts = []
    if e.get("forecast"):
        parts.append(f"dự báo {e['forecast']}")
    if e.get("previous"):
        parts.append(f"kỳ trước {e['previous']}")
    return f" <i>({', '.join(parts)})</i>" if parts else ""


# ---------------------------------------------------------------- kết quả thực tế

def bls_actuals(titles, release_t, http_get_post):
    """Trả về {title: 'giá trị'} cho các tin BLS đã có số liệu tháng mới nhất."""
    want = {t: BLS[t] for t in titles if t in BLS}
    if not want:
        return {}
    year = release_t.year
    body = {"seriesid": sorted({s for s, _ in want.values()}),
            "startyear": str(year - 1), "endyear": str(year)}
    key = os.environ.get("BLS_API_KEY")
    url = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
    if key:
        body["registrationkey"] = key
        url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
    data = json.loads(http_get_post(url, json.dumps(body).encode()))
    series = {s["seriesID"]: [p for p in s["data"] if p["period"].startswith("M") and p["period"] != "M13"]
              for s in data.get("Results", {}).get("series", [])}
    # Số liệu công bố là của tháng trước tháng công bố
    ref = release_t.replace(day=1) - timedelta(days=1)
    prev_m = ref.replace(day=1) - timedelta(days=1)
    out = {}
    for title, (sid, how) in want.items():
        # BLS có tháng trống ('-'), nên tra theo (năm, tháng) thay vì theo thứ tự
        vals = {}
        for p in series.get(sid, []):
            try:
                vals[(int(p["year"]), int(p["period"][1:]))] = float(p["value"])
            except ValueError:
                pass
        cur = vals.get((ref.year, ref.month))
        if cur is None:
            continue  # chưa cập nhật số liệu tháng mới
        if how == "value":
            out[title] = f"{cur:.1f}%"
            continue
        base = vals.get((ref.year - 1, ref.month)) if how == "yoy" else vals.get((prev_m.year, prev_m.month))
        if base is None:
            continue
        if how == "diff_k":
            out[title] = f"{cur - base:.0f}K"
        else:
            out[title] = f"{(cur / base - 1) * 100:.1f}%"
    return out


def fed_rate_actual(release_t, http_get):
    """Đọc mức trần lãi suất Fed từ tuyên bố FOMC trên federalreserve.gov."""
    xml = http_get("https://www.federalreserve.gov/feeds/press_monetary.xml")
    for title, link, pub in re.findall(
            r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>.*?<pubDate>(.*?)</pubDate>", xml, re.S):
        if "FOMC statement" not in title:
            continue
        link = re.sub(r"<!\[CDATA\[|\]\]>", "", link).strip()
        pub = re.sub(r"<!\[CDATA\[|\]\]>", "", pub).strip()
        if abs((parsedate_to_datetime(pub) - release_t).total_seconds()) > 3 * 3600:
            continue
        page = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", http_get(link))).replace("–", "-")
        # vd: "raise the target range for the federal funds rate by 1/4 percentage point to 3-3/4 to 4 percent"
        m = re.search(r"target range for the federal funds rate(?: by [\d\-/]+ percentage points?)?"
                      r" (?:at|to) ([\d\-/]+) to ([\d\-/]+) percent", page)
        if not m:
            return None

        def frac(s):
            whole, _, f = s.partition("-")
            if f:
                a, b = f.split("/")
                return float(whole) + float(a) / float(b)
            if "/" in whole:
                a, b = whole.split("/")
                return float(a) / float(b)
            return float(whole)
        return f"{frac(m.group(2)):.2f}%"
    return None


# ---------------------------------------------------------------- phản ứng giá vàng

def gold_reaction(release_t, http_get):
    """(giá trước tin, giá hiện tại, số phút sau tin) từ dữ liệu 1 phút."""
    try:
        d = json.loads(http_get("https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1m&range=1d"))
        r = d["chart"]["result"][0]
        pts = [(ts, c) for ts, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c]
        cut = release_t.timestamp() - 60
        before = [c for ts, c in pts if ts <= cut]
        if not before or not pts:
            return None
        return before[-1], pts[-1][1], (pts[-1][0] - release_t.timestamp()) / 60
    except Exception:
        return None


def reaction_line(rx, expect):
    """expect: +1 kỳ vọng vàng tăng, -1 kỳ vọng vàng giảm, 0 không rõ."""
    if not rx:
        return "💰 Chưa lấy được phản ứng giá vàng."
    b, a, mins = rx
    d = a - b
    pct = d / b * 100
    line = f"💰 Phản ứng vàng: ${b:,.1f} → <b>${a:,.1f}</b> ({d:+,.1f}$, {pct:+.2f}%) sau {mins:.0f} phút"
    if expect and abs(pct) >= 0.05:
        line += " ✅ đúng kịch bản" if (d > 0) == (expect > 0) else " ⚠️ ngược kịch bản (thị trường đã định giá trước hoặc chú ý yếu tố khác)"
    return line


# ---------------------------------------------------------------- phân tích theo quy tắc

def scenario(e):
    t = e["title"]
    if is_speech(t) or t in ("FOMC Statement", "FOMC Press Conference", "FOMC Meeting Minutes",
                             "FOMC Economic Projections"):
        return "Giọng điệu <b>diều hâu</b> (giữ/tăng lãi suất) → USD ↑ → vàng 🔻 · <b>bồ câu</b> (hạ lãi suất) → USD ↓ → vàng 🟢"
    fc = e.get("forecast") or e.get("previous")
    if not fc:
        return ""
    d = -1 if t in INVERSE else 1
    hi, lo = ("vàng 🔻", "vàng 🟢") if d > 0 else ("vàng 🟢", "vàng 🔻")
    return f"&gt; {fc} → USD {'↑' if d > 0 else '↓'} → {hi} · &lt; {fc} → USD {'↓' if d > 0 else '↑'} → {lo}"


def analyse(e, actual):
    """Trả về (dòng phân tích, hướng kỳ vọng cho vàng: +1 tăng / -1 giảm / 0)."""
    t = e["title"]
    ref_s = e.get("forecast") or e.get("previous")
    a, ref = parse_num(actual), parse_num(ref_s)
    if a is None or ref is None:
        return "", 0
    diff = a - ref
    ref_name = "dự báo" if e.get("forecast") else "kỳ trước"
    unit = unit_of(actual)
    if abs(diff) < 1e-9:
        return f"   ➜ Đúng {ref_name} → tác động trung tính, thị trường chú ý chi tiết khác", 0
    usd = (1 if diff > 0 else -1) * (-1 if t in INVERSE else 1)
    big = abs(diff) >= BIG.get(t, float("inf"))
    what = WHY.get(GROUP.get(t, ""), "số liệu")
    if GROUP.get(t) == "infl":
        story = "lạm phát nóng → Fed khó hạ lãi suất" if usd > 0 else "lạm phát hạ nhiệt → tăng khả năng Fed nới lỏng"
    elif GROUP.get(t) == "fed":
        story = "Fed cứng rắn hơn kỳ vọng" if usd > 0 else "Fed mềm mỏng hơn kỳ vọng"
    else:
        story = f"{what} {'tốt' if usd > 0 else 'yếu'} hơn kỳ vọng"
    arrow = "📈 Cao hơn" if diff > 0 else "📉 Thấp hơn"
    gold = "🔻 BẤT LỢI cho vàng" if usd > 0 else "🟢 HỖ TRỢ vàng"
    strength = " — <b>chênh lệch lớn, dễ biến động mạnh</b>" if big else ""
    return (f"   {arrow} {ref_name} {diff:+g}{unit} → {story} → USD {'↑' if usd > 0 else '↓'} → {gold}{strength}",
            -usd)


# ---------------------------------------------------------------- tin nhắn

def pre_alert_msg(t, events, now):
    mins = int((t - now).total_seconds() // 60)
    lines = [f"⏰ <b>SẮP CÓ TIN USD MẠNH</b> · {t.astimezone(VN_TZ):%H:%M %d/%m} (còn ~{mins} phút)\n"]
    for e in events:
        lines.append(f"🔴 <b>{html.escape(vi_name(e['title']))}</b>{fc_text(e)}")
        sc = scenario(e)
        if sc:
            lines.append(f"   📌 {sc}")
    lines.append("\n⚠️ Giá vàng thường biến động mạnh quanh giờ công bố – cẩn trọng khi giao dịch.")
    return "\n".join(lines)


def result_msg(t, events, actuals, rx):
    lines = [f"⚡ <b>KẾT QUẢ TIN USD</b> · {t.astimezone(VN_TZ):%H:%M %d/%m}\n"]
    votes = []
    sources = set()
    for e in events:
        title = e["title"]
        name = html.escape(vi_name(title))
        act = actuals.get(title)
        if act:
            lines.append(f"🔴 {name}: <b>{act}</b>{fc_text(e)}")
            text, vote = analyse(e, act)
            if text:
                lines.append(text)
            votes.append(vote)
            sources.add("Fed" if title == "Federal Funds Rate" else "BLS – Bộ Lao động Mỹ")
        elif e.get("forecast") or e.get("previous"):
            lines.append(f"🔴 {name}{fc_text(e)} – chưa có nguồn số liệu tự động, "
                         f'<a href="{FF_LINK}">xem kết quả</a>')
        else:
            lines.append(f"🔴 {name}")
    up = votes.count(1)
    down = votes.count(-1)
    expect = 1 if up > down else -1 if down > up else 0
    if votes:
        verdict = ("nghiêng HỖ TRỢ vàng 🟢" if expect > 0 else
                   "nghiêng BẤT LỢI cho vàng 🔻" if expect < 0 else "trái chiều / trung tính ⚪")
        lines.append(f"\n📊 <b>Tổng hợp:</b> {verdict}")
    lines.append(reaction_line(rx, expect))
    if not votes and rx:
        b, a, _ = rx
        pct = (a - b) / b * 100
        if abs(pct) >= 0.15:
            lines.append("   ➜ Thị trường đang hiểu tin theo hướng "
                         + ("<b>bồ câu / USD yếu</b> → vàng tăng" if pct > 0 else "<b>diều hâu / USD mạnh</b> → vàng giảm"))
        else:
            lines.append("   ➜ Phản ứng nhỏ – thị trường chưa có hướng rõ ràng")
    if sources:
        lines.append(f"\n<i>Nguồn số liệu: {', '.join(sorted(sources))} · dự báo: ForexFactory</i>")
    return "\n".join(lines)


# ---------------------------------------------------------------- điều phối

def result_delay_min(events):
    """Chờ bao lâu sau giờ công bố thì gửi kết quả/phản ứng."""
    titles = [e["title"] for e in events]
    if any(t in BLS or t == "Federal Funds Rate" for t in titles):
        return 3
    if any("Press Conference" in t for t in titles):
        return 45
    if any(is_speech(t) for t in titles):
        return 30
    return 10


def run(state, send, http_get, http_get_post, wait_limit_min=40):
    """Gọi trong mỗi lần quét tin. Có thể chờ (sleep) nếu sắp tới giờ công bố."""
    usd = state.setdefault("usd", {})
    events = load_calendar(state, http_get)
    groups = {}
    for e in events:
        groups.setdefault(e["t"], []).append(e)

    for t, evs in sorted(groups.items()):
        gid = t.isoformat()
        rec = usd.setdefault(gid, {})
        now = datetime.now(timezone.utc)

        # 1) Nhắc trước giờ công bố (trong vòng 90 phút tới)
        if not rec.get("pre") and now < t <= now + timedelta(minutes=90):
            rec["pre"] = int(time.time())
            send(pre_alert_msg(t, evs, now))

        # 2) Kết quả + phân tích
        if rec.get("done"):
            continue
        due = t + timedelta(minutes=result_delay_min(evs))
        if now > t + timedelta(hours=3):
            rec["done"] = int(time.time())  # quá cũ, bỏ qua
            continue
        if due > now + timedelta(minutes=wait_limit_min):
            continue  # còn lâu, để lần quét sau
        wait = (due - now).total_seconds()
        if wait > 0:
            print(f"Chờ {wait / 60:.1f} phút tới giờ công bố {t.astimezone(VN_TZ):%H:%M}…")
            time.sleep(wait)

        actuals = {}
        need = [e["title"] for e in evs if e["title"] in BLS or e["title"] == "Federal Funds Rate"]
        deadline = t + timedelta(minutes=25)
        while need:
            try:
                actuals.update(bls_actuals(need, t, http_get_post))
            except Exception as ex:
                print(f"Lỗi BLS: {ex}", file=sys.stderr)
            if "Federal Funds Rate" in need and "Federal Funds Rate" not in actuals:
                try:
                    r = fed_rate_actual(t, http_get)
                    if r:
                        actuals["Federal Funds Rate"] = r
                except Exception as ex:
                    print(f"Lỗi Fed: {ex}", file=sys.stderr)
            if all(n in actuals for n in need) or datetime.now(timezone.utc) > deadline:
                break
            time.sleep(90)
        # đợi thêm cho giá vàng kịp phản ứng (ít nhất 5 phút sau tin)
        settle = (t + timedelta(minutes=5) - datetime.now(timezone.utc)).total_seconds()
        if settle > 0:
            time.sleep(settle)
        rec["done"] = int(time.time())
        send(result_msg(t, evs, actuals, gold_reaction(t, http_get)))

    # Dọn bản ghi cũ hơn 8 ngày
    cutoff = datetime.now(timezone.utc) - timedelta(days=8)
    for gid in list(usd):
        try:
            if datetime.fromisoformat(gid) < cutoff:
                del usd[gid]
        except Exception:
            del usd[gid]
