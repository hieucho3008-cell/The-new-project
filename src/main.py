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
# CAMERA
# ==========================
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

# ==========================
# OBJECTS
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

# Các biến tạm dùng để đóng băng kết quả hiển thị lên bảng cuối phiên
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
    # HAND DETECTION
    # ==========================
    finger_count = 0
    left_count = 0
    right_count = 0
    current_amplitude = 0

    if len(hands) > 0:
        for hand in hands:
            fingers = count_fingers(hand)
            finger_count += fingers

            # Gọi hàm tính biên độ đã định nghĩa ở trên
            amplitude = calculate_amplitude(hand)
            current_amplitude += amplitude

            if hand["type"] == "Left":
                left_count = fingers
            elif hand["type"] == "Right":
                right_count = fingers

        # Lấy trung bình amplitude nếu phát hiện 2 tay
        current_amplitude = current_amplitude / len(hands)

        if test_started and not paused:
            exercise.update(finger_count)
            amplitude_history.append(current_amplitude)

    # ==========================
    # TIMER
    # ==========================
    if test_started and not paused:
        elapsed = time.time() - stats.start_time - total_pause_time
        
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
    # SPEED
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
    # AUTO FINISH
    # ==========================
    if remaining_time == 0 and test_started:
        paused = True
        test_started = False
        finished = True

        # Khóa dữ liệu của session này lại để điền vào bảng kết quả báo cáo
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
    # SESSION STATUS
    # ==========================
    if finished:
        session_status = "FINISHED"
    elif not test_started and elapsed == 0:
        session_status = "READY"
    elif paused:
        session_status = "PAUSED"
    else:
        session_status = "RUNNING"

    # ==========================
    # HAND STATUS
    # ==========================
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
    # UI PANEL (MÀN HÌNH CHÍNH)
    # ==========================

    # Tiêu đề bảng
    cv2.putText(img, "HAND DEXTERITY ASSESSMENT", (35, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2)
    
    # --- Nhóm 1: Live Status ---
    cv2.putText(img, f"Left Hand : {left_count}", (35, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (50, 50, 50), 2)
    cv2.putText(img, f"Right Hand : {right_count}", (35, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (50, 50, 50), 2)
    cv2.putText(img, f"Total Fingers : {finger_count}", (35, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 0, 0), 2)
    cv2.putText(img, f"Status : {status}", (35, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
    cv2.putText(img, f"Repetitions : {exercise.repetitions}", (35, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)
    cv2.putText(img, f"Session : {session_status}", (35, 310), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 0, 0), 2)
    cv2.putText(img, f"Time Left : {remaining_time} sec", (35, 350), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 0, 255), 2)
    
    # --- Nhóm 2: Lịch sử & Thống kê ---
    cv2.putText(img, last_result, (35, 410), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (120, 0, 255), 2)
    cv2.putText(img, f"Total Sessions : {len(session_history)}", (35, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)
    cv2.putText(img, f"Avg Reps : {avg_reps:.1f}", (35, 490), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 150, 0), 2)
    cv2.putText(img, f"Avg Speed : {avg_speed:.2f} sec/cycle", (35, 530), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (150, 0, 150), 2)
    cv2.putText(img, f"Best Reps : {best_reps}", (35, 570), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (200, 0, 0), 2)
    
    # --- Nhóm 3: Biên độ sóng ---
    cv2.putText(img, f"Amplitude : {avg_amplitude:.1f}", (35, 630), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 100, 0), 2)
    cv2.putText(img, f"Amplitude Loss : {amplitude_decrement:.1f}%", (35, 670), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)

    # Nút điều khiển phía bên phải
    cv2.putText(img, "B = Start", (950, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 200, 0), 2)
    cv2.putText(img, "P = Pause / Resume", (950, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 200, 220), 2)
    cv2.putText(img, "R = Reset All", (950, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (200, 0, 0), 2)
    cv2.putText(img, "ESC = Exit", (950, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 200), 2)

    # ==========================
    # BẢNG KẾT QUẢ PHÂN TÍCH (POPUPS KHI FINISHED)
    # ==========================
    if finished:
        # Làm mờ nhẹ màn hình nền camera sau bằng một lớp phủ màu xám trong suốt
        overlay = img.copy()
        cv2.rectangle(overlay, (0, 0), (1280, 720), (40, 40, 40), -1)
        cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)

        # Vẽ bảng kết quả trung tâm (Y: 120 -> 600, X: 340 -> 940)
        bx1, by1, bx2, by2 = 340, 120, 940, 600
        cv2.rectangle(img, (bx1, by1), (bx2, by2), (255, 255, 255), -1) # Nền bảng trắng
        cv2.rectangle(img, (bx1, by1), (bx2, by2), (0, 102, 204), 4)    # Viền xanh dương đậm

        # Tiêu đề bảng báo cáo
        cv2.putText(img, "SESSION PERFORMANCE REPORT", (bx1 + 75, by1 + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 102, 204), 3)
        cv2.line(img, (bx1 + 40, by1 + 75), (bx2 - 40, by1 + 75), (200, 200, 200), 2)

        # Hiển thị các thông số phân tích cụ thể thu được trong đợt thử nghiệm
        cv2.putText(img, f"- Total Repetitions :  {final_reps} cycles", (bx1 + 60, by1 + 140), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        cv2.putText(img, f"- Average Speed     :  {final_speed:.2f} sec/cycle", (bx1 + 60, by1 + 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        cv2.putText(img, f"- Mean Amplitude    :  {final_amplitude:.1f} px", (bx1 + 60, by1 + 260), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        
        # Đánh giá chỉ số mệt mỏi biên độ (Fatigue Index)
        cv2.putText(img, f"- Amplitude Decay   :  {final_decrement:.1f}%", (bx1 + 60, by1 + 320), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255) if final_decrement > 15 else (0, 150, 0), 2)
        
        # Đưa ra chẩn đoán nhanh tự động
        if final_decrement > 20:
            diagnostic = "Status: Significant Fatigue / Slowdown Detected"
            diag_color = (0, 0, 200)
        elif final_reps < 15:
            diagnostic = "Status: Low Speed Activity / Rigidity Check"
            diag_color = (0, 120, 200)
        else:
            diagnostic = "Status: Stable & Fluid Movement Profile"
            diag_color = (0, 150, 0)
            
        cv2.putText(img, diagnostic, (bx1 + 60, by1 + 390), cv2.FONT_HERSHEY_SIMPLEX, 0.65, diag_color, 2)

        # Thanh hướng dẫn điều khiển bên dưới cùng của bảng popup
        cv2.line(img, (bx1 + 40, by1 + 430), (bx2 - 40, by1 + 430), (200, 200, 200), 2)
        cv2.putText(img, "Press 'C' to Continue  |  Press 'R' to Reset All", (bx1 + 70, by1 + 465), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 100), 2)

    # ==========================
    # WINDOW DISPLAY
    # ==========================
    cv2.namedWindow("Hand Dexterity Assessment", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Hand Dexterity Assessment", 1280, 720)
    cv2.imshow("Hand Dexterity Assessment", img)

    # ==========================
    # KEYBOARD CONTROLS
    # ==========================
    key = cv2.waitKey(1)

    # Phím tắt bắt đầu bài test mới
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

    # Phím tắt Tạm dừng cuộc thử nghiệm
    elif key == ord('p'):
        if test_started:
            if not paused:
                paused = True
                pause_start = time.time()
                elapsed_before_pause = elapsed
            else:
                paused = False
                total_pause_time += (time.time() - pause_start)

    # Phím tắt 'C' - Đóng bảng kết quả báo cáo để tiếp tục thử nghiệm phiên mới
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

    # Phím tắt Reset dữ liệu toàn bộ hệ thống
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

    # Thoát chương trình
    elif key == 27:  # ESC
        break

cap.release()
cv2.destroyAllWindows()
