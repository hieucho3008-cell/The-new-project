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
# [5] CONFIGURATION SETTINGS (BIẾN CẤU HÌNH)
# ==========================================
CONFIG = {
    "MAX_TIME": 60,              # Thời gian chạy bài test (giây)
    "FILTER_WINDOW": 5,          # Độ lớn cửa sổ lọc nhiễu Moving Average
    "THRESH_NORM_REPS": 70,      # Ngưỡng Reps bình thường
    "THRESH_MILD_REPS": 50,      # Ngưỡng Reps nhẹ
    "THRESH_MOD_REPS": 30,       # Ngưỡng Reps trung bình
    "THRESH_NORM_DECAY": 10.0,   # Ngưỡng sụt giảm biên độ bình thường (%)
    "THRESH_MILD_DECAY": 20.0,   # Ngưỡng sụt giảm biên độ nhẹ (%)
    "THRESH_MOD_DECAY": 40.0,    # Ngưỡng sụt giảm biên độ trung bình (%)
}

# ==========================================
# [1] NORMALIZED AMPLITUDE FUNCTION WITH FILTER
# ==========================================
def calculate_normalized_amplitude(hand):
    """
    Tính biên độ chuẩn hóa để không phụ thuộc vào khoảng cách xa/gần camera
    """
    if "lmList" in hand and len(hand["lmList"]) >= 13:
        p0 = hand["lmList"][0]   # Wrist (Cổ tay)
        p5 = hand["lmList"][5]   # Index Finger Base (Gốc ngón trỏ)
        p12 = hand["lmList"][12] # Middle Finger Tip (Đầu ngón giữa)
        
        # 1. Khoảng cách động tác thực tế (Wrist -> Middle Tip)
        act_dist = ((p12[0] - p0[0])**2 + (p12[1] - p0[1])**2) ** 0.5
        
        # 2. Khoảng cách tham chiếu cố định của bàn tay (Wrist -> Index Base)
        ref_dist = ((p5[0] - p0[0])**2 + (p5[1] - p0[1])**2) ** 0.5
        
        if ref_dist > 0:
            # Trả về giá trị chuẩn hóa (tỷ lệ phần trăm)
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

