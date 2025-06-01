from flask import Flask, render_template, request, redirect, url_for, flash, session
from models import get_db_connection, init_db, User, NasabahBiasa, NasabahPrioritas, Admin, Merchant, bcrypt, generate_unique_nomor_rekening
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.static_folder = 'static'
bcrypt.init_app(app)

def format_rupiah(amount):
    """Mengubah angka menjadi format Rupiah (contoh: 1000000.0 -> 1.000.000,00)"""
    amount = float(amount)
    amount_str = "{:.2f}".format(amount)
    amount_str = amount_str.replace('.', ',')
    integer_part, decimal_part = amount_str.split(',')
    integer_part = integer_part[::-1]
    chunks = [integer_part[i:i+3] for i in range(0, len(integer_part), 3)]
    integer_part = '.'.join(chunks)[::-1]
    return f"{integer_part},{decimal_part}"

app.jinja_env.filters['rupiah'] = format_rupiah

@app.route('/')
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        user_type = request.form['user_type']

        if User.find_by_email(email):
            flash('Email sudah terdaftar!', 'error')
            return redirect(url_for('register'))
        
        if user_type in ['nasabah_biasa', 'nasabah_prioritas']:
            conn = get_db_connection()
            cursor = conn.cursor()
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            cursor.execute(
                'INSERT INTO permintaan_registrasi (username, email, password, user_type) VALUES (?, ?, ?, ?)',
                (username, email, hashed_password, user_type)
            )
            conn.commit()
            conn.close()
            flash('Permintaan registrasi telah diajukan. Menunggu persetujuan admin.', 'success')
            return redirect(url_for('login'))
        else:
            if user_type == 'admin':
                user = Admin(id=0, username="", email="", password="", adminID="", nama_admin="")
            elif user_type == 'merchant':
                user = Merchant(id=0, username="", email="", password="", merchantID="", nama_merchant="")
            else:
                flash('Tipe user tidak valid!', 'error')
                return redirect(url_for('register'))
            
            user_id = user.register(username, email, password)
            flash('Registrasi berhasil! Silakan login.', 'success')
            return redirect(url_for('login'))

    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.find_by_email(email)
        print(f"User found: {user}")
        if user:
            print(f"Stored password hash: {user.password}, Input password: {password}")
            if user.login(email, password):
                print(f"Login successful for {email}, setting session with user_id: {user.id}")
                session['user_id'] = user.id
                return redirect(url_for('dashboard_page'))
            else:
                print(f"Password verification failed for {email}")
                flash('Email atau password salah!', 'error')
        else:
            print(f"No user found for email: {email}")
            flash('Email atau password salah!', 'error')

    return render_template('index.html')

@app.route('/dashboard', endpoint='dashboard_page')
def dashboard():
    if 'user_id' not in session:
        flash('Silakan login terlebih dahulu!', 'error')
        return redirect(url_for('login'))

    user = User.find_by_id(session['user_id'])
    if user:
        pending_withdrawals = []
        pending_transfers = []
        pending_registrations = user.get_pending_registrations() if user.__class__.__name__ == 'Admin' else []
        
        if user.__class__.__name__ in ['NasabahBiasa', 'NasabahPrioritas']:
            pending_withdrawals = user.get_pending_withdrawals()
            pending_transfers = user.get_pending_transfers()
        elif user.__class__.__name__ == 'Merchant':
            pending_withdrawals = user.get_all_pending_withdrawals()
            pending_transfers = user.get_all_pending_transfers()
        
        dashboard_content = user.display_dashboard()
        return render_template('dashboard.html', 
                            user=user, 
                            dashboard=dashboard_content,
                            pending_withdrawals=pending_withdrawals,
                            pending_transfers=pending_transfers,
                            pending_registrations=pending_registrations)
    else:
        flash('User tidak ditemukan!', 'error')
        return redirect(url_for('login'))

@app.route('/topup', methods=['POST'])
def topup():
    if 'user_id' not in session:
        flash('Silakan login terlebih dahulu!', 'error')
        return redirect(url_for('dashboard_page'))

    user = User.find_by_id(session['user_id'])
    if user and user.__class__.__name__ in ['NasabahBiasa', 'NasabahPrioritas']:
        jumlah = float(request.form['jumlah'])
        if user.topup_saldo(jumlah):
            formatted_jumlah = format_rupiah(jumlah)
            flash(f'Berhasil topup saldo sebesar {formatted_jumlah}!', 'success')
        else:
            flash('Gagal topup saldo!', 'error')
    return redirect(url_for('dashboard_page'))

