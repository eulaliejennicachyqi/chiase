import json
import requests
from datetime import datetime, timedelta
import time
import threading
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import uuid
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
app = Flask(__name__)

# Đọc tệp config.json
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

# Cập nhật cấu hình cho Flask từ config
app.config.update(config)

# Đọc tệp chatToken.json
def load_retoken():
    try:
        with open('json/chatToken.json', 'r') as f:
            retokens = json.load(f)
        return retokens
    except FileNotFoundError:
        return []

# Lưu tệp chatToken.json đã cập nhật
def save_retoken(updated_tokens):
    with open('json/chatToken.json', 'w') as f:
        json.dump(updated_tokens, f, indent=4)


# Đọc tệp claudeToken.json
def load_cltoken():
    try:
        with open('json/claudeToken.json', 'r') as f:
            retokens = json.load(f)
        return retokens
    except FileNotFoundError:
        return []

# Lưu tệp claudeToken.json đã cập nhật
def save_cltoken(updated_tokens):
    with open('json/claudeToken.json', 'w') as f:
        json.dump(updated_tokens, f, indent=4)


# Ghi vào tệp failed_tokens.json
def save_failed_tokens(failed_tokens):
    with open('json/failed_tokens.json', 'w') as f:
        json.dump(failed_tokens, f, indent=4)

