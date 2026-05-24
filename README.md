# 9router Import Tool

Công cụ web local để quản lý Codex OAuth accounts cho 9router và đồng bộ sang CLIProxyAPI khi cần.

Phiên bản hiện tại: `v1.0.6`

## Tổng Quan

Tool này giữ **9router là nguồn chính** cho tài khoản Codex:

- Import Codex OAuth session vào 9router.
- Giữ lại hoặc tự bổ sung refresh token khi dữ liệu import chỉ có access token.
- Lọc trùng email trong 9router, có backup SQLite trước khi xóa.
- Export đúng vài account đã chọn để chuyển giữa local và VPS.
- Ghi account hợp lệ từ 9router sang CLIProxyAPI runtime auths.
- Cảnh báo nếu API key của 9router bị rỗng hoặc thay đổi trong lúc tool ghi database.

Tool dùng cho môi trường cá nhân/local. Nó không nâng quyền account, không tạo refresh token từ access token, và không dùng để vượt quota.

## Chạy Local

Chạy trong thư mục tool trên Windows:

```bat
khoi_dong_o_day.bat
```

Hoặc chạy trực tiếp:

```bash
python server.py
```

Mở UI:

```text
http://127.0.0.1:9876
```

Tool local tự dò database 9router tại:

```text
C:\Users\lequa\AppData\Roaming\9router\db\data.sqlite
```

## Chạy Trên VPS

Local và VPS là 2 instance riêng. Không dùng tool local để sửa database VPS.

Trên VPS, chạy tool với đúng database 9router VPS:

```bash
cd ~/tool-import-9router
export IMPORT9ROUTER_INSTANCE=9router-vps
export IMPORT9ROUTER_NO_BROWSER=1
export IMPORT9ROUTER_DB_PATH=/home/deploy/.9router/db/data.sqlite
python3 server.py
```

Từ Windows, dùng alias PowerShell quen thuộc:

```powershell
9router-vps
```

Các link cần dùng:

| Mục đích | Link |
| --- | --- |
| Dashboard 9router VPS | `http://127.0.0.1:22129/dashboard/providers` |
| Tool import VPS | `http://127.0.0.1:9877` |

Nếu alias lỗi thì mới debug tunnel thủ công. Workflow mặc định vẫn là `9router-vps`.

## Luồng Dùng Chính

1. Dùng 9router làm nguồn chính.
2. Import session JSON vào 9router.
3. Nếu preview hiện `access only`, tool sẽ tìm refresh token theo email/name từ:
   - account cũ trong 9router
   - CLIProxy runtime auths
   - `~/.codex/auth.json`
4. Nếu preview hiện `fill: 9router`, `fill: cliproxy`, hoặc `fill: codex-auth`, khi import account đó sẽ được bổ sung refresh token.
5. Nếu vẫn là `access only`, nghĩa là chưa có nguồn refresh token local cho account đó.
6. Sau khi 9router đã refresh OK, dùng `Ghi sang CLIProxy` nếu cần đồng bộ sang CLIProxy.

Refresh token không thể suy ra từ access token. Nó phải có sẵn từ OAuth/offline access hoặc một local auth store hợp lệ.

## Chuyển Account Local Sang VPS

Dùng luồng chọn account để tránh copy nhầm toàn bộ local database lên VPS.

1. Mở tool local.
2. Vào tab `Tài khoản hiện có`.
3. Tick đúng account cần chuyển.
4. Bấm `Export đã chọn`.
5. Mở tool VPS bằng `9router-vps`.
6. Vào tab `Import từ file`.
7. Chọn file JSON vừa export.
8. Bỏ tick account không muốn import.
9. Bấm `Import vào 9router`.

## Các Nút Quan Trọng

| Nút | Khi Nào Dùng | Ghi Chú |
| --- | --- | --- |
| `Refresh` | Cần tải lại trạng thái hiện tại. | Chỉ đọc dữ liệu, an toàn. |
| `Import vào 9router` | Có session JSON cần nạp vào 9router. | Giữ refresh token cũ nếu account đã tồn tại. |
| `Lọc trùng email` | Một email xuất hiện nhiều dòng. | Backup SQLite trước khi xóa dòng trùng. |
| `Sửa cấu hình` | Codex lỗi model/provider. | Sửa alias `gpt-5.5 -> cx/gpt-5.5` và Codex config. |
| `Nạp từ CLIProxy` | CLIProxy có account/refresh token mà 9router thiếu. | Chỉ dùng khi thật sự cần recovery từ CLIProxy. |
| `Nạp từ Codex` | Codex Desktop/CLI đang đăng nhập tốt. | Đọc `~/.codex/auth.json`. |
| `Ghi sang CLIProxy` | 9router đã ổn và muốn CLIProxy dùng cùng account. | Backup runtime auths trước khi ghi. |
| `Export JSON` | Cần backup hoặc chuyển thủ công. | File có token, phải giữ riêng tư. |
| `Export đã chọn` | Chỉ muốn chuyển vài account. | Nên dùng cho local -> VPS. |
| `Cách ly file cũ` | CLIProxy còn file auth stale. | Chuyển vào quarantine/backup, không xóa vĩnh viễn. |

## Account Free

Account free vẫn add được nếu token hợp lệ. Tool lưu và refresh token giống các gói khác.

Giới hạn model/quota vẫn phụ thuộc quyền của account. Tool không nâng cấp gói và không thay đổi giới hạn từ nhà cung cấp.

## An Toàn Và Bảo Mật

- Server chỉ bind `127.0.0.1`.
- CORS chỉ cho localhost origins.
- Các thao tác ghi quan trọng đều backup SQLite hoặc runtime auths trước.
- Status/API thông thường không in token.
- File JSON export có thể chứa secret, không chia sẻ và không commit.
- API key guard kiểm tra bảng `apiKeys` của 9router trước/sau khi ghi DB. Guard chỉ báo metadata/hash rút gọn, không lộ API key thật.

## Lịch Sử Phiên Bản

| Phiên bản | Thay đổi chính |
| --- | --- |
| `v1.0.6` | Làm lại README GitHub thành hướng dẫn Markdown gọn, rõ, chuyên nghiệp hơn. |
| `v1.0.5` | Thêm guard cảnh báo API key 9router khi import/repair/dedupe. |
| `v1.0.4` | Thêm chọn account, `Export đã chọn`, và import file có tick chọn từng dòng. |
| `v1.0.3` | Thêm chế độ local/VPS, custom SQLite path, no-browser mode và tunnel-friendly ports. |
| `v1.0.2` | Thêm lọc trùng email và preview hydrate refresh cho import file. |
| `v1.0.1` | Làm rõ UI tiếng Việt, account free và wording dễ hiểu hơn. |
| `v1.0.0` | Bản recovery đầu tiên: 9router-first import, hydrate refresh, sync CLIProxy, repair alias/config. |
