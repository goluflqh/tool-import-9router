# 9router Import Tool

Version: 1.0.5

Tool web local để quản lý Codex OAuth accounts cho 9router và CLIProxyAPI.

## Chạy tool local

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

## Dùng cho 9router trên VPS

Không dùng tool local để sửa database VPS. Local và VPS nên là 2 instance riêng.

Chạy tool ngay trên VPS, trỏ vào SQLite của 9router VPS:

```bash
cd ~/tool-import-9router
export IMPORT9ROUTER_INSTANCE=9router-vps
export IMPORT9ROUTER_NO_BROWSER=1
export IMPORT9ROUTER_DB_PATH=/path/to/9router/db/data.sqlite
python3 server.py
```

Nếu 9router VPS dùng đúng path mặc định Linux `~/.config/9router/db/data.sqlite`, có thể bỏ `IMPORT9ROUTER_DB_PATH`.

Tunnel tool bằng port khác để không đụng tool local:

```bash
ssh -N -L 127.0.0.1:9877:127.0.0.1:9876 deploy@165.22.247.29
```

Mở:

```text
http://127.0.0.1:9877
```

Dashboard 9router VPS của bạn vẫn có thể giữ tunnel riêng:

```bash
ssh -N -L 127.0.0.1:22129:172.17.0.1:20128 deploy@165.22.247.29
```

Quy tắc tránh xung đột:

- Tool local chỉ dùng cho 9router local.
- Tool VPS chỉ dùng cho 9router VPS.
- Nhìn dòng trạng thái `Server đang chạy — ...` để biết đang ở instance nào.
- Không bấm `Ghi sang CLIProxy` trên VPS nếu VPS không có CLIProxy runtime-auths mà bạn muốn quản lý.
- Nếu re-OAuth trong dashboard VPS, bấm `Refresh` trong tool VPS để đọc lại SQLite.

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

Import từ file JSON cũng dùng cùng backend với import tay, nên vẫn tự bổ sung refresh token theo email nếu nguồn local đã có.

Di chuyển vài account từ local sang VPS:

1. Mở tool local, tab `Tài khoản hiện có`.
2. Tick đúng account cần chuyển.
3. Bấm `Export đã chọn`.
4. Mở tool VPS, tab `Import từ file`.
5. Chọn file vừa export, bỏ tick account nào không muốn import, rồi bấm `Import vào 9router`.

Refresh token không thể suy ra từ access token. Nó phải đến từ OAuth/offline access hoặc một local store đã có sẵn.

## Account free

Account free vẫn add được nếu access token hợp lệ. Tool lưu và refresh token giống các gói khác.

Giới hạn nằm ở quyền của account: account free có thể không gọi được một số model hoặc bị limit thấp hơn plus/team/pro. Tool không nâng quyền gói, nó chỉ quản lý token an toàn hơn.

## Các nút trong UI

- `Refresh`: tải lại danh sách hiện tại.
- `Lọc trùng email`: giữ lại một dòng tốt nhất cho mỗi email trong 9router, backup SQLite trước khi xóa dòng trùng.
- `Sửa cấu hình`: sửa alias `gpt-5.5 -> cx/gpt-5.5` trong 9router và sửa Codex config. Dùng khi Codex lỗi model/provider.
- `Nạp từ CLIProxy`: lấy auth file trong `D:\CLIProxyAPI\runtime-auths` nạp vào 9router. Dùng khi CLIProxy có refresh token/account mà 9router thiếu.
- `Nạp từ Codex`: lấy token trong `~/.codex/auth.json` nạp vào 9router. Dùng khi Codex Desktop/CLI đang đăng nhập tốt và cần đưa token đó vào 9router.
- `Ghi sang CLIProxy`: ghi account từ 9router sang CLIProxy runtime-auths. Dùng sau khi 9router đã `refresh OK`.
- `Export JSON`: xuất JSON có token để backup/di chuyển thủ công trên máy của bạn. Không chia sẻ file này.
- `Export đã chọn`: xuất JSON có token cho các account đã tick, tiện khi chỉ muốn đưa vài account sang VPS/local khác.
- `Chọn tất cả` / `Bỏ chọn`: chọn nhanh account trong bảng hiện tại hoặc trong file import.
- `Cách ly file cũ`: trong tab CLIProxy, đưa auth file không còn có trong 9router ra folder quarantine/backup để CLIProxy không dùng nhầm.

## Bảo mật

- Không commit `backups/`, `runtime-auths`, `.bak`, `__pycache__`, hoặc file JSON export có token.
- Tool chỉ bind local `127.0.0.1`.
- API CORS chỉ cho Origin từ localhost/127.0.0.1/::1 để hỗ trợ SSH tunnel port riêng.
- Tool có guard kiểm tra bảng `apiKeys` của 9router trước/sau các thao tác ghi SQLite. Guard chỉ báo hash rút gọn, không lộ API key, và sẽ cảnh báo nếu API key bị rỗng/thay đổi.

## Version

- `v1.0.5`: thêm guard bảo vệ/cảnh báo API key 9router để tránh nhầm tool import với lỗi mất key 401 của app khác.
- `v1.0.4`: thêm checkbox chọn account, `Export đã chọn`, và chọn dòng khi import file JSON để chuyển đúng vài account giữa local/VPS.
- `v1.0.3`: thêm chế độ instance cho VPS/local, custom SQLite path qua env, tunnel port riêng, và tùy chọn không auto-open browser.
- `v1.0.2`: thêm lọc trùng email trong 9router và preview hydrate refresh cho import từ file JSON.
- `v1.0.1`: chỉnh UI tiếng Việt có dấu, làm rõ account free, và giữ wording đơn giản hơn.
- `v1.0.0`: recovery build đầu tiên có 9router là nguồn chính, hydrate refresh token từ 9router/CLIProxy/Codex auth, sync CLIProxy, repair alias/config, và UI preview `fill: ...`.
