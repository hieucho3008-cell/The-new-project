import cv2
import time
import os
import sys
from collections import deque

# Thêm thư mục src vào hệ thống nếu chạy từ ngoài thư mục gốc
sys.path.append(os.path.join(os.path.dirname(__file__)))

from hand_detector import HandDetector
from finger_counter import count_fingers
from exercise_logic import DexterityExercise
from statistics import Statistics

# ==========================================
# CONFIGURATION SETTINGS (BIẾN CẤU HÌNH VÀ NGƯỠNG LÂM SÀNG)
# ==========================================
CONFIG = {
    "MAX_TIME": 60,              # Tổng thời gian chạy bài test (bao gồm cả thời gian Calibrate)
    "CALIBRATION_TIME": 3,       # 3 giây đầu tiên để Hiệu chuẩn (Calibrate) Baseline bàn tay
    "FILTER_WINDOW": 5,          # Cửa sổ lọc nhiễu Moving Average
    "THRESH_NORM_REPS": 70,      # Bình thường: > 70 reps
    "THRESH_MOD_REPS": 40,       # Nguy cơ cao: < 40 reps
    "THRESH_NORM_SPEED": 0.8,    # Bình thường: < 0.8 s/cycle
    "THRESH_MOD_SPEED": 1.5,     # Nguy cơ cao: > 1.5 s/cycle
    "THRESH_NORM_DECAY": 10.0,   # Bình thường sụt giảm biên độ mỏi cơ: < 10%
    "THRESH_MOD_DECAY": 25.0,    # Nguy cơ cao sụt giảm biên độ mỏi cơ: > 25%
}

# ==========================================
# TỰ ĐỘNG XỬ LÝ XUỐNG DÒNG CHO VĂN BẢN DÀI
# ==========================================
def wrap_text(text, max_chars):
    """Bọc văn bản thành danh sách các dòng với số ký tự tối đa quy định để chống tràn chữ"""
    words = text.split()
    lines = []
    current_line = []
    current_length = 0
    for word in words:
        if current_length + len(word) + len(current_line) <= max_chars:
            current_line.append(word)
            current_length += len(word)
        else:
            lines.append(" ".join(current_line))
            current_line = [word]
            current_length = len(word)
    if current_line:
        lines.append(" ".join(current_line))
    return lines

# ==========================================
# BIÊN ĐỘ CHUẨN HÓA DỰA TRÊN XƯƠNG BÀN TAY
# ==========================================
def calculate_normalized_amplitude(hand):
    """Tính tỷ lệ khoảng cách động tác dựa trên chiều dài xương gốc bàn tay để chống sai số xa gần"""
    if "lmList" in hand and len(hand["lmList"]) >= 13:
        p0 = hand["lmList"][0]   # Wrist (Cổ tay)
        p5 = hand["lmList"][5]   # Index Finger Base (Gốc ngón trỏ)
        p12 = hand["lmList"][12] # Middle Finger Tip (Đầu ngón giữa)
        
        act_dist = ((p12[0] - p0[0])**2 + (p12[1] - p0[1])**2) ** 0.5
        ref_dist = ((p5[0] - p0[0])**2 + (p5[1] - p0[1])**2) ** 0.5
        
        if ref_dist > 0:
            return (act_dist / ref_dist) * 100
    return 0.0

# ==========================
# CAMERA CONFIGURATION
# ==========================
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

# ==========================
# OBJECTS INITIALIZATION
# ==========================
detector = HandDetector()
exercise = DexterityExercise()
stats = Statistics()

# Hàng đợi lọc làm mịn tín hiệu
amplitude_filter_queue = deque(maxlen=CONFIG["FILTER_WINDOW"])

# ==========================
# SESSION VARIABLES
# ==========================
test_started = False
paused = False
finished = False

pause_start = 0
total_pause_time = 0
elapsed_before_pause = 0

last_result = "No previous session"
session_history = []

avg_reps = 0
avg_speed = 0
best_reps = 0

# Các biến phục vụ thuật toán Peak-Detection và Calibration
calibration_amplitudes = []
calibration_baseline = 1.0  # Mặc định để tránh lỗi chia cho 0
is_calibrating = False
prev_status = "CLOSED"

amplitude_history = []
first_half_amplitude = []
second_half_amplitude = []
avg_amplitude = 0
amplitude_decrement = 0