# [2] Khởi tạo hàng đợi để làm mịn dữ liệu biên độ (Moving Average Filter)
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

            # Gọi hàm tính biên độ chuẩn hóa
            raw_amplitude += calculate_normalized_amplitude(hand)

            if hand["type"] == "Left":
                left_count = fingers
            elif hand["type"] == "Right":
                right_count = fingers

        raw_amplitude = raw_amplitude / len(hands)
        
        # [2] Bộ lọc nhiễu: Chỉ xử lý khi biên độ hợp lệ (>0)
        if raw_amplitude > 0:
            amplitude_filter_queue.append(raw_amplitude)
            
        # Tính toán giá trị sau khi đã làm mịn bằng bộ lọc Moving Average
        current_amplitude = sum(amplitude_filter_queue) / len(amplitude_filter_queue) if amplitude_filter_queue else 0.0

        if test_started and not paused and current_amplitude > 0:
            exercise.update(finger_count)
            amplitude_history.append(current_amplitude)
    else:
        current_amplitude = 0.0

    # ==========================
    # TIMER LOGIC
    # ==========================
    if test_started and not paused:
        elapsed = time.time() - stats.start_time - total_pause_time
        
        # Chia đôi 60s thành 2 pha độc lập để đo Fatigue Index (Sequence Effect)
        if elapsed <= (CONFIG["MAX_TIME"] / 2):
            if current_amplitude > 0:
                first_half_amplitude.append(current_amplitude)
        else:
            if current_amplitude > 0:
                second_half_amplitude.append(current_amplitude)
    elif paused:
        elapsed = elapsed_before_pause
    else:
        elapsed = 0

    remaining_time = max(0, CONFIG["MAX_TIME"] - int(elapsed))

    # ==========================
    # SPEED & AMPLITUDE LOSS
    # ==========================
    speed = (elapsed / exercise.repetitions) if exercise.repetitions > 0 else 0
    avg_amplitude = (sum(amplitude_history) / len(amplitude_history)) if amplitude_history else 0

    if first_half_amplitude and second_half_amplitude:
        first_avg = sum(first_half_amplitude) / len(first_half_amplitude)
        second_avg = sum(second_half_amplitude) / len(second_half_amplitude)
        amplitude_decrement = (((first_avg - second_avg) / first_avg) * 100) if first_avg > 0 else 0
    else:
        amplitude_decrement = 0
    
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

    session_status = "FINISHED" if finished else ("PAUSED" if paused else ("RUNNING" if test_started else "READY"))
    status = "OPEN" if finger_count >= 4 else ("CLOSED" if finger_count <= 1 else "MOVING")
    color = (0, 200, 0) if status == "OPEN" else ((0, 0, 220) if status == "CLOSED" else (0, 180, 220))

    # ==========================
    # BACKGROUND UI PANEL
    # ==========================
    cv2.putText(img, "HAND DEXTERITY ASSESSMENT", (35, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2)
    
    cv2.putText(img, f"Left Hand : {left_count}", (35, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (50, 50, 50), 2)
    cv2.putText(img, f"Right Hand : {right_count}", (35, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (50, 50, 50), 2)
    cv2.putText(img, f"Total Fingers : {finger_count}", (35, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 0, 0), 2)
    cv2.putText(img, f"Status : {status}", (35, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
    cv2.putText(img, f"Repetitions : {exercise.repetitions}", (35, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)
    cv2.putText(img, f"Session : {session_status}", (35, 310), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 0, 0), 2)
    cv2.putText(img, f"Time Left : {remaining_time} sec", (35, 350), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 0, 255), 2)
    
    cv2.putText(img, last_result, (35, 410), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (120, 0, 255), 2)
    cv2.putText(img, f"Total Sessions : {len(session_history)}", (35, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)
    cv2.putText(img, f"Avg Reps : {avg_reps:.1f}", (35, 490), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 150, 0), 2)
    cv2.putText(img, f"Avg Speed : {avg_speed:.2f} sec/cycle", (35, 530), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (150, 0, 150), 2)
    cv2.putText(img, f"Best Reps : {best_reps}", (35, 570), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (200, 0, 0), 2)
    
    cv2.putText(img, f"Norm Amp : {current_amplitude:.1f}%", (35, 630), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 100, 0), 2)
    cv2.putText(img, f"Amplitude Loss : {amplitude_decrement:.1f}%", (35, 670), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)

    # Bảng phím tắt điều khiển góc phải
    cv2.putText(img, "B = Start", (950, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 200, 0), 2)
    cv2.putText(img, "P = Pause / Resume", (950, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 200, 220), 2)
    cv2.putText(img, "R = Reset All", (950, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (200, 0, 0), 2)
    cv2.putText(img, "ESC = Exit", (950, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 200), 2)

    # ==========================================
    # [4] PROGRESS BAR UI NÂNG CAO (THANH TIẾN TRÌNH)
    # ==========================================
    if test_started and not paused:
        progress_ratio = elapsed / CONFIG["MAX_TIME"]
        bar_start_x, bar_end_x = 550, 1230
        bar_y = 680
        current_bar_x = int(bar_start_x + (bar_end_x - bar_start_x) * progress_ratio)
        
        # Vẽ thanh nền xám mờ
        cv2.rectangle(img, (bar_start_x, bar_y), (bar_end_x, bar_y + 15), (220, 220, 220), -1)
        # Vẽ thanh tiến trình động màu tím hồng
        cv2.rectangle(img, (bar_start_x, bar_y), (current_bar_x, bar_y + 15), (255, 0, 180), -1)

    # ==========================================
    # CLINICAL EVALUATION REPORT (POPUP SCREEN)
    # ==========================================
    if finished:
        overlay = img.copy()
        cv2.rectangle(overlay, (0, 0), (1280, 720), (30, 30, 30), -1)
        cv2.addWeighted(overlay, 0.75, img, 0.25, 0, img)

        bx1, by1, bx2, by2 = 220, 100, 1060, 620
        cv2.rectangle(img, (bx1, by1), (bx2, by2), (255, 255, 255), -1)
        cv2.rectangle(img, (bx1, by1), (bx2, by2), (0, 80, 180), 4)

        cv2.putText(img, "PARKINSON MOTOR ASSESSMENT REPORT", (bx1 + 130, by1 + 45), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 80, 180), 3)
        cv2.line(img, (bx1 + 40, by1 + 70), (bx2 - 40, by1 + 70), (220, 220, 220), 2)

        cv2.putText(img, f"Total Repetitions :  {final_reps} cycles (Norm: >{CONFIG['THRESH_NORM_REPS']})", (bx1 + 50, by1 + 115), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (50, 50, 50), 2)
        cv2.putText(img, f"Average Velocity  :  {final_speed:.2f} sec/cycle (Norm: <0.8s)", (bx1 + 50, by1 + 145), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (50, 50, 50), 2)
        cv2.putText(img, f"Mean Norm Amp     :  {final_amplitude:.1f}% (Normalized Scale)", (bx1 + 50, by1 + 175), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (50, 50, 50), 2)
        cv2.putText(img, f"Amplitude Decay   :  {final_decrement:.1f}% (Norm: <{CONFIG['THRESH_NORM_DECAY']}%誤差)", (bx1 + 50, by1 + 205), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (50, 50, 50), 2)
        cv2.line(img, (bx1 + 40, by1 + 225), (bx2 - 40, by1 + 225), (240, 240, 240), 1)

        # --- LOGIC PHÂN CẤP SỬ DỤNG BIẾN TOÀN CỤC CONFIG ---
        if final_reps < CONFIG["THRESH_MOD_REPS"] or final_speed > 2.0 or final_decrement > CONFIG["THRESH_MOD_DECAY"]:
            assessment_str = "SEVERE PROFILE (Severe Bradykinesia & Hypokinesia)"
            status_color = (0, 0, 220)
            advice_lines = [
                "Clinical Analysis: High motor degradation and severe amplitude decay detected.",
                "1. Strongly advise scheduling an examination with a neurologist as soon as possible.",
                "2. Note down daily life motor errors (e.g., small handwriting, shaking, stiffness).",
                "3. This software is only a screening aid; please do not panic and seek hospital tests."
            ]
        elif CONFIG["THRESH_MOD_REPS"] <= final_reps <= CONFIG["THRESH_MILD_REPS"] or 1.2 <= final_speed <= 2.0 or CONFIG["THRESH_MILD_DECAY"] <= final_decrement <= CONFIG["THRESH_MOD_DECAY"]:
            assessment_str = "MODERATE PROFILE (Significant Motor Slowdown)"
            status_color = (0, 69, 255)
            advice_lines = [
                "Clinical Analysis: Clear signs of bradykinesia and reduced movement range observed.",
                "1. Recommended to visit a neurology clinic for professional clinical evaluation.",
                "2. Avoid any excessive hand fatigue or manual work right before taking future tests.",
                "3. Keep records/screenshots of this report history to present to your physician."
            ]
        elif CONFIG["THRESH_MILD_REPS"] < final_reps <= CONFIG["THRESH_NORM_REPS"] or 0.8 <= final_speed < 1.2 or CONFIG["THRESH_NORM_DECAY"] <= final_decrement < CONFIG["THRESH_MILD_DECAY"]:
            assessment_str = "MILD PROFILE (Early Motor Fatigue / Slight Slowdown)"
            status_color = (0, 165, 255)
            advice_lines = [
                "Clinical Analysis: Minor slowdown or hand muscular fatigue detected near the end of session.",
                "1. Retest for 3-5 days at fixed hours to verify if this fatigue pattern is consistent.",
                "2. Perform targeted fine-motor exercises at home (finger tapping, squeezing soft rubber balls).",
                "3. Ensure adequate rest (>7 hours of sleep) and avoid high stress before testing again."
            ]
        else:
            assessment_str = "NORMAL PROFILE (Healthy Motor Control & Speed)"
            status_color = (0, 180, 0)
            advice_lines = [
                "Clinical Analysis: Excellent speed and highly stable movement range maintained throughout.",
                "1. No abnormal clinical signs of bradykinesia or neuromuscular fatigue were found.",
                "2. Continue regular active physical exercise and routine checkups to preserve health.",
                "3. Feel free to re-test on a monthly basis to monitor your long-term neuromotor trends."
            ]

        cv2.putText(img, "Diagnostic Evaluation:", (bx1 + 50, by1 + 250), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2)
        cv2.putText(img, assessment_str, (bx1 + 270, by1 + 250), cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_color, 2)
        
        cv2.rectangle(img, (bx1 + 40, by1 + 280), (bx2 - 40, by1 + 490), (250, 250, 250), -1)
        cv2.rectangle(img, (bx1 + 40, by1 + 280), (bx2 - 40, by1 + 490), (230, 230, 230), 1)

        y_offset = by1 + 315
        for line in advice_lines:
            cv2.putText(img, line, (bx1 + 60, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (40, 40, 40), 1, cv2.LINE_AA)
            y_offset += 40

        cv2.line(img, (bx1 + 40, by1 + 520), (bx2 - 40, by1 + 520), (220, 220, 220), 2)
        cv2.putText(img, "Press 'C' to Close & Save  |  Press 'R' to Reset System Data", (bx1 + 155, by1 + 560), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (100, 100, 100), 2)

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
        stats.start_time = time.time()
        total_pause_time = 0
        raw_amplitude = 0.0
        avg_amplitude = 0
        amplitude_decrement = 0
        amplitude_history.clear()
        first_half_amplitude.clear()
        second_half_amplitude.clear()
        amplitude_filter_queue.clear()
        exercise.repetitions = 0

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
        amplitude_history.clear()
        first_half_amplitude.clear()
        second_half_amplitude.clear()
        amplitude_filter_queue.clear()
        exercise.repetitions = 0

    elif key == ord('r'):
        exercise.repetitions = 0
        test_started = False
        paused = False
        finished = False
        total_pause_time = 0
        avg_amplitude = 0
        amplitude_decrement = 0
        amplitude_history.clear()
        first_half_amplitude.clear()
        second_half_amplitude.clear()
        amplitude_filter_queue.clear()
        last_result = "No previous session"
        session_history.clear()

    elif key == 27:
        break

cap.release()
cv2.destroyAllWindows()