# Đọc lịch sử làm mới
def load_refresh_history():
    try:
        with open('json/refresh_history.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []



# Lưu lịch sử làm mới
def save_refresh_history(history):
    with open('json/refresh_history.json', 'w') as f:
        json.dump(history, f, indent=4)

# Tải bảng người dùng
def load_users():
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []
# Lưu thông tin người dùng
def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


#-----------------------------------------Liên quan đến chatgpt------------------------------------------------------
# Hàm chính để làm mới access_token
def refresh_access_tokens():
    # Đọc danh sách refresh_token
    refresh_tokens = load_retoken()

    failed_tokens = []  # Dùng để ghi lại email và refresh_token không lấy được access_token

    # Duyệt qua danh sách refresh_token
    for token_info in refresh_tokens:
        email = token_info['email']
        refresh_token = token_info['refresh_token']

        # Nếu refresh_token trống, bỏ qua dòng này
        if not refresh_token:
            continue

        try:
            # Sử dụng yêu cầu POST để lấy access_token thông qua refresh_token
            response = requests.post(
                "https://token.oaifree.com/api/auth/refresh",
                data={"refresh_token": refresh_token}
            )
            response_data = response.json()

            access_token = response_data.get("access_token")
            if access_token:  # Nếu lấy được access_token thành công
                # Cập nhật access_token và trạng thái là True
                token_info['access_token'] = access_token
                token_info['status'] = True
            else:
                # Nếu lấy thất bại, đặt trạng thái là False
                token_info['status'] = False
                failed_tokens.append(token_info)
        
        except Exception as e:
            # Bắt lỗi yêu cầu và ghi lại token thất bại, trạng thái là False
            token_info['status'] = False
            failed_tokens.append(token_info)

    # Lưu dữ liệu retoken đã cập nhật
    save_retoken(refresh_tokens)

    # Nếu có token thất bại, ghi vào failed_tokens.json
    save_failed_tokens(failed_tokens)

    return refresh_tokens


# Lấy share token
def register_token(access_token, unique_name, expire_in=0, show_userinfo=True, gpt35_limit=-1, 
                   gpt4_limit=-1, reset_limit=False, show_conversations=False, site_limit="", 
                   temporary_chat=False):
    """
    Hàm đăng ký token chia sẻ.

    :param access_token: Token truy cập của người dùng
    :param unique_name: Tên duy nhất của token chia sẻ
    :param expire_in: Thời gian hết hạn của token chia sẻ, mặc định là 0
    :param show_userinfo: Có hiển thị thông tin người dùng hay không, mặc định là False
    :param gpt35_limit: Giới hạn sử dụng mô hình GPT-3.5, mặc định là -1 không giới hạn
    :param gpt4_limit: Giới hạn sử dụng mô hình GPT-4, mặc định là -1 không giới hạn
    :param reset_limit: Có đặt lại giới hạn sử dụng hay không, mặc định là False
    :param show_conversations: Có hiển thị lịch sử hội thoại hay không, mặc định là True
    :param site_limit: Giới hạn sử dụng trang web, mặc định là chuỗi rỗng, không giới hạn
    :param temporary_chat: Có bật chức năng trò chuyện tạm thời hay không, mặc định là True

    :return: token_key (str), key của token chia sẻ sau khi đăng ký thành công
    """
    
    url = 'https://chat.oaifree.com/token/register'
    
    # 数据 payload
    data = {
        "access_token": access_token,
        "unique_name": unique_name,
        "expire_in": expire_in,
        "show_userinfo": show_userinfo,
        "gpt35_limit": gpt35_limit,
        "gpt4_limit": gpt4_limit,
        "reset_limit": reset_limit,
        "show_conversations": show_conversations,
        "site_limit": site_limit,
        "temporary_chat": temporary_chat
    }

    # Gửi yêu cầu POST
    response = requests.post(url, headers={'Content-Type': 'application/x-www-form-urlencoded'}, data=data)

    # Lấy key token chia sẻ trả về
    token_key = response.json().get("token_key")

    return token_key

# Lấy liên kết đăng nhập
def getoauth(token):
    domain = app.config.get('domain_chatgpt')
    share_token = token 
    
    url = f'https://{domain}/api/auth/oauth_token'
    headers = {
        'Origin': f'https://{domain}',
        'Content-Type': 'application/json'
    }
    data = {
        'share_token': share_token
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        loginurl = response.json().get('login_url')
        return loginurl
    except requests.RequestException as e:
        return None





#-----------------------------------------------------claude相关----------------------------------------------------------------

def get_claude_login_url(session_key,uname):
    domain = app.config.get('domain_claude')
    url = f'https://{domain}/manage-api/auth/oauth_token'
    
    # Yêu cầu tham số
    data = {
        'session_key': session_key,
        'unique_name': uname  # Tạo định danh duy nhất
    }

    # Thiết lập tiêu đề yêu cầu
    headers = {'Content-Type': 'application/json'}

    try:
        # Gửi yêu cầu POST
        response = requests.post(url, headers=headers, data=json.dumps(data))

        # Kiểm tra mã trạng thái phản hồi có phải là 200 không
        if response.status_code == 200:
            response_data = response.json()

            # Kiểm tra 'login_url' có tồn tại không
            if 'login_url' in response_data:
                login_url = response_data['login_url']
                
                # Nếu URL không bắt đầu bằng http, nối URL cơ bản
                if not login_url.startswith('http'):
                    return f'https://{domain}' + login_url
                return login_url
        
        # Nếu mã trạng thái không phải là 200 hoặc login_url không tồn tại, trả về None
        return None
    
    except requests.RequestException as e:
        # Bắt lỗi và trả về thông tin lỗi
        return None




# ---------------------------------------------------Đăng nhập đăng xuất Xác thực trang trí---------------------------------------------------------

app.secret_key = app.config.get('secret_key')  # Dùng để mã hóa session

# Trang đăng nhập
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        users = load_users()
        user = next((user for user in users if user['username'] == username), None)
        
        if user and check_password_hash(user['password'], password):
            # Đăng nhập thành công, lưu thông tin người dùng vào session
            session['logged_in'] = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            flash('Đăng nhập thành công!', 'success')
            
            # Nếu là quản trị viên, chuyển đến trang quản lý, nếu không chuyển đến trang chủ
            if user['role'] == 'admin':
                return redirect(url_for('chatgpt'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Tên người dùng hoặc mật khẩu không đúng, vui lòng thử lại.', 'danger')
    
    return render_template('login.html')

# Đăng xuất
@app.route('/logout')
def logout():
    session.clear()
    flash('Đã đăng xuất thành công.', 'success')
    return redirect(url_for('login'))

# Xác thực đăng nhập
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Vui lòng đăng nhập trước.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Xác thực quyền quản trị viên
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Vui lòng đăng nhập trước.', 'warning')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Yêu cầu quyền quản trị viên.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


#------------------------------------------------------Trang chia sẻ-------------------------------------------------------

# Trang chủ, tạo số lượng div box tương ứng với số lượng tài khoản hợp lệ
@app.route('/')
@login_required
def index():
    # Đọc access_tokens từ chatToken.json
    gpt_tokens = load_retoken()

    # Đọc token từ claudeToken.json
    claude_tokens = load_cltoken()
    
    # Tạo hai danh sách để lưu trữ tài khoản PLUS và tài khoản thường
    gpt_plus_tokens = []
    gpt_normal_tokens = []

    claude_plus_tokens = []
    claude_normal_tokens = []
    
    # Duyệt qua tất cả token và phân nhóm
    for idx, token in enumerate(gpt_tokens):
        if token['status']:  # Nếu token hợp lệ
            token_info = {
                'index': idx,
                'type': token.get('type', 'unknown'),
                'PLUS': token.get('PLUS', 'false')
            }
            
            # Phân nhóm theo trạng thái PLUS
            if token_info['PLUS'].lower() == 'true':
                gpt_plus_tokens.append(token_info)
            else:
                gpt_normal_tokens.append(token_info)

    # Duyệt qua tất cả token và phân nhóm
    for idx, token in enumerate(claude_tokens):
        if token['status']:  # Nếu token hợp lệ
            token_info = {
                'index': idx,
                'type': token.get('type', 'unknown'),
                'PLUS': token.get('PLUS', 'false')
            }
            
            # Phân nhóm theo trạng thái PLUS
            if token_info['PLUS'].lower() == 'true':

                claude_plus_tokens.append(token_info)
            else:
                claude_normal_tokens.append(token_info)
    

    # Hợp nhất hai danh sách theo thứ tự, tài khoản PLUS ở trước
    gpt_valid_tokens = gpt_plus_tokens + gpt_normal_tokens

    claude_valid_tokens = claude_plus_tokens + claude_normal_tokens


    # Render template, truyền thông tin chi tiết của token hợp lệ
    return render_template(
        'index.html',
        gpt_valid_tokens=gpt_valid_tokens,  # Truyền danh sách token đã sắp xếp
        claude_valid_tokens= claude_valid_tokens
    )



# Định nghĩa một route để xử lý việc submit UNIQUE_NAME
@app.route('/submit_name', methods=['POST'])
@login_required
def submit_name():
    data = request.json
    unique_name = data.get('unique_name')
    index = data.get('index')
    Type = data.get('type')


    if Type == 'chatgpt':

        tokens = load_retoken()

        valid_tokens = tokens
        
        # Đảm bảo index là một chỉ số hợp lệ
        if index and 1 <= index <= len(valid_tokens):
            
            # Lấy access_token tương ứng
            token_info = valid_tokens[index - 1]
            
            access_token = token_info['access_token']

            # Đăng ký token và lấy token_key tương ứng
            token_key = register_token(access_token, unique_name)
            if not token_key:
                # Cập nhật trạng thái của mục tương ứng trong chatToken.json thành false
                for token in tokens:
                    if token['access_token'] == access_token:
                        print(token['email'])
                        token['status'] = False
                        break
                
                # Lưu các tokens đã cập nhật vào chatToken.json
                save_retoken(tokens)

                return jsonify({
                    "status": "error",
                    "message": "Tài khoản đã hết hạn, hãy đổi tài khoản khác"
                }), 400

            # Lấy URL đăng nhập OAuth
            logurl = getoauth(token_key)

            return jsonify({
                "status": "success",
                "login_url": logurl
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Chỉ số không hợp lệ."
            }), 400
    else:
        tokens = load_cltoken()

        valid_tokens = tokens

        # Đảm bảo index là một chỉ số hợp lệ
        if index and 1 <= index <= len(valid_tokens):
            
            # Lấy token tương ứng
            token_info = valid_tokens[index - 1]
            
            skToken = token_info['skToken']

            # Lấy liên kết đăng nhập
            logurl = get_claude_login_url(skToken, unique_name)
            if not logurl:
                # Cập nhật trạng thái của mục tương ứng trong chatToken.json thành false
                for token in tokens:
                    if token['skToken'] == skToken:
                        print(token['email'])
                        token['status'] = False
                        break
                
                # Lưu các tokens đã cập nhật vào chatToken.json
                save_cltoken(tokens)

                return jsonify({
                    "status": "error",
                    "message": "Tài khoản đã hết hạn, hãy đổi tài khoản khác"
                }), 400
            return jsonify({
                "status": "success",
                "login_url": logurl
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Chỉ số không hợp lệ."
            }), 400


        


#------------------------------------------------------Nhiệm vụ định kỳ làm mới tokens-------------------------------------

AUTO_REFRESH_CONFIG_FILE = 'json/auto_refresh_config.json'

# Lấy thông tin nhiệm vụ định kỳ
def load_auto_refresh_config():
    try:
        with open(AUTO_REFRESH_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"auto_refresh_enabled": False, "refresh_interval_days": 1, "next_refresh_time": None}
# Lưu thông tin nhiệm vụ định kỳ
def save_auto_refresh_config(config):
    with open(AUTO_REFRESH_CONFIG_FILE, 'w') as f:
        json.dump(config, f)



def is_main_process():
    import os
    return os.environ.get('WERKZEUG_RUN_MAIN') != 'true'

current_timer = None
timer_lock = threading.Lock()

def schedule_next_refresh():
    if not is_main_process():
        print("Trong quá trình reloader, bỏ qua thiết lập bộ hẹn giờ")
        return
        
    global current_timer
    config = load_auto_refresh_config()
    
    with timer_lock:
        if config['auto_refresh_enabled']:
            if current_timer:
                current_timer.cancel()
                
            next_refresh = datetime.now() + timedelta(days=config['refresh_interval_days'])
            config['next_refresh_time'] = next_refresh.isoformat()
            save_auto_refresh_config(config)

            current_timer = threading.Timer(
                (next_refresh - datetime.now()).total_seconds(), 
                auto_refresh_tokens
            )
            current_timer.start()

def auto_refresh_tokens():

    print('Bắt đầu tự động làm mới')
    new_access_tokens = refresh_access_tokens()

    # Cập nhật lịch sử làm mới
    update_refresh_history(len(new_access_tokens))

    # Thêm độ trễ để đảm bảo có đủ khoảng cách giữa hai lần làm mới
    time.sleep(2)  # Chờ 1 giây

    # Sau khi làm mới xong, lên lịch làm mới tiếp theo
    schedule_next_refresh()

# Cập nhật lịch sử làm mới
def update_refresh_history(token_count):

    history = load_refresh_history()

    history.append({
        "timestamp": datetime.now().isoformat(),
        "token_count": token_count
    })

    # Giữ lại 5 bản ghi gần nhất
    history = history[-5:]

    save_refresh_history(history)

# Thiết lập nhiệm vụ định kỳ
@app.route('/set_auto_refresh', methods=['POST'])
@admin_required
def set_auto_refresh():
    data = request.json
    config = load_auto_refresh_config()

    # Hủy nhiệm vụ định kỳ hiện tại
    config['auto_refresh_enabled'] = data['enabled']
    config['refresh_interval_days'] = data['interval']
    save_auto_refresh_config(config)

    if config['auto_refresh_enabled']:
        schedule_next_refresh()

    return jsonify({"status": "success", "message": "Cài đặt tự động làm mới đã được cập nhật"})

# Tải thông tin cấu hình nhiệm vụ định kỳ
@app.route('/get_auto_refresh_config', methods=['GET'])
def get_auto_refresh_config():
    config = load_auto_refresh_config()
    return jsonify(config)

# Gọi hàm này khi ứng dụng khởi động
def init_auto_refresh():
    if not is_main_process():
        print("Trong quá trình reloader, bỏ qua khởi tạo bộ hẹn giờ")
        return
        
    print(f"Khởi tạo tự động làm mới trong tiến trình chính, thời gian hiện tại: {datetime.now()}")
    config = load_auto_refresh_config()

    if config['auto_refresh_enabled'] and config['next_refresh_time']:
        next_refresh = datetime.fromisoformat(config['next_refresh_time'])
        
        if next_refresh > datetime.now():
            delay_seconds = (next_refresh - datetime.now()).total_seconds()
            print(f"Thiết lập bộ hẹn giờ ban đầu, số giây trễ: {delay_seconds}")
            
            global current_timer
            with timer_lock:
                current_timer = threading.Timer(delay_seconds, auto_refresh_tokens)
                current_timer.start()
        else:
            schedule_next_refresh()

# Gọi khi ứng dụng khởi động
init_auto_refresh()

# Làm mới access token thủ công
@app.route('/refresh_tokens', methods=['POST'])
@admin_required
def refresh_tokens():
    try:
        # Gọi hàm làm mới access_token
        new_access_tokens = refresh_access_tokens()
        update_refresh_history(len(new_access_tokens))
        
        return jsonify({
            "status": "success",
            "access_tokens": new_access_tokens
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# -----------------------------------------------------Quản lý trang liên quan----------------------------


# Trang chủ GPT
@app.route('/chatgpt', methods=['GET', 'POST'])
@admin_required
def chatgpt():

    if request.method == 'GET':
        # Tải và hiển thị nội dung từ tệp chatToken.json
        retokens = load_retoken()
        return render_template('GPT.html', retokens=retokens)

    if request.method == 'POST':
        # Lấy dữ liệu retoken đã cập nhật
        new_retokens = request.json.get('retokens')
        
        # Nếu định dạng dữ liệu hợp lệ, lưu vào tệp
        if new_retokens:
            save_retoken(new_retokens)
            return jsonify({"status": "success", "message": "chatToken.json đã được cập nhật!"}), 200
        else:
            return jsonify({"status": "error", "message": "Định dạng dữ liệu không hợp lệ!"}), 400
        
# Trang chủ Claude
@app.route('/claude', methods=['GET', 'POST'])
@admin_required
def claude():

    if request.method == 'GET':
        # Tải và hiển thị nội dung từ tệp chatToken.json
        retokens = load_retoken()
        return render_template('claude.html', retokens=retokens)

    if request.method == 'POST':
        # Lấy dữ liệu retoken đã cập nhật
        new_retokens = request.json.get('retokens')
        
        # Nếu định dạng dữ liệu hợp lệ, lưu vào tệp
        if new_retokens:
            save_retoken(new_retokens)
            return jsonify({"status": "success", "message": "chatToken.json đã được cập nhật!"}), 200
        else:
            return jsonify({"status": "error", "message": "Định dạng dữ liệu không hợp lệ!"}), 400

#-----------------------------------------------------------Quản lý tài khoản GPT-----------------------------------------

# Tải lịch sử làm mới
@app.route('/refresh_history', methods=['GET'])
@admin_required
def get_refresh_history():
    refresh_history = load_refresh_history()
    return jsonify({
        "status": "success",
        "history": refresh_history
    }), 200

# Tải các Refresh Token thất bại
@app.route('/get_failed_tokens')
@admin_required
def get_failed_tokens():
    try:
        with open('json/failed_tokens.json', 'r') as file:
            failed_tokens = json.load(file)
        return jsonify(failed_tokens), 200
    except FileNotFoundError:
        return jsonify([]), 200  # Nếu tệp không tồn tại, trả về danh sách trống
    except json.JSONDecodeError:
        return jsonify({"error": "JSON không hợp lệ trong failed_tokens.json"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

# Tải Refresh Token
@app.route('/get_tokens')
@admin_required
def get_tokens():
    try:
        with open('json/chatToken.json', 'r') as file:
            tokens = json.load(file)
        return jsonify(tokens), 200
    except FileNotFoundError:
        return jsonify([]), 200  # Nếu tệp không tồn tại, trả về danh sách trống
    except json.JSONDecodeError:
        return jsonify({"error": "JSON không hợp lệ trong tokens.json"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Thêm tài khoản mới
@app.route('/api/tokens', methods=['POST'])
@admin_required
def create_tokens():
    data = request.get_json()
    tokens = load_retoken()
    
    # Kiểm tra tài khoản đã tồn tại hay chưa
    if any(token['email'] == data['email'] for token in tokens):
        return jsonify({'success': False, 'message': 'Tài khoản này đã tồn tại'}), 400
    
    new_token = {
        'email': data['email'],
        'refresh_token': data['ReToken'],
        'access_token': data['AcToken'],
        'status': True,
        'type':"/static/gpt.png",
        'PLUS': data['PLUS']
    }
    
    tokens.append(new_token)
    save_retoken(tokens)
    
    return jsonify({'success': True, 'message': 'Tạo tài khoản thành công'})

# Cập nhật thông tin tài khoản
@app.route('/api/tokens/<email>', methods=['PUT'])
@admin_required
def update_token(email):
    data = request.get_json()
    tokens = load_retoken()
    
    token_index = next((i for i, token in enumerate(tokens) if token['email'] == email), None)
    if token_index is None:
        return jsonify({'success': False, 'message': 'Tài khoản không tồn tại'}), 404

    
    # Nếu cung cấp email, cập nhật email
    if data.get('email'):
        tokens[token_index]['email'] = data['email']
    
    # Nếu cung cấp ReToken, cập nhật ReToken
    if data.get('ReToken'):
        tokens[token_index]['refresh_token'] = data['ReToken']
    else:
        tokens[token_index]['refresh_token'] = ''

    # Nếu cung cấp AcToken, cập nhật AcToken
    if data.get('AcToken'):
        tokens[token_index]['access_token'] = data['AcToken']
        tokens[token_index]['status'] = True
    else:
        tokens[token_index]['access_token'] = ''
    if data.get('PLUS'):
        tokens[token_index]['PLUS'] = data['PLUS']
    save_retoken(tokens)
    return jsonify({'success': True, 'message': 'Cập nhật tài khoản thành công'})

# Xóa tài khoản
@app.route('/api/tokens/<email>', methods=['DELETE'])
@admin_required
def delete_token(email):
    tokens = load_retoken()
    
    # Lọc bỏ tài khoản cần xóa
    updated_tokens = [token for token in tokens if token['email'] != email]
    
    if len(updated_tokens) == len(tokens):
        return jsonify({'success': False, 'message': 'Tài khoản không tồn tại'}), 404
    
    save_retoken(updated_tokens)
    return jsonify({'success': True, 'message': 'Xóa tài khoản thành công'})

# Tải Claude Token
@app.route('/get_Claude')
@admin_required
def get_Claude():
    try:
        with open('json/claudeToken.json', 'r') as file:
            tokens = json.load(file)
        return jsonify(tokens), 200
    except FileNotFoundError:
        return jsonify([]), 200  # Nếu tệp không tồn tại, trả về danh sách trống
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON in tokens.json"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Thêm tài khoản mới
@app.route('/api/Claude', methods=['POST'])
@admin_required
def create_Claude():
    data = request.get_json()
    tokens = load_cltoken()
    
    # Kiểm tra tài khoản đã tồn tại hay chưa
    if any(token['email'] == data['email'] for token in tokens):
        return jsonify({'success': False, 'message': 'Tài khoản đã tồn tại'}), 400
    
    new_token = {
        'email': data['email'],
        'skToken': data['SkToken'],
        'status': True,
        'type':"/static/claude.png",
        'PLUS': data['PLUS']
    }
    
    tokens.append(new_token)
    save_cltoken(tokens)
    
    return jsonify({'success': True, 'message': 'Tạo tài khoản thành công'})

# Cập nhật thông tin tài khoản
@app.route('/api/Claude/<email>', methods=['PUT'])
@admin_required
def update_Claude(email):
    data = request.get_json()
    tokens = load_cltoken()
    
    token_index = next((i for i, token in enumerate(tokens) if token['email'] == email), None)
    if token_index is None:
        return jsonify({'success': False, 'message': 'Tài khoản không tồn tại'}), 404

    
    # Nếu cung cấp email, cập nhật email
    if data.get('email'):
        tokens[token_index]['email'] = data['email']
    
    # Nếu cung cấp ReToken, cập nhật ReToken
    if data.get('SkToken'):
        tokens[token_index]['skToken'] = data['SkToken']
        tokens[token_index]['status'] = True
    
    if data.get('PLUS'):
        tokens[token_index]['PLUS'] = data['PLUS']
    save_cltoken(tokens)
    return jsonify({'success': True, 'message': 'Cập nhật tài khoản thành công'})

# Xóa tài khoản
@app.route('/api/Claude/<email>', methods=['DELETE'])
@admin_required
def delete_Claude(email):
    tokens = load_cltoken()
    
    # Lọc bỏ tài khoản cần xóa
    updated_tokens = [token for token in tokens if token['email'] != email]
    
    if len(updated_tokens) == len(tokens):
        return jsonify({'success': False, 'message': 'Tài khoản không tồn tại'}), 404
    
    save_cltoken(updated_tokens)
    return jsonify({'success': True, 'message': 'Xóa tài khoản thành công'})
USERS_FILE = 'json/user.json'

@app.route('/user')
@admin_required
def user_management():
    return render_template('user_management.html')



# Lấy tất cả người dùng
@app.route('/api/users', methods=['GET'])
@admin_required
def get_users():
    users = load_users()
    # Trả về danh sách người dùng mà không bao gồm thông tin mật khẩu
    return jsonify([{k: v for k, v in user.items() if k != 'password'} for user in users])

# Tạo người dùng mới
@app.route('/api/users', methods=['POST'])
@admin_required
def create_user():
    data = request.get_json()
    users = load_users()
    
    # Kiểm tra xem tên người dùng đã tồn tại chưa
    if any(user['username'] == data['username'] for user in users):
        return jsonify({'success': False, 'message': 'Tên người dùng đã tồn tại'}), 400
    
    new_user = {
        'id': str(uuid.uuid4()),
        'username': data['username'],
        'password': generate_password_hash(data['password']),
        'role': data['role']
    }
    
    users.append(new_user)
    save_users(users)
    
    return jsonify({'success': True, 'message': 'Tạo người dùng thành công'})

# Cập nhật thông tin người dùng
@app.route('/api/users/<user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    data = request.get_json()
    users = load_users()
    
    user_index = next((i for i, user in enumerate(users) if user['id'] == user_id), None)
    if user_index is None:
        return jsonify({'success': False, 'message': 'Người dùng không tồn tại'}), 404
    
    # Kiểm tra xem tên người dùng có xung đột với người dùng khác không
    if any(user['username'] == data['username'] and user['id'] != user_id for user in users):
        return jsonify({'success': False, 'message': 'Tên người dùng đã tồn tại'}), 400
    
    # Cập nhật thông tin người dùng
    users[user_index]['username'] = data['username']
    users[user_index]['role'] = data['role']
    
    # Nếu cung cấp mật khẩu mới, cập nhật mật khẩu
    if data.get('password'):
        users[user_index]['password'] = generate_password_hash(data['password'])
    
    save_users(users)
    return jsonify({'success': True, 'message': 'Cập nhật người dùng thành công'})

# Xóa người dùng
@app.route('/api/users/<user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    users = load_users()
    
    # Lọc bỏ người dùng cần xóa
    updated_users = [user for user in users if user['id'] != user_id]
    
    if len(updated_users) == len(users):
        return jsonify({'success': False, 'message': 'Người dùng không tồn tại'}), 404
    
    save_users(updated_users)
    return jsonify({'success': True, 'message': 'Xóa người dùng thành công'})

# Khởi động ứng dụng Flask
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)

@app.route('/api/logout-token', methods=['POST'])
@login_required
def logout_token():
    data = request.get_json()
    token_type = data.get('type')  # 'ChatGPT' hoặc 'Claude'
    token_index = data.get('index')
    
    try:
        if token_type == 'ChatGPT':
            tokens = load_retoken()
            if 0 <= token_index < len(tokens):
                tokens[token_index]['access_token'] = ''  # Xóa access token
                save_retoken(tokens)
        else:
            tokens = load_cltoken()
            if 0 <= token_index < len(tokens):
                tokens[token_index]['skToken'] = ''  # Xóa Claude token
                save_cltoken(tokens)
                
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
