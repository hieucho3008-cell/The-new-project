import cv2
import time
import os
import sys

# Thêm thư mục src vào hệ thống nếu chạy từ ngoài thư mục gốc
sys.path.append(os.path.join(os.path.dirname(__file__)))

from hand_detector import HandDetector
from finger_counter import count_fingers
from exercise_logic import DexterityExercise
from statistics import Statistics

# Định nghĩa hàm tính amplitude trực tiếp tại đây để tránh lỗi thiếu file amplitude.py
def calculate_amplitude(hand):
    """
    Hàm tính biên độ (khoảng cách từ cổ tay đến ngón giữa hoặc lòng bàn tay)
    Thay đổi tùy thuộc vào cách bạn tracking, dưới đây là logic mẫu dựa trên lmList
    """
    if "lmList" in hand and len(hand["lmList"]) > 0:
        # Lấy tọa độ landmark 0 (Wrist - Cổ tay) và landmark 12 (Middle Finger Tip)
        p0 = hand["lmList"][0]
        p12 = hand["lmList"][12]
        # Tính khoảng cách Euclidean
        distance = ((p12[0] - p0[0])**2 + (p12[1] - p0[1])**2) ** 0.5
        return distance
    return 0

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

# ==========================
# SESSION VARIABLES
# ==========================
test_started = False
paused = False
finished = False

MAX_TIME = 60

pause_start = 0
total_pause_time = 0
elapsed_before_pause = 0

last_result = "No previous session"
session_history = []

avg_reps = 0
avg_speed = 0
best_reps = 0

amplitude_history = []
current_amplitude = 0
first_half_amplitude = []
second_half_amplitude = []
avg_amplitude = 0
amplitude_decrement = 0

