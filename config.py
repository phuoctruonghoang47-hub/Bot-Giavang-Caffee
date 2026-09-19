"""Cấu hình bot: nguồn tin, từ khoá, ngưỡng cảnh báo. Sửa file này để tuỳ chỉnh."""

# Chỉ lấy tin trong khoảng này (giờ)
NEWS_MAX_AGE_HOURS = 24

# Số tin tối đa gửi mỗi lần quét (tránh spam kênh)
NEWS_MAX_PER_RUN = 8

# Cảnh báo khi vàng thế giới biến động >= X% so với lần cảnh báo trước
GOLD_ALERT_PCT = 1.0

# Nguồn quốc tế dùng cho tin vàng (lọc bằng site:)
INTL_SITES = [
    "reuters.com", "bloomberg.com", "cnbc.com", "ft.com", "wsj.com",
    "kitco.com", "marketwatch.com",
]
VN_SITES = [
    "vnexpress.net", "cafef.vn", "vneconomy.vn", "tuoitre.vn",
    "thanhnien.vn", "vietnamplus.vn", "baochinhphu.vn", "congthuong.vn",
]


def _sites(sites):
    return "(" + " OR ".join(f"site:{s}" for s in sites) + ")"


# Mỗi truy vấn: (nhãn, câu truy vấn Google News, ngôn ngữ)
NEWS_QUERIES = [
    ("🥇 Vàng", f'(gold price OR bullion OR "gold prices") {_sites(INTL_SITES)}', "en"),
    ("🥇 Vàng", f'("Fed" OR "Federal Reserve" OR "US dollar" OR inflation) gold {_sites(INTL_SITES)}', "en"),
    ("🥇 Vàng", f'("giá vàng" OR "vàng miếng" OR "vàng nhẫn" OR "SJC") {_sites(VN_SITES)}', "vi"),
    # Yếu tố vĩ mô tác động giá vàng: Fed, số liệu kinh tế Mỹ (CPI, Nonfarm...), USD, địa chính trị
    ("🏦 Vĩ mô", f'(Fed OR "Federal Reserve" OR FOMC OR Powell OR Warsh OR "rate cut" OR "rate hike") {_sites(["reuters.com", "bloomberg.com", "cnbc.com", "wsj.com", "ft.com"])}', "en"),
    ("🏦 Vĩ mô", f'(nonfarm OR payrolls OR "jobs report" OR unemployment OR "jobless claims") {_sites(["reuters.com", "bloomberg.com", "cnbc.com", "wsj.com"])}', "en"),
    ("🏦 Vĩ mô", f'(CPI OR PCE OR PPI OR "consumer prices" OR "inflation data" OR "US inflation" OR GDP OR "retail sales") {_sites(["reuters.com", "bloomberg.com", "cnbc.com", "wsj.com"])}', "en"),
    ("🏦 Vĩ mô", f'("dollar index" OR "Treasury yields" OR "safe haven" OR "central bank" OR geopolitical OR sanctions) {_sites(["reuters.com", "bloomberg.com", "ft.com"])}', "en"),
    ("🏦 Vĩ mô", f'("Fed" OR "phi nông nghiệp" OR "CPI Mỹ" OR "lạm phát Mỹ" OR "đồng USD" OR "tỷ giá") {_sites(VN_SITES)}', "vi"),
    ("☕ Cà phê", "coffee futures", "en"),
    ("☕ Cà phê", "arabica robusta coffee prices", "en"),
    ("☕ Cà phê", "coffee (site:reuters.com OR site:bloomberg.com)", "en"),
    ("☕ Cà phê", '"giá cà phê"', "vi"),
    ("☕ Cà phê", '"xuất khẩu cà phê" OR "thị trường cà phê"', "vi"),
]

