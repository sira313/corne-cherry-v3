# Corne + ZMK — firmware lokal

Keymap & build script untuk Corne Cherry V3 (nice!nano v2 / nRF52840) dengan
firmware ZMK, dibangun penuh di lokal (Arch Linux, tanpa Docker).

## Isi repo ini

| File | Isi |
|---|---|
| `config/corne.conf` | opsi build: mouse pointing, deep sleep, OLED |
| `config/corne_left.keymap` | keymap (layer 0-3), dipakai kedua half |
| `config/corne_right.keymap` | symlink ke `corne_left.keymap` |
| `build.sh` | build firmware (`./build.sh left\|right\|all`) |
| `flash.sh` | build + flash interaktif via UF2 |
| `patches/oled-strata.patch` | mod layar OLED strata (portrait 90°) untuk source ZMK di `app/app` |
| `apply-oled-mod.sh` | pasang ulang patch OLED setelah `west update` / checkout baru |
| `tools/convert-oled-logo.py` | konversi gambar + pasang otomatis ke source/patch OLED (lihat bawah) |
| `check-keymap.py` | cek diagram comment vs `bindings` di keymap, dan label vs `map.svg` |
| `map.svg` | peta tombol 4 layer (dihasilkan dari keymap, siap dicetak) |
| `.gitignore` | menutupi west workspace, venv, hasil build |

Source ZMK/Zephyr dan SDK **tidak** ikut di-commit (ratusan MB). Ikuti langkah
setup di bawah di mesin baru.

## Setup (Arch Linux)

### 1. Prasyarat

```bash
sudo pacman -S --needed git python

# serial USB untuk ZMK Studio (Arch: grup uucp)
sudo usermod -aG uucp "$USER"

# bootloader UF2 nice!nano v2 (0483:df11) bisa ditulis tanpa sudo
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0483", ATTR{idProduct}=="df11", MODE="0666", TAG+="uaccess"' \
  | sudo tee /etc/udev/rules.d/99-uf2-flash.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Keluar dari login lalu login lagi supaya grup `uucp` aktif.

### 2. Python env + west

```bash
python -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install west pyelftools pyyaml pykwalify packaging canopen natsort intelhex anytree
```

`cmake<4` di-install lewat venv karena `FindZephyr-sdk.cmake` milik Zephyr
rusak dengan CMake 4; `wget` juga di-shim ke `curl` karena skrip setup SDK
memakai `wget`. Dua-duanya otomatis dipakai karena script memanggil `west`
melalui `.venv/bin`.

### 3. Workspace west

```bash
git clone https://github.com/zmkfirmware/zmk --branch main app
cd app/app
../../.venv/bin/west init -l .
cd ../..
.venv/bin/west update          # ~3.5 GB, butuh waktu
.venv/bin/west zephyr-export
.venv/bin/west packages pip --install
./apply-oled-mod.sh            # pasang mod layar OLED strata
```

### 4. Zephyr SDK

```bash
cd app/app
ZEPHYR_BASE="$PWD/zephyr" PATH="$PWD/../../.venv/bin:$PATH" \
  ../../.venv/bin/west sdk install --install-dir "$PWD/../../sdk" --toolchains arm-zephyr-eabi
cd ../..
```

SDK ditaruh di `./sdk` (bukan `~/`), dibaca `build.sh` lewat
`ZEPHYR_SDK_INSTALL_DIR`. Kalau foldernya dipindah, set env itu sendiri.

Binary host-tools SDK (mis. `dtc`) punya path absolut yang di-*patch* saat
install, jadi SDK **tidak boleh** dipindah dengan `mv` setelah terinstall.
Kalau perlu pindah, install ulang ke lokasi tujuan.

Butuh `wget` untuk skrip setup SDK — di sini digantikan shim `curl` di
`.venv/bin/wget` (lihat langkah 2).

## Pakai

```bash
./build.sh all        # build kedua half -> app/app/build/{left,right}/zephyr/zmk.uf2
./build.sh left