# Biến tạm lưu kết quả đóng băng khi kết thúc phiên để hiện lên bảng báo cáo
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
    current_amplitude = 0

    if len(hands) > 0:
        for hand in hands:
            fingers = count_fingers(hand)
            finger_count += fingers

            amplitude = calculate_amplitude(hand)
            current_amplitude += amplitude

            if hand["type"] == "Left":
                left_count = fingers
            elif hand["type"] == "Right":
                right_count = fingers

        # Lấy trung bình amplitude nếu phát hiện cả 2 tay cùng lúc
        current_amplitude = current_amplitude / len(hands)

        if test_started and not paused:
            exercise.update(finger_count)
            amplitude_history.append(current_amplitude)

    # ==========================
    # TIMER LOGIC
    # ==========================
    if test_started and not paused:
        elapsed = time.time() - stats.start_time - total_pause_time
        
        # Chia đôi thời gian (30s đầu / 30s sau) để tính toán Fatigue Index (Độ suy giảm biên độ)
        if elapsed <= 30:
            if len(hands) > 0:
                first_half_amplitude.append(current_amplitude)
        else:
            if len(hands) > 0:
                second_half_amplitude.append(current_amplitude)
    elif paused:
        elapsed = elapsed_before_pause
    else:
        elapsed = 0

    remaining_time = max(0, MAX_TIME - int(elapsed))

    # ==========================
    # SPEED CALCULATION
    # ==========================
    if exercise.repetitions > 0:
        speed = elapsed / exercise.repetitions
    else:
        speed = 0

    # ==========================
    # AMPLITUDE STATISTICS
    # ==========================
    if len(amplitude_history) > 0:
        avg_amplitude = sum(amplitude_history) / len(amplitude_history)
    else:
        avg_amplitude = 0

    if len(first_half_amplitude) > 0 and len(second_half_amplitude) > 0:
        first_avg = sum(first_half_amplitude) / len(first_half_amplitude)
        second_avg = sum(second_half_amplitude) / len(second_half_amplitude)
        
        if first_avg > 0:
            amplitude_decrement = ((first_avg - second_avg) / first_avg) * 100
        else:
            amplitude_decrement = 0
    else:
        amplitude_decrement = 0
    
    # ==========================
    # AUTOMATIC SESSION FINISH
    # ==========================
    if remaining_time == 0 and test_started:
        paused = True
        test_started = False
        finished = True

        # Khóa dữ liệu của phiên hiện tại để nạp vào Popup báo cáo
        final_reps = exercise.repetitions
        final_speed = speed
        final_amplitude = avg_amplitude
        final_decrement = amplitude_decrement

        session_history.append({
            "reps": final_reps,
            "speed": final_speed
        })
        
        last_result = f"Last Session: {final_reps} reps | {final_speed:.2f} sec/cycle"

    if len(session_history) > 0:
        avg_reps = sum(s["reps"] for s in session_history) / len(session_history)
        avg_speed = sum(s["speed"] for s in session_history) / len(session_history)
        best_reps = max(s["reps"] for s in session_history)
    else:
        avg_reps = 0
        avg_speed = 0
        best_reps = 0

    # ==========================
    # STATUS TRACKING
    # ==========================
    if finished:
        session_status = "FINISHED"
    elif not test_started and elapsed == 0:
        session_status = "READY"
    elif paused:
        session_status = "PAUSED"
    else:
        session_status = "RUNNING"

    if finger_count >= 4:
        status = "OPEN"
        color = (0, 200, 0)
    elif finger_count <= 1:
        status = "CLOSED"
        color = (0, 0, 220)
    else:
        status = "MOVING"
        color = (0, 180, 220)

    # ==========================
    # BACKGROUND UI PANEL
    # ==========================
    # Vẽ bảng thông số real-time bên trái màn hình
    cv2.rectangle(img, (20, 20), (520, 700), (255, 255, 255), -1)
    cv2.putText(img, "HAND DEXTERITY ASSESSMENT", (35, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2)
    
    # Nhóm 1: Trạng thái hiện tại (Live)
    cv2.putText(img, f"Left Hand : {left_count}", (35, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (50, 50, 50), 2)
    cv2.putText(img, f"Right Hand : {right_count}", (35, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (50, 50, 50), 2)
    cv2.putText(img, f"Total Fingers : {finger_count}", (35, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 0, 0), 2)
    cv2.putText(img, f"Status : {status}", (35, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
    cv2.putText(img, f"Repetitions : {exercise.repetitions}", (35, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)
    cv2.putText(img, f"Session : {session_status}", (35, 310), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 0, 0), 2)
    cv2.putText(img, f"Time Left : {remaining_time} sec", (35, 350), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 0, 255), 2)
    
    # Nhóm 2: Lịch sử tổng hợp các session
    cv2.putText(img, last_result, (35, 410), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (120, 0, 255), 2)
    cv2.putText(img, f"Total Sessions : {len(session_history)}", (35, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)
    cv2.putText(img, f"Avg Reps : {avg_reps:.1f}", (35, 490), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 150, 0), 2)
    cv2.putText(img, f"Avg Speed : {avg_speed:.2f} sec/cycle", (35, 530), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (150, 0, 150), 2)
    cv2.putText(img, f"Best Reps : {best_reps}", (35, 570), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (200, 0, 0), 2)
    
    # Nhóm 3: Các chỉ số biên độ (Amplitude)
    cv2.putText(img, f"Amplitude : {avg_amplitude:.1f}", (35, 630), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 100, 0), 2)
    cv2.putText(img, f"Amplitude Loss : {amplitude_decrement:.1f}%", (35, 670), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)

    # Hệ thống phím tắt điều khiển nhanh góc trên bên phải
    cv2.putText(img, "B = Start", (950, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 200, 0), 2)
    cv2.putText(img, "P = Pause / Resume", (950, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 200, 220), 2)
    cv2.putText(img, "R = Reset All", (950, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (200, 0, 0), 2)
    cv2.putText(img, "ESC = Exit", (950, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 200), 2)

    # ==========================
    # CLINICAL EVALUATION REPORT (POPUP SCREEN)
    # ==========================
    if finished:
        # Hiệu ứng làm mờ nền Camera (Dimming Effect)
        overlay = img.copy()
        cv2.rectangle(overlay, (0, 0), (1280, 720), (30, 30, 30), -1)
        cv2.addWeighted(overlay, 0.75, img, 0.25, 0, img)

        # Thiết lập kích thước bảng báo cáo trung tâm mở rộng rộng rãi
        bx1, by1, bx2, by2 = 220, 100, 1060, 620
        cv2.rectangle(img, (bx1, by1), (bx2, by2), (255, 255, 255), -1) # Nền trắng tinh
        cv2.rectangle(img, (bx1, by1), (bx2, by2), (0, 80, 180), 4)    # Khung viền xanh dương sâu

        # Tiêu đề biểu mẫu báo cáo kết quả
        cv2.putText(img, "PARKINSON MOTOR ASSESSMENT REPORT", (bx1 + 130, by1 + 45), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 80, 180), 3)
        cv2.line(img, (bx1 + 40, by1 + 70), (bx2 - 40, by1 + 70), (220, 220, 220), 2)

        # Hiển thị 4 nhóm chỉ số định lượng cơ bản thu thập được
        cv2.putText(img, f"Total Repetitions :  {final_reps} cycles (Normal: >70)", (bx1 + 50, by1 + 115), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (50, 50, 50), 2)
        cv2.putText(img, f"Average Velocity  :  {final_speed:.2f} sec/cycle (Normal: <0.8s)", (bx1 + 50, by1 + 145), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (50, 50, 50), 2)
        cv2.putText(img, f"Mean Amplitude    :  {final_amplitude:.1f} px (Normal: >100 px)", (bx1 + 50, by1 + 175), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (50, 50, 50), 2)
        cv2.putText(img, f"Amplitude Decay   :  {final_decrement:.1f}% (Normal: <10%)", (bx1 + 50, by1 + 205), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (50, 50, 50), 2)
        cv2.line(img, (bx1 + 40, by1 + 225), (bx2 - 40, by1 + 225), (240, 240, 240), 1)

        # --- THUẬT TOÁN QUÉT 4 CẤP ĐỘ LÂM SÀNG CHUYÊN SÂU ---
        if final_reps < 30 or final_speed > 2.0 or final_decrement > 40.0:
            # 1. MỨC ĐỘ NẶNG (Severe)
            assessment_str = "SEVERE PROFILE (Severe Bradykinesia & Hypokinesia)"
            status_color = (0, 0, 220) # Đỏ cảnh báo nguy hiểm
            advice_lines = [
                "Clinical Analysis: High motor degradation and severe amplitude decay detected.",
                "1. Strongly advise scheduling an examination with a neurologist as soon as possible.",
                "2. Note down daily life motor errors (e.g., small handwriting, shaking, stiffness).",
                "3. This software is only a screening aid; please do not panic and seek hospital tests."
            ]
        elif 30 <= final_reps <= 50 or 1.2 <= final_speed <= 2.0 or 20.0 <= final_decrement <= 40.0:
            # 2. MỨC ĐỘ TRUNG BÌNH (Moderate)
            assessment_str = "MODERATE PROFILE (Significant Motor Slowdown)"
            status_color = (0, 69, 255) # Cam đậm nguy cơ cao
            advice_lines = [
                "Clinical Analysis: Clear signs of bradykinesia and reduced movement range observed.",
                "1. Recommended to visit a neurology clinic for professional clinical evaluation.",
                "2. Avoid any excessive hand fatigue or manual work right before taking future tests.",
                "3. Keep records/screenshots of this report history to present to your physician."
            ]
        elif 50 < final_reps <= 70 or 0.8 <= final_speed < 1.2 or 10.0 <= final_decrement < 20.0:
            # 3. MỨC ĐỘ NHẸ / MỎI CƠ SỚM (Mild / Early Fatigue)
            assessment_str = "MILD PROFILE (Early Motor Fatigue / Slight Slowdown)"
            status_color = (0, 165, 255) # Vàng nghệ cảnh báo nhẹ
            advice_lines = [
                "Clinical Analysis: Minor slowdown or hand muscular fatigue detected near the end of session.",
                "1. Retest for 3-5 days at fixed hours to verify if this fatigue pattern is consistent.",
                "2. Perform targeted fine-motor exercises at home (finger tapping, squeezing soft rubber balls).",
                "3. Ensure adequate rest (>7 hours of sleep) and avoid high stress before testing again."
            ]
        else:
            # 4. TRẠNG THÁI BÌNH THƯỜNG (Normal)
            assessment_str = "NORMAL PROFILE (Healthy Motor Control & Speed)"
            status_color = (0, 180, 0) # Xanh lá cây an toàn
            advice_lines = [
                "Clinical Analysis: Excellent speed and highly stable movement range maintained throughout.",
                "1. No abnormal clinical signs of bradykinesia or neuromuscular fatigue were found.",
                "2. Continue regular active physical exercise and routine checkups to preserve health.",
                "3. Feel free to re-test on a monthly basis to monitor your long-term neuromotor trends."
            ]

        # In kết luận phân tích tổng quát ra màn hình
        cv2.putText(img, "Diagnostic Evaluation:", (bx1 + 50, by1 + 250), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2)
        cv2.putText(img, assessment_str, (bx1 + 270, by1 + 250), cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_color, 2)
        
        # Vẽ khối hộp chứa lời khuyên (Advice Card Box) chuyên dụng để tạo điểm nhấn trực quan
        cv2.rectangle(img, (bx1 + 40, by1 + 280), (bx2 - 40, by1 + 490), (250, 250, 250), -1)
        cv2.rectangle(img, (bx1 + 40, by1 + 280), (bx2 - 40, by1 + 490), (230, 230, 230), 1)

        # In từng dòng lời khuyên một cách thẳng hàng bên trong Advice Card Box
        y_offset = by1 + 315
        for line in advice_lines:
            cv2.putText(img, line, (bx1 + 60, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (40, 40, 40), 1, cv2.LINE_AA)
            y_offset += 40

        # Chân trang hướng dẫn tổ hợp phím điều khiển thoát / reset bảng dữ liệu
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

    # Bắt đầu chạy phiên kiểm tra mới (Chỉ kích hoạt khi máy đang READY)
    if key == ord('b') and not test_started and not finished:
        test_started = True
        paused = False
        finished = False
        stats.start_time = time.time()
        total_pause_time = 0
        current_amplitude = 0
        avg_amplitude = 0
        amplitude_decrement = 0
        amplitude_history.clear()
        first_half_amplitude.clear()
        second_half_amplitude.clear()
        exercise.repetitions = 0

    # Tạm dừng cuộc thử nghiệm (Pause)
    elif key == ord('p'):
        if test_started:
            if not paused:
                paused = True
                pause_start = time.time()
                elapsed_before_pause = elapsed
            else:
                paused = False
                total_pause_time += (time.time() - pause_start)

    # Nhấn phím 'C' (Continue) để đóng bảng báo cáo, lưu session này vào bộ nhớ và chuẩn bị lượt test mới
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
        exercise.repetitions = 0

    # Reset toàn diện bộ nhớ của chương trình (Xóa sạch lịch sử)
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
        last_result = "No previous session"
        session_history.clear()

    # Nhấn phím ESC để tắt ứng dụng một cách an toàn
    elif key == 27:
        break

cap.release()
cv2.destroyAllWindows()