# Chỉ nhận tin từ các nguồn này (so khớp một phần tên nguồn, không phân biệt hoa thường)
TRUSTED_SOURCES = [
    # Quốc tế
    "reuters", "bloomberg", "cnbc", "wsj", "wall street journal", "financial times",
    "kitco", "marketwatch", "barchart", "nasdaq", "stonex", "tradingview",
    # Việt Nam
    "vnexpress", "cafef", "vneconomy", "tuổi trẻ", "thanh niên", "vietnamplus",
    "chính phủ", "công thương", "vov", "lao động", "laodong", "vinanet",
    "thế giới và việt nam", "nông nghiệp", "nhân dân", "vtv", "gia lai", "đắk lắk",
]

# Tin phải chứa ít nhất một từ khoá này trong tiêu đề (không phân biệt hoa thường)
REQUIRED_KEYWORDS = {
    "🥇 Vàng": ["gold", "bullion", "vàng", "sjc"],
    # Chỉ tin liên quan Mỹ: Fed, số liệu kinh tế Mỹ, USD, lợi suất trái phiếu Mỹ
    "🏦 Vĩ mô": ["fed", "federal reserve", "powell", "warsh", "fomc", "nonfarm", "non-farm",
                "payrolls", "jobs report", "jobless claims", "us unemployment", "u.s. unemployment",
                "cpi", "pce", "ppi", "us inflation", "u.s. inflation", "us gdp", "u.s. gdp",
                "us retail sales", "u.s. retail sales", "treasury yields", "dollar", "safe haven",
                # Tiếng Việt: chỉ nhận tin về Fed/USD/số liệu Mỹ, bỏ tin lãi suất cho vay trong nước
                "phi nông nghiệp", "cpi mỹ", "lạm phát mỹ", "tỷ giá", "đồng usd", "đô la mỹ",
                "ngân hàng trung ương"],
    "☕ Cà phê": ["coffee", "arabica", "robusta", "giá cà phê", "xuất khẩu cà phê",
                 "cà phê nhân", "niên vụ", "thị trường cà phê", "ngành cà phê", "tt cà phê"],
}

# Bỏ tin có tiêu đề chứa các từ này (tin không liên quan)
EXCLUDE_KEYWORDS = [
    "golden state", "gold medal", "huy chương vàng", "goldman", "golden globe",
    "quả bóng vàng", "giờ vàng", "coffee shop", "starbucks", "tuần lễ vàng",
    "live gold prices", "| kitco",  # trang bảng giá, không phải bài báo
    "coffee tasting", "barista",
    # tin tổng hợp chứng khoán, không phải tin vĩ mô
    "stock futures", "equity fund", "wall st set", "wall street set", "stocks set to",
]

# Loại riêng cho nhóm Vĩ mô: tin nước khác, tin chứng khoán, bình luận/talkshow
LABEL_EXCLUDE = {
    "🏦 Vĩ mô": [
        "bank of england", "boe", "boj", "bank of japan", "ecb", "rba", "sterling", "yen",
        "rand", "u.k.", "uk", "britain", "british", "japan", "australia", "hungary", "india",
        "russia", "russian", "latam", "europe", "european", "china", "canada",
        "stocks", "stock", "equities", "ipo", "jim cramer", "the club", "live q&a", "investors can",
        "chứng khoán", "ví bạn",
    ],
}

# Tin quan trọng nhất với vàng -> gắn 🔥 và ưu tiên gửi trước
HIGH_IMPACT_KEYWORDS = [
    "fomc", "fed decision", "rate decision", "fed raises", "fed hikes", "fed cuts",
    "fed holds", "fed keeps", "fed minutes", "nonfarm", "non-farm", "payrolls", "jobs report",
    "cpi", "pce", "consumer prices", "phi nông nghiệp", "cpi mỹ",
    "fed tăng lãi suất", "fed giảm lãi suất", "fed giữ nguyên",
]

# Số tin tối đa mỗi nhóm trong một lần gửi (tin còn lại để lần quét sau)
NEWS_MAX_PER_LABEL = {"🏦 Vĩ mô": 4, "🥇 Vàng": 4, "☕ Cà phê": 4}