@app.route('/transfer', methods=['POST'])
def transfer():
    if 'user_id' not in session:
        flash('Silakan login terlebih dahulu!', 'error')
        return redirect(url_for('dashboard_page'))

    user = User.find_by_id(session['user_id'])
    if user and user.__class__.__name__ in ['NasabahBiasa', 'NasabahPrioritas']:
        nomor_rekening = request.form['nomor_rekening']
        jumlah = float(request.form['jumlah'])

        target_user = User.find_by_nomor_rekening(nomor_rekening)
        if not target_user:
            flash('Nomor rekening tujuan tidak ditemukan!', 'error')
            return redirect(url_for('dashboard_page'))
        if target_user.id == user.id:
            flash('Tidak dapat transfer ke rekening sendiri!', 'error')
            return redirect(url_for('dashboard_page'))
        if jumlah <= 0:
            flash('Jumlah transfer harus lebih dari 0!', 'error')
            return redirect(url_for('dashboard_page'))
        if user.saldo < jumlah:
            flash('Saldo tidak cukup untuk transfer!', 'error')
            return redirect(url_for('dashboard_page'))

        conn = sqlite3.connect('bank.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO permintaan_transfer (user_id, nomor_rekening_tujuan, jumlah, status) VALUES (?, ?, ?, "pending")',
                    (user.id, nomor_rekening, jumlah))
        conn.commit()
        conn.close()

        formatted_jumlah = format_rupiah(jumlah)
        flash(f'Permintaan transfer sebesar {formatted_jumlah} ke {nomor_rekening} telah diajukan dan menunggu persetujuan merchant.', 'success')
    else:
        flash('Fitur transfer hanya tersedia untuk Nasabah Biasa dan Nasabah Prioritas.', 'error')
    return redirect(url_for('dashboard_page'))

@app.route('/tarik', methods=['POST'])
def tarik():
    if 'user_id' not in session:
        flash('Silakan login terlebih dahulu!', 'error')
        return redirect(url_for('dashboard_page'))

    user = User.find_by_id(session['user_id'])
    if user and user.__class__.__name__ in ['NasabahBiasa', 'NasabahPrioritas']:
        jumlah = float(request.form['jumlah'])

        if jumlah <= 0:
            flash('Jumlah penarikan harus lebih dari 0!', 'error')
            return redirect(url_for('dashboard_page'))
        if user.saldo < jumlah:
            flash('Saldo tidak cukup untuk penarikan!', 'error')
            return redirect(url_for('dashboard_page'))
        if user.__class__.__name__ == 'NasabahBiasa' and jumlah > 10000000:
            flash('Batas penarikan untuk Nasabah Biasa adalah Rp 10.000.000!', 'error')
            return redirect(url_for('dashboard_page'))

        conn = sqlite3.connect('bank.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO permintaan_penarikan (user_id, jumlah, status) VALUES (?, ?, "pending")',
                    (user.id, jumlah))
        conn.commit()
        conn.close()

        formatted_jumlah = format_rupiah(jumlah)
        flash(f'Permintaan penarikan sebesar {formatted_jumlah} telah diajukan dan menunggu persetujuan merchant.', 'success')
    return redirect(url_for('dashboard_page'))

@app.route('/hadiah')
def hadiah():
    if 'user_id' not in session:
        flash('Silakan login terlebih dahulu!', 'error')
        return redirect(url_for('dashboard_page'))

    user = User.find_by_id(session['user_id'])
    if user and user.__class__.__name__ == 'NasabahPrioritas':
        daftar_hadiah = user.lihat_daftar_hadiah()
        poin = user.lihat_poin()
        return render_template('hadiah.html', daftar_hadiah=daftar_hadiah, poin=poin)
    else:
        flash('Fitur ini hanya tersedia untuk Nasabah Prioritas!', 'error')
        return redirect(url_for('dashboard_page'))