./flash.sh            # build + flash kiri lalu kanan (interaktif)
./flash.sh --no-build # pakai build terakhir
```

## Tes pemakaian baterai half kiri

`battery-left.sh` membaca persentase baterai Corne kiri melalui UPower/BlueZ
dan mencatatnya ke `battery-left.csv`. Karena indikator 100% saat charging
bisa muncul sebelum baterai benar-benar penuh, titik awal hanya ditetapkan
setelah LED charging mati.

```bash
./battery-left.sh --list
./battery-left.sh --interval 300
```

Saat diminta, jawab `y` hanya ketika LED charging kiri sudah mati. Biarkan
script berjalan selama pemakaian normal; hentikan dengan `Ctrl-C`. Untuk
memilih device secara manual, gunakan `--device PATH` dari output `--list`.

`flash.sh` mengenali tiap half lewat USB serial, jadi tidak akan tertukar:

| Half | Serial |
|---|---|
| kiri (central) | `7F5CD247CF72BAF0` |
| kanan (peripheral) | `7336F183FB24A382` |

Ganti serial di baris atas `flash.sh` kalau board-nya berbeda.

Masuk bootloader: **double-tap tombol reset**, atau **tahan reset sambil
colok USB**.

## Layar OLED strata

Source ZMK di `app/app` di-ignore git (checkout west), jadi mod layarnya
disimpan sebagai patch di repo ini: `patches/oled-strata.patch`. Isinya:
canvas portrait 32×128 di-rotate 90° software ke panel 128×32; kiri =
output/BT + 5 kotak layer + baterai, kanan = logo piksel + LINK + baterai
(ikon baterai rounded, petir di dalamnya saat charging). Logo kanan saat ini
berupa bitmap 1-bit 32×79 hasil konversi gambar.

Kalau `west update` / checkout ulang menghapus mod-nya:

```bash
./apply-oled-mod.sh   # idempoten, lalu ./build.sh all
```

### Ganti gambar logo OLED (cara universal)

Area logo di kanvas portrait adalah baris `14..100` (LINK di atas, baterai di
bawah). Lebar gambar selalu `32` — ini memetakan ke tinggi penuh layar 32 px —
sedangkan tinggi `H = round(32 × tinggi_sumber / lebar_sumber)` memetakan ke
panjang layar 128 px, dan ditempatkan di tengah: `y0 = 14 + (87 − H) / 2`.

Aturan konversinya:

- `luminansi > 80` → piksel digambar hitam (`STRATA_FG`); sisanya dibiarkan
  putih/transparan. Ini sengaja di-invert supaya tidak ada kotak background
  putih mengelilingi objek.
- bit 0 = piksel paling kiri tiap baris, disimpan sebagai `1 << (31 − x)`.
- gambar **tidak** dipra-rotasi; rotasi 90° CW dilakukan `strata_redraw()`
  saat menyalin canvas portrait ke panel. Jadi di layar tampil 90° ke kanan
  dari gambar sumber.

Untuk hasil paling optimal, gunakan **pixel art 1-bit hitam-putih** yang sudah
mendekati grid `32 × H`. Setiap pikselnya sudah presisi di grid OLED, jadi tidak
perlu menebak threshold dan garis tidak kabur setelah di-*resize*. Foto atau
gambar grayscale tetap bisa, tapi hasilnya lebih bergantung pada threshold dan
sering meninggalkan *noise* setelah dikonversi ke 1-bit.

Gunakan script agar tidak menghitung manual (butuh Pillow):

```bash
python3 -m pip install pillow            # atau: .venv/bin/pip install pillow
python3 tools/convert-oled-logo.py GAMBAR
```

Output default hanya mencetak potongan C siap ditempel. Tambahkan `--patch`
supaya script **langsung menulis** ke dua file sekaligus — tidak perlu edit
manual:

```bash
python3 tools/convert-oled-logo.py GAMBAR --patch
# tambahkan --dry-run kalau cuma mau melihat ringkasannya
```

Yang diubah otomatis:

- `app/app/src/display/status_screen.c` — array `strata_logo[]`, `const int y0`,
  dan batas `for (int y = 0; y < H; y++)` di `strata_draw_logo()`.
- `patches/oled-strata.patch` — blok array ber-awalan `+`, header hunk, dan
  diffstat yang dihitung ulang.

Setelah itu cukup:

```bash
./apply-oled-mod.sh     # harus bilang "sudah terpasang", bukan menimpa
./build.sh right
```

Opsi `--threshold`, `--width`, `--top`, `--bottom` tersedia kalau aturan di atas
diubah. Tambahkan `--invert` kalau gambar perlu dibalik lebih dulu (putih jadi
hitam, hitam jadi putih) sebelum threshold diterapkan — berguna untuk gambar
dengan background cerah dan subjek gelap.

Jika `H > 87`, gambar terlalu tinggi untuk area antara LINK dan baterai; script
memotongnya sambil memberi peringatan — lebih baik *crop* gambar dulu atau
turunkan `--width`.

## Opsi build (`config/corne.conf`)

| Opsi | Efek |
|---|---|
| `CONFIG_ZMK_POINTING` | mengaktifkan `&mkp`, `&mmv`, `&msc` (mouse emulation) |
| `CONFIG_ZMK_SLEEP` | deep sleep setelah 15 menit idle (hemat baterai; hanya half central yang tidur) |
| `CONFIG_ZMK_DISPLAY` | OLED SSD1306 128×32 di I2C `0x3c`, menampilkan nomor layer |

Studio: `flash.sh`/`build.sh` menambah snippet `studio-rpc-usb-uart` +
`CONFIG_ZMK_STUDIO=y` **hanya untuk half kiri** (central). Half kanan tetap
mouse + sleep saja.

## Layer

| Layer | Isi |
|---|---|
| 0 | QWERTY, `'` tap/hold SHFT, `ESC` tap/hold CTRL, thumb `ALT LWR SPC/ENT MO RSE GUI` |
| 1 | angka, `BT1-5`, panah, `BT CLR`, `STUDIO UNLOCK` |
| 2 | simbol, `DEL`, `PRTSC`, brightness, volume |
| 3 | mouse: `E` atas, `S` kiri, `D` bawah, `F` kanan, `J` klik kiri, `K` klik kanan, scroll, `MB3-5` |

