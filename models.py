import sqlite3
import random
from abc import ABC, abstractmethod
from flask_bcrypt import Bcrypt
from utils import format_rupiah
from datetime import datetime

bcrypt = Bcrypt()

def get_db_connection():
    conn = sqlite3.connect('bank.db')
    conn.row_factory = sqlite3.Row
    return conn

def generate_unique_nomor_rekening():
    conn = get_db_connection()
    cursor = conn.cursor()
    while True:
        nomor_rekening = ''.join([str(random.randint(0, 9)) for _ in range(8)])
        cursor.execute('SELECT nomor_rekening FROM nasabah WHERE nomor_rekening = ?', (nomor_rekening,))
        if not cursor.fetchone():
            break
    conn.close()
    return nomor_rekening

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nasabah (
            user_id INTEGER PRIMARY KEY,
            nasabahID TEXT UNIQUE NOT NULL,
            nomor_rekening TEXT UNIQUE NOT NULL,
            saldo REAL DEFAULT 0.0,
            biaya_layanan REAL DEFAULT 50000.0,
            withdrawal_limit REAL,
            poin_loyalitas INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin (
            user_id INTEGER PRIMARY KEY,
            adminID TEXT UNIQUE NOT NULL,
            nama_admin TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS merchant (
            user_id INTEGER PRIMARY KEY,
            merchantID TEXT UNIQUE NOT NULL,
            nama_merchant TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS permintaan_penarikan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            jumlah REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            tanggal TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS permintaan_transfer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            nomor_rekening_tujuan TEXT NOT NULL,
            jumlah REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            tanggal TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS permintaan_registrasi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL,
            user_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            tanggal TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS klaim_hadiah (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            hadiah_id INTEGER NOT NULL,
            nama_hadiah TEXT NOT NULL,
            poin_digunakan INTEGER NOT NULL,
            tanggal_klaim TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )          
    ''')
    
    conn.commit()
    conn.close()

class User(ABC):
    def __init__(self, id=0, username="", email="", password=""):
        self.__id = id
        self.__username = username
        self.__email = email
        self.__password = password

    @property
    def id(self):
        return self.__id

    @property
    def username(self):
        return self.__username

    @property
    def email(self):
        return self.__email

    @property
    def password(self):
        return self.__password

    @password.setter
    def password(self, value):
        self.__password = value

    @abstractmethod
    def register(self, username, email, password):
        pass

    @staticmethod
    def find_by_email(email):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        user_id = row['id']
        cursor.execute('SELECT * FROM nasabah WHERE user_id = ?', (user_id,))
        nasabah_row = cursor.fetchone()
        if nasabah_row:
            if nasabah_row['poin_loyalitas'] is not None:
                conn.close()
                return NasabahPrioritas(
                    id=row['id'], username=row['username'], email=row['email'],
                    password=row['password'], nasabahID=nasabah_row['nasabahID'],
                    nomor_rekening=nasabah_row['nomor_rekening'], saldo=nasabah_row['saldo'],
                    poin_loyalitas=nasabah_row['poin_loyalitas']
                )
            else:
                conn.close()
                return NasabahBiasa(
                    id=row['id'], username=row['username'], email=row['email'],
                    password=row['password'], nasabahID=nasabah_row['nasabahID'],
                    nomor_rekening=nasabah_row['nomor_rekening'], saldo=nasabah_row['saldo'],
                    biaya_layanan=nasabah_row['biaya_layanan'], withdrawal_limit=nasabah_row['withdrawal_limit']
                )

        cursor.execute('SELECT * FROM admin WHERE user_id = ?', (user_id,))
        admin_row = cursor.fetchone()
        if admin_row:
            conn.close()
            return Admin(
                id=row['id'], username=row['username'], email=row['email'],
                password=row['password'], adminID=admin_row['adminID'], nama_admin=admin_row['nama_admin']
            )

        cursor.execute('SELECT * FROM merchant WHERE user_id = ?', (user_id,))
        merchant_row = cursor.fetchone()
        if merchant_row:
            conn.close()
            return Merchant(
                id=row['id'], username=row['username'], email=row['email'],
                password=row['password'], merchantID=merchant_row['merchantID'], nama_merchant=merchant_row['nama_merchant']
            )

        conn.close()
        return None

    @staticmethod
    def find_by_id(user_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        cursor.execute('SELECT * FROM nasabah WHERE user_id = ?', (user_id,))
        nasabah_row = cursor.fetchone()
        if nasabah_row:
            if nasabah_row['poin_loyalitas'] is not None: 
                conn.close()
                return NasabahPrioritas(
                    id=row['id'], username=row['username'], email=row['email'],
                    password=row['password'], nasabahID=nasabah_row['nasabahID'],
                    nomor_rekening=nasabah_row['nomor_rekening'], saldo=nasabah_row['saldo'],
                    poin_loyalitas=nasabah_row['poin_loyalitas']
                )
            else:  
                conn.close()
                return NasabahBiasa(
                    id=row['id'], username=row['username'], email=row['email'],
                    password=row['password'], nasabahID=nasabah_row['nasabahID'],
                    nomor_rekening=nasabah_row['nomor_rekening'], saldo=nasabah_row['saldo'],
                    biaya_layanan=nasabah_row['biaya_layanan'], withdrawal_limit=nasabah_row['withdrawal_limit']
                )

        cursor.execute('SELECT * FROM admin WHERE user_id = ?', (user_id,))
        admin_row = cursor.fetchone()
        if admin_row:
            conn.close()
            return Admin(
                id=row['id'], username=row['username'], email=row['email'],
                password=row['password'], adminID=admin_row['adminID'], nama_admin=admin_row['nama_admin']
            )

        cursor.execute('SELECT * FROM merchant WHERE user_id = ?', (user_id,))
        merchant_row = cursor.fetchone()
        if merchant_row:
            conn.close()
            return Merchant(
                id=row['id'], username=row['username'], email=row['email'],
                password=row['password'], merchantID=merchant_row['merchantID'], nama_merchant=merchant_row['nama_merchant']
            )

        conn.close()
        return None
    
    @staticmethod
    def find_by_nomor_rekening(nomor_rekening):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM nasabah WHERE nomor_rekening = ?', (nomor_rekening,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        user_id = row['user_id']
        user = User.find_by_id(user_id)
        conn.close()
        return user

    def login(self, email, password):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT password FROM users WHERE email = ?', (email,))
        row = cursor.fetchone()
        conn.close()
        if row and bcrypt.check_password_hash(row['password'], password):
            return True
        return False
    
    @abstractmethod
    def logout(self):
        pass

    def display_dashboard(self):
        return f"Dashboard for {self.username}"

class Nasabah(User):
    def __init__(self, id=0, username="", email="", password="", nasabahID="", nomor_rekening="", saldo=0.0):
        super().__init__(id, username, email, password)
        self.__nasabahID = nasabahID
        self.__nomor_rekening = nomor_rekening
        self.__saldo = saldo

    @property
    def nasabahID(self):
        return self.__nasabahID

    @property
    def nomor_rekening(self):
        return self.__nomor_rekening

    @property
    def saldo(self):
        return self.__saldo

    @saldo.setter
    def saldo(self, value):
        self.__saldo = value

    @staticmethod
    def find_by_user_id(user_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM nasabah WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return Nasabah(
                user_id=row['user_id'], nasabahID=row['nasabahID'], nomor_rekening=row['nomor_rekening'],
                saldo=row['saldo']
            )
        return None

    @property
    def saldo_view(self):
        return self.saldo
    
    def ganti_password(self, old_password, new_password):
        """Mengganti password nasabah setelah memverifikasi password lama."""
        if not bcrypt.check_password_hash(self.password, old_password):
            return False, "Password lama salah."
        
        hashed_new_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE users SET password = ? WHERE id = ?',
            (hashed_new_password, self.id)
        )
        conn.commit()
        conn.close()
        self.password = hashed_new_password  
        return True, "Password berhasil diganti."

    def can_withdraw(self, jumlah):
        return self.saldo >= jumlah
    
    def tarik_saldo(self, jumlah):
        if not self.can_withdraw(jumlah):
            return False, "Tidak dapat menarik saldo"
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO permintaan_penarikan (user_id, jumlah, status, tanggal) 
            VALUES (?, ?, 'pending', ?)''',
            (self.id, jumlah, datetime.now())
        )
        conn.commit()
        conn.close()
        return True, "Permintaan penarikan diajukan, menunggu persetujuan merchant"

    def transfer_saldo(self, nomor_rekening, jumlah):
        if self.nomor_rekening == nomor_rekening:
            return False, "Tidak bisa transfer ke rekening sendiri"

        target_user = User.find_by_nomor_rekening(nomor_rekening)
        if not target_user:
            return False, "Nomor rekening tujuan tidak ditemukan"

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO permintaan_transfer (user_id, nomor_rekening_tujuan, jumlah, status, tanggal) 
            VALUES (?, ?, ?, 'pending', ?)''',
            (self.id, nomor_rekening, jumlah, datetime.now())
        )
        conn.commit()
        conn.close()
        return True, "Permintaan transfer diajukan, menunggu persetujuan merchant"

    @property
    def formatted_saldo(self):
        return format_rupiah(self.saldo)
    
    def display_dashboard(self):
        return f"Nasabah Dashboard: {self.username}"

class NasabahBiasa(Nasabah):
    def __init__(self, id=0, username="", email="", password="", nasabahID="", nomor_rekening="", saldo=0.0, biaya_layanan=50000.0,
                withdrawal_limit=5000000.0):
        super().__init__(id, username, email, password, nasabahID, nomor_rekening, saldo)
        self.__biaya_layanan = biaya_layanan
        self.__withdrawal_limit = withdrawal_limit

    @property
    def biaya_layanan(self):
        return self.__biaya_layanan

    @property
    def withdrawal_limit(self):
        return self.__withdrawal_limit

    def register(self, username, email, password):
        conn = get_db_connection()
        cursor = conn.cursor()
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        cursor.execute(
            'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
            (username, email, hashed_password)
        )
        user_id = cursor.lastrowid

        nasabahID = f"NB-{username}"
        nomor_rekening = generate_unique_nomor_rekening()  
        cursor.execute(
            'INSERT INTO nasabah (user_id, nasabahID, nomor_rekening, biaya_layanan, withdrawal_limit) VALUES (?, ?, ?, ?, ?)',
            (user_id, nasabahID, nomor_rekening, 50000.0, 5000000.0)
        )
        
        conn.commit()
        conn.close()
        return user_id

    def topup_saldo(self, jumlah):
        self.saldo += jumlah
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE nasabah SET saldo = ? WHERE user_id = ?',
            (self.saldo, self.id)
        )
        conn.commit()
        conn.close()
        return True
    
    def can_withdraw(self, jumlah):
        biaya_layanan = 0
        if jumlah >= 100000:
            biaya_layanan = jumlah / 1000
        total_pengurangan = jumlah + biaya_layanan
        return self.saldo >= total_pengurangan and jumlah <= self.withdrawal_limit
    
    def get_pending_withdrawals(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM permintaan_penarikan 
            WHERE user_id = ? AND status = 'pending'
        ''', (self.id,))
        pending = cursor.fetchall()
        conn.close()
        return pending

    def get_pending_transfers(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM permintaan_transfer 
            WHERE user_id = ? AND status = 'pending'
        ''', (self.id,))
        pending = cursor.fetchall()
        conn.close()
        return pending

    def transfer_saldo(self, nomor_rekening, jumlah):
        if self.nomor_rekening == nomor_rekening:
            return False, "Tidak bisa transfer ke rekening sendiri"

        target_user = User.find_by_nomor_rekening(nomor_rekening)
        if not target_user:
            return False, "Nomor rekening tujuan tidak ditemukan"

        biaya_layanan = 0
        if jumlah >= 100000:
            biaya_layanan = jumlah / 1000
        
        total_pengurangan = jumlah + biaya_layanan
        
        if self.saldo < total_pengurangan:
            return False, "Saldo tidak mencukupi"

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO permintaan_transfer 
            (user_id, nomor_rekening_tujuan, jumlah, status, tanggal) 
            VALUES (?, ?, ?, 'pending', ?)''',
            (self.id, nomor_rekening, jumlah, datetime.now())
        )
        conn.commit()
        conn.close()

        self.saldo -= biaya_layanan
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE nasabah SET saldo = ? WHERE user_id = ?',
            (self.saldo, self.id)
        )
        conn.commit()
        conn.close()
        
        return True, "Permintaan transfer diajukan"


    def logout(self):
        print(f"NasabahBiasa {self.username} telah logout.")
        return True