final_reps = 0
final_speed = 0
final_amplitude = 0
final_decrement = 0

# ==========================
# MAIN LOOP
# ==========================
while True:
    success, img = cap.read()
    if not success:
        break

    img = cv2.flip(img, 1)
    hands, img = detector.find_hands(img)

    # ==========================
    # HAND DETECTION & METRICS
    # ==========================
    finger_count = 0
    left_count = 0
    right_count = 0
    raw_amplitude = 0.0

    if len(hands) > 0:
        for hand in hands:
            fingers = count_fingers(hand)
            finger_count += fingers
            raw_amplitude += calculate_normalized_amplitude(hand)

            if hand["type"] == "Left":
                left_count = fingers
            elif hand["type"] == "Right":
                right_count = fingers

        raw_amplitude = raw_amplitude / len(hands)
        
        # Áp dụng bộ lọc Moving Average để làm mịn biên độ liên tục
        if raw_amplitude > 0:
            amplitude_filter_queue.append(raw_amplitude)
            
        current_amplitude = sum(amplitude_filter_queue) / len(amplitude_filter_queue) if amplitude_filter_queue else 0.0
    else:
        current_amplitude = 0.0

    # Xác định trạng thái đóng mở real-time
    status = "OPEN" if finger_count >= 4 else ("CLOSED" if finger_count <= 1 else "MOVING")

    # ==========================
    # TIMER & CALIBRATION LOGIC
    # ==========================
    if test_started and not paused:
        elapsed = time.time() - stats.start_time - total_pause_time
        
        # GIAI ĐOẠN 1: TỰ ĐỘNG HIỆU CHUẨN (3 GIÂY ĐẦU)
        if elapsed <= CONFIG["CALIBRATION_TIME"]:
            is_calibrating = True
            session_status = "CALIBRATING... OPEN HAND WIDE"
            if current_amplitude > 0:
                calibration_amplitudes.append(current_amplitude)
        
        # GIAI ĐOẠN 2: BẮT ĐẦU ĐẾM VÀ TÍNH TOÁN LÂM SÀNG
        else:
            if is_calibrating:
                is_calibrating = False
                if calibration_amplitudes:
                    calibration_baseline = sum(calibration_amplitudes) / len(calibration_amplitudes)
                else:
                    calibration_baseline = 100.0
            
            session_status = "RUNNING"
            exercise.update(finger_count)

            # Tính biên độ theo tỷ lệ % so với Baseline (Đã Calibrate)
            scaled_amplitude = (current_amplitude / calibration_baseline) * 100 if calibration_baseline > 0 else 0.0

            # THUẬT TOÁN PEAK-DETECTION (BẮT ĐỈNH)
            if prev_status != "OPEN" and status == "OPEN" and scaled_amplitude > 0:
                amplitude_history.append(scaled_amplitude)
                
                test_active_time = CONFIG["MAX_TIME"] - CONFIG["CALIBRATION_TIME"]
                mid_point = CONFIG["CALIBRATION_TIME"] + (test_active_time / 2)
                
                if elapsed <= mid_point:
                    first_half_amplitude.append(scaled_amplitude)
                else:
                    second_half_amplitude.append(scaled_amplitude)
                    
    elif paused:
        elapsed = elapsed_before_pause
        session_status = "PAUSED"
    else:
        elapsed = 0
        session_status = "READY"

    if finished:
        session_status = "FINISHED"

    prev_status = status  
    remaining_time = max(0, CONFIG["MAX_TIME"] - int(elapsed))

    # ĐỊNH NGHĨA SỚM BIẾN ĐỂ TRÁNH LỖI NAMEERROR KHI CHƯA CHẠY BÀI TEST
    display_amp = (current_amplitude / calibration_baseline) * 100 if test_started and not is_calibrating else 0.0

    # ==========================
    # SPEED & AMPLITUDE LOSS
    # ==========================
    actual_test_elapsed = max(0, elapsed - CONFIG["CALIBRATION_TIME"])
    speed = (actual_test_elapsed / exercise.repetitions) if exercise.repetitions > 0 else 0
    avg_amplitude = (sum(amplitude_history) / len(amplitude_history)) if amplitude_history else 0.0

    if first_half_amplitude and second_half_amplitude:
        first_avg = sum(first_half_amplitude) / len(first_half_amplitude)
        second_avg = sum(second_half_amplitude) / len(second_half_amplitude)
        amplitude_decrement = (((first_avg - second_avg) / first_avg) * 100) if first_avg > 0 else 0.0
        if amplitude_decrement < 0: 
            amplitude_decrement = 0.0
    else:
        amplitude_decrement = 0.0
    
    # ==========================
    # AUTOMATIC SESSION FINISH
    # ==========================
    if remaining_time == 0 and test_started:
        paused = True
        test_started = False
        finished = True

        final_reps = exercise.repetitions
        final_speed = speed
        final_amplitude = avg_amplitude
        final_decrement = amplitude_decrement

        session_history.append({"reps": final_reps, "speed": final_speed})
        last_result = f"Last Session: {final_reps} reps | {final_speed:.2f} sec/cycle"

    if session_history:
        avg_reps = sum(s["reps"] for s in session_history) / len(session_history)
        avg_speed = sum(s["speed"] for s in session_history) / len(session_history)
        best_reps = max(s["reps"] for s in session_history)
    else:
        avg_reps = avg_speed = best_reps = 0

    # =========================================================================
    # BACKGROUND UI PANEL - PHỐI MÀU THEO PHONG CÁCH MONITOR Y TẾ (DARK MODE)
    # =========================================================================
    # Nền panel bên trái màu xám đen/đen tuyền huyền bí của monitor chuyên dụng
    cv2.rectangle(img, (20, 20), (520, 700), (15, 15, 15), -1)
    cv2.rectangle(img, (20, 20), (520, 700), (50, 50, 50), 2) 
    
    # Tiêu đề chính - Chữ trắng tinh khiết nổi bật
    cv2.putText(img, "HAND DEXTERITY ASSESSMENT", (35, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2)
    cv2.line(img, (35, 75), (505, 75), (40, 40, 40), 1)
    
    # 1. NHÓM CHỈ SỐ CƠ HỌC -> Xanh lá Neon dịu mát (0, 230, 0)
    cv2.putText(img, f"Left Hand : {left_count}", (35, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 230, 0), 2)
    cv2.putText(img, f"Right Hand : {right_count}", (35, 155), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 230, 0), 2)
    cv2.putText(img, f"Total Fingers : {finger_count}", (35, 195), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 230, 0), 2)
    cv2.putText(img, f"Repetitions : {exercise.repetitions}", (35, 235), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 230, 0), 2)
    
    # 2. NHÓM TRẠNG THÁI HỆ THỐNG -> Xanh dương Monitor / Cyan sắc sảo (255, 220, 0)
    cv2.putText(img, f"Status : {status}", (35, 285), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 220, 0), 2)
    cv2.putText(img, f"Session : {session_status}", (35, 325), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 220, 0), 2)
    
    # 3. THỜI GIAN ĐẾM NGƯỢC -> Đỏ Cam Cảnh báo phản xạ nhanh (0, 60, 240)
    cv2.putText(img, f"Time Left : {remaining_time} sec", (35, 375), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 60, 240), 2)
    cv2.line(img, (35, 400), (505, 400), (40, 40, 40), 1)
    
    # 4. LỊCH SỬ VÀ THỐNG KÊ -> Vàng Hổ Phách sang trọng (0, 210, 255)
    cv2.putText(img, last_result, (35, 440), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 210, 255), 2)
    cv2.putText(img, f"Total Sessions : {len(session_history)}", (35, 480), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 210, 255), 2)
    cv2.putText(img, f"Avg Reps : {avg_reps:.1f}", (35, 520), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 210, 255), 2)
    cv2.putText(img, f"Avg Speed : {avg_speed:.2f} sec/cycle", (35, 560), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 210, 255), 2)
    cv2.putText(img, f"Best Reps : {best_reps}", (35, 600), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 210, 255), 2)
    
    # 5. BIÊN ĐỘ VÀ ĐỘ MỎI CƠ -> Màu Đỏ Cam Monitor (0, 60, 240)
    cv2.putText(img, f"Peak Amp (Live) : {display_amp:.1f}%", (35, 650), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 60, 240), 2)
    cv2.putText(img, f"Amplitude Loss : {amplitude_decrement:.1f}%", (35, 680), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 60, 240), 2)

    # ĐOẠN ĐƯỢC ĐỔI THÀNH MÀU ĐEN (0, 0, 0) THEO YÊU CẦU
    cv2.putText(img, "B = Start Assessment", (900, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)
    cv2.putText(img, "P = Pause / Resume", (900, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)
    cv2.putText(img, "R = Reset System", (900, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)
    cv2.putText(img, "ESC = Exit", (900, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)

    # ==========================================
    # PROGRESS BAR UI (THANH TIẾN TRÌNH)
    # ==========================================
    if test_started and not paused:
        progress_ratio = elapsed / CONFIG["MAX_TIME"]
        bar_start_x, bar_end_x = 550, 1230
        bar_y = 680
        current_bar_x = int(bar_start_x + (bar_end_x - bar_start_x) * progress_ratio)
        
        cv2.rectangle(img, (bar_start_x, bar_y), (bar_end_x, bar_y + 15), (40, 40, 40), -1)
        cv2.rectangle(img, (bar_start_x, bar_y), (current_bar_x, bar_y + 15), (255, 200, 0), -1)

    # ==========================================
    # CLINICAL EVALUATION REPORT (POPUP SCREEN)
    # ==========================================
    if finished:
        overlay = img.copy()
        cv2.rectangle(overlay, (0, 0), (1280, 720), (15, 15, 15), -1)
        cv2.addWeighted(overlay, 0.85, img, 0.15, 0, img)

        bx1, by1, bx2, by2 = 180, 60, 1100, 660
        cv2.rectangle(img, (bx1, by1), (bx2, by2), (25, 25, 25), -1) 
        cv2.rectangle(img, (bx1, by1), (bx2, by2), (80, 80, 80), 2)  

        cv2.putText(img, "PARKINSON MOTOR ASSESSMENT REPORT", (bx1 + 180, by1 + 45), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 3)
        cv2.line(img, (bx1 + 40, by1 + 70), (bx2 - 40, by1 + 70), (60, 60, 60), 1)

        cv2.putText(img, f"Total Repetitions :  {final_reps} cycles (Norm: >{CONFIG['THRESH_NORM_REPS']})", (bx1 + 50, by1 + 115), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 2)
        cv2.putText(img, f"Average Velocity  :  {final_speed:.2f} sec/cycle (Norm: <{CONFIG['THRESH_NORM_SPEED']}s)", (bx1 + 50, by1 + 145), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 2)
        cv2.putText(img, f"Mean Peak Amplitude:  {final_amplitude:.1f}% (Calibrated Scale)", (bx1 + 50, by1 + 175), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 2)
        cv2.putText(img, f"Amplitude Decay   :  {final_decrement:.1f}% (Norm: <{CONFIG['THRESH_NORM_DECAY']}%誤差)", (bx1 + 50, by1 + 205), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 2)
        cv2.line(img, (bx1 + 40, by1 + 225), (bx2 - 40, by1 + 225), (60, 60, 60), 1)

        # --- LOGIC PHÂN LOẠI KẾT QUẢ POPUP ---
        if final_reps < CONFIG["THRESH_MOD_REPS"] or final_speed > CONFIG["THRESH_MOD_SPEED"] or final_decrement > CONFIG["THRESH_MOD_DECAY"]:
            assessment_str = "SEVERE PROFILE (Severe Bradykinesia & Hypokinesia)"
            advice_lines = [
                "1. Strongly advise scheduling an examination with a neurologist as soon as possible.",
                "2. Note down daily life motor errors (e.g., small handwriting, shaking, stiffness).",
                "3. This software is only a screening aid; please do not panic and seek hospital medical tests."
            ]
        elif CONFIG["THRESH_MOD_REPS"] <= final_reps <= CONFIG["THRESH_NORM_REPS"] or CONFIG["THRESH_NORM_SPEED"] <= final_speed <= CONFIG["THRESH_MOD_SPEED"] or CONFIG["THRESH_NORM_DECAY"] <= final_decrement <= CONFIG["THRESH_MOD_DECAY"]:
            if final_reps <= 50 or final_speed >= 1.2 or final_decrement >= 20.0:
                assessment_str = "MODERATE PROFILE (Significant Motor Slowdown)"
                advice_lines = [
                    "1. Recommended to visit a neurology clinic for professional clinical evaluation.",
                    "2. Avoid any excessive hand fatigue or manual work right before taking future tests.",
                    "3. Keep records/screenshots of this report history to present to your physician."
                ]
            else:
                assessment_str = "MILD PROFILE (Early Motor Fatigue / Slight Slowdown)"
                advice_lines = [
                    "1. Retest for 3-5 days at fixed hours to verify if this fatigue pattern is consistent.",
                    "2. Perform targeted fine-motor exercises at home (finger tapping, squeezing soft rubber balls).",
                    "3. Ensure adequate rest (>7 hours of sleep) and avoid high stress before testing again."
                ]
        else:
            assessment_str = "NORMAL PROFILE (Healthy Motor Control & Speed)"
            advice_lines = [
                "1. No abnormal clinical signs of bradykinesia or neuromuscular fatigue were found.",
                "2. Continue regular active physical exercise and routine checkups to preserve health.",
                "3. Feel free to re-test on a monthly basis to monitor your long-term neuromotor trends."
            ]

        cv2.putText(img, "Diagnostic Evaluation:", (bx1 + 50, by1 + 250), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 2)
        cv2.putText(img, assessment_str, (bx1 + 270, by1 + 250), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 210, 255), 2) 
        
        cv2.rectangle(img, (bx1 + 40, by1 + 280), (bx2 - 40, by1 + 530), (35, 35, 35), -1)
        cv2.rectangle(img, (bx1 + 40, by1 + 280), (bx2 - 40, by1 + 530), (50, 50, 50), 1)

        y_offset = by1 + 315
        for line in advice_lines:
            wrapped_lines = wrap_text(line, max_chars=85)
            for wrapped_line in wrapped_lines:
                cv2.putText(img, wrapped_line, (bx1 + 60, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (220, 220, 220), 1, cv2.LINE_AA)
                y_offset += 35

        cv2.line(img, (bx1 + 40, by1 + 560), (bx2 - 40, by1 + 560), (60, 60, 60), 2)
        cv2.putText(img, "Press 'C' to Close & Save  |  Press 'R' to Reset System Data", (bx1 + 210, by1 + 600), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (150, 150, 150), 2)

    # ==========================
    # WINDOW RENDERING
    # ==========================
    cv2.namedWindow("Hand Dexterity Assessment", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Hand Dexterity Assessment", 1280, 720)
    cv2.imshow("Hand Dexterity Assessment", img)

    # ==========================
    # KEYBOARD CONTROLS LOGIC
    # ==========================
    key = cv2.waitKey(1)

    if key == ord('b') and not test_started and not finished:
        test_started = True
        paused = False
        finished = False
        is_calibrating = True
        stats.start_time = time.time()
        total_pause_time = 0
        raw_amplitude = 0.0
        avg_amplitude = 0
        amplitude_decrement = 0
        calibration_baseline = 1.0
        calibration_amplitudes.clear()
        amplitude_history.clear()
        first_half_amplitude.clear()
        second_half_amplitude.clear()
        amplitude_filter_queue.clear()
        exercise.repetitions = 0
        prev_status = "CLOSED"

    elif key == ord('p'):
        if test_started:
            if not paused:
                paused = True
                pause_start = time.time()
                elapsed_before_pause = elapsed
            else:
                paused = False
                total_pause_time += (time.time() - pause_start)

    elif key == ord('c') and finished:
        finished = False
        test_started = False
        paused = False
        total_pause_time = 0
        avg_amplitude = 0
        amplitude_decrement = 0
        calibration_baseline = 1.0
        calibration_amplitudes.clear()
        amplitude_history.clear()
        first_half_amplitude.clear()
        second_half_amplitude.clear()
        amplitude_filter_queue.clear()
        exercise.repetitions = 0
        prev_status = "CLOSED"

    elif key == ord('r'):
        exercise.repetitions = 0
        test_started = False
        paused = False
        finished = False
        is_calibrating = False
        total_pause_time = 0
        avg_amplitude = 0
        amplitude_decrement = 0
        calibration_baseline = 1.0
        calibration_amplitudes.clear()
        amplitude_history.clear()
        first_half_amplitude.clear()
        second_half_amplitude.clear()
        amplitude_filter_queue.clear()
        last_result = "No previous session"
        session_history.clear()
        prev_status = "CLOSED"

    elif key == 27:
        break

cap.release()
cv2.destroyAllWindows()
