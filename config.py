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
    # Yếu tố vĩ mô tác động giá vàng: Fed/lãi suất, USD, lạm phát, việc làm Mỹ, địa chính trị
    ("🏦 Vĩ mô", f'(Fed OR "Federal Reserve" OR "rate cut" OR "rate hike" OR "interest rates") {_sites(["reuters.com", "bloomberg.com", "cnbc.com", "wsj.com", "ft.com"])}', "en"),
    ("🏦 Vĩ mô", f'(inflation OR CPI OR PCE OR payrolls OR "jobs report" OR "Treasury yields" OR "dollar index") {_sites(["reuters.com", "bloomberg.com", "cnbc.com", "wsj.com"])}', "en"),
    ("🏦 Vĩ mô", f'("safe haven" OR "central bank" OR geopolitical OR sanctions OR escalation) {_sites(["reuters.com", "bloomberg.com", "ft.com"])}', "en"),
    ("🏦 Vĩ mô", f'("Fed" OR "lãi suất" OR "tỷ giá" OR "đồng USD" OR "lạm phát Mỹ") {_sites(VN_SITES)}', "vi"),
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
    "🏦 Vĩ mô": ["fed", "federal reserve", "powell", "warsh", "fomc", "rate cut", "rate cuts",
                "rate hike", "rate hikes", "interest rates", "inflation", "cpi", "pce", "payrolls",
                "jobs report", "treasury yields", "yields", "dollar", "safe haven", "central bank",
                # Tiếng Việt: chỉ nhận tin về Fed/USD/tỷ giá, bỏ tin lãi suất cho vay trong nước
                "tỷ giá", "đồng usd", "đô la mỹ", "lạm phát mỹ", "ngân hàng trung ương"],
    "☕ Cà phê": ["coffee", "arabica", "robusta", "giá cà phê", "xuất khẩu cà phê",
                 "cà phê nhân", "niên vụ", "thị trường cà phê", "ngành cà phê", "tt cà phê"],
}

# Bỏ tin có tiêu đề chứa các từ này (tin không liên quan)
EXCLUDE_KEYWORDS = [
    "golden state", "gold medal", "huy chương vàng", "goldman", "golden globe",
    "quả bóng vàng", "giờ vàng", "coffee shop", "starbucks", "tuần lễ vàng",
    "live gold prices", "| kitco",  # trang bảng giá, không phải bài báo
    "coffee tasting", "barista",
]
