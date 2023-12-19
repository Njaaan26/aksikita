import os
import pymongo
from pymongo import MongoClient
from flask import Flask, request, flash, send_from_directory, redirect, url_for, render_template
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from datetime import datetime
from functools import wraps
from flask_bcrypt import Bcrypt
from bson import ObjectId
from datetime import datetime
from werkzeug.utils import secure_filename
current_time = datetime.utcnow()

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
IMG_AKTIVITAS = os.getenv("IMG_AKTIVITAS")
IMG_ARTIKEL = os.getenv("IMG_ARTIKEL")
IMG_DONATUR = os.getenv("IMG_DONATUR")
IMG_QR = os.getenv("IMG_QR")
USERNAME = os.getenv("DATABASE_USERNAME")
PASSWORD = os.getenv("DATABASE_PASSWORD")

app = Flask(__name__,
            static_url_path='',
            static_folder='static',
            template_folder='templates')


app.config['IMG_AKTIVITAS'] = IMG_AKTIVITAS
app.config['IMG_ARTIKEL'] = IMG_ARTIKEL
app.config['IMG_DONATUR'] = IMG_DONATUR
app.config['IMG_QR'] = IMG_QR
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
bcrypt = Bcrypt(app)

login = LoginManager()
login.init_app(app)
login.login_view = 'login'


cluster = MongoClient(
    f'mongodb://{USERNAME}:{PASSWORD}@ac-p2eru3r-shard-00-00.tjckrzw.mongodb.net:27017,ac-p2eru3r-shard-00-01.tjckrzw.mongodb.net:27017,ac-p2eru3r-shard-00-02.tjckrzw.mongodb.net:27017/?ssl=true&replicaSet=atlas-8r06d2-shard-0&authSource=admin&retryWrites=true&w=majority')

db = cluster["sukakita"]

try:
    cluster.admin.command('ping')
    print("You successfully connected to MongoDB!")
except Exception as e:
    print(e)


users = db['users']
roles = db['roles']
users = db["users"]
donatur = db["donatur"]
artikel = db["artikel"]
aktivitas = db["aktivitas"]
aktivitasku = db["aktivitasku"]


@login.user_loader
def load_user(username):
    u = users.find_one({"username": username})
    if not u:
        return None
    return User(username=u['username'], role=u['role'], id=u['_id'])


class User:
    def __init__(self, id, username, role):
        self._id = id
        self.username = username
        self.role = role

    @staticmethod
    def is_authenticated():
        return True

    @staticmethod
    def is_active():
        return True

    @staticmethod
    def is_anonymous():
        return False

    def get_id(self):
        return self.username

    @staticmethod
    def check_password(password_hash, password):
        return check_password_hash(password_hash, password)


