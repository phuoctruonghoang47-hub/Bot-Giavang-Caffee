# Bot Telegram – Giá vàng & Cà phê

Tự động gửi vào Channel Telegram:

| Việc | Lịch (giờ VN) | Nội dung |
|---|---|---|
| **Bản tin giá** | 8:30 · 11:30 · 16:30 | Vàng thế giới (COMEX) + quy đổi VNĐ, vàng miếng/nhẫn SJC, nhẫn PNJ, chênh lệch SJC – thế giới, cà phê nhân Tây Nguyên |
| **Tin mới** | mỗi 30 phút | Tin vàng & cà phê từ Reuters, Bloomberg, WSJ, FT, CNBC, Kitco, StoneX, Barchart, VnExpress, VnEconomy, Thanh Niên, Tuổi Trẻ, VOV, Vinanet… |
| **Cảnh báo** | mỗi 30 phút | Vàng thế giới biến động ≥ 1% |

Không cần server, không tốn phí – chạy trên GitHub Actions.

---

## Bước 1 – Tạo bot Telegram

1. Mở Telegram, tìm **@BotFather** → gõ `/newbot`.
2. Đặt tên và username (phải kết thúc bằng `bot`, ví dụ `GiaVangCaPheVN_bot`).
3. BotFather trả về **token** dạng `123456789:ABC...` → lưu lại, **không chia sẻ cho ai**.

## Bước 2 – Thêm bot vào Channel

1. Tạo Channel (nếu chưa có).
2. Vào Channel → **Quản trị viên (Administrators)** → **Thêm quản trị viên** → tìm username bot → cho quyền **Đăng tin (Post messages)**.
3. **Chat ID** của kênh:
   - Kênh công khai: dùng `@username_kenh` (ví dụ `@giavangcaphe`).
   - Kênh riêng tư: chuyển tiếp 1 tin trong kênh cho **@userinfobot** / **@RawDataBot** để lấy ID dạng `-100xxxxxxxxxx`.

## Bước 3 – (Tuỳ chọn) Chạy thử trên máy

```bash
copy .env.example .env
```
Mở `.env`, điền token và chat ID, rồi:
```bash
python bot.py test
```
Kênh nhận tin “✅ Bot đã kết nối thành công” là OK. Xem trước nội dung mà không gửi:
```bash
python bot.py prices --dry-run
```

## Bước 4 – Đưa lên GitHub

1. Đăng nhập https://github.com → **New repository** → đặt tên (ví dụ `bot-gia-vang`) → chọn **Public** → **Create**.
   > Public: GitHub Actions miễn phí không giới hạn. Token vẫn an toàn vì nằm trong *Secrets*, không nằm trong code.
   > Nếu chọn Private: bản miễn phí có 2.000 phút/tháng – nên đổi `*/30` thành `0 * * * *` (mỗi giờ) trong `bot.yml`.
2. Trong repo mới: **Add file → Upload files** → kéo thả **toàn bộ** thư mục này (gồm cả thư mục `.github`) → **Commit changes**.
   - Không upload file `.env`.
   - Nếu thư mục `.github` không lên được: **Add file → Create new file**, gõ tên `.github/workflows/bot.yml`, dán nội dung file `bot.yml` vào → Commit.
3. **Settings → Secrets and variables → Actions → New repository secret**, tạo 2 secret:
   - `TELEGRAM_BOT_TOKEN` = token ở bước 1
   - `TELEGRAM_CHAT_ID` = chat ID ở bước 2
4. **Settings → Actions → General → Workflow permissions** → chọn **Read and write permissions** → Save.
5. Tab **Actions** → chọn workflow “Bot giá vàng & cà phê” → **Run workflow** → chọn `test` → Run. Sau đó chạy `prices` và `news` để kiểm tra.

Xong! Từ giờ bot tự chạy theo lịch.

---

## Tuỳ chỉnh (file `config.py`)

- `NEWS_QUERIES` – thêm/bớt chủ đề tìm tin.
- `TRUSTED_SOURCES` – danh sách nguồn được chấp nhận.
- `EXCLUDE_KEYWORDS` – loại tin rác.
- `GOLD_ALERT_PCT` – ngưỡng cảnh báo (%).
- `NEWS_MAX_PER_RUN` – số tin tối đa mỗi lần.

Đổi giờ gửi: sửa dòng `cron` trong `.github/workflows/bot.yml` (giờ **UTC** = giờ VN − 7). Nếu đổi lịch bản tin giá, sửa cả chuỗi so sánh `"30 1,4,9 * * *"` ở bên dưới cho khớp.

## Lưu ý

- GitHub có thể chạy lịch trễ 5–20 phút vào giờ cao điểm.
- Bot lưu trạng thái (tin đã gửi, giá lần trước) vào `state/state.json` – tự commit sau mỗi lần chạy.
- Giá cà phê là **giá trung bình Tây Nguyên** do giacaphe.com công bố (trang này không cho lấy bảng giá từng tỉnh tự động) – tin nhắn có link xem chi tiết theo tỉnh.
- Nếu một nguồn giá lỗi (đổi giao diện/API), bot vẫn gửi phần còn lại; xem log ở tab **Actions**.
