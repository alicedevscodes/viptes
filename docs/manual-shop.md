# Checkout bukti foto

Target invoice sementara memakai LOG_SELLER. Tidak ada channel tujuan lain yang ditetapkan.

Produk yang dialihkan: nokos, Netflix, Stars, Telegram Premium, suntik GC/CH. Alur VIP channel lain tidak diubah.

Buyer memilih produk, melihat QRIS statis CODEQR, lalu mengirim foto. Foto berhasil masuk LOG_SELLER menjadi pemicu pengiriman, BUKAN pemeriksaan dana. Pemilik secara eksplisit memilih risiko ini. Tidak ada tombol Terima.

Nokos/Netflix direservasi saat checkout dan dikirim setelah bukti masuk log. Pesanan tanpa bukti berakhir 30 menit. Nomor nokos hanya dijual otomatis jika session stok sudah di-bind. Login akun stok milik sendiri memakai alur pembuatan userbot repo, kemudian owner menjalankan /bindnokos +628xxx USERBOT_ID. Session stok dipisahkan dari ubotdb dan dipantau hanya untuk satu pesanan selama 10 menit. Bot hanya meneruskan kode login baru dari 777000 sesudah pengiriman nomor. Tidak mendukung OTP SMS/WhatsApp. Session dan kode tidak dicetak di log atau invoice. Database dan backup tetap merupakan data rahasia.

Stars/Premium/suntik menerima pemberitahuan menunggu owner. Harga suntik belum ada dalam katalog repo: invoice menulis sesuai kesepakatan owner, tidak mengarang nominal.

Tombol Transaksi Selesai tersedia pada notifikasi buyer dan bukti di log. Hanya buyer pesanan atau OWNER_ID boleh memakainya. Invoice dikirim segera oleh worker setelah tombol diklik; jika tidak, 30 menit setelah percobaan pengiriman notifikasi pertama. Pemeriksaan worker setiap 10 detik. Invoice timer untuk layanan manual tetap menyebut menunggu owner.

Status, reservasi, batas waktu, dan snapshot invoice disimpan di MANUAL_SHOP_V1 pada database repo. Pengiriman menggunakan random_id MTProto stabil per pesanan/tahap untuk mengurangi duplikasi ketika retry. Jangan menjalankan dua instance bot untuk database yang sama. Tidak menjanjikan exactly-once tanpa batas waktu di luar jaminan deduplikasi server Telegram. Foto yang sama dideteksi lewat file_unique_id, bukan analisis keaslian gambar atau verifikasi bank.

Session stok yang belum login, stok kosong, kegagalan log, atau kegagalan kirim tidak boleh dianggap transaksi selesai. /pesananku memperlihatkan status tanpa menampilkan kredensial. Invoice hanya ringkasan tersanitasi; tidak meneruskan foto bukti mentah atau isi akun/OTP.

Sesudah deploy: uji memakai akun stok milik sendiri, buyer uji, dan log privat. Belum diuji langsung pada Telegram/Casaku oleh assistant.