class NasabahPrioritas(Nasabah):
    def __init__(self, id=0, username="", email="", password="", nasabahID="", nomor_rekening="", saldo=0.0, poin_loyalitas=0):
        super().__init__(id, username, email, password, nasabahID, nomor_rekening, saldo)
        self.__poin_loyalitas = poin_loyalitas

    @property
    def poin_loyalitas(self):
        return self.__poin_loyalitas

    @poin_loyalitas.setter
    def poin_loyalitas(self, value):
        self.__poin_loyalitas = value

    def register(self, username, email, password):
        conn = get_db_connection()
        cursor = conn.cursor()
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        cursor.execute(
            'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
            (username, email, hashed_password)
        )
        user_id = cursor.lastrowid
        
        nasabahID = f"NP-{username}"
        nomor_rekening = generate_unique_nomor_rekening()
        cursor.execute(
            'INSERT INTO nasabah (user_id, nasabahID, nomor_rekening, poin_loyalitas) VALUES (?, ?, ?, ?)',
            (user_id, nasabahID, nomor_rekening, 0)
        )
        
        conn.commit()
        conn.close()
        return user_id
    
    def can_withdraw(self, jumlah):
        return self.saldo >= jumlah 
    
    def get_pending_withdrawals(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM permintaan_penarikan 
            WHERE user_id = ? AND status = 'pending'
        ''', (self.id,))
        pending = cursor.fetchall()
        conn.close()
        return pending

    def get_pending_transfers(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM permintaan_transfer 
            WHERE user_id = ? AND status = 'pending'
        ''', (self.id,))
        pending = cursor.fetchall()
        conn.close()
        return pending

    def topup_saldo(self, jumlah):
        self.saldo += jumlah
        self.poin_loyalitas += int(jumlah / 10000)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE nasabah SET saldo = ?, poin_loyalitas = ? WHERE user_id = ?',
            (self.saldo, self.poin_loyalitas, self.id)
        )
        conn.commit()
        conn.close()
        return True

    def transfer_saldo(self, nomor_rekening, jumlah):
        if self.nomor_rekening == nomor_rekening:
            return False, "Tidak bisa transfer ke rekening sendiri"

        target_user = User.find_by_nomor_rekening(nomor_rekening)
        if not target_user:
            return False, "Nomor rekening tujuan tidak ditemukan"
        
        if self.saldo < jumlah:
            return False, "Saldo tidak mencukupi"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO permintaan_transfer 
            (user_id, nomor_rekening_tujuan, jumlah, status, tanggal) 
            VALUES (?, ?, ?, 'pending', ?)''',
            (self.id, nomor_rekening, jumlah, datetime.now())
        )
        conn.commit()
        conn.close()
        
        return True, "Permintaan transfer diajukan"

    def tarik_saldo(self, jumlah):
        if self.saldo >= jumlah:
            self.saldo -= jumlah
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE nasabah SET saldo = ? WHERE user_id = ?',
                (self.saldo, self.id)
            )
            conn.commit()
            conn.close()
            return True
        return False

    DAFTAR_HADIAH = [
        {"id": 1, "nama": "Voucher Belanja Rp 50.000", "poin": 50},
        {"id": 2, "nama": "Paylater Cashback 10%", "poin": 100},
        {"id": 3, "nama": "Gratis Transfer 5x", "poin": 75},
        {"id": 4, "nama": "Diskon 20% Merchant", "poin": 120},
        {"id": 5, "nama": "E-Voucher Streaming 1 Bulan", "poin": 150},
        {"id": 6, "nama": "Tas Branded Limited Edition", "poin": 500}
    ]

    def lihat_daftar_hadiah(self):
        """Mengembalikan daftar hadiah yang tersedia"""
        return self.DAFTAR_HADIAH

    def claim_hadiah_poin_loyalitas(self, hadiah_id):
        """
        Mengklaim hadiah berdasarkan ID hadiah
        Return: 
        - Tuple (status: bool, message: str, hadiah: dict)
        """
        hadiah_dipilih = None
        for hadiah in self.DAFTAR_HADIAH:
            if hadiah['id'] == hadiah_id:
                hadiah_dipilih = hadiah
                break
        
        if not hadiah_dipilih:
            return False, "Hadiah tidak ditemukan", None
        
        if self.poin_loyalitas < hadiah_dipilih['poin']:
            return False, f"Poin tidak cukup. Poin Anda: {self.poin_loyalitas}, Poin dibutuhkan: {hadiah_dipilih['poin']}", None
        
        self.poin_loyalitas -= hadiah_dipilih['poin']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'UPDATE nasabah SET poin_loyalitas = ? WHERE user_id = ?',
                (self.poin_loyalitas, self.id)
            )
            
            cursor.execute(
                '''INSERT INTO klaim_hadiah 
                (user_id, hadiah_id, nama_hadiah, poin_digunakan, tanggal_klaim) 
                VALUES (?, ?, ?, ?, datetime('now'))''',
                (self.id, hadiah_dipilih['id'], hadiah_dipilih['nama'], hadiah_dipilih['poin'])
            )
            
            conn.commit()
            return True, "Hadiah berhasil diklaim", hadiah_dipilih
        
        except Exception as e:
            conn.rollback()
            return False, f"Error: {str(e)}", None
        
        finally:
            conn.close()

    def lihat_riwayat_klaim(self):
        """Mengembalikan riwayat klaim hadiah nasabah"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT nama_hadiah, poin_digunakan, tanggal_klaim 
            FROM klaim_hadiah 
            WHERE user_id = ? 
            ORDER BY tanggal_klaim DESC''',
            (self.id,)
        )
        riwayat = cursor.fetchall()
        conn.close()
        return riwayat

    def lihat_poin(self):
        return self.poin_loyalitas

    def logout(self):
        print(f"NasabahPrioritas {self.username} telah logout dengan poin loyalitas: {self.poin_loyalitas}.")
        return True

