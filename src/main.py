import cv2
import time

from hand_detector import HandDetector
from finger_counter import count_fingers
from exercise_logic import DexterityExercise
from statistics import Statistics

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

test_started = False
paused = False
MAX_TIME = 60
pause_start = 0
total_pause_time = 0

# ==========================
# MAIN LOOP
# ==========================
while True:
    success, img = cap.read()
    if not success:
        break

    img = cv2.flip(img, 1)
    hands, img = detector.find_hands(img)
    finger_count = 0

    # ==========================
    # HAND DETECTION
    # ==========================
    if len(hands) > 0:
        hand = hands[0]
        finger_count = count_fingers(hand)

    if test_started and not paused:
        exercise.update(finger_count)

    # ==========================
    # STATISTICS
    # ==========================
    if test_started:
        elapsed = (time.time() - stats.start_time - total_pause_time)
    else:
        elapsed = 0

    remaining_time = max(0, MAX_TIME - int(elapsed))

    # Tự động kết thúc bài test khi hết giờ
    if remaining_time == 0 and test_started:
        paused = True
        test_started = False

    if not test_started and elapsed == 0:
        session_status = "READY"
    elif paused:
        session_status = "PAUSED"
    elif remaining_time == 0:
        session_status = "FINISHED"
    else:
        session_status = "RUNNING"
        speed = stats.average_speed(exercise.repetitions)

    # ==========================
    # HAND STATUS
    # ==========================
    if finger_count >= 4:
        status = "OPEN"
        color = (0, 255, 0)
    elif finger_count <= 1:
        status = "CLOSED"
        color = (0, 0, 255)
    else:
        status = "MOVING"
        color = (0, 255, 255)

    # ==========================
    # UI PANEL
    # ==========================
    cv2.rectangle(img, (20, 20), (450, 350), (255, 255, 255), -1)

    cv2.putText(img, "HAND DEXTERITY ASSESSMENT", (35, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.putText(img, f"Finger Count : {finger_count}", (35, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(img, f"Status : {status}", (35, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 3)
    cv2.putText(img, f"Repetitions : {exercise.repetitions}", (35, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    cv2.putText(img, f"Session : {session_status}", (35, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
    cv2.putText(img, f"Time : {elapsed:.1f} sec", (35, 310), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
    
    # Tính tốc độ trung bình nếu ở trạng thái RUNNING
    if session_status == "RUNNING" and 'speed' in locals():
        cv2.putText(img, f"Avg Speed : {speed:.2f} sec/cycle", (35, 360), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2)

    # ==========================
    # WINDOW
    # ==========================
    cv2.namedWindow("Hand Dexterity Assessment", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Hand Dexterity Assessment", 1280, 720)
    cv2.imshow("Hand Dexterity Assessment", img)

    key = cv2.waitKey(1)
    if key == ord('b'):
        test_started = True
        stats.start_time = time.time()  # Khởi tạo thời gian bắt đầu test
        total_pause_time = 0
    elif key == ord('p'):
        paused = not paused
        # Logic tính thời gian pause có thể bổ sung thêm ở đây nếu cần
    elif key == ord('r'):
        exercise.repetitions = 0
    elif key == 27:  # Phím ESC để thoát
        break

# ==========================
# EXIT (Nằm hẳn ngoài vòng lặp while)
# ==========================
cap.release()
cv2.destroyAllWindows()