Akses layer 3: tekan-tahan `MO` di thumb (menyisakan layer 2 di thumb sebelahnya).

## Peta tombol

![Peta tombol Corne 4 layer](map.svg)


| Penanda | Arti |
|---|---|
| shadow | tombol hold-tap — perlu ditahan (`&mt`), contoh `'/SFT`, `ES/CTL`, `SPC/ENT` |
| outline kuning | tombol yang mengaktifkan layer aktif (Lower→`LWR`, Raise→`RSE`, Mouse→`&mo3`) |

Peta ini dibuat dari `config/corne_left.keymap`, jadi selalu ikut dengan isi
keymap. Setelah edit keymap, cek keduanya sekaligus:

```bash
python3 check-keymap.py   # bandingkan comment vs bindings, lalu bindings vs map.svg
```

Label baru yang tidak ada di `MAP` (`check-keymap.py`) akan dianggap `&trans` dan
memicu mismatch — tambah entri `MAP`-nya lebih dulu.

## Catatan penting

- **ZMK Studio menyimpan keymap di NVS device, bukan di firmware.** Setelah
  Studio dipakai, perubahan di `config/*.keymap` tidak terlihat sampai
  **Restore Stock Settings** di Studio. Flash UF2 tidak menghapus settings.
- Keymap diproses di half **kiri/central**; firmware half kanan tidak perlu
  contain keymap yang sama, tapi tetap dibangun agar sinkron.
- `build.sh` selalu pakai `-p` (pristine) supaya perubahan snippet/konfigurasi
  tidak tertinggal di CMake cache.
