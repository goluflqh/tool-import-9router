# 9router Import Tool

Version: 1.0.1

Tool web local để quản lý Codex OAuth accounts cho 9router và CLIProxyAPI.

## Chạy tool

Windows:

```bat
khoi_dong_o_day.bat
```

Hoặc:

```bash
python server.py
```

Mở UI tại:

```text
http://127.0.0.1:9876
```

## Luồng dùng chính

1. Dùng 9router làm nguồn chính.
2. Import session JSON vào 9router.
3. Nếu JSON hiện `access only`, tool sẽ tự tìm refresh token theo email từ:
   - account cũ đã có trong 9router
   - CLIProxy runtime-auths
   - `~/.codex/auth.json`
4. Nếu preview hiện `fill: 9router`, `fill: cliproxy`, hoặc `fill: codex-auth`, khi import vào 9router account đó sẽ được bổ sung refresh token.
5. Chỉ khi preview vẫn hiện `access only` sau khi server online thì account đó không có refresh token trong các nguồn local.
6. Sau khi 9router đã `refresh OK`, dùng `Ghi sang CLIProxy` nếu cần đồng bộ sang CLIProxy.

Refresh token không thể suy ra từ access token. Nó phải đến từ OAuth/offline access hoặc một local store đã có sẵn.

## Account free

Account free vẫn add được nếu access token hợp lệ. Tool lưu và refresh token giống các gói khác.

Giới hạn nằm ở quyền của account: account free có thể không gọi được một số model hoặc bị limit thấp hơn plus/team/pro. Tool không nâng quyền gói, nó chỉ quản lý token an toàn hơn.

## Các nút trong UI

- `Refresh`: tải lại danh sách hiện tại.
- `Sửa cấu hình`: sửa alias `gpt-5.5 -> cx/gpt-5.5` trong 9router và sửa Codex config. Dùng khi Codex lỗi model/provider.
- `Nạp từ CLIProxy`: lấy auth file trong `D:\CLIProxyAPI\runtime-auths` nạp vào 9router. Dùng khi CLIProxy có refresh token/account mà 9router thiếu.
- `Nạp từ Codex`: lấy token trong `~/.codex/auth.json` nạp vào 9router. Dùng khi Codex Desktop/CLI đang đăng nhập tốt và cần đưa token đó vào 9router.
- `Ghi sang CLIProxy`: ghi account từ 9router sang CLIProxy runtime-auths. Dùng sau khi 9router đã `refresh OK`.
- `Export JSON`: xuất JSON có token để backup/di chuyển thủ công trên máy của bạn. Không chia sẻ file này.
- `Cách ly file cũ`: trong tab CLIProxy, đưa auth file không còn có trong 9router ra folder quarantine/backup để CLIProxy không dùng nhầm.

## Bảo mật

- Không commit `backups/`, `runtime-auths`, `.bak`, `__pycache__`, hoặc file JSON export có token.
- Tool chỉ bind local `127.0.0.1:9876`.
- API CORS chỉ cho localhost/127.0.0.1 cùng port.

## Version

- `v1.0.1`: chỉnh UI tiếng Việt có dấu, làm rõ account free, và giữ wording đơn giản hơn.
- `v1.0.0`: recovery build đầu tiên có 9router là nguồn chính, hydrate refresh token từ 9router/CLIProxy/Codex auth, sync CLIProxy, repair alias/config, và UI preview `fill: ...`.