@app.route('/klaim_hadiah', methods=['POST'])
def klaim_hadiah():
    if 'user_id' not in session:
        flash('Silakan login terlebih dahulu!', 'error')
        return redirect(url_for('dashboard_page'))

    user = User.find_by_id(session['user_id'])
    if user and user.__class__.__name__ == 'NasabahPrioritas':
        hadiah_id = int(request.form['hadiah_id'])
        status, message, hadiah = user.claim_hadiah_poin_loyalitas(hadiah_id)
        
        if status:
            flash(f'Berhasil klaim hadiah: {hadiah["nama"]}!', 'success')
        else:
            flash(message, 'error')
    else:
        flash('Fitur ini hanya tersedia untuk Nasabah Prioritas!', 'error')
    
    return redirect(url_for('hadiah'))

@app.route('/riwayat_hadiah')
def riwayat_hadiah():
    if 'user_id' not in session:
        flash('Silakan login terlebih dahulu!', 'error')
        return redirect(url_for('dashboard_page'))

    user = User.find_by_id(session['user_id'])
    if user and user.__class__.__name__ == 'NasabahPrioritas':
        riwayat = user.lihat_riwayat_klaim()
        return render_template('riwayat_hadiah.html', riwayat=riwayat)
    else:
        flash('Fitur ini hanya tersedia untuk Nasabah Prioritas!', 'error')
        return redirect(url_for('dashboard_page'))

