# Garena Phone Recovery Tool v3

Tool để lấy số điện thoại đầy đủ của tài khoản Garena thông qua 3 phases:

## 📋 Các Phase

### Phase 1: Garena Login & Lấy 4 số cuối
- Đăng nhập vào account.garena.com
- Tìm số điện thoại bị mask: "+84 ****7287"
- Trích xuất 4 số cuối: "7287"

### Phase 2: napthe.vn API & Lấy 3 số đầu  
- Đăng nhập vào napthe.vn
- Gọi API để lấy thông tin user
- Tìm field "display_mobile_no": "+84 94*****87"
- Trích xuất 3 số đầu: "094"

### Phase 3: Brute-force & Tìm số hoàn chỉnh
- Vào trang recovery
- Test số điện thoại: 094000-7287 → 094999-7287 (1000 lần)
- Khi đúng, hệ thống sẽ hiện "Nhận mã" → lấy được số đầy đủ

## 🚀 Cách chạy

### Chuẩn bị
```bash
pip install playwright aiofiles
playwright install chromium
```

### Tạo file input

**accounts.txt** (danh sách tài khoản):
```
username1:password1
username2:password2
```

### Chạy Tool (có proxy)
```bash
python garena_recovery_fixed.py \
  -i accounts.txt \
  -o result \
  --napthe-user your_napthe_username \
  --napthe-pass your_napthe_password \
  --proxy-list proxy.txt \
  --delay 25 \
  --phase-delay 5 \
  --phase3-delay 3
```

## 📊 Output

### result.json - Chi tiết đầy đủ
### result.txt - Tóm tắt nhanh

## ⚙️ Tham số

- `--delay`: Độ trễ giữa các account (giây)
- `--phase-delay`: Độ trễ giữa các phase (giây)
- `--phase3-delay`: Độ trễ giữa mỗi lần brute-force (giây)
- `--concurrency`: Số worker (1 khuyên dùng)
- `--timeout`: Timeout cho browser (ms)