def roles_required(*role_names):
    def decorator(original_route):
        @wraps(original_route)
        def decorated_route(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('home'))
            if not current_user.role in role_names:
                return redirect(url_for('home'))
            else:
                return original_route(*args, **kwargs)
        return decorated_route
    return decorator


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        user = users.find_one({"username": request.form['username']})
        if not user:
            flash('Username tidak ditemukan!', 'error')
            return render_template('view/auth/login.html')

        if not bcrypt.check_password_hash(user['password'], request.form['password']):
            flash('Password tidak sesuai!', 'error')
            return render_template('view/auth/login.html')

        user_obj = User(username=user['username'],
                        role=user['role'], id=user['_id'])
        login_user(user_obj)
        next_page = request.args.get('next')

        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('dashboard')
            return redirect(next_page)
        return redirect(request.args.get("next") or url_for("dashboard"))
    return render_template('view/auth/login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        current_time = datetime.utcnow()
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        required_fields = ['username', 'email', 'password']

        error_messages = {
            'username': 'Username tidak boleh kosong!',
            'email': 'Email tidak boleh kosong!',
            'password': 'Password tidak boleh kosong!',
        }

        for field in required_fields:
            if not locals()[field]:
                flash(error_messages[field], 'error')
                return redirect(url_for('register'))

        hashed_password = bcrypt.generate_password_hash(
            password).decode('utf-8')
        users.insert_one({
            'username': username,
            'email': email,
            'password': hashed_password,
            'role': 'guest',
            'createdAt': current_time,
            'updateAt': current_time
        })
        flash('Registrasi berhasil dilakukan!', 'success')
        return redirect(url_for('login'))
    return render_template('view/auth/register.html')


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/')
def home():
    artikel = db["artikel"]
    aktivitas = db["aktivitas"]
    artikel_data = artikel.find().sort("createdAt", pymongo.DESCENDING)
    aktivitas_data = aktivitas.find().sort("createdAt", pymongo.DESCENDING)
    return render_template('view/index.html', artikel=artikel_data, aktivitas=aktivitas_data)


@app.route('/tentang')
def tentang():
    return render_template('view/client/tentang.html')


@app.route('/donatur')
def donatur():
    donatur = db["donatur"]
    donatur_data = donatur.find().sort("createdAt", pymongo.DESCENDING)
    return render_template('view/client/donatur.html', donatur=donatur_data)


@app.route('/donatur_detail/<id>')
def donatur_detail(id):
    donatur = db["donatur"]
    donatur_data = donatur.find_one({"_id": ObjectId(id)})
    return render_template('view/client/donatur-detail.html', donatur=donatur_data)


@app.route('/artikel')
def artikel():
    artikel = db["artikel"]
    artikel_data = artikel.find().sort("createdAt", pymongo.DESCENDING)
    return render_template('view/client/artikel.html', artikel=artikel_data)


@app.route('/artikel_detail/<id>')
def artikel_detail(id):
    artikel = db["artikel"]
    artikel_data = artikel.find_one({"_id": ObjectId(id)})
    return render_template('view/client/artikel-detail.html', artikel=artikel_data)


@app.route('/aktivitasku')
@login_required
def aktivitasku():
    aktivitas = db["aktivitas"]
    aktivitasku = db["aktivitasku"]
    aktivitas_data = aktivitas.find()
    aktivitasku_data = aktivitasku.find()
    return render_template('view/client/aktivitasku.html', aktivitas=aktivitas_data, aktivitasku=aktivitasku_data)


@app.route('/aktivitas')
def aktivitas():
    aktivitas = db["aktivitas"]
    aktivitas_data = aktivitas.find().sort("createdAt", pymongo.DESCENDING)
    return render_template('view/client/aktivitas.html', aktivitas=aktivitas_data)


@app.route('/aktivitas_detail/<id>')
def aktivitas_detail(id):
    username = ''
    aktivitaskuId = ''
    aktivitas = db["aktivitas"]
    aktivitasku = db["aktivitasku"]
    aktivitas_data = aktivitas.find_one({"_id": ObjectId(id)})
    aktivitasku_data = aktivitasku.find_one(
        {"aktivitasData._id": ObjectId(id)})
    print(aktivitasku_data)
    if aktivitasku_data:
        username = aktivitasku_data['username']
        aktivitaskuId = aktivitasku_data['_id']
    return render_template('view/client/aktivitas-detail.html', aktivitas=aktivitas_data, username=username, id=aktivitaskuId)


@app.route('/dashboard')
@login_required
@roles_required('admin')
def dashboard():
    users = db["users"].count_documents({})
    donatur = db["donatur"].count_documents({})
    artikel = db["artikel"].count_documents({})
    aktivitas = db["aktivitas"].count_documents({})
    aktivitasku = db["aktivitasku"].count_documents({})
    return render_template('view/server/dashboard.html', users=users, donatur=donatur, artikel=artikel, aktivitas=aktivitas, aktivitasku=aktivitasku)


@app.route('/data_users', methods=["GET"])
def data_users():
    users = db["users"]
    users_data = users.find().sort("createdAt", pymongo.DESCENDING)
    return render_template('view/server/data-user/index.html', users=users_data)


@app.route('/data_users/<id>/edit', methods=["GET"])
def data_users_edit(id):
    users = db["users"]
    users_data = users.find_one({"_id": ObjectId(id)})
    return render_template('view/server/data-user/edit.html', users=users_data)


@app.route('/data_users/<id>', methods=["POST"])
def data_users_update(id):
    users = db["users"]
    username = request.form['username']
    email = request.form['email']
    role = request.form['role']
    password = request.form['password']
    confirm_password = request.form['confirm-password']

    required_fields = ['username', 'email',
                       'role', 'password', 'confirm_password']
    error_messages = {
        'username': 'Data username tidak boleh kosong',
        'email': 'Data email tidak boleh kosong',
        'role': 'Data role tidak boleh kosong',
        'password': 'Data password tidak boleh kosong',
        'confirm_password': 'Data confirm_password tidak boleh kosong',
    }

    for field in required_fields:
        if not locals()[field]:
            flash(error_messages[field], 'error')
            return redirect(url_for('data_users_edit', id=id))

    if password != confirm_password:
        flash('Password dan Confirm password tidak sama', 'error')
        return redirect(url_for('data_users_edit', id=id))

    user = users.find_one({"username": request.form['username']})
    if user and bcrypt.check_password_hash(user['password'], request.form['password']):
        hashed_password = bcrypt.generate_password_hash(
            password).decode('utf-8')
        users.update_one({"_id": ObjectId(id)},
                         {"$set": {
                             'username': username,
                             'email': email,
                             'password': hashed_password,
                             'role': role,
                             'updateAt': current_time}
                          })
        flash('Data user berhasil di edit!', 'success')
        return redirect(url_for('data_users'))
    else:
        return redirect(url_for('data_users_edit', id=id))


@app.route('/data_users/delete/<id>', methods=["POST"])
@login_required
@roles_required('admin')
def data_users_delete(id):
    users = db["users"]
    delete_user = users.find_one({'_id': ObjectId(id)})
    users.delete_one(delete_user)
    flash('Data user berhasil di hapus!', 'success')
    return redirect(url_for('data_users'))


TARGET_IMG_DONATUR = os.path.join(
    APP_ROOT, app.config['IMG_DONATUR'])
TARGET_IMG_QR = os.path.join(
    APP_ROOT, app.config['IMG_QR'])


@app.route('/data_donatur', methods=["GET"])
def data_donatur():
    donatur = db["donatur"]
    donatur_data = donatur.find().sort("createdAt", pymongo.DESCENDING)
    return render_template('view/server/data-donatur/index.html', donatur=donatur_data)


@app.route('/data_donatur/create', methods=["GET"])
def data_donatur_create():
    return render_template('view/server/data-donatur/create.html')


@app.route('/data_donatur/<id>/edit', methods=["GET"])
def data_donatur_edit(id):
    donatur = db["donatur"]
    donatur_data = donatur.find_one({"_id": ObjectId(id)})
    return render_template('view/server/data-donatur/edit.html', donatur=donatur_data)


@app.route('/data_donatur', methods=["POST"])
def data_donatur_store():
    donatur = db["donatur"]
    if not os.path.isdir(TARGET_IMG_DONATUR):
        os.mkdir(TARGET_IMG_DONATUR)
    judul = request.form['judul']
    deskripsi = request.form['deskripsi']
    image = request.files["image"]
    imageQr = request.files["imageQr"]

    required_fields = ['judul', 'deskripsi', 'image', 'imageQr']
    error_messages = {
        'judul': 'Data judul tidak boleh kosong',
        'deskripsi': 'Data deskripsi tidak boleh kosong',
        'image': 'Data image tidak boleh kosong',
        'imageQr': 'Data image QR tidak boleh kosong',
    }

    for field in required_fields:
        if not locals()[field]:
            flash(error_messages[field], 'error')
            return redirect(url_for('data_donatur_create'))

    current_time = datetime.utcnow()
    filename = secure_filename(image.filename)
    unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{filename}"
    destination = os.path.join(TARGET_IMG_DONATUR, unique_filename)
    image.save(destination)

    filename2 = secure_filename(imageQr.filename)
    unique_filename2 = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{filename2}"
    destination2 = os.path.join(TARGET_IMG_QR, unique_filename2)
    imageQr.save(destination2)
    donatur.insert_one({'judul': judul,
                        'deskripsi': deskripsi,
                        "image": unique_filename,
                        "imageQr": unique_filename2,
                        "createdAt": current_time,
                        "updateAt": current_time})
    flash('Data donatur berhasil di tambah!', 'success')
    return redirect(url_for('data_donatur'))


@app.route('/data_donatur/<id>', methods=["POST"])
def data_donatur_update(id):
    donatur = db["donatur"]
    judul = request.form['judul']
    deskripsi = request.form['deskripsi']
    new_image = request.files["image"]
    new_imageQr = request.files["imageQr"]

    required_fields = ['judul', 'deskripsi', 'new_image', 'new_imageQr']

    error_messages = {
        'judul': 'Data judul tidak boleh kosong',
        'deskripsi': 'Data deskripsi tidak boleh kosong',
        'new_image': 'Data image tidak boleh kosong',
        'new_imageQr': 'Data image QR tidak boleh kosong',
    }

    for field in required_fields:
        if not locals()[field]:
            flash(error_messages[field], 'error')
            return redirect(url_for('data_donatur_edit', id=id))

    if not os.path.isdir(TARGET_IMG_DONATUR):
        os.mkdir(TARGET_IMG_DONATUR)

    existing_data = donatur.find_one({"_id": ObjectId(id)})
    existing_image = existing_data.get("image")

    if existing_image:
        existing_image_path = os.path.join(TARGET_IMG_DONATUR, existing_image)
        if os.path.exists(existing_image_path):
            os.remove(existing_image_path)

    filename = secure_filename(new_image.filename)
    unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{filename}"
    destination = os.path.join(TARGET_IMG_DONATUR, unique_filename)
    new_image.save(destination)

    if not os.path.isdir(TARGET_IMG_QR):
        os.mkdir(TARGET_IMG_QR)
    existing_image2 = existing_data.get("imageQr")

    if existing_image2:
        existing_image_path2 = os.path.join(TARGET_IMG_QR, existing_image2)
        if os.path.exists(existing_image_path2):
            os.remove(existing_image_path2)

    filename2 = secure_filename(new_imageQr.filename)
    unique_filename2 = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{filename2}"
    destination2 = os.path.join(TARGET_IMG_QR, unique_filename2)
    new_imageQr.save(destination2)

    donatur.update_one({"_id": ObjectId(id)},
                       {"$set": {
                           "judul": judul,
                           "deskripsi": deskripsi,
                           "image": unique_filename,
                           "imageQr": unique_filename2,
                           "updateAt": current_time}
                        })
    flash('Data donatur berhasil di edit!', 'success')
    return redirect(url_for('data_donatur'))


@app.route('/data_donatur/delete/<id>', methods=["POST"])
def data_donatur_delete(id):
    donatur = db["donatur"]
    if not os.path.isdir(TARGET_IMG_DONATUR):
        os.mkdir(TARGET_IMG_DONATUR)

    existing_data = donatur.find_one({"_id": ObjectId(id)})
    existing_image = existing_data.get("image")

    if existing_image:
        existing_image_path = os.path.join(TARGET_IMG_DONATUR, existing_image)
        if os.path.exists(existing_image_path):
            os.remove(existing_image_path)

    if not os.path.isdir(TARGET_IMG_QR):
        os.mkdir(TARGET_IMG_QR)
    existing_image2 = existing_data.get("imageQr")

    if existing_image2:
        existing_image_path2 = os.path.join(TARGET_IMG_QR, existing_image2)
        if os.path.exists(existing_image_path2):
            os.remove(existing_image_path2)
    donatur.delete_one({"_id": ObjectId(id)})
    flash('Data donatur berhasil di hapus!', 'success')
    return redirect(url_for('data_donatur'))


TARGET_IMG_ARTIKEL = os.path.join(
    APP_ROOT, app.config['IMG_ARTIKEL'])


@app.route('/data_artikel', methods=["GET"])
@login_required
@roles_required('admin')
def data_artikel():
    artikel = db["artikel"]
    artikel_data = artikel.find().sort("createdAt", pymongo.DESCENDING)
    return render_template('view/server/data-artikel/index.html', artikel=artikel_data)


@app.route('/data_artikel/create', methods=["GET"])
@login_required
@roles_required('admin')
def data_artikel_create():
    return render_template('view/server/data-artikel/create.html')


@app.route('/data_artikel/<id>/edit', methods=["GET"])
@login_required
@roles_required('admin')
def data_artikel_edit(id):
    artikel = db["artikel"]
    artikel_data = artikel.find_one({"_id": ObjectId(id)})
    return render_template('view/server/data-artikel/edit.html', artikel=artikel_data)


@app.route('/data_artikel', methods=["POST"])
@login_required
@roles_required('admin')
def data_artikel_store():
    artikel = db["artikel"]
    if not os.path.isdir(TARGET_IMG_ARTIKEL):
        os.mkdir(TARGET_IMG_ARTIKEL)
    judul = request.form['judul']
    deskripsi = request.form['deskripsi']
    image = request.files["image"]

    required_fields = ['judul', 'deskripsi', 'image']
    error_messages = {
        'judul': 'Data judul tidak boleh kosong',
        'deskripsi': 'Data deskripsi tidak boleh kosong',
        'image': 'Data image tidak boleh kosong',
    }

    for field in required_fields:
        if not locals()[field]:
            flash(error_messages[field], 'error')
            return redirect(url_for('data_artikel_create'))

    filename = secure_filename(image.filename)
    unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{filename}"
    destination = os.path.join(TARGET_IMG_ARTIKEL, unique_filename)
    image.save(destination)
    artikel.insert_one({'judul': judul,
                        'deskripsi': deskripsi,
                        "image": unique_filename,
                        "createdAt": current_time,
                        "updateAt": current_time})
    flash('Data artikel berhasil di tambah!', 'success')
    return redirect(url_for('data_artikel'))


@app.route('/data_artikel/<id>', methods=["POST"])
@login_required
@roles_required('admin')
def data_artikel_update(id):
    artikel = db["artikel"]
    judul = request.form['judul']
    deskripsi = request.form['deskripsi']
    new_image = request.files["image"]

    required_fields = ['judul', 'deskripsi', 'new_image']
    error_messages = {
        'judul': 'Data judul tidak boleh kosong',
        'deskripsi': 'Data deskripsi tidak boleh kosong',
        'new_image': 'Data image tidak boleh kosong',
    }

    for field in required_fields:
        if not locals()[field]:
            flash(error_messages[field], 'error')
            return redirect(url_for('data_artikel_edit', id=id))

    if not os.path.isdir(TARGET_IMG_ARTIKEL):
        os.mkdir(TARGET_IMG_ARTIKEL)

    existing_data = artikel.find_one({"_id": ObjectId(id)})
    existing_image = existing_data.get("image")

    if existing_image:
        existing_image_path = os.path.join(TARGET_IMG_ARTIKEL, existing_image)
        if os.path.exists(existing_image_path):
            os.remove(existing_image_path)

    filename = secure_filename(new_image.filename)
    unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{filename}"
    destination = os.path.join(TARGET_IMG_ARTIKEL, unique_filename)
    new_image.save(destination)

    artikel.update_one({"_id": ObjectId(id)},
                       {"$set": {
                           "judul": judul,
                           "deskripsi": deskripsi,
                           "image": unique_filename,
                           "updateAt": current_time}
                        })
    flash('Data artikel berhasil di edit!', 'success')
    return redirect(url_for('data_artikel'))


@app.route('/data_artikel/delete/<id>', methods=["POST"])
@login_required
@roles_required('admin')
def data_artikel_delete(id):
    artikel = db["artikel"]
    if not os.path.isdir(TARGET_IMG_ARTIKEL):
        os.mkdir(TARGET_IMG_ARTIKEL)

    existing_data = artikel.find_one({"_id": ObjectId(id)})
    existing_image = existing_data.get("image")

    if existing_image:
        existing_image_path = os.path.join(TARGET_IMG_ARTIKEL, existing_image)
        if os.path.exists(existing_image_path):
            os.remove(existing_image_path)
    artikel.delete_one({"_id": ObjectId(id)})
    flash('Data artikel berhasil di hapus!', 'success')
    return redirect(url_for('data_artikel'))


@app.route('/data_aktivitasku', methods=["GET"])
@login_required
@roles_required('admin')
def data_aktivitasku():
    aktivitasku = db["aktivitasku"]
    aktivitasku_data = aktivitasku.find().sort("createdAt", pymongo.DESCENDING)
    return render_template('view/server/data-aktivitasku/index.html', aktivitasku=aktivitasku_data)


@app.route('/data_aktivitasku/<id>/edit', methods=["GET"])
@login_required
@roles_required('admin')
def data_aktivitasku_edit(id):
    aktivitasku = db["aktivitasku"]
    aktivitasku_data = aktivitasku.find_one({"_id": ObjectId(id)})
    return render_template('view/server/data-aktivitasku/edit.html', aktivitasku=aktivitasku_data)


@app.route('/data_aktivitasku', methods=["POST"])
@login_required
@roles_required('guest', 'donatur', 'admin')
def data_aktivitasku_store():
    id = request.args.get('id')
    aktivitasku = db["aktivitasku"]
    aktivitas_data = aktivitas.find_one({"_id": ObjectId(id)})
    deskripsi = request.form['deskripsi']
    deskripsi2 = request.form['deskripsi2']
    pekerjaan = request.form['pekerjaan']

    required_fields = ['deskripsi', 'deskripsi2', 'pekerjaan']
    error_messages = {
        'deskripsi': 'Data deskripsi tidak boleh kosong',
        'deskripsi2': 'Data deskripsi tidak boleh kosong',
        'pekerjaan': 'Data pekerjaan tidak boleh kosong',
    }

    for field in required_fields:
        if not locals()[field]:
            flash(error_messages[field], 'error')
            return redirect(url_for('aktivitas_detail', id=id))

    aktivitasku.insert_one({"username": current_user.username,
                            "deskripsi": deskripsi,
                            "deskripsi2": deskripsi2,
                            "pekerjaan": pekerjaan,
                            "aktivitasData": aktivitas_data,
                            "status": "pending",
                            "createdAt": current_time,
                            "updateAt": current_time})
    flash('Permohonan bergabung pada aktivitas berhasil di kirim!', 'success')
    return redirect(url_for('aktivitasku'))


@app.route('/data_aktivitasku/<id>', methods=["POST"])
@login_required
@roles_required('admin')
def data_aktivitasku_update(id):
    aktivitasku = db["aktivitasku"]
    deskripsi = request.form['deskripsi']
    deskripsi2 = request.form['deskripsi2']
    pekerjaan = request.form['pekerjaan']
    status = request.form['status']

    required_fields = ['deskripsi',
                       'deskripsi2', 'pekerjaan', 'status']
    error_messages = {
        'deskripsi': 'Data deskripsi tidak boleh kosong',
        'deskripsi2': 'Data deskripsi tidak boleh kosong',
        'pekerjaan': 'Data pekerjaan tidak boleh kosong',
        'status': 'Data status tidak boleh kosong',
    }

    aktivitasku.update_one({"_id": ObjectId(id)},
                           {"$set": {
                               "deskripsi": deskripsi,
                               "deskripsi2": deskripsi2,
                               "pekerjaan": pekerjaan,
                               "status": status,
                               "updateAt": current_time}
                            })
    flash('Data aktivitasku berhasil di edit!', 'success')
    return redirect(url_for('data_aktivitasku'))


@app.route('/data_aktivitasku/delete/<id>', methods=["POST"])
@login_required
@roles_required('guest', 'donatur', 'admin')
def data_aktivitasku_delete(id):
    aktivitasku = db["aktivitasku"]
    aktivitasku.delete_one({"_id": ObjectId(id)})
    flash('Data aktivitasku berhasil di hapus!', 'success')
    return redirect(url_for('data_aktivitasku'))


TARGET_IMG_AKTIVITAS = os.path.join(
    APP_ROOT, app.config['IMG_AKTIVITAS'])


@app.route('/data_aktivitas', methods=["GET"])
@login_required
@roles_required('admin')
def data_aktivitas():
    aktivitas = db["aktivitas"]
    aktivitas_data = aktivitas.find().sort("createdAt", pymongo.DESCENDING)
    return render_template('view/server/data-aktivitas/index.html', aktivitas=aktivitas_data)


@app.route('/data_aktivitas/create', methods=["GET"])
@login_required
@roles_required('admin')
def data_aktivitas_create():
    return render_template('view/server/data-aktivitas/create.html')


@app.route('/data_aktivitas/<id>/edit', methods=["GET"])
@login_required
@roles_required('admin')
def data_aktivitas_edit(id):
    aktivitas = db["aktivitas"]
    aktivitas_data = aktivitas.find_one({"_id": ObjectId(id)})
    return render_template('view/server/data-aktivitas/edit.html', aktivitas=aktivitas_data)


@app.route('/data_aktivitas', methods=["POST"])
@login_required
@roles_required('admin')
def data_aktivitas_store():
    aktivitas = db["aktivitas"]
    if not os.path.isdir(TARGET_IMG_AKTIVITAS):
        os.mkdir(TARGET_IMG_AKTIVITAS)
    judul = request.form['judul']
    deskripsi = request.form['deskripsi']
    image = request.files["image"]

    required_fields = ['judul', 'deskripsi', 'image']
    error_messages = {
        'judul': 'Data judul tidak boleh kosong',
        'deskripsi': 'Data deskripsi tidak boleh kosong',
        'image': 'Data image tidak boleh kosong',
    }

    for field in required_fields:
        if not locals()[field]:
            flash(error_messages[field], 'error')
            return redirect(url_for('data_aktivitas_create'))

    filename = secure_filename(image.filename)
    unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{filename}"
    destination = os.path.join(TARGET_IMG_AKTIVITAS, unique_filename)
    image.save(destination)

    aktivitas.insert_one({'judul': judul,
                          'deskripsi': deskripsi,
                          "image": unique_filename,
                          "createdAt": current_time,
                          "updateAt": current_time})
    flash('Data aktivitas berhasil di tambah!', 'success')
    return redirect(url_for('data_aktivitas'))


@app.route('/data_aktivitas/<id>', methods=["POST"])
@login_required
@roles_required('admin')
def data_aktivitas_update(id):
    aktivitas = db["aktivitas"]
    judul = request.form['judul']
    deskripsi = request.form['deskripsi']
    new_image = request.files["image"]

    required_fields = ['judul', 'deskripsi', 'new_image']
    error_messages = {
        'judul': 'Data judul tidak boleh kosong',
        'deskripsi': 'Data deskripsi tidak boleh kosong',
        'new_image': 'Data image tidak boleh kosong',
    }

    for field in required_fields:
        if not locals()[field]:
            flash(error_messages[field], 'error')
            return redirect(url_for('data_aktivitas_edit', id=id))

    if not os.path.isdir(TARGET_IMG_AKTIVITAS):
        os.mkdir(TARGET_IMG_AKTIVITAS)

    existing_data = aktivitas.find_one({"_id": ObjectId(id)})
    existing_image = existing_data.get("image")

    if existing_image:
        existing_image_path = os.path.join(
            TARGET_IMG_AKTIVITAS, existing_image)
        if os.path.exists(existing_image_path):
            os.remove(existing_image_path)

    filename = secure_filename(new_image.filename)
    unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{filename}"
    destination = os.path.join(TARGET_IMG_AKTIVITAS, unique_filename)
    new_image.save(destination)

    aktivitas.update_one({"_id": ObjectId(id)},
                         {"$set": {
                             "judul": judul,
                             "deskripsi": deskripsi,
                             "image": unique_filename,
                             "updateAt": current_time}
                          })
    flash('Data aktivitas berhasil di edit!', 'success')
    return redirect(url_for('data_aktivitas'))


@app.route('/data_aktivitas/delete/<id>', methods=["POST"])
@login_required
@roles_required('admin')
def data_aktivitas_delete(id):
    aktivitas = db["aktivitas"]
    if not os.path.isdir(TARGET_IMG_AKTIVITAS):
        os.mkdir(TARGET_IMG_AKTIVITAS)

    existing_data = aktivitas.find_one({"_id": ObjectId(id)})
    existing_image = existing_data.get("image")

    if existing_image:
        existing_image_path = os.path.join(
            TARGET_IMG_AKTIVITAS, existing_image)
        if os.path.exists(existing_image_path):
            os.remove(existing_image_path)
    aktivitas.delete_one({"_id": ObjectId(id)})
    flash('Data aktivitas berhasil di hapus!', 'success')
    return redirect(url_for('data_aktivitas'))


@app.template_filter(name='linebreaksbr')
def linebreaksbr_filter(text):
    return text.replace('\n', '<br>')


@app.template_filter(name='date')
def date(d):
    d = datetime.strptime(str(d), '%Y-%m-%d %H:%M:%S.%f').date()
    d.strftime("%d-%m-%y")
    return d


if __name__ == "__main__":
    app.run(debug=True)