@app.route('/hapus_nasabah', methods=['GET', 'POST'])
def hapus_nasabah():
    """Menampilkan daftar nasabah dan menangani proses penghapusan oleh Admin."""
    if 'user_id' not in session:
        flash('Silakan login terlebih dahulu!', 'error')
        return redirect(url_for('dashboard_page'))

    user = User.find_by_id(session['user_id'])
    if user and user.__class__.__name__ != 'Admin':
        flash('Hanya Admin yang dapat mengakses fitur ini!', 'error')
        return redirect(url_for('dashboard_page'))

    if request.method == 'POST':
        nasabahID = request.form['nasabahID']
        if user.hapus_nasabah(nasabahID):
            flash(f'Berhasil menghapus nasabah dengan ID {nasabahID}!', 'success')
        else:
            flash('Gagal menghapus nasabah! ID tidak ditemukan.', 'error')
        return redirect(url_for('hapus_nasabah'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT n.nasabahID, n.nomor_rekening, n.saldo, u.username, 
            CASE 
                WHEN n.poin_loyalitas IS NOT NULL THEN 'Nasabah Prioritas'
                ELSE 'Nasabah Biasa'
            END AS tipe_nasabah
        FROM nasabah n
        JOIN users u ON n.user_id = u.id
    ''')
    nasabah_list = cursor.fetchall()
    conn.close()

    nasabah_list = [dict(row) for row in nasabah_list]
    return render_template('hapus_nasabah.html', nasabah_list=nasabah_list)

@app.route('/approve_penarikan', methods=['POST'])
def approve_penarikan():
    """Menangani persetujuan atau penolakan penarikan oleh Merchant."""
    if 'user_id' not in session:
        flash('Silakan login terlebih dahulu!', 'error')
        return redirect(url_for('dashboard_page'))

    user = User.find_by_id(session['user_id'])
    if user and user.__class__.__name__ == 'Merchant':
        permintaan_id = int(request.form['permintaan_id'])
        action = request.form['action']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM permintaan_penarikan WHERE id = ? AND status = "pending"', (permintaan_id,))
        request_data = cursor.fetchone()
        if not request_data:
            flash('Permintaan tidak ditemukan atau sudah diproses!', 'error')
            conn.close()
            return redirect(url_for('dashboard_page'))

        request_data = dict(request_data)
        nasabah_id = request_data['user_id']
        jumlah = request_data['jumlah']
        nasabah = User.find_by_id(nasabah_id)
        if not nasabah:
            flash('Nasabah tidak ditemukan!', 'error')
            conn.close()
            return redirect(url_for('dashboard_page'))

        if action == 'approve':
            if nasabah.__class__.__name__ == 'NasabahBiasa':
                biaya_layanan = jumlah / 1000 if jumlah >= 100000 else 0
                total_pengurangan = jumlah + biaya_layanan
                if nasabah.saldo < total_pengurangan:
                    flash('Saldo nasabah tidak mencukupi!', 'error')
                    conn.close()
                    return redirect(url_for('dashboard_page'))
                saldo_baru = nasabah.saldo - total_pengurangan
                cursor.execute('UPDATE nasabah SET saldo = ? WHERE user_id = ?', (saldo_baru, nasabah_id))
            else:
                if nasabah.saldo < jumlah:
                    flash('Saldo nasabah tidak mencukupi!', 'error')
                    conn.close()
                    return redirect(url_for('dashboard_page'))
                saldo_baru = nasabah.saldo - jumlah
                cursor.execute('UPDATE nasabah SET saldo = ? WHERE user_id = ?', (saldo_baru, nasabah_id))

            cursor.execute('UPDATE permintaan_penarikan SET status = "approved" WHERE id = ?', (permintaan_id,))
            conn.commit()
            formatted_jumlah = format_rupiah(jumlah)
            flash(f'Berhasil menyetujui penarikan sebesar {formatted_jumlah} untuk nasabah!', 'success')
        else:
            cursor.execute('UPDATE permintaan_penarikan SET status = "rejected" WHERE id = ?', (permintaan_id,))
            conn.commit()
            flash('Permintaan penarikan telah ditolak.', 'success')

        conn.close()
    return redirect(url_for('dashboard_page'))

@app.route('/approve_transfer', methods=['POST'])
def approve_transfer():
    if 'user_id' not in session:
        flash('Silakan login terlebih dahulu!', 'error')
        return redirect(url_for('dashboard_page'))

    user = User.find_by_id(session['user_id'])
    if user and user.__class__.__name__ == 'Merchant':
        permintaan_id = int(request.form['permintaan_id'])
        action = request.form['action']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.*, n.saldo, n.nomor_rekening, n.withdrawal_limit, n.poin_loyalitas
            FROM permintaan_transfer t
            JOIN nasabah n ON t.user_id = n.user_id
            WHERE t.id = ? AND t.status = "pending"
        ''', (permintaan_id,))
        request_data = cursor.fetchone()
        if not request_data:
            flash('Permintaan tidak ditemukan atau sudah diproses!', 'error')
            conn.close()
            return redirect(url_for('dashboard_page'))

        request_data = dict(request_data)
        nasabah_id = request_data['user_id']
        jumlah = request_data['jumlah']
        nomor_rekening_tujuan = request_data['nomor_rekening_tujuan']
        nasabah_pengirim = User.find_by_id(nasabah_id)
        if not nasabah_pengirim:
            flash('Nasabah pengirim tidak ditemukan!', 'error')
            conn.close()
            return redirect(url_for('dashboard_page'))

        nasabah_penerima = User.find_by_nomor_rekening(nomor_rekening_tujuan)
        if not nasabah_penerima and action == 'reject':
            cursor.execute('UPDATE permintaan_transfer SET status = "rejected" WHERE id = ?', (permintaan_id,))
            conn.commit()
            flash('Permintaan transfer telah ditolak karena nasabah penerima tidak ditemukan.', 'success')
            conn.close()
            return redirect(url_for('dashboard_page'))
        elif not nasabah_penerima:
            flash('Nasabah penerima tidak ditemukan! Tidak dapat menyetujui.', 'error')
            conn.close()
            return redirect(url_for('dashboard_page'))

        if action == 'approve':
            if nasabah_pengirim.__class__.__name__ == 'NasabahBiasa':
                biaya_layanan = jumlah / 1000 if jumlah >= 100000 else 0
                total_pengurangan = jumlah + biaya_layanan
                if nasabah_pengirim.saldo < total_pengurangan:
                    flash('Saldo nasabah pengirim tidak mencukupi!', 'error')
                    conn.close()
                    return redirect(url_for('dashboard_page'))
                saldo_pengirim_baru = nasabah_pengirim.saldo - total_pengurangan
                cursor.execute('UPDATE nasabah SET saldo = ? WHERE user_id = ?', (saldo_pengirim_baru, nasabah_id))
                saldo_penerima_baru = nasabah_penerima.saldo + jumlah
                cursor.execute('UPDATE nasabah SET saldo = ? WHERE user_id = ?', (saldo_penerima_baru, nasabah_penerima.id))
            else:
                if nasabah_pengirim.saldo < jumlah:
                    flash('Saldo nasabah pengirim tidak mencukupi!', 'error')
                    conn.close()
                    return redirect(url_for('dashboard_page'))
                saldo_pengirim_baru = nasabah_pengirim.saldo - jumlah
                cursor.execute('UPDATE nasabah SET saldo = ? WHERE user_id = ?', (saldo_pengirim_baru, nasabah_id))
                saldo_penerima_baru = nasabah_penerima.saldo + jumlah
                cursor.execute('UPDATE nasabah SET saldo = ? WHERE user_id = ?', (saldo_penerima_baru, nasabah_penerima.id))

            cursor.execute('UPDATE permintaan_transfer SET status = "approved" WHERE id = ?', (permintaan_id,))
            conn.commit()
            formatted_jumlah = format_rupiah(jumlah)
            flash(f'Berhasil menyetujui transfer sebesar {formatted_jumlah} dari {nasabah_pengirim.nomor_rekening} ke {nasabah_penerima.nomor_rekening}!', 'success')
        else:
            cursor.execute('UPDATE permintaan_transfer SET status = "rejected" WHERE id = ?', (permintaan_id,))
            conn.commit()
            flash('Permintaan transfer telah ditolak.', 'success')

        conn.close()
    return redirect(url_for('dashboard_page'))

@app.route('/approve_registration', methods=['POST'])
def approve_registration():
    if 'user_id' not in session:
        flash('Silakan login terlebih dahulu!', 'error')
        return redirect(url_for('dashboard_page'))

    user = User.find_by_id(session['user_id'])
    if user and user.__class__.__name__ == 'Admin':
        request_id = int(request.form['request_id'])
        action = request.form.get('action')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM permintaan_registrasi WHERE id = ? AND status = ?', (request_id, 'pending'))
        request_data = cursor.fetchone()
        if not request_data:
            flash('Permintaan registrasi tidak ditemukan atau sudah diproses!', 'error')
            conn.close()
            return redirect(url_for('dashboard_page'))

        if action == 'approve':
            user_id = request_data['user_id']
            username = request_data['username']
            email = request_data['email']
            password = request_data['password']
            user_type = request_data['user_type']

            cursor.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                        (username, email, password))
            new_user_id = cursor.lastrowid

            if user_type == 'nasabah_biasa':
                nasabahID = f"NB-{username}"
                nomor_rekening = generate_unique_nomor_rekening()
                cursor.execute('INSERT INTO nasabah (user_id, nasabahID, nomor_rekening, biaya_layanan, withdrawal_limit) VALUES (?, ?, ?, ?, ?)',
                            (new_user_id, nasabahID, nomor_rekening, 50000.0, 5000000.0))
            elif user_type == 'nasabah_prioritas':
                nasabahID = f"NP-{username}"
                nomor_rekening = generate_unique_nomor_rekening()
                cursor.execute('INSERT INTO nasabah (user_id, nasabahID, nomor_rekening, poin_loyalitas) VALUES (?, ?, ?, ?)',
                            (new_user_id, nasabahID, nomor_rekening, 0))

            cursor.execute('DELETE FROM permintaan_registrasi WHERE id = ?', (request_id,))
            conn.commit()
            flash(f'Registrasi untuk {username} telah disetujui.', 'success')
        elif action == 'reject':
            cursor.execute('DELETE FROM permintaan_registrasi WHERE id = ?', (request_id,))
            conn.commit()
            flash('Permintaan registrasi telah ditolak.', 'success')
        else:
            flash('Aksi tidak valid!', 'error')

        conn.close()
    return redirect(url_for('dashboard_page'))

@app.route('/logout')
def logout():
    if 'user_id' in session:
        user = User.find_by_id(session['user_id'])
        if user:
            if user.__class__.__name__ == 'NasabahBiasa':
                user.logout()
            elif user.__class__.__name__ == 'NasabahPrioritas':
                user.logout()
            elif user.__class__.__name__ == 'Admin':
                user.logout()
            elif user.__class__.__name__ == 'Merchant':
                user.logout()
        session.pop('user_id', None)
        flash('Anda telah logout.', 'success')
    return redirect(url_for('login'))

@app.route('/ganti_password', methods=['GET', 'POST'])
def ganti_password():
    if 'user_id' not in session:
        flash('Silakan login terlebih dahulu!', 'error')
        return redirect(url_for('dashboard_page'))

    user = User.find_by_id(session['user_id'])
    if not user:
        flash('User tidak ditemukan!', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        old_password = request.form['old_password']
        new_password = request.form['new_password']
        status, message = user.ganti_password(old_password, new_password)
        flash(message, 'success' if status else 'error')
        return redirect(url_for('dashboard_page'))

    return render_template('ganti_password.html', user=user)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)