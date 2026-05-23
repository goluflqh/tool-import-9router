# 9router Import Tool

Version: 1.0.0

Local web tool de quan ly Codex OAuth accounts cho 9router va CLIProxyAPI.

## Chay tool

Windows:

```bat
khoi_dong_o_day.bat
```

Hoac:

```bash
python server.py
```

Mo UI tai:

```text
http://127.0.0.1:9876
```

## Luong dung chinh

1. Dung 9router lam nguon chinh.
2. Import session JSON vao 9router.
3. Neu JSON hien `access only`, tool se tu tim refresh token theo email tu:
   - account cu da co trong 9router
   - CLIProxy runtime-auths
   - `~/.codex/auth.json`
4. Neu preview hien `fill: 9router`, `fill: cliproxy`, hoac `fill: codex-auth` thi khi import vao 9router no se duoc bo sung refresh token.
5. Chi khi preview van hien `access only` sau khi server online thi account do khong co refresh token trong cac nguon local.
6. Sau khi 9router da `refresh OK`, dung `Ghi 9router -> CLIProxy` neu can dong bo sang CLIProxy.

Refresh token khong the suy ra tu access token. No phai den tu OAuth/offline access hoac mot local store da co san.

## Cac nut trong UI

- `Refresh`: tai lai danh sach hien tai.
- `Sua alias/config`: sua alias `gpt-5.5 -> cx/gpt-5.5` trong 9router va sua Codex config dung provider router9/cliproxy. Dung khi Codex loi model/provider.
- `Nap CLIProxy -> 9router`: lay cac auth file trong `D:\CLIProxyAPI\runtime-auths` nap vao 9router. Dung khi CLIProxy co refresh token/account ma 9router thieu.
- `Nap Codex auth -> 9router`: lay token trong `~/.codex/auth.json` nap vao 9router. Dung khi Codex Desktop/CLI dang login tot va can dua token do vao 9router.
- `Ghi 9router -> CLIProxy`: ghi account tu 9router sang CLIProxy runtime-auths. Dung sau khi 9router da refresh OK.
- `Export JSON`: xuat JSON co token de backup/di chuyen thu cong tren may cua ban. Khong chia se file nay.
- `Quarantine stale`: trong tab CLIProxy, dua auth file khong con co trong 9router ra folder quarantine/backup de CLIProxy khong dung nham.

## Bao mat

- Khong commit `backups/`, `runtime-auths`, `.bak`, `__pycache__`, hoac file JSON export co token.
- Tool chi bind local `127.0.0.1:9876`.
- API CORS chi cho localhost/127.0.0.1 cung port.

## Version

- `v1.0.0`: recovery build dau tien co 9router la nguon chinh, hydrate refresh token tu 9router/CLIProxy/Codex auth, sync CLIProxy, repair alias/config, va UI preview `fill: ...`.