class Admin(User):
    def __init__(self, id=0, username="", email="", password="", adminID="", nama_admin=""):
        super().__init__(id, username, email, password)
        self.__adminID = adminID
        self.__nama_admin = nama_admin

    def register(self, username, email, password):
        conn = get_db_connection()
        cursor = conn.cursor()
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        cursor.execute(
            'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
            (username, email, hashed_password)
        )
        user_id = cursor.lastrowid
        
        adminID = f"ADM-{username}"
        nama_admin = username
        cursor.execute(
            'INSERT INTO admin (user_id, adminID, nama_admin) VALUES (?, ?, ?)',
            (user_id, adminID, nama_admin)
        )
        
        conn.commit()
        conn.close()
        return user_id

    @staticmethod
    def find_by_user_id(user_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM admin WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return Admin(user_id=row['user_id'], adminID=row['adminID'], nama_admin=row['nama_admin'])
        return None

    def hapus_nasabah(self, nasabahID):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM nasabah WHERE nasabahID = ?', (nasabahID,))
        row = cursor.fetchone()
        if row:
            user_id = row['user_id']
            cursor.execute('DELETE FROM nasabah WHERE user_id = ?', (user_id,))
            cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
            conn.commit()
            conn.close()
            return True
        conn.close()
        return False
    
    def get_pending_registrations(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM permintaan_registrasi WHERE status = 'pending'
        ''')
        pending = cursor.fetchall()
        conn.close()
        return [dict(row) for row in pending]
    
    def approve_registration(self, request_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM permintaan_registrasi WHERE id = ? AND status = ?', (request_id, 'pending'))
        request_data = cursor.fetchone()
        if not request_data:
            conn.close()
            return False, "Permintaan registrasi tidak ditemukan atau sudah diproses."

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
        conn.close()
        return True, f"Registrasi untuk {username} telah disetujui."
    
    def ganti_password(self, old_password, new_password):
        """Mengganti password nasabah setelah memverifikasi password lama."""
        if not bcrypt.check_password_hash(self.password, old_password):
            return False, "Password lama salah."
        
        hashed_new_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE users SET password = ? WHERE id = ?',
            (hashed_new_password, self.id)
        )
        conn.commit()
        conn.close()
        self.password = hashed_new_password  
        return True, "Password berhasil diganti."

    def logout(self):
        print(f"Admin {self.username} telah logout.")
        return True

class Merchant(User):
    def __init__(self, id=0, username="", email="", password="", merchantID="", nama_merchant=""):
        super().__init__(id, username, email, password)
        self.__merchantID = merchantID
        self.__nama_merchant = nama_merchant

    def register(self, username, email, password):
        conn = get_db_connection()
        cursor = conn.cursor()
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        cursor.execute(
            'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
            (username, email, hashed_password)
        )
        user_id = cursor.lastrowid
        
        merchantID = f"MER-{username}"
        nama_merchant = username
        cursor.execute(
            'INSERT INTO merchant (user_id, merchantID, nama_merchant) VALUES (?, ?, ?)',
            (user_id, merchantID, nama_merchant)
        )
        
        conn.commit()
        conn.close()
        return user_id

    @staticmethod
    def find_by_user_id(user_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM merchant WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return Merchant(user_id=row['user_id'], merchantID=row['merchantID'], nama_merchant=row['nama_merchant'])
        return None
    
    def get_all_pending_withdrawals(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.id, p.user_id, p.jumlah, p.status, p.tanggal, 
                u.username, n.nomor_rekening 
            FROM permintaan_penarikan p
            JOIN users u ON p.user_id = u.id
            JOIN nasabah n ON p.user_id = n.user_id
            WHERE p.status = 'pending'
        ''')
        pending = cursor.fetchall()
        conn.close()
        return [dict(row) for row in pending]

    def get_all_pending_transfers(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.id, t.user_id, t.nomor_rekening_tujuan, t.jumlah, t.status, t.tanggal,
                u.username, n.nomor_rekening 
            FROM permintaan_transfer t
            JOIN users u ON t.user_id = u.id
            JOIN nasabah n ON t.user_id = n.user_id
            WHERE t.status = 'pending'
        ''')
        pending = cursor.fetchall()
        conn.close()
        return [dict(row) for row in pending]

    def approve_tarik(self, nasabah, jumlah):
        return nasabah.tarik_saldo(jumlah)

    def approve_transfer(self, nasabah, nomor_rekening, jumlah):
        return nasabah.transfer_saldo(nomor_rekening, jumlah)
    
    def ganti_password(self, old_password, new_password):
        """Mengganti password nasabah setelah memverifikasi password lama."""
        if not bcrypt.check_password_hash(self.password, old_password):
            return False, "Password lama salah."
        
        hashed_new_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE users SET password = ? WHERE id = ?',
            (hashed_new_password, self.id)
        )
        conn.commit()
        conn.close()
        self.password = hashed_new_password  
        return True, "Password berhasil diganti."

    def logout(self):
        print(f"Merchant {self.username} telah logout.")
        return True